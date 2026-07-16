"""Crash-resistant and process-safe filesystem writes for Noesis vaults."""

from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Iterator


_LOCK_STATE = threading.local()


@contextmanager
def vault_lock(vault_path: Path | str) -> Iterator[None]:
    root = Path(vault_path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
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


def vault_write_operation(writer: Any) -> Any:
    @wraps(writer)
    def locked(vault_path: Path | str, *args: Any, **kwargs: Any) -> Any:
        with vault_lock(vault_path):
            return writer(vault_path, *args, **kwargs)

    return locked


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
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
