"""Binary audio frames: version, flags, sequence, payload.

The client can play chunks as they arrive and can drop a sentence on barge-in
without mixing it into the next utterance.
"""

from __future__ import annotations

import struct

FRAME_VERSION = 1
FLAG_LAST = 0x01
FLAG_MP3 = 0x02  # unset means a self-contained WAV chunk


def pack_audio_frame(seq: int, payload: bytes, *, last: bool, codec: str) -> bytes:
    flags = 0
    if last:
        flags |= FLAG_LAST
    if codec == "mp3":
        flags |= FLAG_MP3
    return struct.pack(">BBH", FRAME_VERSION, flags, seq & 0xFFFF) + payload
