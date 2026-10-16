"""Stores artifact files on disk and computes their SHA-256 checksum while saving."""
import hashlib
import os
import re
from pathlib import Path
from typing import BinaryIO

NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,99}")
CHUNK = 1024 * 1024  # read 1 MB at a time: a 5 GB file never has to fit in memory


def valid_product(name: str) -> bool:
    return bool(NAME_RE.fullmatch(name))


def safe_filename(name: str) -> str:
    """'../../etc/passwd' -> 'passwd'. Blocks path traversal attacks."""
    cleaned = Path(name or "").name
    if cleaned in ("", ".", ".."):
        raise ValueError("invalid filename")
    return cleaned


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, product: str, version: str, filename: str) -> Path:
        return self.root / product / version / filename

    def save(self, product: str, version: str, filename: str, src: BinaryIO) -> tuple[str, int]:
        """Stream to a temp file, hash while writing, then atomically rename into place."""
        final = self.path(product, version, filename)
        final.parent.mkdir(parents=True, exist_ok=True)
        tmp = final.with_name(final.name + ".partial")
        digest, size = hashlib.sha256(), 0
        with open(tmp, "wb") as out:
            while chunk := src.read(CHUNK):
                digest.update(chunk)
                out.write(chunk)
                size += len(chunk)
        os.replace(tmp, final)   # atomic: readers see either no file or the whole file
        return digest.hexdigest(), size
