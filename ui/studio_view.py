import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QPlainTextEdit, QComboBox, QSpinBox,
    QSplitter, QProgressBar, QFileDialog, QScrollArea, QFrame,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QTextOption
from ui.glass_widgets import GlassCard, SelectableStyleCard, StepIndicatorBar
from ui.storyboard_inspector import StoryboardInspectorWidget


IDEA_BANKS = [
    [
        ("How Sand Turns to Glass", "How It's Made", "3D_Pixar"),
        ("How Noise-Canceling Headphones Erase Sound", "Engineering", "3D_Teardown"),
        ("Why Airplane Windows Have a Tiny Hole", "Engineering", "3D_Pixar"),
    ],
    [
        ("How Quartz Watches Keep Exact Time", "Engineering", "3D_Teardown"),
        ("How Bulletproof Glass Stops an Impact", "How It's Made", "3D_Pixar"),
        ("Why Suspension Bridges Don't Snap", "Architecture", "3D_Pixar"),
    ],
    [
        ("How Piezoelectric Igniters Make 15,000V", "Engineering", "3D_Teardown"),
        ("How Touchscreens Detect Your Finger", "STEM", "3D_Teardown"),
        ("Why Déjà Vu Happens in the Brain", "Psychology", "2D_Kurzgesagt"),
    ],
]


class StudioView(QWidget):
    """
    Apple Pro Guided Studio Workspace:
    - Step 1: Topic & Visual Look (separate rows for Look and Engine — no horizontal crowding)
    - Step 2: Script & Pacing (distraction-free writer with word/timing telemetry)
    - Step 3 & 4: Storyboard Timeline & Video Pipeline
    """
    state_changed = Signal()
    generate_script_requested = Signal()
    revise_script_requested = Signal(str)
    save_project_requested = Signal()
    run_audio_requested = Signal()
    run_render_requested = Signal()
    open_research_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.style_reference_path: str = ""
        self._idea_bank_idx: int = 0
        self.style_cards: dict[str, SelectableStyleCard] = {}
        self.mode_cards: dict[str, SelectableStyleCard] = {}
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(8)

        # Top Sleek 36px Stage Tracker
        self.step_bar = StepIndicatorBar()
        self.step_bar.step_clicked.connect(self._on_step_pill_clicked)
        self.step_bar.next_action_triggered.connect(self._on_next_step_cta)
        outer.addWidget(self.step_bar)

        # Main Scrollable Area for workspace content
        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setFrameShape(QFrame.Shape.NoFrame)
        main_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(10)

        # Splitter between Script Deck and Storyboard
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(2)

        # =====================================================================
        # TOP HALF: STEP 1 (TOPIC & LOOK) + STEP 2 (SCRIPT & PACING)
        # =====================================================================
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        # --- STEP 1 CARD: Topic & Production Setup ---
        self.card_step1 = GlassCard(radius=8)
        s1_layout = QVBoxLayout(self.card_step1)
        s1_layout.setContentsMargins(14, 12, 14, 12)
        s1_layout.setSpacing(8)

        # Topic Header + Input
        topic_hdr = QHBoxLayout()
        lbl_step1 = QLabel("TOPIC & CONCEPT")
        lbl_step1.setProperty("class", "eyebrow")
        topic_hdr.addWidget(lbl_step1)
        topic_hdr.addStretch()

        self.btn_extras_toggle = QPushButton("Options ▸")
        self.btn_extras_toggle.setProperty("class", "chip")
        self.btn_extras_toggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_extras_toggle.clicked.connect(self._toggle_extras)
        topic_hdr.addWidget(self.btn_extras_toggle)
        s1_layout.addLayout(topic_hdr)

        topic_input_row = QHBoxLayout()
        topic_input_row.setSpacing(8)
        self.input_title = QLineEdit()
        self.input_title.setPlaceholderText("Enter topic (e.g., How Sand Turns to Glass, Why Bridges Don't Collapse)...")
        self.input_title.setStyleSheet("font-size: 13px; padding: 8px 12px;")
        self.input_title.textChanged.connect(self._on_any_change)
        topic_input_row.addWidget(self.input_title, stretch=1)

        self.btn_generate_script = QPushButton("Write Script")
        self.btn_generate_script.setProperty("class", "primary")
        self.btn_generate_script.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_generate_script.clicked.connect(self.generate_script_requested.emit)
        topic_input_row.addWidget(self.btn_generate_script)
        s1_layout.addLayout(topic_input_row)

        # Suggestions Row
        ideas_row = QHBoxLayout()
        ideas_row.setSpacing(6)
        lbl_ideas = QLabel("Suggestions:")
        lbl_ideas.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 11px; font-weight: 500; background: transparent;")
        ideas_row.addWidget(lbl_ideas)

        self.idea_chip_buttons: list[QPushButton] = []
        for _ in range(3):
            chip = QPushButton()
            chip.setProperty("class", "chip")
            chip.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            chip.clicked.connect(self._on_idea_chip_clicked)
            ideas_row.addWidget(chip)
            self.idea_chip_buttons.append(chip)

        ideas_row.addStretch()

        self.btn_more_ideas = QPushButton("Cycle Ideas")
        self.btn_more_ideas.setProperty("class", "chip")
        self.btn_more_ideas.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_more_ideas.clicked.connect(self._cycle_idea_bank)
        ideas_row.addWidget(self.btn_more_ideas)

        self.btn_find_trends = QPushButton("Topic Finder")
        self.btn_find_trends.setProperty("class", "chip")
        self.btn_find_trends.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_find_trends.clicked.connect(self.open_research_requested.emit)
        ideas_row.addWidget(self.btn_find_trends)

        s1_layout.addLayout(ideas_row)
        self._populate_idea_chips()

        # Row 1 of Cards: Visual Style (3 cards across - clean and spacious)
        lbl_vis = QLabel("VISUAL STYLE")
        lbl_vis.setProperty("class", "eyebrow")
        s1_layout.addWidget(lbl_vis)

        style_cards_h = QHBoxLayout()
        style_cards_h.setSpacing(8)
        style_defs = [
            ("3D_Pixar", "3D Cutaway", "Pixar & Zack D. Films cross-section", "Standard"),
            ("3D_Teardown", "3D Teardown", "Exploded mechanical and engineering view", ""),
            ("2D_Kurzgesagt", "Illustrated", "Clean vector infographics & scientific art", ""),
        ]
        for key, title, desc, badge in style_defs:
            sc = SelectableStyleCard(key, title, desc, badge, selected=(key == "3D_Pixar"))
            sc.clicked.connect(self._on_style_card_clicked)
            style_cards_h.addWidget(sc)
            self.style_cards[key] = sc
        s1_layout.addLayout(style_cards_h)

        # Row 2 of Cards: Render Mode (3 cards across)
        lbl_mod = QLabel("RENDER PIPELINE")
        lbl_mod.setProperty("class", "eyebrow")
        s1_layout.addWidget(lbl_mod)

        mode_cards_h = QHBoxLayout()
        mode_cards_h.setSpacing(8)
        mode_defs = [
            ("smart_hybrid", "Smart Hybrid", "AI video hook + 2.5D motion keyframes", "Balanced"),
            ("full_omni", "AI Video Clips", "Every scene generated as motion video (Wan)", "Maximum"),
            ("keyframe_only", "Keyframe Motion", "High-speed keyframes with Ken Burns camera", "Fast Draft"),
        ]
        for key, title, desc, badge in mode_defs:
            mc = SelectableStyleCard(key, title, desc, badge, selected=(key == "smart_hybrid"))
            mc.clicked.connect(self._on_mode_card_clicked)
            mode_cards_h.addWidget(mc)
            self.mode_cards[key] = mc
        s1_layout.addLayout(mode_cards_h)

        # Collapsible Optional Extras Drawer
        self.extras_widget = QWidget()
        extras_layout = QHBoxLayout(self.extras_widget)
        extras_layout.setContentsMargins(0, 4, 0, 0)
        extras_layout.setSpacing(10)

        extras_layout.addWidget(QLabel("Category:"))
        self.combo_category = QComboBox()
        self.combo_category.addItems([
            "STEM",
            "Engineering",
            "How It's Made",
            "Architecture",
            "Escape/Heist",
            "Psychology",
        ])
        self.combo_category.currentTextChanged.connect(self._on_any_change)
        extras_layout.addWidget(self.combo_category)

        lbl_dur = QLabel("Target Duration:")
        lbl_dur.setStyleSheet("color: #f3f4f6; font-weight: 500; background: transparent;")
        extras_layout.addWidget(lbl_dur)
        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(30, 120)
        self.spin_duration.setValue(65)
        self.spin_duration.setSuffix(" sec (61-70s TikTok)")
        self.spin_duration.valueChanged.connect(self._on_duration_or_script_changed)
        extras_layout.addWidget(self.spin_duration)

        extras_layout.addWidget(QLabel("Product Mention:"))
        self.input_product = QLineEdit()
        self.input_product.setPlaceholderText("Leave blank for educational...")
        self.input_product.textChanged.connect(self._on_any_change)
        extras_layout.addWidget(self.input_product, stretch=1)

        self.btn_pick_style_ref = QPushButton("Custom Style Image...")
        self.btn_pick_style_ref.setProperty("class", "chip")
        self.btn_pick_style_ref.clicked.connect(self._pick_style_ref)
        extras_layout.addWidget(self.btn_pick_style_ref)

        # Hidden synchronized combos for programmatic access
        self.combo_style = QComboBox()
        self.combo_style.addItem("3D Cutaway", "3D_Pixar")
        self.combo_style.addItem("3D Teardown", "3D_Teardown")
        self.combo_style.addItem("2D Storybook", "2D_Kurzgesagt")
        self.combo_style.currentIndexChanged.connect(self._sync_cards_from_combos)
        self.combo_style.setVisible(False)
        extras_layout.addWidget(self.combo_style)

        self.combo_render_mode = QComboBox()
        self.combo_render_mode.addItem("Smart Hybrid", "smart_hybrid")
        self.combo_render_mode.addItem("Full Omni", "full_omni")
        self.combo_render_mode.addItem("Keyframe Only", "keyframe_only")
        self.combo_render_mode.setCurrentIndex(0)
        self.combo_render_mode.currentIndexChanged.connect(self._sync_cards_from_combos)
        self.combo_render_mode.setVisible(False)
        extras_layout.addWidget(self.combo_render_mode)

        self.extras_widget.setVisible(False)
        s1_layout.addWidget(self.extras_widget)
        top_layout.addWidget(self.card_step1)

        # --- STEP 2 CARD: Script Editor & Pacing ---
        self.card_step2 = GlassCard(radius=8)
        s2_layout = QVBoxLayout(self.card_step2)
        s2_layout.setContentsMargins(14, 12, 14, 12)
        s2_layout.setSpacing(8)

        s2_header = QHBoxLayout()
        lbl_step2 = QLabel("SCRIPT & PACING")
        lbl_step2.setProperty("class", "eyebrow")
        s2_header.addWidget(lbl_step2)

        self.lbl_word_stats = QLabel("00:00.00  •  0 words")
        self.lbl_word_stats.setProperty("class", "mono")
        self.lbl_word_stats.setStyleSheet(
            "background-color: rgba(255,255,255,0.06); color: #d1d5db; border: 1px solid rgba(255,255,255,0.10); border-radius: 6px; padding: 2px 8px; font-size: 11px;"
        )
        s2_header.addWidget(self.lbl_word_stats)
        s2_header.addStretch()

        self.btn_save = QPushButton("Save Draft")
        self.btn_save.setProperty("class", "chip")
        self.btn_save.clicked.connect(self.save_project_requested.emit)
        s2_header.addWidget(self.btn_save)
        s2_layout.addLayout(s2_header)

        self.txt_script = QPlainTextEdit()
        self.txt_script.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.txt_script.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.txt_script.setPlaceholderText(
            "Click 'Write Script' above or enter custom narration here. Generated script automatically turns into timed voiceover and scenes."
        )
        self.txt_script.setMinimumHeight(110)
        self.txt_script.setMaximumHeight(200)
        self.txt_script.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.txt_script.textChanged.connect(self._on_duration_or_script_changed)
        s2_layout.addWidget(self.txt_script)

        # Quick Polish Tools
        polish_row = QHBoxLayout()
        polish_row.setSpacing(6)
        lbl_pol = QLabel("Quick Polish:")
        lbl_pol.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 11px; font-weight: 500; background: transparent;")
        polish_row.addWidget(lbl_pol)

        quick_prompts = [
            ("Enhance Hook", "Make the opening hook more exciting and curiosity-inducing."),
            ("Simplify Language", "Explain the mechanism in simpler, everyday conversational language."),
            ("Extend to 65s", "Expand the explanation with fascinating scientific details so the script reaches 61-70s to qualify for TikTok Creator Rewards monetization."),
            ("Tighten Pacing", "Shorten and tighten the pacing so it is punchier."),
            ("Clean Standalone", "Stop referring to the video name and rewrite cleanly as a standalone script."),
        ]
        for btn_label, instruction in quick_prompts:
            q_btn = QPushButton(btn_label)
            q_btn.setProperty("class", "chip")
            q_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            q_btn.clicked.connect(lambda _checked=False, inst=instruction: self.revise_script_requested.emit(inst))
            polish_row.addWidget(q_btn)

        polish_row.addStretch()
        s2_layout.addLayout(polish_row)

        rev_bar = QHBoxLayout()
        rev_bar.setSpacing(8)
        self.input_ai_prompt = QLineEdit()
        self.input_ai_prompt.setPlaceholderText(
            "Direct revision instructions (e.g., 'Add a fun fact about lightning melting quartz sand')..."
        )
        self.input_ai_prompt.returnPressed.connect(self._emit_script_revision)
        rev_bar.addWidget(self.input_ai_prompt, stretch=1)

        self.btn_apply_revision = QPushButton("Apply Edit")
        self.btn_apply_revision.clicked.connect(self._emit_script_revision)
        rev_bar.addWidget(self.btn_apply_revision)
        s2_layout.addLayout(rev_bar)

        top_layout.addWidget(self.card_step2, stretch=1)
        splitter.addWidget(top_container)

        # =====================================================================
        # BOTTOM HALF: STEP 3 (VOICE & SCENES) + STEP 4 (CREATE VIDEO)
        # =====================================================================
        self.card_step3 = GlassCard(radius=8)
        s3_layout = QVBoxLayout(self.card_step3)
        s3_layout.setContentsMargins(14, 12, 14, 12)
        s3_layout.setSpacing(8)

        s3_header = QHBoxLayout()
        lbl_step3 = QLabel("SCENE BREAKDOWN & PRODUCTION")
        lbl_step3.setProperty("class", "eyebrow")
        s3_header.addWidget(lbl_step3)
        s3_header.addStretch()
        s3_layout.addLayout(s3_header)

        self.storyboard_inspector = StoryboardInspectorWidget()
        s3_layout.addWidget(self.storyboard_inspector, stretch=1)

        # Bottom Guided Action Bar (Two clean rows to eliminate squeeze)
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        self.btn_run_audio = QPushButton("Build Voiceover && Scenes")
        self.btn_run_audio.setProperty("class", "primary")
        self.btn_run_audio.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_run_audio.clicked.connect(self.run_audio_requested.emit)
        action_row.addWidget(self.btn_run_audio)

        self.btn_run_render = QPushButton("Render Final Video (Est. $0.00)")
        self.btn_run_render.setProperty("class", "success")
        self.btn_run_render.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_run_render.clicked.connect(self.run_render_requested.emit)
        action_row.addWidget(self.btn_run_render)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(140)
        action_row.addWidget(self.progress_bar)

        action_row.addStretch()
        s3_layout.addLayout(action_row)

        self.lbl_pipeline_status = QLabel("Ready — Pick a topic in Step 1 to begin.")
        self.lbl_pipeline_status.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 11.5px; background: transparent;")
        s3_layout.addWidget(self.lbl_pipeline_status)

        splitter.addWidget(self.card_step3)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)
        scroll_layout.addWidget(splitter)

        main_scroll.setWidget(scroll_content)
        outer.addWidget(main_scroll, stretch=1)

    # =========================================================================
    # INTERACTIVE HELPERS
    # =========================================================================
    def _populate_idea_chips(self):
        bank = IDEA_BANKS[self._idea_bank_idx % len(IDEA_BANKS)]
        for i, btn in enumerate(self.idea_chip_buttons):
            if i < len(bank):
                title, cat, style = bank[i]
                btn.setText(title)
                btn.setProperty("idea_data", (title, cat, style))

    def _cycle_idea_bank(self):
        self._idea_bank_idx = (self._idea_bank_idx + 1) % len(IDEA_BANKS)
        self._populate_idea_chips()

    def _on_idea_chip_clicked(self):
        btn = self.sender()
        if not btn:
            return
        data = btn.property("idea_data")
        if data:
            title, cat, style = data
            self.input_title.setText(title)
            c_idx = self.combo_category.findText(cat)
            if c_idx >= 0:
                self.combo_category.setCurrentIndex(c_idx)
            self._on_style_card_clicked(style)
            self.step_bar.set_step(0, "", "Write Script ⌘↵")

    def _toggle_extras(self):
        vis = not self.extras_widget.isVisible()
        self.extras_widget.setVisible(vis)
        self.btn_extras_toggle.setText("Options ▾" if vis else "Options ▸")

    def _on_style_card_clicked(self, key: str):
        idx = self.combo_style.findData(key)
        if idx >= 0:
            self.combo_style.setCurrentIndex(idx)
        for k, card in self.style_cards.items():
            card.set_selected(k == key)
        self._on_any_change()

    def _on_mode_card_clicked(self, key: str):
        idx = self.combo_render_mode.findData(key)
        if idx >= 0:
            self.combo_render_mode.setCurrentIndex(idx)
        for k, card in self.mode_cards.items():
            card.set_selected(k == key)
        self._on_any_change()

    def _sync_cards_from_combos(self, *_):
        style_key = self.combo_style.currentData()
        for k, card in self.style_cards.items():
            card.set_selected(k == style_key)

        mode_key = self.combo_render_mode.currentData()
        for k, card in self.mode_cards.items():
            card.set_selected(k == mode_key)
        self._on_any_change()

    def _on_step_pill_clicked(self, step_idx: int):
        self.step_bar.set_step(step_idx)

    def _on_next_step_cta(self, current_step: int):
        if current_step == 0:
            self.generate_script_requested.emit()
        elif current_step == 1:
            self.run_audio_requested.emit()
        elif current_step == 2:
            self.run_render_requested.emit()
        else:
            self.run_render_requested.emit()

    def update_cost_estimates(self, tracker: object, image_model: str = "gemini-nano-banana-2.1", omni_res: str = "720p"):
        scenes = self.storyboard_inspector.get_scenes()
        current_mode = self.combo_render_mode.currentData() or "smart_hybrid"

        for mode_key, card in self.mode_cards.items():
            est = tracker.estimate_render_cost(scenes, mode_key, image_model, omni_res)
            card.set_badge(est.get("badge", ""))
            if mode_key == current_mode:
                self.btn_run_render.setText(f"Render Final Video ({est.get('badge', 'Est. $0.00')})")
                self.btn_run_render.setToolTip(est.get("summary", ""))

    def _pick_style_ref(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Style Reference Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if path:
            self.set_style_reference_path(path)
            self._on_any_change()

    def set_style_reference_path(self, path: str):
        self.style_reference_path = path or ""
        if self.style_reference_path and os.path.exists(self.style_reference_path):
            self.btn_pick_style_ref.setText(os.path.basename(self.style_reference_path))
            self.btn_pick_style_ref.setToolTip(self.style_reference_path)
        else:
            self.btn_pick_style_ref.setText("Custom Style Image...")
            self.btn_pick_style_ref.setToolTip("")

    def _emit_script_revision(self):
        instruction = self.input_ai_prompt.text().strip()
        if instruction:
            self.revise_script_requested.emit(instruction)

    def _on_duration_or_script_changed(self):
        words = [w for w in self.txt_script.toPlainText().split() if w.strip()]
        w_count = len(words)
        est_sec = int(round(w_count / 2.35))
        m, s = divmod(est_sec, 60)
        timecode = f"{m:02d}:{s:02d}.00"
        if est_sec >= 61 and est_sec <= 75:
            self.lbl_word_stats.setText(f"{timecode}  •  {w_count} words  •  Monetized (61–70s)")
            self.lbl_word_stats.setStyleSheet(
                "background-color: rgba(48,209,88,0.15); color: #30D158; border: 1px solid rgba(48,209,88,0.30); border-radius: 6px; padding: 2px 8px; font-size: 11px;"
            )
        elif est_sec < 61 and w_count > 0:
            shortfall = max(1, 145 - w_count)
            self.lbl_word_stats.setText(f"{timecode}  •  {w_count} words  •  Under 61s (+{shortfall}w needed)")
            self.lbl_word_stats.setStyleSheet(
                "background-color: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.30); border-radius: 6px; padding: 2px 8px; font-size: 11px;"
            )
        elif est_sec > 75:
            self.lbl_word_stats.setText(f"{timecode}  •  {w_count} words  •  Longer than 75s")
            self.lbl_word_stats.setStyleSheet(
                "background-color: rgba(255,255,255,0.06); color: #d1d5db; border: 1px solid rgba(255,255,255,0.10); border-radius: 6px; padding: 2px 8px; font-size: 11px;"
            )
        else:
            self.lbl_word_stats.setText("00:00.00  •  0 words  •  Target: 61–70s")
            self.lbl_word_stats.setStyleSheet(
                "background-color: rgba(255,255,255,0.06); color: #d1d5db; border: 1px solid rgba(255,255,255,0.10); border-radius: 6px; padding: 2px 8px; font-size: 11px;"
            )
        if w_count >= 20 and self.step_bar.current_step == 0:
            self.step_bar.set_step(1)
        self.state_changed.emit()

    def _on_any_change(self, *_):
        self.state_changed.emit()
