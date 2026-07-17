"""Crash-resistant and process-safe filesystem writes for Noesis vaults."""

from __future__ import annotations

from contextlib import contextmanager
import errno
from functools import wraps
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Iterator


_LOCK_STATE = threading.local()
_PROCESS_LOCKS: dict[Path, threading.RLock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


def process_lock_for(root: Path) -> threading.RLock:
    with _PROCESS_LOCKS_GUARD:
        return _PROCESS_LOCKS.setdefault(root, threading.RLock())


@contextmanager
def vault_lock(vault_path: Path | str, *, create_root: bool = False) -> Iterator[None]:
    root = Path(vault_path).expanduser().resolve()
    if create_root:
        root.mkdir(parents=True, exist_ok=True)
    elif not root.is_dir():
        raise ValueError(f"vault path is not a directory: {root}")
    with process_lock_for(root):
        active_roots = getattr(_LOCK_STATE, "active_roots", set())
        if root in active_roots:
            yield
            return

        lock_path = root / ".noesis.lock"
        lock_handle = lock_path.open("a+", encoding="utf-8")
        try:
            try:
                import fcntl

                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            except ModuleNotFoundError:
                import msvcrt

                lock_handle.seek(0)
                msvcrt.locking(lock_handle.fileno(), msvcrt.LK_LOCK, 1)
            active_roots = set(active_roots)
            active_roots.add(root)
            _LOCK_STATE.active_roots = active_roots
            yield
        finally:
            active_roots = set(getattr(_LOCK_STATE, "active_roots", set()))
            active_roots.discard(root)
            _LOCK_STATE.active_roots = active_roots
            try:
                try:
                    import fcntl

                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
                except ModuleNotFoundError:
                    import msvcrt

                    lock_handle.seek(0)
                    msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                lock_handle.close()


def vault_write_operation(writer: Any = None, *, create_root: bool = False) -> Any:
    def decorate(operation: Any) -> Any:
        @wraps(operation)
        def locked(vault_path: Path | str, *args: Any, **kwargs: Any) -> Any:
            with vault_lock(vault_path, create_root=create_root):
                return operation(vault_path, *args, **kwargs)

        return locked

    if writer is None:
        return decorate
    return decorate(writer)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode if path.exists() else None
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        if mode is not None:
            os.chmod(temp_path, mode)
            with temp_path.open("rb") as handle:
                os.fsync(handle.fileno())
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def fsync_directory(path: Path) -> None:
    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        try:
            os.fsync(directory_fd)
        except OSError as exc:
            unsupported = {errno.EBADF, errno.EINVAL}
            if hasattr(errno, "ENOTSUP"):
                unsupported.add(errno.ENOTSUP)
            if exc.errno not in unsupported:
                raise
    finally:
        os.close(directory_fd)
