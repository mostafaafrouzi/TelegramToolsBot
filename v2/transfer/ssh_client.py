"""SSH/SFTP helpers for registered servers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


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
        transport = paramiko.Transport((host, int(port)))
        if key_filename:
            pkey = paramiko.RSAKey.from_private_key_file(key_filename)
            transport.connect(username=username, pkey=pkey, timeout=timeout)
        else:
            transport.connect(username=username, password=password, timeout=timeout)
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
        transport = paramiko.Transport((host, int(port)))
        if key_filename:
            pkey = paramiko.RSAKey.from_private_key_file(key_filename)
            transport.connect(username=username, pkey=pkey, timeout=timeout)
        else:
            transport.connect(username=username, password=password, timeout=timeout)
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
