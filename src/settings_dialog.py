import os
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.detector import resolve_model_path
from src.i18n import (
    LANGUAGE_NAMES,
    SUPPORTED_LANGUAGES,
    SYSTEM_LANGUAGE_PREF,
    I18nManager,
    get_i18n,
)
from src.win_shell import FONT_FAMILY_CSS, load_bundled_pretendard_fonts


class SettingsDialog(QDialog):
    """
    표시 언어(자동 시스템 언어 감지 + 8개 다국어 선택) 및 기본 실행 옵션을 변경하는 설정 대화상자.
    콤보박스에서 언어를 변경하는 즉시 앱 전체 UI가 실시간 재번역되며 설정 파일에 영구 저장된다.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        i18n: Optional[I18nManager] = None,
        on_preferences_changed: Optional[Callable[[bool, bool], None]] = None,
    ):
        super().__init__(parent)
        self.i18n: I18nManager = i18n or get_i18n()
        self._on_preferences_changed = on_preferences_changed
        self._updating_controls: bool = False

        self.setModal(True)
        self.setMinimumSize(540, 440)
        self.resize(580, 470)

        icon_path = resolve_model_path("assets/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._apply_styles()
        self._build_ui()
        self.retranslate_ui()
        self.i18n.subscribe(self._on_language_changed)

    def closeEvent(self, event: QCloseEvent):
        self.i18n.unsubscribe(self._on_language_changed)
        super().closeEvent(event)

    def done(self, result: int):
        self.i18n.unsubscribe(self._on_language_changed)
        super().done(result)

    def _apply_styles(self):
        load_bundled_pretendard_fonts()
        check_svg = resolve_model_path("assets/check.svg").replace("\\", "/")
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: #F1F5F9;
                color: #0F172A;
                font-family: {FONT_FAMILY_CSS};
                font-size: 18px;
                font-weight: 500;
            }}
            QFrame#settingsCard {{
                background-color: #FFFFFF;
                border: 1px solid #B8C4D4;
                border-radius: 10px;
            }}
            QLabel {{
                color: #0F172A;
                background-color: transparent;
            }}
            QLabel#cardTitle {{
                color: #1E40AF;
                font-size: 19px;
                font-weight: 700;
            }}
            QFrame#cardDivider {{
                background-color: #CBD5E1;
                border: none;
                max-height: 1px;
                min-height: 1px;
            }}
            QComboBox {{
                background-color: #FFFFFF;
                border: 1px solid #64748B;
                border-radius: 8px;
                padding: 7px 12px;
                font-size: 18px;
                font-weight: 600;
                color: #0F172A;
                min-height: 26px;
            }}
            QComboBox:hover {{
                border-color: #2563EB;
                background-color: #F8FAFC;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 28px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #FFFFFF;
                border: 1px solid #94A3B8;
                selection-background-color: #DBEAFE;
                selection-color: #1E3A8A;
                color: #0F172A;
                font-size: 18px;
                padding: 4px;
            }}
            QCheckBox {{
                font-size: 18px;
                font-weight: 600;
                spacing: 8px;
                color: #0F172A;
                background-color: transparent;
            }}
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 5px;
                border: 2px solid #475569;
                background-color: #FFFFFF;
            }}
            QCheckBox::indicator:hover {{
                border-color: #2563EB;
            }}
            QCheckBox::indicator:checked {{
                border: 2px solid #2563EB;
                background-color: #2563EB;
                image: url("{check_svg}");
            }}
            QPushButton {{
                background-color: #FFFFFF;
                border: 1px solid #64748B;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 18px;
                font-weight: 700;
                color: #0F172A;
            }}
            QPushButton:hover {{
                background-color: #EFF6FF;
                border-color: #2563EB;
                color: #1D4ED8;
            }}
            QPushButton#primaryCloseBtn {{
                background-color: #2563EB;
                border-color: #1D4ED8;
                color: #FFFFFF;
                min-width: 110px;
            }}
            QPushButton#primaryCloseBtn:hover {{
                background-color: #1D4ED8;
                color: #FFFFFF;
            }}
            """
        )

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(14)

        # 상단 타이틀 영역
        header_col = QVBoxLayout()
        header_col.setSpacing(4)
        self.lbl_header_title = QLabel(self)
        self.lbl_header_title.setStyleSheet("font-size: 23px; font-weight: 700; color: #1E40AF;")
        self.lbl_header_subtitle = QLabel(self)
        self.lbl_header_subtitle.setStyleSheet("font-size: 17px; font-weight: 500; color: #334155;")
        self.lbl_header_subtitle.setWordWrap(True)
        header_col.addWidget(self.lbl_header_title)
        header_col.addWidget(self.lbl_header_subtitle)
        outer.addLayout(header_col)

        # 1. 언어 설정 카드
        lang_card = QFrame(self)
        lang_card.setObjectName("settingsCard")
        lang_layout = QVBoxLayout(lang_card)
        lang_layout.setContentsMargins(16, 14, 16, 14)
        lang_layout.setSpacing(10)

        self.lbl_lang_group = QLabel(lang_card)
        self.lbl_lang_group.setObjectName("cardTitle")
        lang_layout.addWidget(self.lbl_lang_group)

        div1 = QFrame(lang_card)
        div1.setObjectName("cardDivider")
        div1.setFrameShape(QFrame.Shape.HLine)
        lang_layout.addWidget(div1)

        lang_row = QHBoxLayout()
        lang_row.setSpacing(12)
        self.lbl_lang_label = QLabel(lang_card)
        self.lbl_lang_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #0F172A;")

        self.combo_language = QComboBox(lang_card)
        self.combo_language.setCursor(Qt.CursorShape.PointingHandCursor)
        self._populate_language_combo()
        self.combo_language.currentIndexChanged.connect(self._on_combo_changed)

        lang_row.addWidget(self.lbl_lang_label)
        lang_row.addWidget(self.combo_language, stretch=1)
        lang_layout.addLayout(lang_row)

        self.lbl_lang_desc = QLabel(lang_card)
        self.lbl_lang_desc.setStyleSheet("font-size: 16px; font-weight: 500; color: #334155;")
        self.lbl_lang_desc.setWordWrap(True)
        lang_layout.addWidget(self.lbl_lang_desc)

        self.lbl_detected_system = QLabel(lang_card)
        self.lbl_detected_system.setStyleSheet("font-size: 16px; font-weight: 600; color: #1D4ED8;")
        self.lbl_detected_system.setWordWrap(True)
        lang_layout.addWidget(self.lbl_detected_system)

        outer.addWidget(lang_card)

        # 2. 기본 실행 옵션 카드
        defaults_card = QFrame(self)
        defaults_card.setObjectName("settingsCard")
        defaults_layout = QVBoxLayout(defaults_card)
        defaults_layout.setContentsMargins(16, 14, 16, 14)
        defaults_layout.setSpacing(10)

        self.lbl_defaults_group = QLabel(defaults_card)
        self.lbl_defaults_group.setObjectName("cardTitle")
        defaults_layout.addWidget(self.lbl_defaults_group)

        div2 = QFrame(defaults_card)
        div2.setObjectName("cardDivider")
        div2.setFrameShape(QFrame.Shape.HLine)
        defaults_layout.addWidget(div2)

        self.chk_default_guides = QCheckBox(defaults_card)
        self.chk_default_guides.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_default_guides.setChecked(self.i18n.store.default_show_guides)
        self.chk_default_guides.toggled.connect(self._on_default_prefs_toggled)
        defaults_layout.addWidget(self.chk_default_guides)

        self.chk_default_strip_meta = QCheckBox(defaults_card)
        self.chk_default_strip_meta.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_default_strip_meta.setChecked(self.i18n.store.default_strip_metadata)
        self.chk_default_strip_meta.toggled.connect(self._on_default_prefs_toggled)
        defaults_layout.addWidget(self.chk_default_strip_meta)

        outer.addWidget(defaults_card)
        outer.addStretch(1)

        # 하단 버튼 바
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_reset = QPushButton(self)
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self._on_reset_clicked)

        self.btn_close = QPushButton(self)
        self.btn_close.setObjectName("primaryCloseBtn")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_reset)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_close)
        outer.addLayout(btn_row)

    def _populate_language_combo(self):
        self._updating_controls = True
        try:
            self.combo_language.clear()
            detected_name = self.i18n.detected_system_language_name()
            self.combo_language.addItem(
                self.i18n.tr("lang.auto_option", detected=detected_name),
                SYSTEM_LANGUAGE_PREF,
            )
            for code in SUPPORTED_LANGUAGES:
                self.combo_language.addItem(LANGUAGE_NAMES[code], code)

            pref = self.i18n.language_preference
            idx = self.combo_language.findData(pref)
            self.combo_language.setCurrentIndex(max(0, idx))
        finally:
            self._updating_controls = False

    def _on_combo_changed(self, index: int):
        if self._updating_controls or index < 0:
            return
        pref = self.combo_language.itemData(index)
        if isinstance(pref, str):
            self.i18n.set_language(pref, persist=True)

    def _on_default_prefs_toggled(self, _checked: bool):
        if self._updating_controls:
            return
        guides = self.chk_default_guides.isChecked()
        strip_meta = self.chk_default_strip_meta.isChecked()
        self.i18n.store.default_show_guides = guides
        self.i18n.store.default_strip_metadata = strip_meta
        if self._on_preferences_changed is not None:
            self._on_preferences_changed(guides, strip_meta)

    def _on_reset_clicked(self):
        self._updating_controls = True
        try:
            self.i18n.store.reset_defaults()
            self.chk_default_guides.setChecked(True)
            self.chk_default_strip_meta.setChecked(True)
        finally:
            self._updating_controls = False

        self.i18n.set_language(SYSTEM_LANGUAGE_PREF, persist=True)
        self.retranslate_ui()
        if self._on_preferences_changed is not None:
            self._on_preferences_changed(True, True)

    def _on_language_changed(self, _lang: str):
        self.retranslate_ui()

    def retranslate_ui(self):
        t = self.i18n.tr
        detected_name = self.i18n.detected_system_language_name()

        self.setWindowTitle(t("settings.window_title"))
        self.lbl_header_title.setText(f"⚙️ {t('settings.header_title')}")
        self.lbl_header_subtitle.setText(t("settings.header_subtitle"))

        self.lbl_lang_group.setText(t("settings.lang_group"))
        self.lbl_lang_label.setText(t("settings.lang_label"))
        self.lbl_lang_desc.setText(t("settings.lang_desc"))
        self.lbl_detected_system.setText(t("settings.detected_system", detected=detected_name))

        self.lbl_defaults_group.setText(t("settings.defaults_group"))
        self.chk_default_guides.setText(t("settings.default_guides"))
        self.chk_default_strip_meta.setText(t("settings.default_strip_meta"))

        self.btn_reset.setText(t("settings.reset_btn"))
        self.btn_close.setText(t("dialog.close"))

        self._updating_controls = True
        try:
            if self.combo_language.count() > 0:
                self.combo_language.setItemText(
                    0, t("lang.auto_option", detected=detected_name)
                )
            idx = self.combo_language.findData(self.i18n.language_preference)
            if idx >= 0:
                self.combo_language.setCurrentIndex(idx)
        finally:
            self._updating_controls = False
