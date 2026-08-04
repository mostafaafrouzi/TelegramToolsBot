"""Server-side link/video probe and download.

Metadata via HTTP HEAD/Range or yt-dlp; download via requests stream or yt-dlp.
"""

from __future__ import annotations

import mimetypes
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import unquote, urljoin, urlparse

import requests

_YT_HOSTS = ("youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com", "music.youtube.com")
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_TG_BOT_UPLOAD_MAX = 50 * 1024 * 1024  # Telegram Bot API hard-ish limit without local API

_MIME_EXT = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "application/zip": ".zip",
    "application/pdf": ".pdf",
    "application/octet-stream": ".bin",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "text/plain": ".txt",
}


@dataclass(frozen=True)
class LinkMetadata:
    url: str
    link_type: str
    title: str
    size_bytes: Optional[int]
    downloadable: bool
    filename_hint: str
    detail: str = ""
    content_type: str = ""
    referer: str = ""


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


def _parse_content_disposition_filename(cd: str) -> str:
    if not cd:
        return ""
    m = re.search(r"filename\*\s*=\s*([^']*)''([^;]+)", cd, flags=re.I)
    if m:
        return _safe_name(unquote(m.group(2).strip().strip('"')))
    m = re.search(r'filename\s*=\s*"([^"]+)"', cd, flags=re.I)
    if m:
        return _safe_name(m.group(1))
    m = re.search(r"filename\s*=\s*([^;]+)", cd, flags=re.I)
    if m:
        return _safe_name(m.group(1).strip().strip("'"))
    return ""


def _parse_size(headers: Any) -> Optional[int]:
    try:
        cr = headers.get("content-range") or ""
        m = re.search(r"/(\d+)\s*$", cr)
        if m:
            return int(m.group(1))
        cl = headers.get("content-length")
        if cl and str(cl).isdigit():
            return int(cl)
    except Exception:
        pass
    return None


def _ext_for_ctype(ctype: str) -> str:
    ctype = (ctype or "").split(";")[0].strip().lower()
    if ctype in _MIME_EXT:
        return _MIME_EXT[ctype]
    guessed = mimetypes.guess_extension(ctype) if ctype else None
    return guessed or ".bin"


def _ytdlp_base_opts() -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    cookie = (os.getenv("YTDLP_COOKIES") or "").strip()
    if cookie and Path(cookie).is_file():
        opts["cookiefile"] = cookie
    return opts


def _scrape_download_url(page_url: str, html: str) -> Optional[str]:
    """Best-effort: find a real file URL on HTML landing pages (e.g. examplefile.com)."""
    candidates: list[str] = []
    for pat in (
        r'href=["\']([^"\']+\.(?:pdf|zip|bin|mp4|mp3|png|jpe?g|webp|rar|7z|docx?))["\']',
        r'href=["\']([^"\']*download[^"\']*)["\']',
        r'data-url=["\']([^"\']+)["\']',
        r'content=["\'](https?://[^"\']+\.(?:pdf|zip|bin|mp4|png|jpe?g))["\']',
    ):
        for m in re.finditer(pat, html, flags=re.I):
            candidates.append(m.group(1))
    for rel in candidates:
        abs_u = urljoin(page_url, rel)
        if abs_u.rstrip("/") == page_url.rstrip("/"):
            continue
        low = abs_u.lower()
        if any(x in low for x in ("privacy", "terms", "login", "javascript:", "#")):
            continue
        return abs_u
    return None


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
    if link_type in ("unsupported", "empty"):
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


def _binary_headers(referer: str = "") -> dict[str, str]:
    h = {
        "User-Agent": _BROWSER_UA,
        "Accept": "application/pdf,application/octet-stream,image/*,*/*;q=0.8",
    }
    if referer:
        h["Referer"] = referer
    return h


def _meta_from_headers(url: str, headers: Any, *, referer: str = "") -> LinkMetadata:
    cd = headers.get("content-disposition", "") or ""
    ctype = (headers.get("content-type") or "").split(";")[0].strip().lower()
    size = _parse_size(headers)
    name = _parse_content_disposition_filename(cd)
    if not name:
        name = Path(urlparse(url).path).name
    name = _safe_name(name or f"file_{int(time.time())}")
    if "." not in Path(name).name:
        name += _ext_for_ctype(ctype)
    return LinkMetadata(
        url=url,
        link_type="direct",
        title=name,
        size_bytes=size,
        downloadable=True,
        filename_hint=name,
        detail="ok",
        content_type=ctype,
        referer=referer or "",
    )


def _try_binary_get(
    url: str, *, timeout: tuple[float, float], referer: str
) -> Optional[LinkMetadata]:
    """GET with Referer for sites that serve HTML without it (e.g. examplefile.com)."""
    try:
        resp = requests.get(
            url,
            stream=True,
            timeout=timeout,
            allow_redirects=True,
            headers=_binary_headers(referer),
        )
    except requests.exceptions.RequestException:
        return None
    try:
        if resp.status_code >= 400:
            return None
        ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
        cd = resp.headers.get("content-disposition", "") or ""
        if ctype.startswith("text/html") and "attachment" not in cd.lower():
            # Peek magic bytes
            chunk = next(resp.iter_content(16), b"")
            if chunk.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
                return None
            # Non-HTML body despite HTML content-type — rare
        final = str(resp.url or url)
        # Prefer Content-Length; if missing and PDF, still ok
        meta = _meta_from_headers(final, resp.headers, referer=referer)
        if (meta.content_type or "").startswith("text/html"):
            # Re-check with first bytes already consumed — treat as fail
            return None
        # If size unknown, try Range after close
        if meta.size_bytes is None:
            try:
                resp.close()
            except Exception:
                pass
            try:
                rr = requests.get(
                    url,
                    stream=True,
                    timeout=timeout,
                    allow_redirects=True,
                    headers={**_binary_headers(referer), "Range": "bytes=0-0"},
                )
                size = _parse_size(rr.headers)
                if size:
                    meta = LinkMetadata(
                        url=meta.url,
                        link_type=meta.link_type,
                        title=meta.title,
                        size_bytes=size,
                        downloadable=True,
                        filename_hint=meta.filename_hint,
                        detail="ok",
                        content_type=meta.content_type,
                        referer=referer,
                    )
            except Exception:
                pass
        return meta
    finally:
        try:
            resp.close()
        except Exception:
            pass


def _probe_direct(
    url: str, *, timeout: tuple[float, float], referer: str = ""
) -> LinkMetadata:
    headers = {"User-Agent": _BROWSER_UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
        headers["Accept"] = "application/pdf,application/octet-stream,image/*,*/*;q=0.8"
    resp = None
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout, headers=headers)
        if resp.status_code >= 400 or resp.status_code == 405:
            resp = None
    except requests.exceptions.RequestException:
        resp = None
    if resp is None:
        try:
            resp = requests.get(
                url,
                stream=True,
                timeout=timeout,
                headers={**headers, "Range": "bytes=0-0"},
                allow_redirects=True,
            )
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
    try:
        if resp.status_code >= 400 and resp.status_code != 206:
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

    final_url = str(resp.url or url)
    cd = resp.headers.get("content-disposition", "") or ""
    ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
    size = _parse_size(resp.headers)

    if "attachment" not in cd.lower() and ctype.startswith("text/html"):
        page_url = final_url
        # Sites like examplefile.com: download URL needs Referer of the HTML page
        for candidate in dict.fromkeys([url, final_url]):
            if "file-download" in candidate or "/download/" in candidate:
                got = _try_binary_get(candidate, timeout=timeout, referer=page_url)
                if got and got.downloadable:
                    return got
        try:
            full = requests.get(final_url, timeout=timeout, headers={"User-Agent": _BROWSER_UA}, allow_redirects=True)
            html = full.text[:400_000]
            page_url = str(full.url)
            scraped = _scrape_download_url(page_url, html)
            # Prefer file-download style links even if same host
            if scraped:
                got = _try_binary_get(scraped, timeout=timeout, referer=page_url)
                if got and got.downloadable:
                    return got
                nested = _probe_direct(scraped, timeout=timeout, referer=page_url)
                if nested.downloadable and not (nested.content_type or "").startswith("text/html"):
                    return nested
            # file-download/N on same site from path id
            m = re.search(r"file-download/(\d+)", html, flags=re.I)
            if m:
                dl = urljoin(page_url, f"/file-download/{m.group(1)}")
                got = _try_binary_get(dl, timeout=timeout, referer=page_url)
                if got and got.downloadable:
                    return got
        except Exception:
            pass
        video_meta = _probe_youtube(final_url)
        if video_meta.downloadable:
            return video_meta
        return LinkMetadata(
            url=final_url,
            link_type="direct",
            title=Path(urlparse(final_url).path).name or "page",
            size_bytes=None,
            downloadable=False,
            filename_hint="",
            detail="html_landing_page",
            content_type=ctype,
        )

    name = _parse_content_disposition_filename(cd)
    if not name:
        name = Path(urlparse(final_url).path).name
    name = _safe_name(name or f"file_{int(time.time())}")
    if "." not in Path(name).name:
        name += _ext_for_ctype(ctype)

    return LinkMetadata(
        url=final_url if not referer else url,
        link_type="direct",
        title=name,
        size_bytes=size,
        downloadable=True,
        filename_hint=name,
        detail="ok",
        content_type=ctype,
        referer=referer or "",
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

    opts = {**_ytdlp_base_opts(), "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        detail = str(e)
        if "Sign in to confirm" in detail or "not a bot" in detail.lower():
            detail = "youtube_needs_cookies"
        return LinkMetadata(
            url=url,
            link_type="youtube",
            title="YouTube",
            size_bytes=None,
            downloadable=False,
            filename_hint="",
            detail=detail,
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
        content_type="video/mp4",
    )


def download_to_path(
    url: str,
    dest_dir: Path,
    *,
    metadata: Optional[LinkMetadata] = None,
    progress_cb: Optional[Callable[[str], None]] = None,
    quality: str = "best",
    audio_only: bool = False,
) -> Path:
    """Download link to dest_dir; raises RuntimeError on failure."""
    meta = metadata or probe_metadata(url)
    if not meta.downloadable:
        raise RuntimeError(meta.detail or "not_downloadable")

    dest_dir.mkdir(parents=True, exist_ok=True)
    if meta.link_type == "youtube":
        return _download_youtube(
            url,
            dest_dir,
            meta,
            progress_cb=progress_cb,
            quality=quality,
            audio_only=audio_only,
        )
    return _download_direct(meta.url or url, dest_dir, meta, progress_cb=progress_cb)


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

    referer = (getattr(meta, "referer", "") or "").strip()
    headers = _binary_headers(referer) if referer else {"User-Agent": _BROWSER_UA, "Accept": "*/*"}
    last_err: Optional[Exception] = None
    resp = None
    for attempt in range(3):
        try:
            resp = requests.get(
                url,
                stream=True,
                timeout=(15, 600),
                allow_redirects=True,
                headers=headers,
            )
            resp.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            last_err = e
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    if resp is None:
        raise RuntimeError(str(last_err) if last_err else "download_failed")

    ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
    cd = resp.headers.get("content-disposition", "") or ""
    if ctype.startswith("text/html") and "attachment" not in cd.lower():
        peek = b""
        for chunk in resp.iter_content(64 * 1024):
            peek += chunk
            if len(peek) >= 64 * 1024:
                break
        page_url = str(resp.url)
        html = peek.decode("utf-8", errors="ignore")
        scraped = _scrape_download_url(page_url, html)
        m = re.search(r"file-download/(\d+)", html, flags=re.I)
        if m:
            scraped = scraped or urljoin(page_url, f"/file-download/{m.group(1)}")
        retry_urls = [u for u in dict.fromkeys([scraped, url]) if u]
        recovered = False
        for candidate in retry_urls:
            try:
                rr = requests.get(
                    candidate,
                    stream=True,
                    timeout=(15, 600),
                    allow_redirects=True,
                    headers=_binary_headers(page_url),
                )
                rr.raise_for_status()
                ct2 = (rr.headers.get("content-type") or "").split(";")[0].strip().lower()
                if ct2.startswith("text/html"):
                    rr.close()
                    continue
                try:
                    resp.close()
                except Exception:
                    pass
                resp = rr
                ctype = ct2
                cd = rr.headers.get("content-disposition", "") or ""
                url = candidate
                recovered = True
                break
            except requests.exceptions.RequestException:
                continue
        if not recovered:
            raise RuntimeError("html_landing_page")

    # Fix extension from real content-type if still .bin
    if target.suffix.lower() == ".bin" and ctype:
        new_ext = _ext_for_ctype(ctype)
        if new_ext != ".bin":
            target = target.with_suffix(new_ext)

    total = int(resp.headers.get("content-length") or 0) or (meta.size_bytes or 0)
    downloaded = 0
    started = time.time()
    last_update = 0.0

    with open(target, "wb") as f:
        # If we already peeked, write peek first — but only when we didn't scrape-redirect
        for chunk in resp.iter_content(1024 * 512):
            if not chunk:
                continue
            # Guard: first chunks look like HTML when expecting a binary
            if downloaded == 0 and chunk.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
                raise RuntimeError("html_landing_page")
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


def _build_youtube_format(quality: str = "best", audio_only: bool = False) -> str:
    if audio_only:
        return "bestaudio/best"
    if quality == "best" or not quality:
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    return f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}]/best"


def _download_youtube(
    url: str,
    dest_dir: Path,
    meta: LinkMetadata,
    *,
    progress_cb: Optional[Callable[[str], None]],
    quality: str = "best",
    audio_only: bool = False,
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
            speed = d.get("speed") or 0
            speed_str = f" @ {speed / (1024 * 1024):.1f} MB/s" if speed else ""
            if total:
                progress_cb(f"YouTube {done * 100 // total}%{speed_str}")
            else:
                progress_cb(f"YouTube downloading...{speed_str}")

    fmt = _build_youtube_format(quality, audio_only)
    postprocessors = []
    if audio_only:
        postprocessors.append(
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}
        )
    else:
        postprocessors.append({"key": "FFmpegMetadata"})

    opts: dict[str, Any] = {
        **_ytdlp_base_opts(),
        "outtmpl": outtmpl,
        "format": fmt,
        "merge_output_format": "mp3" if audio_only else "mp4",
        "progress_hooks": [_hook],
        "retries": 10,
        "fragment_retries": 10,
        "postprocessors": postprocessors,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError("youtube_download_failed")
            path = Path(ydl.prepare_filename(info))
            if path.exists():
                return path
    except RuntimeError:
        raise
    except Exception as e:
        msg = str(e)
        if "Sign in to confirm" in msg or "not a bot" in msg.lower():
            raise RuntimeError("youtube_needs_cookies") from e
        raise RuntimeError(msg) from e
    candidates = sorted(dest_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if candidates:
        return candidates[0]
    raise RuntimeError("youtube_output_missing")


def telegram_upload_too_large(size_bytes: Optional[int]) -> bool:
    return bool(size_bytes and size_bytes > _TG_BOT_UPLOAD_MAX)


def tg_bot_upload_max() -> int:
    return _TG_BOT_UPLOAD_MAX
