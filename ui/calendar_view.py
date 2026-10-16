from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit
)
from PySide6.QtCore import QDate, Signal
from ui.glass_widgets import GlassCard


class CalendarView(QWidget):
    """
    Production Pipeline & Content Calendar View:
    - Lists all persisted projects with their style, render mode, status, metadata, and scheduled date
    - Restores full project state (script, storyboard scenes, metadata, video) on load
    """
    project_selected = Signal(dict)
    new_project_requested = Signal()
    schedule_date_requested = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.projects: list[dict] = []
        self._build_ui()

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(320, 200)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        header_card = GlassCard(radius=8)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(18, 14, 18, 14)
        h_layout.setSpacing(10)

        lbl = QLabel("SAVED PROJECTS & SCHEDULE")
        lbl.setProperty("class", "eyebrow")
        lbl.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 10px; font-weight: 600; letter-spacing: 1.2px;")
        h_layout.addWidget(lbl)
        h_layout.addStretch()

        lbl_sched = QLabel("Schedule Date:")
        lbl_sched.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 12px;")
        h_layout.addWidget(lbl_sched)
        self.date_picker = QDateEdit()
        self.date_picker.setCalendarPopup(True)
        self.date_picker.setDate(QDate.currentDate())
        h_layout.addWidget(self.date_picker)

        self.btn_assign_date = QPushButton("Set Date")
        self.btn_assign_date.setProperty("class", "chip")
        self.btn_assign_date.clicked.connect(self._assign_date)
        h_layout.addWidget(self.btn_assign_date)

        self.btn_new_project = QPushButton("New Project")
        self.btn_new_project.setProperty("class", "primary")
        self.btn_new_project.clicked.connect(self.new_project_requested.emit)
        h_layout.addWidget(self.btn_new_project)

        self.btn_load_selected = QPushButton("Open Project")
        self.btn_load_selected.setProperty("class", "success")
        self.btn_load_selected.clicked.connect(self._open_selected)
        h_layout.addWidget(self.btn_load_selected)

        layout.addWidget(header_card)

        table_card = GlassCard(radius=8)
        t_layout = QVBoxLayout(table_card)
        t_layout.setContentsMargins(16, 16, 16, 16)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Video Topic", "Category", "Visual Style", "Quality Mode", "Status", "Scheduled Date"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(lambda _r, _c: self._open_selected())
        t_layout.addWidget(self.table)

        layout.addWidget(table_card, stretch=1)

    def refresh_projects(self, projects: list[dict]):
        self.projects = projects or []
        self.table.setRowCount(0)
        for p in self.projects:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(p.get("id", ""))))
            self.table.setItem(r, 1, QTableWidgetItem(str(p.get("title", ""))))
            self.table.setItem(r, 2, QTableWidgetItem(str(p.get("category", "STEM"))))
            self.table.setItem(r, 3, QTableWidgetItem(str(p.get("visual_engine", "3D_Pixar"))))
            self.table.setItem(r, 4, QTableWidgetItem(str(p.get("render_mode", "smart_hybrid"))))
            self.table.setItem(r, 5, QTableWidgetItem(str(p.get("status", "Draft"))))
            self.table.setItem(r, 6, QTableWidgetItem(str(p.get("scheduled_time") or "Unscheduled")))

    def _open_selected(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.projects):
            self.project_selected.emit(dict(self.projects[row]))

    def _assign_date(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.projects):
            proj_id = int(self.projects[row]["id"])
            date_str = self.date_picker.date().toString("yyyy-MM-dd")
            self.schedule_date_requested.emit(proj_id, date_str)
