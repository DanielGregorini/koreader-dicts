"""dictzip: a gzip file that can be seeked into.

A ``.dict.dz`` is a perfectly ordinary gzip file -- ``gunzip`` reads it -- whose
FEXTRA header carries a ``RA`` subfield listing the compressed length of every
fixed-size chunk of the original.  A reader that wants bytes at offset *o* can
therefore inflate only the chunk containing *o* instead of the whole file,
which is what makes a 50 MB dictionary usable on an e-reader.

Layout of the ``RA`` subfield payload (all little-endian)::

    uint16 VER    always 1
    uint16 CHLEN  uncompressed bytes per chunk
    uint16 CHCNT  number of chunks
    uint16 CHLEN_i  compressed size of chunk i, CHCNT times

The 16-bit XLEN field caps the number of chunks, which caps the file size at
``CHLEN * 0xFFFF`` bytes.  With the standard 58315-byte chunk that is ~3.5 GB,
well past the 4 GB limit the 32-bit ``.idx`` offsets impose anyway.
"""

from __future__ import annotations

import os
import struct
import time
import zlib
from pathlib import Path

__all__ = ["CHUNK_SIZE", "dictzip_bytes", "write_dictzip"]

#: The chunk size dictzip itself uses.  Chosen upstream so that a worst-case
#: incompressible chunk still fits the 16-bit per-chunk length field.
CHUNK_SIZE = 58315

_GZIP_MAGIC = b"\x1f\x8b"
_DEFLATE = 8
_FEXTRA = 0x04
_FNAME = 0x08
_OS_UNIX = 3


def dictzip_bytes(data: bytes, *, filename: str = "", mtime: int | None = None) -> bytes:
    """Compress *data* into a random-access gzip (dictzip) stream."""
    chunk_count = (len(data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    if chunk_count > 0xFFFF:
        raise ValueError(
            f"{len(data)} bytes needs {chunk_count} dictzip chunks, "
            f"but the format allows at most {0xFFFF}"
        )

    # One deflate stream spans the whole file, exactly as dictd's dictzip.c
    # does.  Z_FULL_FLUSH after each chunk resets the LZ77 window so that any
    # chunk can be inflated on its own without the preceding ones -- that costs
    # a little ratio and is the entire point of the format.  The final
    # Z_FINISH emits the end-of-stream marker and is appended *after* the last
    # chunk, so it is not counted in any chunk length (again matching dictzip;
    # readers only ever seek to a chunk boundary).
    compressor = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    compressed_chunks: list[bytes] = []
    for start in range(0, len(data), CHUNK_SIZE):
        block = compressor.compress(data[start : start + CHUNK_SIZE])
        block += compressor.flush(zlib.Z_FULL_FLUSH)
        if len(block) > 0xFFFF:
            raise ValueError("compressed chunk exceeds the 16-bit length field")
        compressed_chunks.append(block)
    tail = compressor.flush(zlib.Z_FINISH)

    subfield = struct.pack("<HHH", 1, CHUNK_SIZE, chunk_count)
    subfield += b"".join(struct.pack("<H", len(c)) for c in compressed_chunks)
    extra = b"RA" + struct.pack("<H", len(subfield)) + subfield

    name = os.path.basename(filename).encode("latin-1", "replace") if filename else b""
    flags = _FEXTRA | (_FNAME if name else 0)
    header = _GZIP_MAGIC + bytes([_DEFLATE, flags])
    header += struct.pack("<I", int(mtime if mtime is not None else time.time()))
    header += bytes([0, _OS_UNIX])
    header += struct.pack("<H", len(extra)) + extra
    if name:
        header += name + b"\x00"

    trailer = struct.pack("<II", zlib.crc32(data) & 0xFFFFFFFF, len(data) & 0xFFFFFFFF)
    return header + b"".join(compressed_chunks) + tail + trailer


def write_dictzip(path: Path, data: bytes, *, mtime: int | None = None) -> int:
    """Write *data* to *path* as a dictzip file. Returns bytes written."""
    path = Path(path)
    # The FNAME field should name the *uncompressed* file, i.e. drop ".dz".
    inner = path.name[:-3] if path.name.endswith(".dz") else path.name
    blob = dictzip_bytes(data, filename=inner, mtime=mtime)
    path.write_bytes(blob)
    return len(blob)


def dictzip_file(src: Path, dest: Path, *, mtime: int | None = None) -> int:
    """dictzip *src* into *dest*, streaming a chunk at a time.

    A tier-1 ``.dict`` body runs to hundreds of megabytes; this keeps peak
    memory at one chunk plus the (tiny) chunk table rather than two full
    copies of the body.
    """
    src, dest = Path(src), Path(dest)
    total = src.stat().st_size
    chunk_count = (total + CHUNK_SIZE - 1) // CHUNK_SIZE
    if chunk_count > 0xFFFF:
        raise ValueError(
            f"{total} bytes needs {chunk_count} dictzip chunks, "
            f"but the format allows at most {0xFFFF}"
        )

    compressor = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    sizes: list[int] = []
    body: list[bytes] = []
    crc = 0
    with src.open("rb") as handle:
        while True:
            raw = handle.read(CHUNK_SIZE)
            if not raw:
                break
            crc = zlib.crc32(raw, crc)
            block = compressor.compress(raw) + compressor.flush(zlib.Z_FULL_FLUSH)
            if len(block) > 0xFFFF:
                raise ValueError("compressed chunk exceeds the 16-bit length field")
            sizes.append(len(block))
            body.append(block)
    tail = compressor.flush(zlib.Z_FINISH)

    subfield = struct.pack("<HHH", 1, CHUNK_SIZE, len(sizes))
    subfield += b"".join(struct.pack("<H", n) for n in sizes)
    extra = b"RA" + struct.pack("<H", len(subfield)) + subfield

    inner = dest.name[:-3] if dest.name.endswith(".dz") else dest.name
    name = inner.encode("latin-1", "replace")
    header = _GZIP_MAGIC + bytes([_DEFLATE, _FEXTRA | _FNAME])
    header += struct.pack("<I", int(mtime if mtime is not None else time.time()))
    header += bytes([0, _OS_UNIX])
    header += struct.pack("<H", len(extra)) + extra + name + b"\x00"

    written = 0
    with dest.open("wb") as out:
        written += out.write(header)
        for block in body:
            written += out.write(block)
        written += out.write(tail)
        written += out.write(struct.pack("<II", crc & 0xFFFFFFFF, total & 0xFFFFFFFF))
    return written
