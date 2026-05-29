"""SSH/SFTP helpers for registered servers."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional


def _load_private_key(
    *,
    password: Optional[str] = None,
    key_filename: Optional[str] = None,
    key_text: Optional[str] = None,
):
    import paramiko

    if key_text:
        stream = io.StringIO(key_text.strip())
        for loader in (
            paramiko.RSAKey.from_private_key,
            paramiko.ECDSAKey.from_private_key,
            paramiko.Ed25519Key.from_private_key,
        ):
            try:
                stream.seek(0)
                return loader(stream, password=password)
            except Exception:
                continue
        raise ValueError("unsupported or invalid private key")
    if key_filename:
        for loader in (
            paramiko.RSAKey.from_private_key_file,
            paramiko.ECDSAKey.from_private_key_file,
            paramiko.Ed25519Key.from_private_key_file,
        ):
            try:
                return loader(key_filename, password=password)
            except Exception:
                continue
        raise ValueError("unsupported or invalid private key file")
    return None


def _connect_transport(
    host: str,
    port: int,
    username: str,
    *,
    password: Optional[str] = None,
    key_filename: Optional[str] = None,
    timeout: int = 60,
):
    import paramiko

    transport = paramiko.Transport((host, int(port)))
    pkey = _load_private_key(password=password, key_filename=key_filename)
    if pkey is not None:
        transport.connect(username=username, pkey=pkey, timeout=timeout)
    else:
        transport.connect(username=username, password=password, timeout=timeout)
    return transport


def sftp_put(
    host: str,
    port: int,
    username: str,
    local_path: str | Path,
    remote_path: str,
    *,
    password: Optional[str] = None,
    key_filename: Optional[str] = None,
    timeout: int = 120,
) -> tuple[bool, str]:
    try:
        import paramiko
    except ImportError:
        return False, "install paramiko on server (pip install paramiko)"

    local = Path(local_path)
    if not local.is_file():
        return False, "local file not found"
    if not password and not key_filename:
        return False, "SSH password or key required for this server"

    transport = None
    try:
        transport = _connect_transport(
            host,
            port,
            username,
            password=password,
            key_filename=key_filename,
            timeout=timeout,
        )
        sftp = paramiko.SFTPClient.from_transport(transport)
        if sftp is None:
            return False, "SFTP session failed"
        sftp.put(str(local), remote_path)
        sftp.close()
        return True, remote_path
    except Exception as e:
        return False, str(e)[:900]
    finally:
        if transport:
            transport.close()


def sftp_get(
    host: str,
    port: int,
    username: str,
    remote_path: str,
    local_path: str | Path,
    *,
    password: Optional[str] = None,
    key_filename: Optional[str] = None,
    timeout: int = 120,
) -> tuple[bool, str]:
    try:
        import paramiko
    except ImportError:
        return False, "install paramiko on server"

    transport = None
    try:
        transport = _connect_transport(
            host,
            port,
            username,
            password=password,
            key_filename=key_filename,
            timeout=timeout,
        )
        sftp = paramiko.SFTPClient.from_transport(transport)
        if sftp is None:
            return False, "SFTP session failed"
        sftp.get(remote_path, str(local_path))
        sftp.close()
        return True, str(local_path)
    except Exception as e:
        return False, str(e)[:900]
    finally:
        if transport:
            transport.close()


def sftp_list(
    host: str,
    port: int,
    username: str,
    remote_path: str,
    *,
    password: Optional[str] = None,
    key_filename: Optional[str] = None,
    timeout: int = 60,
    limit: int = 30,
) -> tuple[bool, str]:
    try:
        import paramiko
    except ImportError:
        return False, "install paramiko on server"

    transport = None
    try:
        transport = _connect_transport(
            host,
            port,
            username,
            password=password,
            key_filename=key_filename,
            timeout=timeout,
        )
        sftp = paramiko.SFTPClient.from_transport(transport)
        if sftp is None:
            return False, "SFTP session failed"
        rows = sftp.listdir_attr(remote_path or ".")
        rows = sorted(rows, key=lambda r: r.filename.lower())[: max(1, min(limit, 100))]
        lines = []
        for item in rows:
            kind = "d" if str(item.longname).startswith("d") else "-"
            size = int(getattr(item, "st_size", 0) or 0)
            lines.append(f"{kind} {size:>10} {item.filename}")
        sftp.close()
        return True, "\n".join(lines) if lines else "empty"
    except Exception as e:
        return False, str(e)[:900]
    finally:
        if transport:
            transport.close()
