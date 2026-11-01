"""Sentence splitting for incremental TTS.

The first chunk uses a shorter minimum so playback can start before a long
sentence is finished. Later chunks stay longer so speech does not sound chopped.
"""

from __future__ import annotations

FIRST_CHUNK_MIN = 12
LATER_CHUNK_MIN = 40
FORCE_SPLIT_FACTOR = 3


def split_sentence(text: str, *, first_chunk: bool) -> tuple[str, str]:
    """Return (ready_piece, remainder).

    A ready piece is empty when the buffer should keep growing.
    """
    if not text:
        return "", text

    min_len = FIRST_CHUNK_MIN if first_chunk else LATER_CHUNK_MIN
    if len(text) < min_len:
        return "", text

    for i, char in enumerate(text):
        if i < min_len - 1:
            continue
        if char in ".!?" and i < len(text) - 1 and text[i + 1] == " ":
            return text[: i + 1].strip(), text[i + 2 :]
        if first_chunk and char in ",;:" and i < len(text) - 1 and text[i + 1] == " ":
            return text[: i + 1].strip(), text[i + 2 :]

    if "\n" in text:
        idx = text.index("\n")
        if idx >= min_len:
            return text[:idx].strip(), text[idx + 1 :]

    # A long buffer with no punctuation still has to move, or TTS never starts.
    if len(text) >= min_len * FORCE_SPLIT_FACTOR:
        window = min_len * 2
        cut = text.rfind(" ", 0, window)
        if cut >= min_len:
            return text[:cut].strip(), text[cut + 1 :]
    return "", text
