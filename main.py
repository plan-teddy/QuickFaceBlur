import os
import sys
from typing import List, Optional

# Windows 150% 등 고배율 및 텍스트 확대 설정 시 폰트가 과도하게 커져 깨지는 현상 방지
if sys.platform == "win32":
    os.environ.setdefault("QT_FONT_DPI", "96")

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QFileOpenEvent, QGuiApplication
from PySide6.QtWidgets import QApplication

from src.canvas_widget import SUPPORTED_EXTENSIONS
from src.detector import resolve_model_path
from src.i18n import get_i18n
from src.main_window import MainWindow
from src.win_shell import (
    APP_USER_MODEL_ID,
    apply_app_icon,
    configure_light_theme_and_font,
    init_windows_app_id,
)


class QuickFaceBlurApplication(QApplication):
    """macOS Dock 아이콘 드롭 및 Finder '다음으로 열기(Open With)' 이벤트를 수신하는 QApplication."""

    def __init__(self, argv: List[str]):
        super().__init__(argv)
        self.main_window: Optional[MainWindow] = None
        self.pending_files: List[str] = []

    def event(self, ev: QEvent) -> bool:
        if ev.type() == QEvent.Type.FileOpen and isinstance(ev, QFileOpenEvent):
            local_file = ev.file()
            if local_file and os.path.isfile(local_file):
                if self.main_window is not None:
                    self.main_window.load_images_from_paths([local_file])
                else:
                    self.pending_files.append(local_file)
                return True
        return super().event(ev)


def resolve_app_icon_path() -> str:
    if sys.platform == "darwin":
        icns = resolve_model_path("assets/icon.icns")
        if os.path.exists(icns):
            return icns
    return resolve_model_path("assets/icon.ico")


def configure_high_dpi_and_windows_shell(display_name: str):
    """
    Windows 10/11 환경의 High-DPI(125%, 150%, 200% 배율) 대응 및
    작업 표시줄(Taskbar) 고유 AppUserModelID + 아이콘 레지스트리 등록을 수행한다.
    """
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    icon_path = resolve_model_path("assets/icon.ico")
    init_windows_app_id(
        icon_path=icon_path,
        app_id=APP_USER_MODEL_ID,
        display_name=display_name,
    )


def _extract_cli_image_args(argv: List[str]) -> List[str]:
    paths: List[str] = []
    for arg in argv[1:]:
        if arg.startswith("-"):
            continue
        if os.path.isfile(arg) and os.path.splitext(arg)[1].lower() in SUPPORTED_EXTENSIONS:
            paths.append(os.path.abspath(arg))
    return paths


def main():
    if "--uninstall" in sys.argv:
        from src.installer_gui import run_uninstaller_main
        run_uninstaller_main()
        return

    i18n = get_i18n()
    configure_high_dpi_and_windows_shell(i18n.tr("app.display_name"))
    app = QuickFaceBlurApplication(sys.argv)
    i18n.refresh_from_system()

    app.setApplicationName("QuickFaceBlur")
    app.setApplicationDisplayName(i18n.tr("app.display_name"))
    app.setOrganizationName("QuickFaceBlur")

    # 밝은 테마(Light Theme) 및 Pretendard 19px(+3px 확대) 기본 폰트 전역 적용
    configure_light_theme_and_font(app, pixel_size=19)

    icon_path = resolve_app_icon_path()
    apply_app_icon(app, icon_path)

    if "--smoke-test" in sys.argv or os.environ.get("QFB_SMOKE_TEST") == "1":
        import numpy as np
        from src.detector import SCRFDDetector
        from src.renderer import apply_face_blurs

        det = SCRFDDetector()
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        regions = det.detect(dummy, conf_thresh=0.2)
        _ = apply_face_blurs(dummy, regions)
        window = MainWindow(detector=det)
        window.show()
        app.processEvents()
        window.close()
        if sys.stdout is not None:
            print("SMOKE_TEST_OK")
        sys.exit(0)

    window = MainWindow()
    app.main_window = window
    window.show()

    initial_files = _extract_cli_image_args(sys.argv) + list(app.pending_files)
    app.pending_files.clear()
    if initial_files:
        QTimer.singleShot(80, lambda: window.load_images_from_paths(initial_files))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
