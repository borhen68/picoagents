"""Shared utilities for channel adapters."""
from __future__ import annotations


def split_message(content: str, max_len: int = 2000) -> list[str]:
    """Split a long message into chunks, preferring newline/space boundaries.

    Args:
        content: The message text to split.
        max_len: Maximum length of each chunk.

    Returns:
        A list of message chunks, each at most ``max_len`` characters.
    """
    text = content or ""
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Search up to max_len+1 so a boundary exactly at max_len is found
        cut = text.rfind("\n", 0, max_len + 1)
        if cut <= 0:
            cut = text.rfind(" ", 0, max_len + 1)
        if cut <= 0:
            # No word boundary found — hard cut
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip()
    return chunks
