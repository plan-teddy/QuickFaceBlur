import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

os.environ.setdefault("QT_FONT_DPI", "96")

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication, QIcon, QPixmap, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from src.i18n import (
    LANGUAGE_NAMES,
    SUPPORTED_LANGUAGES,
    SYSTEM_LANGUAGE_PREF,
    I18nManager,
    get_i18n,
)
from src.win_shell import (
    APP_USER_MODEL_ID,
    FONT_FAMILY_CSS,
    INSTALLER_USER_MODEL_ID,
    apply_app_icon,
    apply_window_taskbar_icon,
    configure_light_theme_and_font,
    create_windows_shortcut,
    init_windows_app_id,
    load_bundled_pretendard_fonts,
    notify_shell_icon_cache_updated,
    register_aumid_in_registry,
    register_windows_uninstall_entry,
    unregister_windows_uninstall_entry,
)


def _get_windows_special_folder(folder_name: str) -> str:
    """PowerShell을 통해 OneDrive 리디렉션 등이 반영된 실제 Desktop / Programs 폴더 경로를 조회한다."""
    if sys.platform != "win32":
        return os.path.expanduser("~")
    try:
        res = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; [Environment]::GetFolderPath('{folder_name}')",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            creationflags=0x08000000,
        )
        out = res.stdout.strip()
        if out and os.path.exists(out):
            return out
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


class InstallerWizardDialog(QDialog):
    def __init__(self, source_dir: Path, i18n: Optional[I18nManager] = None):
        super().__init__()
        self.source_dir = source_dir
        self.i18n: I18nManager = i18n or get_i18n()
        self._updating_combo: bool = False
        self._status_key: str = "installer.status_ready"

        local_appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        self.install_dir = Path(local_appdata) / "Programs" / "QuickFaceBlur"

        self.setFixedSize(680, 490)
        self.icon_file = self.source_dir / "assets" / "icon.ico"
        if self.icon_file.exists():
            self.setWindowIcon(QIcon(str(self.icon_file)))

        load_bundled_pretendard_fonts()
        check_svg = str((self.source_dir / "assets" / "check.svg").resolve()).replace("\\", "/")
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: #F1F5F9;
                color: #0F172A;
                font-family: {FONT_FAMILY_CSS};
                font-size: 19px;
                font-weight: 500;
            }}
            QFrame#installerCard {{
                background-color: #FFFFFF;
                border: 1px solid #B8C4D4;
                border-radius: 12px;
            }}
            QLabel {{
                color: #0F172A;
                background-color: transparent;
            }}
            QComboBox {{
                background-color: #FFFFFF;
                border: 1px solid #64748B;
                border-radius: 8px;
                padding: 5px 10px;
                font-size: 16px;
                font-weight: 600;
                color: #0F172A;
                min-width: 150px;
            }}
            QComboBox:hover {{
                border-color: #2563EB;
            }}
            QCheckBox {{
                font-size: 18px;
                font-weight: 600;
                color: #0F172A;
                spacing: 10px;
                background-color: transparent;
            }}
            QCheckBox::indicator {{
                width: 21px;
                height: 21px;
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
            QProgressBar {{
                border: 1px solid #94A3B8;
                border-radius: 7px;
                background-color: #E2E8F0;
                text-align: center;
                color: #0F172A;
                font-size: 18px;
                font-weight: 700;
                height: 28px;
            }}
            QProgressBar::chunk {{
                background-color: #2563EB;
                border-radius: 6px;
            }}
            QPushButton {{
                background-color: #16A34A;
                border: 1px solid #15803D;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 20px;
                font-weight: 700;
                color: #FFFFFF;
            }}
            QPushButton:hover {{
                background-color: #15803D;
            }}
            QPushButton:disabled {{
                background-color: #E2E8F0;
                border-color: #CBD5E1;
                color: #64748B;
            }}
            QPushButton#cancelBtn {{
                background-color: #FFFFFF;
                border: 1px solid #64748B;
                font-size: 19px;
                font-weight: 700;
                color: #0F172A;
            }}
            QPushButton#cancelBtn:hover {{
                background-color: #EFF6FF;
                border-color: #2563EB;
                color: #1D4ED8;
            }}
            """
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(14)

        # 상단 헤더 영역 (아이콘 + 타이틀 + 언어 선택)
        header_row = QHBoxLayout()
        header_row.setSpacing(14)
        if self.icon_file.exists():
            icon_lbl = QLabel(self)
            pix = QPixmap(str(self.icon_file)).scaled(
                48,
                48,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon_lbl.setPixmap(pix)
            icon_lbl.setFixedSize(52, 52)
            header_row.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        self.lbl_title = QLabel()
        self.lbl_title.setStyleSheet("font-size: 23px; font-weight: 700; color: #1E40AF;")
        self.lbl_subtitle = QLabel()
        self.lbl_subtitle.setStyleSheet("font-size: 17px; font-weight: 600; color: #1E293B;")
        title_col.addWidget(self.lbl_title)
        title_col.addWidget(self.lbl_subtitle)
        header_row.addLayout(title_col, 1)

        self.combo_language = QComboBox(self)
        self.combo_language.setCursor(Qt.CursorShape.PointingHandCursor)
        self._populate_language_combo()
        self.combo_language.currentIndexChanged.connect(self._on_language_combo_changed)
        header_row.addWidget(self.combo_language, 0, Qt.AlignmentFlag.AlignTop)

        outer.addLayout(header_row)

        # 본문 흰색 카드 영역
        card = QFrame(self)
        card.setObjectName("installerCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        self.lbl_desc = QLabel()
        self.lbl_desc.setStyleSheet("font-size: 18px; color: #1E293B; font-weight: 600;")
        self.lbl_desc.setWordWrap(True)
        card_layout.addWidget(self.lbl_desc)

        self.chk_desktop = QCheckBox()
        self.chk_desktop.setChecked(True)
        card_layout.addWidget(self.chk_desktop)

        self.chk_startmenu = QCheckBox()
        self.chk_startmenu.setChecked(True)
        card_layout.addWidget(self.chk_startmenu)

        self.chk_launch = QCheckBox()
        self.chk_launch.setChecked(True)
        card_layout.addWidget(self.chk_launch)

        card_layout.addStretch(1)

        self.progress = QProgressBar(card)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        card_layout.addWidget(self.progress)

        self.status_lbl = QLabel()
        self.status_lbl.setStyleSheet("font-size: 18px; font-weight: 600; color: #1E293B;")
        self.status_lbl.setWordWrap(True)
        card_layout.addWidget(self.status_lbl)

        outer.addWidget(card, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.btn_cancel = QPushButton()
        self.btn_cancel.setObjectName("cancelBtn")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_install = QPushButton()
        self.btn_install.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_install.clicked.connect(self.run_install)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_install)
        outer.addLayout(btn_row)

        self.retranslate_ui()
        self.i18n.subscribe(self._on_language_changed)

    def closeEvent(self, event: QCloseEvent):
        self.i18n.unsubscribe(self._on_language_changed)
        super().closeEvent(event)

    def _populate_language_combo(self):
        self._updating_combo = True
        try:
            self.combo_language.clear()
            detected_name = self.i18n.detected_system_language_name()
            self.combo_language.addItem(
                self.i18n.tr("lang.auto_option", detected=detected_name),
                SYSTEM_LANGUAGE_PREF,
            )
            for code in SUPPORTED_LANGUAGES:
                self.combo_language.addItem(LANGUAGE_NAMES[code], code)
            idx = self.combo_language.findData(self.i18n.language_preference)
            self.combo_language.setCurrentIndex(max(0, idx))
        finally:
            self._updating_combo = False

    def _on_language_combo_changed(self, index: int):
        if self._updating_combo or index < 0:
            return
        pref = self.combo_language.itemData(index)
        if isinstance(pref, str):
            self.i18n.set_language(pref, persist=True)

    def _on_language_changed(self, _lang: str):
        self.retranslate_ui()

    def retranslate_ui(self):
        t = self.i18n.tr
        app_short = t("app.short_name")
        detected_name = self.i18n.detected_system_language_name()

        self.setWindowTitle(t("installer.window_title"))
        self.lbl_title.setText(t("installer.header_title"))
        self.lbl_subtitle.setText(t("installer.header_subtitle"))
        self.lbl_desc.setText(t("installer.install_path", install_dir=self.install_dir))
        self.chk_desktop.setText(t("installer.chk_desktop", app_name=app_short))
        self.chk_startmenu.setText(t("installer.chk_startmenu"))
        self.chk_launch.setText(t("installer.chk_launch"))
        self.status_lbl.setText(t(self._status_key))
        self.btn_cancel.setText(t("dialog.cancel"))
        self.btn_install.setText(t("installer.btn_install"))

        self._updating_combo = True
        try:
            if self.combo_language.count() > 0:
                self.combo_language.setItemText(
                    0, t("lang.auto_option", detected=detected_name)
                )
            idx = self.combo_language.findData(self.i18n.language_preference)
            if idx >= 0:
                self.combo_language.setCurrentIndex(idx)
        finally:
            self._updating_combo = False

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if self.icon_file.exists():
            apply_window_taskbar_icon(
                self,
                str(self.icon_file),
                app_id=INSTALLER_USER_MODEL_ID,
                display_name=self.i18n.tr("installer.header_title"),
            )

    def run_install(self):
        t = self.i18n.tr
        self.btn_install.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.combo_language.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(5)
        self._status_key = "installer.status_copying"
        self.status_lbl.setText(t(self._status_key))
        QApplication.processEvents()

        try:
            if self.source_dir.resolve() != self.install_dir.resolve():
                self.install_dir.mkdir(parents=True, exist_ok=True)
                items = [
                    p
                    for p in self.source_dir.iterdir()
                    if "설치" not in p.name
                ]
                total = max(1, len(items))
                for idx, item in enumerate(items):
                    dest = self.install_dir / item.name
                    if item.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest, ignore_errors=True)
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)
                    pct = 10 + int(((idx + 1) / total) * 65)
                    self.progress.setValue(pct)
                    QApplication.processEvents()
            else:
                self.progress.setValue(75)

            target_exe = str(self.install_dir / "QuickFaceBlur.exe")
            icon_path = str(self.install_dir / "assets" / "icon.ico")
            created_shortcut: Optional[str] = None
            app_short = t("app.short_name")
            app_display = t("app.display_name")

            if sys.platform == "win32":
                self._status_key = "installer.status_registering"
                self.status_lbl.setText(t(self._status_key))
                QApplication.processEvents()

                # 1. 작업 표시줄 아이콘용 AppUserModelID 레지스트리 등록
                register_aumid_in_registry(
                    app_id=APP_USER_MODEL_ID,
                    display_name=app_display,
                    icon_path=icon_path,
                )

                # 2. Windows [설정 -> 앱 -> 설치된 앱] 정식 등록
                register_windows_uninstall_entry(
                    install_dir=str(self.install_dir),
                    target_exe=target_exe,
                    icon_path=icon_path,
                )

                # 3. 시작 메뉴 바로가기 생성 (AppUserModel.ID 및 IconLocation 각인)
                if self.chk_startmenu.isChecked():
                    programs_dir = _get_windows_special_folder("Programs")
                    start_lnk = os.path.join(programs_dir, f"{app_short}.lnk")
                    create_windows_shortcut(
                        target_exe=target_exe,
                        working_dir=str(self.install_dir),
                        shortcut_path=start_lnk,
                        icon_path=icon_path,
                        app_id=APP_USER_MODEL_ID,
                        description=app_display,
                    )
                    created_shortcut = start_lnk

                # 4. 바탕화면 바로가기 생성 (AppUserModel.ID 및 IconLocation 각인)
                if self.chk_desktop.isChecked():
                    desktop_dir = _get_windows_special_folder("Desktop")
                    desktop_lnk = os.path.join(desktop_dir, f"{app_short}.lnk")
                    create_windows_shortcut(
                        target_exe=target_exe,
                        working_dir=str(self.install_dir),
                        shortcut_path=desktop_lnk,
                        icon_path=icon_path,
                        app_id=APP_USER_MODEL_ID,
                        description=app_display,
                    )
                    created_shortcut = desktop_lnk

                # 5. Windows 탐색기 아이콘 캐시 즉시 새로고침
                notify_shell_icon_cache_updated()

            self.progress.setValue(100)
            self._status_key = "installer.status_done"
            self.status_lbl.setText(t(self._status_key))
            QApplication.processEvents()

            msg = QMessageBox(self)
            msg.setWindowTitle(t("installer.done_title"))
            if os.path.exists(icon_path):
                msg.setWindowIcon(QIcon(icon_path))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(t("installer.done_message", app_name=app_short))
            msg.addButton(t("dialog.ok"), QMessageBox.ButtonRole.AcceptRole)
            msg.exec()

            if self.chk_launch.isChecked() and os.path.exists(target_exe):
                if sys.platform == "win32" and created_shortcut and os.path.exists(created_shortcut):
                    try:
                        os.startfile(created_shortcut)  # type: ignore[attr-defined]
                    except Exception:
                        subprocess.Popen([target_exe], cwd=str(self.install_dir))
                else:
                    subprocess.Popen([target_exe], cwd=str(self.install_dir))

            self.accept()
        except Exception as exc:
            QMessageBox.critical(
                self,
                t("installer.failed_title"),
                t("installer.failed_message", error=exc),
            )
            self.btn_install.setEnabled(True)
            self.btn_cancel.setEnabled(True)
            self.combo_language.setEnabled(True)


def run_uninstaller_main():
    """Windows [설치된 앱]에서 제거 실행 시 바로가기와 레지스트리를 정리한다."""
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    i18n = get_i18n()
    i18n.refresh_from_system()
    configure_light_theme_and_font(app, pixel_size=19)

    if sys.platform == "win32":
        candidate_names = {
            "QuickFaceBlur.lnk",
            "QuickFaceBlur (자동 얼굴 블러).lnk",
            f"{i18n.tr('app.short_name')}.lnk",
        }
        for folder_key in ("Desktop", "Programs"):
            folder = _get_windows_special_folder(folder_key)
            for lnk_name in candidate_names:
                lnk = os.path.join(folder, lnk_name)
                if os.path.exists(lnk):
                    try:
                        os.remove(lnk)
                    except OSError:
                        pass
        unregister_windows_uninstall_entry()
        notify_shell_icon_cache_updated()

    QMessageBox.information(
        None,
        i18n.tr("uninstaller.done_title"),
        i18n.tr("uninstaller.done_message"),
    )
    sys.exit(0)


def run_installer_main():
    os.environ.setdefault("QT_FONT_DPI", "96")
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    base_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent
    icon_file = base_dir / "assets" / "icon.ico"
    i18n = get_i18n()
    init_windows_app_id(
        icon_path=str(icon_file) if icon_file.exists() else None,
        app_id=INSTALLER_USER_MODEL_ID,
        display_name=i18n.tr("installer.header_title"),
    )

    app = QApplication(sys.argv)
    i18n.refresh_from_system()
    configure_light_theme_and_font(app, pixel_size=19)
    if icon_file.exists():
        apply_app_icon(app, str(icon_file))

    dlg = InstallerWizardDialog(source_dir=base_dir, i18n=i18n)
    if os.environ.get("QFB_INSTALLER_SMOKE_TEST") == "1":
        dlg.show()
        app.processEvents()
        dlg.close()
        sys.exit(0)
    dlg.show()
    sys.exit(app.exec())
