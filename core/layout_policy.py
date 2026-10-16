"""Width policy for the phone-preview column.

The player tab used to place a 9:16 preview and the checklist in one horizontal
layout. Each side had a large minimum size, and the card stylesheet added
padding that Qt layouts do not subtract, so on a narrow window the preview
painted over the checklist. These widths always sum to the container, and the
preview is dropped before the checklist would be squeezed under it.
"""

from __future__ import annotations

# Below this container width the preview hides. Both columns cannot keep a
# readable checklist (480px) and a usable phone (200px) plus the splitter.
PREVIEW_COLLAPSE_BELOW = 720
CONTENT_FLOOR = 480
PREVIEW_MIN = 200
PREVIEW_MAX = 360
PREVIEW_FRACTION = 0.30


def split_widths(container_width: int, preview_enabled: bool) -> tuple[int, int]:
    """Return ``(content_width, preview_width)`` for the player splitter.

    The preview is the trailing column. Its width is 0 when the user has hidden
    it or when showing it would cover the checklist.
    """
    width = max(0, int(container_width))
    if not preview_enabled or width < PREVIEW_COLLAPSE_BELOW:
        return width, 0

    preview = int(width * PREVIEW_FRACTION)
    preview = max(PREVIEW_MIN, min(PREVIEW_MAX, preview))
    content = width - preview
    if content < CONTENT_FLOOR:
        preview = width - CONTENT_FLOOR
        if preview < 180:
            return width, 0
        content = width - preview
    return content, preview
