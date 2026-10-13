"""Private file writes for the tool's state."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _write_private(path: Path, text: str) -> None:
    """Atomic, 0600, same-directory temp. Never a truncate-then-stream."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
