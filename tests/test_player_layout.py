"""Offscreen check that the phone preview never covers the checklist."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytest.importorskip("PySide6")
pytest.importorskip("cv2")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_preview_does_not_cover_checklist_at_any_honored_width():
    from PySide6.QtWidgets import QApplication, QScrollArea

    application = QApplication.instance() or QApplication([])
    import app as studio

    window = studio.CrayonStudioApp()
    window.tab_widget.setCurrentIndex(2)
    window.show()
    application.processEvents()

    def columns(width):
        window.resize(width, 800)
        window.tab_widget.setCurrentIndex(2)
        application.processEvents()
        layout = window.centralWidget().layout()
        if layout is not None:
            layout.activate()
        application.processEvents()
        window._apply_preview_columns()
        application.processEvents()
        content = window.player_splitter.widget(0).geometry()
        preview = window.player_splitter.widget(1).geometry()
        intersection = content.intersected(preview)
        assert intersection.width() <= 2 or intersection.height() <= 2
        assert content.width() > 200
        if preview.width() > 2:
            assert content.right() <= preview.left() + 2
        return content.width(), preview.width()

    wide_content, wide_preview = columns(1280)
    assert wide_preview > 150
    assert wide_content > wide_preview

    # The window floor is 960. Asking for less must not produce an overlap
    # at the size Qt actually honors.
    small_content, small_preview = columns(640)
    assert small_content > 200
    assert small_content + small_preview <= window.player_splitter.width() + 8

    window._preview_user_choice = False
    _content, hidden = columns(1280)
    assert hidden <= 2

    assert isinstance(window.tab_studio, QScrollArea)
    window.close()
