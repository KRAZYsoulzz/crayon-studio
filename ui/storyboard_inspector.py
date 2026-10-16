import os
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QComboBox, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QCursor
from ui.glass_widgets import GlassCard


class SceneCardWidget(GlassCard):
    """Plain-English, human-friendly card for a single storyboard scene."""
    scene_modified = Signal(int, dict)
    regenerate_requested = Signal(int, dict)
    delete_requested = Signal(int)

    def __init__(self, index: int, scene_data: dict, project_dir: str = "", parent=None):
        super().__init__(radius=8, elevated=False, parent=parent)
        self.index = index
        self.scene_data = dict(scene_data)
        self.project_dir = project_dir
        self._build_ui()
        self.refresh_thumbnail()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        # Left 9:16 Thumbnail Preview
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedSize(78, 138)
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumb.setStyleSheet(
            "background-color: #0d0f13; border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; color: rgba(255,255,255,0.45); font-size: 11px;"
        )
        layout.addWidget(self.lbl_thumb)

        # Right Details Column
        right_col = QVBoxLayout()
        right_col.setSpacing(6)

        # Header Row: Scene #, Timecode, Status Pill, Mode Selector, Redo Button
        header = QHBoxLayout()
        header.setSpacing(8)

        scene_num = int(self.scene_data.get("scene_idx", self.index)) + 1
        start_t = float(self.scene_data.get("start_time", self.scene_data.get("start", 0.0)))
        end_t = float(self.scene_data.get("end_time", self.scene_data.get("end", start_t + 5.0)))
        lbl_title = QLabel(f"Scene {scene_num:02d}  [{start_t:05.2f}s – {end_t:05.2f}s]")
        lbl_title.setProperty("class", "mono")
        lbl_title.setStyleSheet("color: #f5f5f7; font-weight: 600; font-size: 12px; background: transparent;")
        header.addWidget(lbl_title)

        self.lbl_badge = QLabel()
        self._update_badge()
        header.addWidget(self.lbl_badge)

        header.addStretch()

        self.combo_mode = QComboBox()
        self.combo_mode.addItem("Auto (Match Studio Mode)", "auto")
        self.combo_mode.addItem("2.5D Motion Keyframe", "keyframe")
        self.combo_mode.addItem("AI Video Clip (Wan)", "omni_video")
        current_mode = self.scene_data.get("render_mode", self.scene_data.get("scene_mode", "auto"))
        idx = self.combo_mode.findData(current_mode)
        if idx >= 0:
            self.combo_mode.setCurrentIndex(idx)
        self.combo_mode.setFixedWidth(200)
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        header.addWidget(self.combo_mode)

        self.btn_regen = QPushButton("Redo Scene")
        self.btn_regen.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_regen.setToolTip("Re-render this individual scene with updated prompt")
        self.btn_regen.clicked.connect(self._on_regenerate_clicked)
        header.addWidget(self.btn_regen)

        self.btn_delete = QPushButton("Remove")
        self.btn_delete.setProperty("class", "chip")
        self.btn_delete.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_delete.setToolTip("Delete this scene")
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.index))
        header.addWidget(self.btn_delete)

        right_col.addLayout(header)

        # What the narrator says
        narration = (self.scene_data.get("script_excerpt") or self.scene_data.get("text") or "").strip()
        self.lbl_narration = QLabel(f"Narration: \"{narration}\"")
        self.lbl_narration.setWordWrap(True)
        self.lbl_narration.setStyleSheet("color: #a1a1a6; font-size: 12px; background: transparent;")
        right_col.addWidget(self.lbl_narration)

        # What appears on screen (Plain English editable description)
        lbl_vis_hint = QLabel("SCENE ACTION & PROMPT")
        lbl_vis_hint.setProperty("class", "eyebrow")
        lbl_vis_hint.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 10px; font-weight: 600; letter-spacing: 1.2px; background: transparent;")
        right_col.addWidget(lbl_vis_hint)

        self.txt_prompt = QPlainTextEdit()
        display_prompt = self.scene_data.get("action_desc") or self.scene_data.get("prompt", "")
        self.txt_prompt.setPlainText(display_prompt)
        self.txt_prompt.setFixedHeight(50)
        self.txt_prompt.setPlaceholderText("Describe visual action and camera movement...")
        self.txt_prompt.textChanged.connect(self._on_prompt_changed)
        right_col.addWidget(self.txt_prompt)

        layout.addLayout(right_col, stretch=1)

    def _update_badge(self):
        has_hash = bool(self.scene_data.get("scene_hash"))
        eff_mode = self.scene_data.get("effective_mode", "keyframe")
        self.lbl_badge.setProperty("class", "mono")
        if has_hash:
            label = "AI Video" if eff_mode == "omni_video" else "Keyframe"
            self.lbl_badge.setText(f"Ready ({label})")
            self.lbl_badge.setStyleSheet(
                "background-color: rgba(48, 209, 88, 0.12); color: #30D158; border: 1px solid rgba(48,209,88,0.28); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 600;"
            )
        else:
            self.lbl_badge.setText("Unrendered")
            self.lbl_badge.setStyleSheet(
                "background-color: rgba(245, 158, 11, 0.12); color: #f59e0b; border: 1px solid rgba(245,158,11,0.28); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 600;"
            )

    def refresh_thumbnail(self):
        img_path = self.scene_data.get("image_path", "")
        if not img_path and self.project_dir:
            for candidate in (
                os.path.join(self.project_dir, "storyboard", f"scene_{self.index + 1:02d}.png"),
                os.path.join(self.project_dir, f"scene_{self.index + 1:02d}.png"),
            ):
                if os.path.exists(candidate):
                    img_path = candidate
                    break
        if img_path and os.path.exists(img_path):
            pix = QPixmap(img_path)
            if not pix.isNull():
                scaled = pix.scaled(
                    self.lbl_thumb.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.lbl_thumb.setPixmap(scaled)
                self._update_badge()
                return
        self.lbl_thumb.setText(f"Scene {self.index + 1}\nPreview")
        self._update_badge()

    def _on_prompt_changed(self):
        new_action = self.txt_prompt.toPlainText().strip()
        if new_action != self.scene_data.get("action_desc", ""):
            self.scene_data["action_desc"] = new_action
            self.scene_data["prompt"] = new_action
            self.scene_data["omni_prompt"] = f"Single continuous vertical 9:16 shot: {new_action}. Smooth physical motion. No dialogue. No text."
            self.scene_data["user_edited"] = True
            self.scene_data["scene_hash"] = ""
            self._update_badge()
            self.scene_modified.emit(self.index, dict(self.scene_data))

    def _on_mode_changed(self):
        mode_val = self.combo_mode.currentData()
        self.scene_data["render_mode"] = mode_val
        if mode_val in ("keyframe", "omni_video"):
            self.scene_data["effective_mode"] = mode_val
        self.scene_data["user_edited"] = True
        self.scene_data["scene_hash"] = ""
        self._update_badge()
        self.scene_modified.emit(self.index, dict(self.scene_data))

    def _on_regenerate_clicked(self):
        self.scene_data["action_desc"] = self.txt_prompt.toPlainText().strip()
        self.scene_data["prompt"] = self.scene_data["action_desc"]
        self.scene_data["render_mode"] = self.combo_mode.currentData()
        self.scene_data["user_edited"] = True
        self.scene_data["scene_hash"] = ""
        self.regenerate_requested.emit(self.index, dict(self.scene_data))

    def get_scene_data(self) -> dict:
        action = self.txt_prompt.toPlainText().strip()
        if action:
            self.scene_data["action_desc"] = action
            if not self.scene_data.get("prompt"):
                self.scene_data["prompt"] = action
        self.scene_data["render_mode"] = self.combo_mode.currentData()
        return dict(self.scene_data)


class StoryboardInspectorWidget(QWidget):
    """Plain-English Scene-by-Scene Storyboard Inspector."""
    scenes_updated = Signal(list)
    regenerate_scene_requested = Signal(int, dict)
    auto_segment_requested = Signal()
    copy_prompts_requested = Signal()
    import_clips_requested = Signal()
    clear_scenes_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scenes: list[dict] = []
        self.cards: list[SceneCardWidget] = []
        self.project_dir: str = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.lbl_summary = QLabel("Scenes will appear here automatically once your script is written.")
        self.lbl_summary.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 12px; background: transparent;")
        toolbar.addWidget(self.lbl_summary)

        toolbar.addStretch()

        self.btn_add_scene = QPushButton("Add Scene")
        self.btn_add_scene.setProperty("class", "chip")
        self.btn_add_scene.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_add_scene.clicked.connect(self._add_empty_scene)
        toolbar.addWidget(self.btn_add_scene)

        self.btn_auto_segment = QPushButton("Sync from Script")
        self.btn_auto_segment.setProperty("class", "chip")
        self.btn_auto_segment.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_auto_segment.clicked.connect(self.auto_segment_requested.emit)
        toolbar.addWidget(self.btn_auto_segment)

        self.btn_copy_prompts = QPushButton("Copy Prompts")
        self.btn_copy_prompts.setProperty("class", "chip")
        self.btn_copy_prompts.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_copy_prompts.clicked.connect(self.copy_prompts_requested.emit)
        toolbar.addWidget(self.btn_copy_prompts)

        self.btn_import_clips = QPushButton("Import Clips")
        self.btn_import_clips.setProperty("class", "chip")
        self.btn_import_clips.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_import_clips.clicked.connect(self.import_clips_requested.emit)
        toolbar.addWidget(self.btn_import_clips)

        self.btn_clear_scenes = QPushButton("Clear All")
        self.btn_clear_scenes.setProperty("class", "chip")
        self.btn_clear_scenes.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_clear_scenes.setToolTip("Remove all scene cards and reset preview canvas")
        self.btn_clear_scenes.clicked.connect(self.clear_all_scenes)
        toolbar.addWidget(self.btn_clear_scenes)

        layout.addLayout(toolbar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 4, 0)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()

        self.scroll.setWidget(self.cards_container)
        layout.addWidget(self.scroll, stretch=1)

    def load_scenes(self, scenes: list[dict], project_dir: str = ""):
        self.scenes = [dict(s) for s in (scenes or [])]
        if project_dir:
            self.project_dir = project_dir

        for card in self.cards:
            card.deleteLater()
        self.cards.clear()

        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for idx, s_data in enumerate(self.scenes):
            card = SceneCardWidget(idx, s_data, self.project_dir, self)
            card.scene_modified.connect(self._on_card_modified)
            card.regenerate_requested.connect(self.regenerate_scene_requested.emit)
            card.delete_requested.connect(self.delete_scene)
            self.cards_layout.addWidget(card)
            self.cards.append(card)

        self.cards_layout.addStretch()
        self._update_summary()

    def delete_scene(self, idx: int):
        if 0 <= idx < len(self.scenes):
            self.scenes.pop(idx)
            # Re-index remaining scenes & recalculate start/end timestamps
            t_acc = 0.0
            for i, sc in enumerate(self.scenes):
                dur = float(sc.get("duration", 7.5))
                sc["scene_idx"] = i
                sc["start_time"] = round(t_acc, 2)
                sc["end_time"] = round(t_acc + dur, 2)
                t_acc += dur
            self.load_scenes(self.scenes, self.project_dir)
            self.scenes_updated.emit(self.get_scenes())

    def _add_empty_scene(self):
        new_idx = len(self.scenes)
        last_end = float(self.scenes[-1].get("end_time", 0.0)) if self.scenes else 0.0
        new_scene = {
            "scene_idx": new_idx,
            "start_time": round(last_end, 2),
            "end_time": round(last_end + 7.5, 2),
            "duration": 7.5,
            "script_excerpt": "",
            "action_desc": "New visual beat: detailed 3D cutaway showing internal mechanism",
            "prompt": "New visual beat: detailed 3D cutaway showing internal mechanism",
            "render_mode": "auto",
            "effective_mode": "keyframe",
            "image_path": "",
            "video_clip_path": "",
            "scene_hash": "",
        }
        self.scenes.append(new_scene)
        self.load_scenes(self.scenes, self.project_dir)
        self.scenes_updated.emit(self.get_scenes())

    def clear_all_scenes(self):
        self.scenes = []
        self.load_scenes([], self.project_dir)
        self.clear_scenes_requested.emit()
        self.scenes_updated.emit([])

    def _on_card_modified(self, idx: int, updated_scene: dict):
        if 0 <= idx < len(self.scenes):
            self.scenes[idx] = updated_scene
            self._update_summary()
            self.scenes_updated.emit(self.get_scenes())

    def update_single_scene(self, idx: int, updated_scene: dict):
        if 0 <= idx < len(self.scenes):
            self.scenes[idx] = dict(updated_scene)
        if 0 <= idx < len(self.cards):
            self.cards[idx].scene_data = dict(updated_scene)
            self.cards[idx].refresh_thumbnail()
        self._update_summary()

    def _update_summary(self):
        total = len(self.scenes)
        if total == 0:
            self.lbl_summary.setText("Scenes will appear here automatically once your script is written.")
            return
        cached = sum(1 for s in self.scenes if s.get("scene_hash"))
        self.lbl_summary.setText(
            f"{total} Visual Scenes  •  {cached} of {total} already cached (unchanged scenes won't use extra credits)"
        )

    def get_scenes(self) -> list[dict]:
        if self.cards:
            self.scenes = [c.get_scene_data() for c in self.cards]
        return [dict(s) for s in self.scenes]

    def apply_visual_revision(self, instruction: str) -> list[int]:
        instruction = (instruction or "").strip()
        if not instruction:
            return []

        current_scenes = self.get_scenes()
        if not current_scenes:
            return []

        targeted = [int(m) - 1 for m in re.findall(r"scene\s*(\d+)", instruction, flags=re.IGNORECASE)]
        targeted = [idx for idx in targeted if 0 <= idx < len(current_scenes)]
        if not targeted:
            targeted = list(range(len(current_scenes)))

        for idx in targeted:
            base_action = (current_scenes[idx].get("action_desc") or current_scenes[idx].get("prompt") or "").strip()
            rev_tag = f" [Visual Revision: {instruction}]"
            if rev_tag not in base_action:
                updated_action = (base_action + rev_tag).strip()
                current_scenes[idx]["action_desc"] = updated_action
                current_scenes[idx]["prompt"] = updated_action
            current_scenes[idx]["revision_note"] = instruction
            current_scenes[idx]["user_edited"] = True
            current_scenes[idx]["scene_hash"] = ""

        self.load_scenes(current_scenes, self.project_dir)
        self.scenes_updated.emit(self.get_scenes())
        return targeted
