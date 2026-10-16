from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QListWidget, QListWidgetItem, QSplitter
)
from PySide6.QtCore import Qt, Signal
from ui.glass_widgets import GlassCard


class ResearchView(QWidget):
    """
    Competitor Intelligence & Trend Synthesis View:
    - Live YouTube/Shorts search & channel scanning
    - Gemini 3.5 Flash-Lite / 3.8 Flash structured concept generator
    - One-click transfer of selected topic + audience confusion/complaint/gap insights to Studio
    """
    scrape_requested = Signal(str, str)  # (query, mode: 'keyword' | 'channel')
    send_to_studio_requested = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scraped_trends: list[dict] = []
        self.suggestions: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        # Search Header Card
        search_card = GlassCard()
        s_layout = QHBoxLayout(search_card)
        s_layout.setContentsMargins(18, 14, 18, 14)
        s_layout.setSpacing(12)

        lbl = QLabel("🔍 Topic & Channel Finder")
        lbl.setStyleSheet("color: #F5F5F7; font-weight: 700; font-size: 15px;")
        s_layout.addWidget(lbl)

        self.input_query = QLineEdit()
        self.input_query.setPlaceholderText("Search a topic or @channel handle (e.g., 'How jet engines work', '@zackdfilms')...")
        self.input_query.setText("How everyday technology works")
        self.input_query.returnPressed.connect(self._trigger_search)
        s_layout.addWidget(self.input_query, stretch=1)

        self.btn_scrape = QPushButton("🔍 Find Viral Topics & Ideas")
        self.btn_scrape.setProperty("class", "primary")
        self.btn_scrape.clicked.connect(self._trigger_search)
        s_layout.addWidget(self.btn_scrape)

        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color: #98989D; font-size: 12px;")
        s_layout.addWidget(self.lbl_status)

        layout.addWidget(search_card)

        # Main Horizontal Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Scraped Competitor Videos Table
        vid_card = GlassCard()
        v_layout = QVBoxLayout(vid_card)
        v_layout.setContentsMargins(14, 14, 14, 14)
        v_layout.setSpacing(8)
        lbl_v = QLabel("Top Videos in This Niche")
        lbl_v.setStyleSheet("color: #F5F5F7; font-weight: 700; font-size: 14px;")
        v_layout.addWidget(lbl_v)

        self.table_videos = QTableWidget(0, 3)
        self.table_videos.setHorizontalHeaderLabels(["Title / Topic", "Views", "Category"])
        self.table_videos.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_videos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_videos.itemSelectionChanged.connect(self._on_video_selection_changed)
        self.table_videos.cellDoubleClicked.connect(self._on_video_double_clicked)
        v_layout.addWidget(self.table_videos, stretch=1)
        splitter.addWidget(vid_card)

        # Middle: Audience Comment Breakdown (Confusion / Complaints / Gaps)
        ins_card = GlassCard()
        i_layout = QVBoxLayout(ins_card)
        i_layout.setContentsMargins(14, 14, 14, 14)
        i_layout.setSpacing(6)
        lbl_i = QLabel("What Viewers Are Asking")
        lbl_i.setStyleSheet("color: #F5F5F7; font-weight: 700; font-size: 14px;")
        i_layout.addWidget(lbl_i)

        lbl_c1 = QLabel("❓ Common Questions:")
        lbl_c1.setStyleSheet("color: #98989D; font-size: 12px; font-weight: 600;")
        i_layout.addWidget(lbl_c1)
        self.list_confusion = QListWidget()
        i_layout.addWidget(self.list_confusion, stretch=1)

        lbl_c2 = QLabel("⚠️ Viewer Frustrations:")
        lbl_c2.setStyleSheet("color: #98989D; font-size: 12px; font-weight: 600;")
        i_layout.addWidget(lbl_c2)
        self.list_complaints = QListWidget()
        i_layout.addWidget(self.list_complaints, stretch=1)

        lbl_c3 = QLabel("💡 Untapped Angles:")
        lbl_c3.setStyleSheet("color: #98989D; font-size: 12px; font-weight: 600;")
        i_layout.addWidget(lbl_c3)
        self.list_gaps = QListWidget()
        i_layout.addWidget(self.list_gaps, stretch=1)
        splitter.addWidget(ins_card)

        # Right: Gemini-Synthesized Viral Video Concepts
        sug_card = GlassCard()
        g_layout = QVBoxLayout(sug_card)
        g_layout.setContentsMargins(14, 14, 14, 14)
        g_layout.setSpacing(8)
        lbl_g = QLabel("Ready-to-Use Video Ideas")
        lbl_g.setStyleSheet("color: #F5F5F7; font-weight: 700; font-size: 14px;")
        g_layout.addWidget(lbl_g)

        self.list_suggestions = QListWidget()
        self.list_suggestions.itemDoubleClicked.connect(lambda _: self._send_selected_to_studio())
        g_layout.addWidget(self.list_suggestions, stretch=1)

        self.btn_send_studio = QPushButton("🚀 Use This Idea in Studio →")
        self.btn_send_studio.setProperty("class", "success")
        self.btn_send_studio.clicked.connect(self._send_selected_to_studio)
        g_layout.addWidget(self.btn_send_studio)
        splitter.addWidget(sug_card)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 3)
        layout.addWidget(splitter, stretch=1)

    def _trigger_search(self):
        q = self.input_query.text().strip() or "How everyday technology works"
        mode = "channel" if q.startswith("@") or "youtube.com/" in q else "keyword"
        self.lbl_status.setText("Finding ideas...")
        self.btn_scrape.setEnabled(False)
        self.scrape_requested.emit(q, mode)

    def _on_video_selection_changed(self):
        row = self.table_videos.currentRow()
        if 0 <= row < len(self.scraped_trends):
            self._populate_comment_lists([self.scraped_trends[row]])

    def _populate_comment_lists(self, items: list[dict]):
        self.list_confusion.clear()
        self.list_complaints.clear()
        self.list_gaps.clear()
        for item in items:
            for c in str(item.get("confusion_points", "")).split("|"):
                if c.strip():
                    self.list_confusion.addItem(c.strip())
            for c in str(item.get("complaints", "")).split("|"):
                if c.strip():
                    self.list_complaints.addItem(c.strip())
            for c in str(item.get("content_gaps", "")).split("|"):
                if c.strip():
                    self.list_gaps.addItem(c.strip())

    def _on_video_double_clicked(self, row: int, _col: int):
        if 0 <= row < len(self.scraped_trends):
            t = self.scraped_trends[row]
            self.send_to_studio_requested.emit({
                "title": t.get("topic", ""),
                "category": t.get("category", "STEM"),
                "style": "3D_Pixar",
                "confusion_points": t.get("confusion_points", ""),
                "complaints": t.get("complaints", ""),
                "content_gaps": t.get("content_gaps", ""),
            })

    def load_results(self, payload: dict):
        self.btn_scrape.setEnabled(True)
        self.scraped_trends = payload.get("trends", payload.get("videos", []))
        self.suggestions = payload.get("suggestions", [])

        self.table_videos.setRowCount(0)
        for v in self.scraped_trends:
            r = self.table_videos.rowCount()
            self.table_videos.insertRow(r)
            self.table_videos.setItem(r, 0, QTableWidgetItem(str(v.get("topic") or v.get("title", ""))))
            views = v.get("views", v.get("view_count", 0))
            v_str = f"{views:,}" if isinstance(views, int) else str(views)
            self.table_videos.setItem(r, 1, QTableWidgetItem(v_str))
            self.table_videos.setItem(r, 2, QTableWidgetItem(str(v.get("category", "STEM"))))

        self._populate_comment_lists(self.scraped_trends)

        self.list_suggestions.clear()
        for sug in self.suggestions:
            title = sug.get("title", "Untitled Concept")
            hook = sug.get("hook", "")
            angle = sug.get("competitive_advantage") or sug.get("angle", "")
            style = sug.get("recommended_engine") or sug.get("recommended_style", "3D_Pixar")
            item = QListWidgetItem(f"💡 {title}\n   Opening: {hook}\n   Why it works: {angle}  [{style}]")
            item.setData(Qt.ItemDataRole.UserRole, sug)
            self.list_suggestions.addItem(item)

        if self.list_suggestions.count() > 0:
            self.list_suggestions.setCurrentRow(0)
        self.lbl_status.setText(f"Found {len(self.scraped_trends)} videos & {len(self.suggestions)} ready-to-use ideas")

    def _send_selected_to_studio(self):
        item = self.list_suggestions.currentItem()
        if item:
            sug = item.data(Qt.ItemDataRole.UserRole) or {}
            self.send_to_studio_requested.emit({
                "title": sug.get("title", self.input_query.text().strip()),
                "category": sug.get("category", "STEM"),
                "style": sug.get("recommended_engine") or sug.get("recommended_style", "3D_Pixar"),
                "hook": sug.get("hook", ""),
                "confusion_points": sug.get("confusion_focus", ""),
                "complaints": sug.get("complaint_resolved", ""),
                "content_gaps": sug.get("competitive_advantage", ""),
            })
        elif self.input_query.text().strip():
            self.send_to_studio_requested.emit({
                "title": self.input_query.text().strip(),
                "category": "STEM",
                "style": "3D_Pixar",
            })
