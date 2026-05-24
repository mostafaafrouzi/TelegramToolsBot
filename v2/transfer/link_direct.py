"""Server-side link/video probe and download (AzuDL-style, no Colab).

Metadata via HTTP HEAD or yt-dlp extract_info; download via requests stream or yt-dlp.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import requests

_YT_HOSTS = ("youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com")


@dataclass(frozen=True)
class LinkMetadata:
    url: str
    link_type: str
    title: str
    size_bytes: Optional[int]
    downloadable: bool
    filename_hint: str
    detail: str = ""


def detect_link_type(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return "empty"
    if u.lower().startswith("magnet:?"):
        return "magnet"
    try:
        parsed = urlparse(u)
    except Exception:
        return "unsupported"
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "unsupported"
    host = (parsed.netloc or "").lower()
    if any(h in host for h in _YT_HOSTS) or host == "youtu.be":
        return "youtube"
    return "direct"


def _safe_name(name: str, fallback: str = "download") -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", (name or "").strip()) or fallback
    return name[:180]


def probe_metadata(url: str, timeout: tuple[float, float] = (10.0, 30.0)) -> LinkMetadata:
    """Resolve title/size without downloading body when possible."""
    link_type = detect_link_type(url)
    if link_type == "magnet":
        return LinkMetadata(
            url=url,
            link_type=link_type,
            title="Torrent magnet",
            size_bytes=None,
            downloadable=False,
            filename_hint="",
            detail="torrent_not_supported_yet",
        )
    if link_type == "unsupported" or link_type == "empty":
        return LinkMetadata(
            url=url,
            link_type=link_type,
            title="",
            size_bytes=None,
            downloadable=False,
            filename_hint="",
            detail="unsupported_url",
        )
    if link_type == "youtube":
        return _probe_youtube(url)
    return _probe_direct(url, timeout=timeout)


def _probe_direct(url: str, *, timeout: tuple[float, float]) -> LinkMetadata:
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout)
        if resp.status_code >= 400:
            resp = requests.get(url, stream=True, timeout=timeout, headers={"Range": "bytes=0-0"})
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return LinkMetadata(
            url=url,
            link_type="direct",
            title=Path(urlparse(url).path).name or "file",
            size_bytes=None,
            downloadable=False,
            filename_hint="",
            detail=str(e),
        )

    cd = resp.headers.get("content-disposition", "")
    ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
    if "attachment" not in cd.lower() and ctype.startswith("text/html"):
        # Many video sites expose an HTML page, not a file HEAD. Let yt-dlp's
        # generic extractor probe quality/size metadata before we download.
        video_meta = _probe_youtube(url)
        if video_meta.downloadable:
            return video_meta
    match = re.findall(r'filename="(.+?)"', cd)
    name = match[0] if match else Path(urlparse(url).path).name
    name = _safe_name(name or f"file_{int(time.time())}")
    if "." not in name:
        ext = {
            "video/mp4": ".mp4",
            "application/zip": ".zip",
            "application/pdf": ".pdf",
        }.get(ctype, ".bin")
        name += ext

    total = resp.headers.get("content-length")
    size = int(total) if total and str(total).isdigit() else None
    return LinkMetadata(
        url=url,
        link_type="direct",
        title=name,
        size_bytes=size,
        downloadable=True,
        filename_hint=name,
        detail="ok",
    )


def _probe_youtube(url: str) -> LinkMetadata:
    try:
        import yt_dlp
    except ImportError:
        return LinkMetadata(
            url=url,
            link_type="youtube",
            title="YouTube",
            size_bytes=None,
            downloadable=False,
            filename_hint="",
            detail="yt_dlp_not_installed",
        )

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return LinkMetadata(
            url=url,
            link_type="youtube",
            title="YouTube",
            size_bytes=None,
            downloadable=False,
            filename_hint="",
            detail=str(e),
        )

    if not info:
        return LinkMetadata(
            url=url,
            link_type="youtube",
            title="YouTube",
            size_bytes=None,
            downloadable=False,
            filename_hint="",
            detail="no_info",
        )

    entries = info.get("entries")
    if entries:
        first = next((x for x in entries if x), None)
        if first:
            info = first

    title = _safe_name(str(info.get("title") or "video_download"), "video_download")
    ext = info.get("ext") or "mp4"
    if not title.endswith(f".{ext}"):
        title = f"{title}.{ext}"
    size = info.get("filesize") or info.get("filesize_approx")
    if not size:
        requested = info.get("requested_formats") or []
        try:
            size = sum(int(f.get("filesize") or f.get("filesize_approx") or 0) for f in requested) or None
        except Exception:
            size = None
    try:
        size_i = int(size) if size else None
    except (TypeError, ValueError):
        size_i = None

    return LinkMetadata(
        url=url,
        link_type="youtube",
        title=title,
        size_bytes=size_i,
        downloadable=True,
        filename_hint=title,
        detail="ok",
    )


def download_to_path(
    url: str,
    dest_dir: Path,
    *,
    metadata: Optional[LinkMetadata] = None,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Path:
    """Download link to dest_dir; raises RuntimeError on failure."""
    meta = metadata or probe_metadata(url)
    if not meta.downloadable:
        raise RuntimeError(meta.detail or "not_downloadable")

    dest_dir.mkdir(parents=True, exist_ok=True)
    if meta.link_type == "youtube":
        return _download_youtube(url, dest_dir, meta, progress_cb=progress_cb)
    return _download_direct(url, dest_dir, meta, progress_cb=progress_cb)


def _download_direct(
    url: str,
    dest_dir: Path,
    meta: LinkMetadata,
    *,
    progress_cb: Optional[Callable[[str], None]],
) -> Path:
    name = _safe_name(meta.filename_hint or f"file_{int(time.time())}")
    target = dest_dir / name
    if target.exists():
        target = dest_dir / f"{target.stem}_{int(time.time())}{target.suffix}"

    resp = requests.get(url, stream=True, timeout=(10, 120), allow_redirects=True)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length") or 0)
    downloaded = 0
    started = time.time()
    last_update = 0.0

    with open(target, "wb") as f:
        for chunk in resp.iter_content(1024 * 512):
            if not chunk:
                continue
            f.write(chunk)
            downloaded += len(chunk)
            now = time.time()
            if progress_cb and (now - last_update >= 2 or (total and downloaded >= total)):
                last_update = now
                speed = downloaded / max(now - started, 0.1)
                msg = f"{downloaded // (1024 * 1024)} MB"
                if total:
                    msg += f" / {total // (1024 * 1024)} MB"
                msg += f" @ {speed / (1024 * 1024):.1f} MB/s"
                progress_cb(msg)

    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError("empty_download")
    return target


def _download_youtube(
    url: str,
    dest_dir: Path,
    meta: LinkMetadata,
    *,
    progress_cb: Optional[Callable[[str], None]],
) -> Path:
    try:
        import yt_dlp
    except ImportError as e:
        raise RuntimeError("yt_dlp_not_installed") from e

    outtmpl = str(dest_dir / "%(title).180s.%(ext)s")

    def _hook(d: dict) -> None:
        if progress_cb and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            if total:
                progress_cb(f"YouTube {done * 100 // total}%")
            else:
                progress_cb("YouTube downloading...")

    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "progress_hooks": [_hook],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    if not info:
        raise RuntimeError("youtube_download_failed")
    path = Path(ydl.prepare_filename(info))
    if path.exists():
        return path
    candidates = sorted(dest_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if candidates:
        return candidates[0]
    raise RuntimeError("youtube_output_missing")
