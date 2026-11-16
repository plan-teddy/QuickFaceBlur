from dataclasses import dataclass, field
import io
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QIcon,
    QImage,
    QKeySequence,
    QPixmap,
    QShortcut,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from src.canvas_widget import (
    FaceBlurCanvasWidget,
    extract_image_paths_from_mimedata,
)
from src.detector import SCRFDDetector, resolve_model_path
from src.i18n import (
    LANGUAGE_NAMES,
    SUPPORTED_LANGUAGES,
    SYSTEM_LANGUAGE_PREF,
    I18nManager,
    get_i18n,
    tr,
)
from src.models import FaceRegion
from src.renderer import apply_face_blurs
from src.settings_dialog import SettingsDialog
from src.win_shell import (
    APP_DISPLAY_NAME,
    APP_SHORT_NAME,
    APP_USER_MODEL_ID,
    FONT_FAMILY_CSS,
    apply_app_icon,
    apply_window_taskbar_icon,
    create_windows_shortcut,
    load_bundled_pretendard_fonts,
    notify_shell_icon_cache_updated,
)

MAX_PREVIEW_SIDE = 1280


@dataclass
class PhotoEntry:
    file_path: str
    orig_img_bgr: np.ndarray
    preview_img_bgr: np.ndarray
    exif_bytes: Optional[bytes] = None
    regions: List[FaceRegion] = field(default_factory=list)
    detect_ms: float = 0.0


def load_image_with_metadata(file_path: str) -> Tuple[np.ndarray, Optional[bytes]]:
    """
    스마트폰 EXIF 회전 태그(Orientation)를 자동 보정하고,
    Windows 한글 경로에서도 안전하게 BGR 이미지와 정규화된 EXIF 바이트를 반환한다.
    """
    try:
        with Image.open(file_path) as pil_img:
            transposed = ImageOps.exif_transpose(pil_img)
            exif_bytes: Optional[bytes] = None
            try:
                exif_obj = transposed.getexif()
                if exif_obj:
                    exif_obj[0x0112] = 1
                    exif_bytes = exif_obj.tobytes()
            except Exception:
                exif_bytes = None

            rgb_img = transposed.convert("RGB")
            arr_rgb = np.array(rgb_img, dtype=np.uint8)
            return cv2.cvtColor(arr_rgb, cv2.COLOR_RGB2BGR), exif_bytes
    except Exception:
        raw = np.fromfile(file_path, dtype=np.uint8)
        img_bgr = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise ValueError(tr("error.cannot_read_image", path=file_path))
        return img_bgr, None


def load_image_safe(file_path: str) -> np.ndarray:
    """하위 호환용 단일 BGR 배열 반환 로더."""
    img_bgr, _ = load_image_with_metadata(file_path)
    return img_bgr


def save_image_safe(
    file_path: str,
    img_bgr: np.ndarray,
    jpeg_quality: int = 95,
    strip_metadata: bool = True,
    exif_bytes: Optional[bytes] = None,
) -> bool:
    """
    Windows 한글 폴더/파일명 경로에서도 깨짐 없이 고화질로 저장한다.
    - strip_metadata=True 인 경우: EXIF/GPS 등 모든 메타데이터를 제거하고 순수 픽셀만 저장한다.
    - strip_metadata=False 인 경우: 원본 EXIF 메타데이터(회전 보정됨)를 보존하여 저장한다.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if not ext:
        ext = ".jpg"
        file_path += ext

    if not strip_metadata and exif_bytes and ext in (".jpg", ".jpeg", ".webp", ".png"):
        try:
            rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil_out = Image.fromarray(rgb)
            buf = io.BytesIO()
            fmt = "JPEG" if ext in (".jpg", ".jpeg") else ext.lstrip(".").upper()
            save_kwargs = {"exif": exif_bytes}
            if fmt in ("JPEG", "WEBP"):
                save_kwargs["quality"] = int(jpeg_quality)
            pil_out.save(buf, format=fmt, **save_kwargs)
            np.frombuffer(buf.getvalue(), dtype=np.uint8).tofile(file_path)
            return True
        except Exception:
            pass

    encode_params = []
    if ext in (".jpg", ".jpeg"):
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)]
    elif ext == ".webp":
        encode_params = [int(cv2.IMWRITE_WEBP_QUALITY), int(jpeg_quality)]
    elif ext == ".png":
        encode_params = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]

    # cv2.imencode는 순수 픽셀만 인코딩하므로 EXIF/GPS 메타데이터가 100% 제거됨
    success, encoded_img = cv2.imencode(ext, img_bgr, encode_params)
    if not success:
        return False
    encoded_img.tofile(file_path)
    return True


def make_thumbnail_icon(img_bgr: np.ndarray, thumb_w: int = 48, thumb_h: int = 36) -> QIcon:
    """좌측 사진 목록에 표시할 밝은 테마용 비율 유지 썸네일 아이콘(48x36)을 생성한다."""
    h, w = img_bgr.shape[:2]
    scale = min(thumb_w / max(w, 1), thumb_h / max(h, 1))
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    small = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_AREA)

    # 밝은 테마에 어울리는 연한 슬레이트 배경(RGB 236, 240, 245)
    canvas = np.full((thumb_h, thumb_w, 3), 240, dtype=np.uint8)
    y0 = (thumb_h - nh) // 2
    x0 = (thumb_w - nw) // 2
    canvas[y0 : y0 + nh, x0 : x0 + nw] = small

    rgb = np.ascontiguousarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    qimg = QImage(rgb.data, thumb_w, thumb_h, 3 * thumb_w, QImage.Format.Format_RGB888).copy()
    return QIcon(QPixmap.fromImage(qimg))


class SectionCard(QFrame):
    """
    QGroupBox의 타이틀-테두리 겹침 문제를 원천 차단하는 밝은 테마 전용 카드 컨테이너.
    상단 타이틀 라벨 + 구분선 + 내부 컨텐츠 레이아웃이 수직으로 분리되어
    어떠한 배율이나 폰트 크기에서도 타이틀과 하위 요소가 절대 겹치지 않는다.
    """

    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("sectionCard")

        self._card_layout = QVBoxLayout(self)
        self._card_layout.setContentsMargins(16, 12, 16, 14)
        self._card_layout.setSpacing(8)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("sectionTitleLabel")
        self._card_layout.addWidget(self.title_label)

        self.divider = QFrame(self)
        self.divider.setObjectName("sectionDivider")
        self.divider.setFrameShape(QFrame.Shape.HLine)
        self.divider.setFixedHeight(1)
        self._card_layout.addWidget(self.divider)

        self.body_widget = QWidget(self)
        self.body_widget.setObjectName("sectionBody")
        self.body_layout = QVBoxLayout(self.body_widget)
        self.body_layout.setContentsMargins(0, 4, 0, 0)
        self.body_layout.setSpacing(10)
        self._card_layout.addWidget(self.body_widget, stretch=1)

    def setTitle(self, title: str):
        self.title_label.setText(title)

    def title(self) -> str:
        return self.title_label.text()


class DropPhotoListWidget(QListWidget):
    """드래그 앤 드롭으로 사진을 추가할 수 있는 컴팩트 좌측 썸네일 목록 위젯."""

    filesDropped = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setIconSize(QSize(48, 36))
        self.setSpacing(4)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    def dragEnterEvent(self, event: QDragEnterEvent):
        paths = extract_image_paths_from_mimedata(event.mimeData())
        if paths:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        paths = extract_image_paths_from_mimedata(event.mimeData())
        if paths:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        paths = extract_image_paths_from_mimedata(event.mimeData())
        if paths:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            self.filesDropped.emit(paths)
        else:
            event.ignore()


class MainWindow(QMainWindow):
    def __init__(
        self,
        detector: Optional[SCRFDDetector] = None,
        i18n: Optional[I18nManager] = None,
    ):
        super().__init__()
        self.i18n: I18nManager = i18n or get_i18n()
        self._updating_lang_combo: bool = False
        self._status_state: Tuple[str, dict] = ("status.empty", {})

        self.setWindowTitle(self.i18n.tr("app.display_name"))

        self.icon_path = resolve_model_path("assets/icon.ico")
        if os.path.exists(self.icon_path):
            app_inst = QApplication.instance()
            if isinstance(app_inst, QApplication):
                apply_app_icon(app_inst, self.icon_path)
            self.setWindowIcon(QIcon(self.icon_path))

        # 14인치 150% 배율(논리 해상도 1280x720)에서도 창을 줄여 스크롤할 수 있도록 최소 크기 유지(640x440)
        self.setMinimumSize(640, 440)
        self.setAcceptDrops(True)

        self.detector: Optional[SCRFDDetector] = detector

        # 다중 사진 목록 상태 및 현재 선택된 사진 상태
        self.photo_entries: List[PhotoEntry] = []
        self.current_index: int = -1
        self._switching_photo: bool = False

        self.current_file_path: Optional[str] = None
        self.orig_img_bgr: Optional[np.ndarray] = None
        self.preview_img_bgr: Optional[np.ndarray] = None
        self.current_exif_bytes: Optional[bytes] = None
        self.regions: List[FaceRegion] = []
        self.last_detect_ms: float = 0.0

        # 컨트롤 파라미터 기본값 (SPEC 3.1 + 메타데이터 제거 옵션 + 사용자 기본 설정 반영)
        self.blur_mode: str = "bokeh"        # "bokeh" or "mosaic"
        self.blur_strength: float = 0.60     # 10% ~ 100% (기본 60%)
        self.mask_scale: float = 1.15        # 80% ~ 150% (기본 115%)
        self.conf_threshold: float = 0.35    # 0.20 ~ 0.80 (기본 0.35)
        self.show_guides: bool = self.i18n.store.default_show_guides
        self.strip_metadata: bool = self.i18n.store.default_strip_metadata

        self.tray_icon: Optional[QSystemTrayIcon] = None
        self.act_tray_show: Optional[QAction] = None
        self.act_tray_open: Optional[QAction] = None
        self.act_tray_settings: Optional[QAction] = None
        self.act_tray_quit: Optional[QAction] = None

        self._apply_global_styles()
        self._build_ui()
        self._setup_system_tray()
        self.retranslate_ui()
        self.i18n.subscribe(self._on_language_changed)
        self._apply_initial_screen_fit()

        # 클립보드 복사 단축키 (Ctrl+C)
        self.shortcut_copy = QShortcut(QKeySequence.StandardKey.Copy, self)
        self.shortcut_copy.activated.connect(self.copy_result_to_clipboard)

        if self.detector is None:
            QTimer.singleShot(50, self._init_detector_with_progress)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if os.path.exists(self.icon_path):
            apply_window_taskbar_icon(
                self,
                self.icon_path,
                app_id=APP_USER_MODEL_ID,
                display_name=self.i18n.tr("app.display_name"),
            )

    def closeEvent(self, event: QCloseEvent):
        self.i18n.unsubscribe(self._on_language_changed)
        if self.tray_icon is not None:
            self.tray_icon.hide()
        super().closeEvent(event)

    def _setup_system_tray(self):
        """작업 표시줄 우측 시스템 트레이(알림 영역)에도 앱 아이콘과 빠른 메뉴를 표시한다."""
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        if not os.path.exists(self.icon_path):
            return

        tray = QSystemTrayIcon(QIcon(self.icon_path), self)
        tray.setToolTip(self.i18n.tr("app.display_name"))

        menu = QMenu(self)
        self.act_tray_show = QAction(self.i18n.tr("tray.open_window"), self)
        self.act_tray_show.triggered.connect(self._restore_from_tray)
        self.act_tray_open = QAction(self.i18n.tr("tray.open_photos"), self)
        self.act_tray_open.triggered.connect(self.open_image_dialog)
        self.act_tray_settings = QAction(self.i18n.tr("tray.settings"), self)
        self.act_tray_settings.triggered.connect(self.open_settings_dialog)
        self.act_tray_quit = QAction(self.i18n.tr("tray.quit"), self)
        self.act_tray_quit.triggered.connect(self.close)

        menu.addAction(self.act_tray_show)
        menu.addAction(self.act_tray_open)
        menu.addAction(self.act_tray_settings)
        menu.addSeparator()
        menu.addAction(self.act_tray_quit)

        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        self.tray_icon = tray

    def _restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_from_tray()

    def _apply_initial_screen_fit(self):
        """
        14인치 150% 배율(논리 작업 영역 약 1280x672) 등 소형 화면에서도
        창 하단 영역이 작업 표시줄 아래로 잘리지 않도록 화면 크기에 맞춰 초기 창 크기를 설정한다.
        """
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            target_w = min(1280, max(820, int(avail.width() * 0.95)))
            target_h = min(820, max(540, int(avail.height() * 0.94)))
            self.resize(target_w, target_h)
            x = avail.x() + max(0, (avail.width() - target_w) // 2)
            y = avail.y() + max(0, (avail.height() - target_h) // 2)
            self.move(x, y)
        else:
            self.resize(1240, 760)

    def _apply_global_styles(self):
        """
        밝은 테마(Light Theme) 전용 스타일시트 및 Pretendard 폰트(+3px 추가 확대, 고대비 가독성 강화)를 적용한다.
        """
        load_bundled_pretendard_fonts()
        check_svg = resolve_model_path("assets/check.svg").replace("\\", "/")
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background-color: #F1F5F9;
                color: #0F172A;
            }}
            QWidget {{
                font-family: {FONT_FAMILY_CSS};
                font-size: 19px;
                font-weight: 500;
                color: #0F172A;
            }}
            QScrollArea {{
                background-color: #F1F5F9;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: #F1F5F9;
            }}
            QScrollBar:vertical {{
                background: #E2E8F0;
                width: 12px;
                margin: 0px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: #94A3B8;
                min-height: 28px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #64748B;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background: #E2E8F0;
                height: 12px;
                margin: 0px;
                border-radius: 6px;
            }}
            QScrollBar::handle:horizontal {{
                background: #94A3B8;
                min-width: 28px;
                border-radius: 6px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: #64748B;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QDialog, QMessageBox, QProgressDialog {{
                background-color: #FFFFFF;
                color: #0F172A;
            }}
            QMessageBox QLabel {{
                color: #0F172A;
                font-size: 20px;
                font-weight: 600;
                min-width: 340px;
            }}
            QMessageBox QPushButton {{
                background-color: #2563EB;
                border: 1px solid #1D4ED8;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 19px;
                font-weight: 700;
                color: #FFFFFF;
                min-width: 96px;
            }}
            QMessageBox QPushButton:hover {{
                background-color: #1D4ED8;
            }}
            QFrame#topBar, QFrame#footerBar {{
                background-color: #FFFFFF;
                border: 1px solid #B8C4D4;
                border-radius: 10px;
            }}
            QFrame#sectionCard {{
                background-color: #FFFFFF;
                border: 1px solid #B8C4D4;
                border-radius: 10px;
            }}
            QFrame#sectionBody, QWidget#sectionBody {{
                background-color: transparent;
                border: none;
            }}
            QLabel#sectionTitleLabel {{
                color: #1E40AF;
                font-size: 19px;
                font-weight: 700;
                background-color: transparent;
                border: none;
                padding: 0px 2px;
            }}
            QFrame#sectionDivider {{
                background-color: #CBD5E1;
                border: none;
                max-height: 1px;
                min-height: 1px;
            }}
            QListWidget {{
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding: 4px;
                font-size: 17px;
                font-weight: 600;
                color: #0F172A;
            }}
            QListWidget::item {{
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 5px;
                margin-bottom: 4px;
                color: #0F172A;
            }}
            QListWidget::item:selected {{
                background-color: #DBEAFE;
                border: 2px solid #2563EB;
                color: #1E3A8A;
                font-weight: 700;
            }}
            QListWidget::item:hover {{
                background-color: #EFF6FF;
                border: 1px solid #60A5FA;
            }}
            QPushButton {{
                background-color: #FFFFFF;
                border: 1px solid #64748B;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 19px;
                font-weight: 700;
                color: #0F172A;
            }}
            QPushButton:hover {{
                background-color: #EFF6FF;
                border-color: #2563EB;
                color: #1D4ED8;
            }}
            QPushButton:pressed {{
                background-color: #DBEAFE;
            }}
            QPushButton:disabled {{
                background-color: #F1F5F9;
                color: #64748B;
                border-color: #CBD5E1;
            }}
            QPushButton#openButton {{
                background-color: #2563EB;
                border-color: #1D4ED8;
                color: #FFFFFF;
            }}
            QPushButton#openButton:hover {{
                background-color: #1D4ED8;
                color: #FFFFFF;
            }}
            QPushButton#copyButton {{
                background-color: #7C3AED;
                border-color: #6D28D9;
                color: #FFFFFF;
            }}
            QPushButton#copyButton:hover {{
                background-color: #6D28D9;
                color: #FFFFFF;
            }}
            QPushButton#copyButton:disabled {{
                background-color: #F1F5F9;
                border-color: #CBD5E1;
                color: #64748B;
            }}
            QPushButton#saveButton {{
                background-color: #16A34A;
                border-color: #15803D;
                padding: 6px 14px;
                color: #FFFFFF;
            }}
            QPushButton#saveButton:hover {{
                background-color: #15803D;
                color: #FFFFFF;
            }}
            QPushButton#saveButton:disabled {{
                background-color: #F1F5F9;
                border-color: #CBD5E1;
                color: #64748B;
            }}
            QPushButton#batchSaveButton {{
                background-color: #0D9488;
                border-color: #0F766E;
                color: #FFFFFF;
            }}
            QPushButton#batchSaveButton:hover {{
                background-color: #0F766E;
                color: #FFFFFF;
            }}
            QPushButton#batchSaveButton:disabled {{
                background-color: #F1F5F9;
                border-color: #CBD5E1;
                color: #64748B;
            }}
            QCheckBox, QRadioButton {{
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
            QRadioButton::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 11px;
                border: 2px solid #475569;
                background-color: #FFFFFF;
            }}
            QRadioButton::indicator:hover {{
                border-color: #2563EB;
            }}
            QRadioButton::indicator:checked {{
                border: 2px solid #2563EB;
                background-color: qradialgradient(
                    cx:0.5, cy:0.5, radius:0.45,
                    fx:0.5, fy:0.5,
                    stop:0 #2563EB, stop:0.55 #2563EB,
                    stop:0.60 #FFFFFF, stop:1.0 #FFFFFF
                );
            }}
            QSlider::groove:horizontal {{
                border: 1px solid #94A3B8;
                height: 8px;
                background: #CBD5E1;
                border-radius: 4px;
            }}
            QSlider::sub-page:horizontal {{
                background: #2563EB;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: #FFFFFF;
                border: 2px solid #2563EB;
                width: 19px;
                height: 19px;
                margin: -6px 0;
                border-radius: 10px;
            }}
            QSlider::handle:horizontal:hover {{
                background: #EFF6FF;
                border-color: #1D4ED8;
            }}
            QMenu {{
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                padding: 4px;
                font-size: 18px;
                font-weight: 600;
                color: #0F172A;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: #EFF6FF;
                color: #1D4ED8;
            }}
            QFrame#topBar QPushButton {{
                padding: 5px 7px;
                font-size: 16px;
            }}
            QFrame#topBar QCheckBox {{
                font-size: 16px;
            }}
            QPushButton#settingsButton {{
                background-color: #F8FAFC;
                border-color: #64748B;
                color: #0F172A;
            }}
            QPushButton#settingsButton:hover {{
                background-color: #EFF6FF;
                border-color: #2563EB;
                color: #1D4ED8;
            }}
            QComboBox {{
                background-color: #FFFFFF;
                border: 1px solid #64748B;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 17px;
                font-weight: 600;
                color: #0F172A;
                min-height: 24px;
            }}
            QComboBox:hover {{
                border-color: #2563EB;
                background-color: #F8FAFC;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #FFFFFF;
                border: 1px solid #94A3B8;
                selection-background-color: #DBEAFE;
                selection-color: #1E3A8A;
                color: #0F172A;
                font-size: 17px;
                padding: 4px;
            }}
            """
        )

    def _build_ui(self):
        # 바깥 래퍼(centralWidget) -> 하단 상태바 및 내부 QScrollArea 배치
        central = QWidget(self)
        central.setAcceptDrops(True)
        self.setCentralWidget(central)

        outer_layout = QVBoxLayout(central)
        # 하단 상태바(38px) + 여백을 합쳐 썸네일 영역이 창 하단으로부터 50px 이상 버퍼를 확보하도록 구성
        outer_layout.setContentsMargins(10, 8, 10, 10)
        outer_layout.setSpacing(6)

        # 창을 작게 줄였을 때 가로/세로 스크롤바가 자동으로 나타나도록 QScrollArea 구성
        self.main_scroll_area = QScrollArea(self)
        self.main_scroll_area.setWidgetResizable(True)
        self.main_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.main_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.main_scroll_area.setAcceptDrops(True)

        scroll_content = QWidget()
        scroll_content.setAcceptDrops(True)
        # 내부 컨텐츠 최소 크기 설정 -> 이 크기보다 창을 작게 줄이면 가로/세로 스크롤바 생성
        scroll_content.setMinimumSize(1020, 440)
        self.main_scroll_area.setWidget(scroll_content)

        root_layout = QVBoxLayout(scroll_content)
        root_layout.setContentsMargins(2, 2, 2, 2)
        root_layout.setSpacing(6)

        # --- 1. 상단 툴바 (Top Bar) ---
        top_bar = QFrame(scroll_content)
        top_bar.setObjectName("topBar")
        self.top_bar = top_bar
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 6, 8, 6)
        top_layout.setSpacing(6)

        self.btn_open = QPushButton()
        self.btn_open.setObjectName("openButton")
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open.clicked.connect(self.open_image_dialog)

        self.btn_all_on = QPushButton()
        self.btn_all_on.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_all_on.setEnabled(False)
        self.btn_all_on.clicked.connect(self._on_btn_all_on_clicked)

        self.btn_all_off = QPushButton()
        self.btn_all_off.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_all_off.setEnabled(False)
        self.btn_all_off.clicked.connect(self._on_btn_all_off_clicked)

        self.chk_guides = QCheckBox()
        self.chk_guides.setChecked(self.show_guides)
        self.chk_guides.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_guides.toggled.connect(self._on_guides_toggled)

        self.btn_copy_clipboard = QPushButton()
        self.btn_copy_clipboard.setObjectName("copyButton")
        self.btn_copy_clipboard.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_clipboard.setEnabled(False)
        self.btn_copy_clipboard.clicked.connect(self.copy_result_to_clipboard)

        self.btn_save = QPushButton()
        self.btn_save.setObjectName("saveButton")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_image_dialog)

        self.btn_batch_save = QPushButton()
        self.btn_batch_save.setObjectName("batchSaveButton")
        self.btn_batch_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_batch_save.setEnabled(False)
        self.btn_batch_save.clicked.connect(self.save_all_images_dialog)

        self.btn_settings = QPushButton()
        self.btn_settings.setObjectName("settingsButton")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.clicked.connect(self.open_settings_dialog)

        top_layout.addWidget(self.btn_open)
        top_layout.addWidget(self.btn_all_on)
        top_layout.addWidget(self.btn_all_off)
        top_layout.addSpacing(4)
        top_layout.addWidget(self.chk_guides)
        top_layout.addStretch(1)
        top_layout.addWidget(self.btn_copy_clipboard)
        top_layout.addWidget(self.btn_save)
        top_layout.addWidget(self.btn_batch_save)
        top_layout.addWidget(self.btn_settings)
        root_layout.addWidget(top_bar)

        # --- 2. 중앙 영역 (좌측 썸네일 목록 + 중앙 캔버스 + 우측 컨트롤 패널) ---
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)

        # 2-A. 좌측 다중 사진 썸네일 목록 패널 (다국어 버튼이 1줄에 깔끔히 들어가도록 284px 폭 적용)
        left_col = QWidget(scroll_content)
        left_col.setFixedWidth(284)
        left_col_layout = QVBoxLayout(left_col)
        left_col_layout.setContentsMargins(0, 0, 0, 6)
        left_col_layout.setSpacing(0)

        left_group = SectionCard("", left_col)
        self.left_photo_group = left_group
        left_layout = left_group.body_layout

        self.photo_list = DropPhotoListWidget(left_group)
        self.photo_list.currentRowChanged.connect(self._on_photo_list_row_changed)
        self.photo_list.filesDropped.connect(self.load_images_from_paths)
        left_layout.addWidget(self.photo_list, stretch=1)

        list_btn_layout = QHBoxLayout()
        list_btn_layout.setSpacing(4)
        self.left_btn_layout = list_btn_layout

        self.btn_add_photos = QPushButton()
        self.btn_add_photos.setStyleSheet("font-size: 15px; font-weight: 700; padding: 5px 4px;")
        self.btn_add_photos.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_photos.clicked.connect(self.open_image_dialog)

        self.btn_remove_photo = QPushButton()
        self.btn_remove_photo.setStyleSheet("font-size: 15px; font-weight: 700; padding: 5px 4px;")
        self.btn_remove_photo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove_photo.setEnabled(False)
        self.btn_remove_photo.clicked.connect(self.remove_current_photo)

        self.btn_clear_photos = QPushButton()
        self.btn_clear_photos.setStyleSheet("font-size: 15px; font-weight: 700; padding: 5px 4px;")
        self.btn_clear_photos.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_photos.setEnabled(False)
        self.btn_clear_photos.clicked.connect(self.clear_all_photos)

        list_btn_layout.addWidget(self.btn_add_photos)
        list_btn_layout.addWidget(self.btn_remove_photo)
        list_btn_layout.addWidget(self.btn_clear_photos)
        left_layout.addLayout(list_btn_layout)

        left_col_layout.addWidget(left_group, stretch=1)
        body_layout.addWidget(left_col)

        # 2-B. 중앙 인터랙티브 프리뷰 캔버스
        self.canvas = FaceBlurCanvasWidget(scroll_content, i18n=self.i18n)
        self.canvas._show_guides = self.show_guides
        self.canvas.filesDropped.connect(self.load_images_from_paths)
        self.canvas.regionsChanged.connect(self._on_canvas_regions_changed)
        body_layout.addWidget(self.canvas, stretch=1)

        # 2-C. 우측 컨트롤 패널 (항목 간 간격을 넉넉히 벌려 가독성을 높이고, 소형 화면에서는 우측 패널만 독립 스크롤 지원)
        self.right_scroll_area = QScrollArea(scroll_content)
        self.right_scroll_area.setWidgetResizable(True)
        self.right_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.right_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.right_scroll_area.setFixedWidth(404)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 4, 4)
        right_layout.setSpacing(12)

        # (1) 블러 스타일 카드 (다국어 긴 문구도 잘리지 않도록 수직 배치)
        self.style_group = SectionCard("", right_panel)
        style_layout = self.style_group.body_layout
        style_layout.setSpacing(8)

        self.radio_bokeh = QRadioButton()
        self.radio_mosaic = QRadioButton()
        self.radio_bokeh.setChecked(True)

        self.style_btn_group = QButtonGroup(self)
        self.style_btn_group.addButton(self.radio_bokeh)
        self.style_btn_group.addButton(self.radio_mosaic)
        self.radio_bokeh.toggled.connect(self._on_style_changed)

        radio_col = QVBoxLayout()
        radio_col.setContentsMargins(2, 2, 2, 2)
        radio_col.setSpacing(8)
        radio_col.addWidget(self.radio_bokeh)
        radio_col.addWidget(self.radio_mosaic)
        style_layout.addLayout(radio_col)
        right_layout.addWidget(self.style_group)

        # (2) 세부 조절 슬라이더 카드 (각 슬라이더 블록 간 14px 간격으로 시각적 그룹화 강화)
        self.slider_group = SectionCard("", right_panel)
        slider_layout = self.slider_group.body_layout
        slider_layout.setSpacing(14)

        # (a) 블러 강도 슬라이더 (10% ~ 100%, 기본 60%)
        strength_block = QVBoxLayout()
        strength_block.setSpacing(6)
        strength_header = QHBoxLayout()
        self.lbl_strength_title = QLabel()
        self.lbl_strength_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #0F172A;")
        self.lbl_strength_val = QLabel("60%")
        self.lbl_strength_val.setStyleSheet("font-size: 18px; font-weight: 700; color: #1D4ED8;")
        strength_header.addWidget(self.lbl_strength_title)
        strength_header.addStretch(1)
        strength_header.addWidget(self.lbl_strength_val)

        self.slider_strength = QSlider(Qt.Orientation.Horizontal)
        self.slider_strength.setRange(10, 100)
        self.slider_strength.setValue(60)
        self.slider_strength.valueChanged.connect(self._on_strength_changed)

        strength_block.addLayout(strength_header)
        strength_block.addWidget(self.slider_strength)
        slider_layout.addLayout(strength_block)

        # (b) 영역 크기 슬라이더 (80% ~ 150%, 기본 115%)
        scale_block = QVBoxLayout()
        scale_block.setSpacing(6)
        scale_header = QHBoxLayout()
        self.lbl_scale_title = QLabel()
        self.lbl_scale_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #0F172A;")
        self.lbl_scale_val = QLabel("115%")
        self.lbl_scale_val.setStyleSheet("font-size: 18px; font-weight: 700; color: #1D4ED8;")
        scale_header.addWidget(self.lbl_scale_title)
        scale_header.addStretch(1)
        scale_header.addWidget(self.lbl_scale_val)

        self.slider_scale = QSlider(Qt.Orientation.Horizontal)
        self.slider_scale.setRange(80, 150)
        self.slider_scale.setValue(115)
        self.slider_scale.valueChanged.connect(self._on_scale_changed)

        scale_block.addLayout(scale_header)
        scale_block.addWidget(self.slider_scale)
        slider_layout.addLayout(scale_block)

        # (c) 얼굴 감지 민감도 슬라이더 (0.20 ~ 0.80, 기본 0.35)
        conf_block = QVBoxLayout()
        conf_block.setSpacing(6)
        conf_header = QHBoxLayout()
        self.lbl_conf_title = QLabel()
        self.lbl_conf_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #0F172A;")
        self.lbl_conf_val = QLabel("0.35")
        self.lbl_conf_val.setStyleSheet("font-size: 18px; font-weight: 700; color: #1D4ED8;")
        conf_header.addWidget(self.lbl_conf_title)
        conf_header.addStretch(1)
        conf_header.addWidget(self.lbl_conf_val)

        self.slider_conf = QSlider(Qt.Orientation.Horizontal)
        self.slider_conf.setRange(20, 80)
        self.slider_conf.setValue(35)
        self.slider_conf.valueChanged.connect(self._on_conf_changed)

        self.lbl_conf_hint = QLabel()
        self.lbl_conf_hint.setStyleSheet(
            "font-size: 17px; font-weight: 500; color: #1E293B; padding-top: 2px;"
        )
        self.lbl_conf_hint.setWordWrap(True)

        conf_block.addLayout(conf_header)
        conf_block.addWidget(self.slider_conf)
        conf_block.addWidget(self.lbl_conf_hint)
        slider_layout.addLayout(conf_block)
        right_layout.addWidget(self.slider_group)

        # (3) 개인정보 및 저장 옵션 카드 (메타데이터 제거 옵션)
        self.privacy_group = SectionCard("", right_panel)
        privacy_layout = self.privacy_group.body_layout
        privacy_layout.setSpacing(8)

        self.chk_strip_metadata = QCheckBox()
        self.chk_strip_metadata.setChecked(self.strip_metadata)
        self.chk_strip_metadata.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_strip_metadata.toggled.connect(self._on_strip_metadata_toggled)

        self.lbl_meta_hint = QLabel()
        self.lbl_meta_hint.setStyleSheet(
            "font-size: 17px; font-weight: 500; color: #1E293B; padding-left: 2px;"
        )
        self.lbl_meta_hint.setWordWrap(True)

        privacy_layout.addWidget(self.chk_strip_metadata)
        privacy_layout.addWidget(self.lbl_meta_hint)
        right_layout.addWidget(self.privacy_group)

        # (4) 수동 영역 관리 및 간편 조작 안내 카드 (줄 간격 및 버튼 간격 여유 확보)
        self.help_group = SectionCard("", right_panel)
        help_layout = self.help_group.body_layout
        help_layout.setSpacing(10)

        self.lbl_guide_text = QLabel()
        self.lbl_guide_text.setStyleSheet("font-size: 17px; font-weight: 500; color: #0F172A;")
        self.lbl_guide_text.setWordWrap(True)
        help_layout.addWidget(self.lbl_guide_text)

        self.btn_clear_manual = QPushButton()
        self.btn_clear_manual.setStyleSheet("font-size: 18px; font-weight: 700; padding: 7px 12px;")
        self.btn_clear_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_manual.setEnabled(False)
        self.btn_clear_manual.clicked.connect(self.clear_manual_regions)
        help_layout.addWidget(self.btn_clear_manual)

        # 하위 호환용 속성 유지 (화면에는 노출하지 않음)
        self.btn_create_shortcut = QPushButton()
        self.btn_create_shortcut.setVisible(False)
        self.btn_create_shortcut.clicked.connect(self.install_desktop_shortcut)

        right_layout.addWidget(self.help_group)

        # (5) 표시 언어 빠른 전환 카드 (상단 [⚙️ 설정] 대화상자와 실시간 동기화)
        self.lang_group = SectionCard("", right_panel)
        lang_layout = self.lang_group.body_layout
        lang_layout.setSpacing(8)

        self.combo_language = QComboBox(self.lang_group)
        self.combo_language.setCursor(Qt.CursorShape.PointingHandCursor)
        self._populate_quick_language_combo()
        self.combo_language.currentIndexChanged.connect(self._on_quick_language_changed)
        lang_layout.addWidget(self.combo_language)

        right_layout.addWidget(self.lang_group)
        right_layout.addStretch(1)

        self.right_scroll_area.setWidget(right_panel)
        body_layout.addWidget(self.right_scroll_area)
        root_layout.addLayout(body_layout, stretch=1)

        outer_layout.addWidget(self.main_scroll_area, stretch=1)

        # --- 3. 하단 안내 텍스트 영역 (잘림 방지를 위해 고정 공간 확보 및 줄바꿈 지원) ---
        footer_bar = QFrame(central)
        footer_bar.setObjectName("footerBar")
        footer_bar.setMinimumHeight(40)
        footer_layout = QHBoxLayout(footer_bar)
        footer_layout.setContentsMargins(14, 6, 14, 6)

        self.status_label = QLabel()
        self.status_label.setStyleSheet(
            "font-size: 18px; font-weight: 600; color: #0F172A; border: none;"
        )
        self.status_label.setWordWrap(True)
        footer_layout.addWidget(self.status_label, 1)

        outer_layout.addWidget(footer_bar)

    def _populate_quick_language_combo(self):
        self._updating_lang_combo = True
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
            self._updating_lang_combo = False

    def _on_quick_language_changed(self, index: int):
        if self._updating_lang_combo or index < 0:
            return
        pref = self.combo_language.itemData(index)
        if isinstance(pref, str):
            self.i18n.set_language(pref, persist=True)

    def set_language(self, preference: str, persist: bool = True):
        """프로그래밍 방식 또는 설정 UI에서 언어를 즉시 변경한다."""
        self.i18n.set_language(preference, persist=persist)

    def open_settings_dialog(self) -> SettingsDialog:
        dlg = SettingsDialog(
            self,
            i18n=self.i18n,
            on_preferences_changed=self._on_default_preferences_updated,
        )
        dlg.exec()
        return dlg

    def _on_default_preferences_updated(self, show_guides: bool, strip_metadata: bool):
        self.chk_guides.setChecked(show_guides)
        self.chk_strip_metadata.setChecked(strip_metadata)

    def _on_language_changed(self, _lang: str):
        self.retranslate_ui()

    def _set_status_state(self, state_key: str, **kwargs):
        self._status_state = (state_key, dict(kwargs))
        self._render_status_state()

    def _render_status_state(self):
        key, kwargs = self._status_state
        render_kwargs = dict(kwargs)
        if "stripped" in render_kwargs:
            stripped = bool(render_kwargs.pop("stripped"))
            render_kwargs["meta_msg"] = (
                self.i18n.tr("save.meta_stripped")
                if stripped
                else self.i18n.tr("save.meta_kept")
            )
        self.status_label.setText(self.i18n.tr(key, **render_kwargs))

    def retranslate_ui(self):
        """현재 선택된 언어에 맞춰 창 전체의 모든 텍스트, 툴팁, 목록 요약 및 상태바를 즉시 갱신한다."""
        t = self.i18n.tr
        display_name = t("app.display_name")
        self.setWindowTitle(display_name)
        app_inst = QApplication.instance()
        if isinstance(app_inst, QApplication):
            app_inst.setApplicationDisplayName(display_name)

        # 시스템 트레이 메뉴
        if self.tray_icon is not None:
            self.tray_icon.setToolTip(display_name)
        if self.act_tray_show is not None:
            self.act_tray_show.setText(t("tray.open_window"))
        if self.act_tray_open is not None:
            self.act_tray_open.setText(t("tray.open_photos"))
        if self.act_tray_settings is not None:
            self.act_tray_settings.setText(t("tray.settings"))
        if self.act_tray_quit is not None:
            self.act_tray_quit.setText(t("tray.quit"))

        # 상단 툴바
        self.btn_open.setText(t("toolbar.open"))
        self.btn_open.setToolTip(t("toolbar.open_tooltip"))
        self.btn_all_on.setText(t("toolbar.all_on"))
        self.btn_all_on.setToolTip(t("toolbar.all_on_tooltip"))
        self.btn_all_off.setText(t("toolbar.all_off"))
        self.btn_all_off.setToolTip(t("toolbar.all_off_tooltip"))
        self.chk_guides.setText(t("toolbar.guides"))
        self.chk_guides.setToolTip(t("toolbar.guides_tooltip"))
        self.btn_copy_clipboard.setText(t("toolbar.copy"))
        self.btn_copy_clipboard.setToolTip(t("toolbar.copy_tooltip"))
        self.btn_save.setText(t("toolbar.save"))
        self.btn_save.setToolTip(t("toolbar.save_tooltip"))
        self.btn_batch_save.setText(t("toolbar.save_all"))
        self.btn_batch_save.setToolTip(t("toolbar.save_all_tooltip"))
        self.btn_settings.setText(t("toolbar.settings"))
        self.btn_settings.setToolTip(t("toolbar.settings_tooltip"))

        # 좌측 사진 목록
        self._update_photo_list_header()
        self.btn_add_photos.setText(t("photos.add"))
        self.btn_add_photos.setToolTip(t("photos.add_tooltip"))
        self.btn_remove_photo.setText(t("photos.remove"))
        self.btn_remove_photo.setToolTip(t("photos.remove_tooltip"))
        self.btn_clear_photos.setText(t("photos.clear"))
        self.btn_clear_photos.setToolTip(t("photos.clear_tooltip"))
        self._refresh_all_list_item_labels()

        # 중앙 캔버스 플레이스홀더
        self.canvas.retranslate_ui()

        # 우측 컨트롤 패널
        self.style_group.setTitle(t("style.section_title"))
        self.radio_bokeh.setText(t("style.bokeh"))
        self.radio_mosaic.setText(t("style.mosaic"))

        self.slider_group.setTitle(t("slider.section_title"))
        self.lbl_strength_title.setText(t("slider.strength"))
        self.lbl_scale_title.setText(t("slider.scale"))
        self.lbl_conf_title.setText(t("slider.confidence"))
        self.lbl_conf_hint.setText(t("slider.confidence_hint"))

        self.privacy_group.setTitle(t("privacy.section_title"))
        self.chk_strip_metadata.setText(t("privacy.strip_metadata"))
        self.lbl_meta_hint.setText(t("privacy.strip_metadata_hint"))

        self.help_group.setTitle(t("guide.section_title"))
        self.lbl_guide_text.setText(t("guide.html"))
        self.btn_clear_manual.setText(t("guide.clear_manual"))
        self.btn_create_shortcut.setText(t("shortcut.install_btn"))

        self.lang_group.setTitle(t("lang.section_title"))
        self._updating_lang_combo = True
        try:
            detected_name = self.i18n.detected_system_language_name()
            if self.combo_language.count() > 0:
                self.combo_language.setItemText(
                    0, t("lang.auto_option", detected=detected_name)
                )
            idx = self.combo_language.findData(self.i18n.language_preference)
            if idx >= 0:
                self.combo_language.setCurrentIndex(idx)
        finally:
            self._updating_lang_combo = False

        # 하단 상태바
        self._render_status_state()

    def _show_completion_dialog(
        self,
        title: str,
        message: str,
        folder_to_open: Optional[str] = None,
    ):
        """
        밝은 테마에서 글씨가 선명하게 보이는 완료 알림 모달 대화상자를 표시한다.
        """
        t = self.i18n.tr
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        if os.path.exists(self.icon_path):
            msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setText(message)

        btn_ok = msg_box.addButton(t("dialog.ok"), QMessageBox.ButtonRole.AcceptRole)
        btn_open_dir = None
        if folder_to_open and os.path.exists(folder_to_open):
            btn_open_dir = msg_box.addButton(t("dialog.open_saved_folder"), QMessageBox.ButtonRole.ActionRole)

        msg_box.setDefaultButton(btn_ok)
        msg_box.raise_()
        msg_box.activateWindow()
        msg_box.exec()

        if btn_open_dir is not None and msg_box.clickedButton() == btn_open_dir:
            try:
                if sys.platform == "win32":
                    os.startfile(folder_to_open)  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", folder_to_open])
            except Exception:
                pass

    def _init_detector_with_progress(self):
        t = self.i18n.tr
        model_path = resolve_model_path("models/scrfd_2.5g_bnkps.onnx")
        progress_dlg: Optional[QProgressDialog] = None

        if not os.path.exists(model_path):
            progress_dlg = QProgressDialog(
                t("model.downloading_message"),
                None,
                0,
                100,
                self,
            )
            progress_dlg.setWindowTitle(t("model.downloading_title"))
            progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dlg.setMinimumDuration(0)
            progress_dlg.setValue(0)
            progress_dlg.show()
            QApplication.processEvents()

        def _on_progress(downloaded: int, total: int):
            if progress_dlg is not None and total > 0:
                pct = int(min(100, (downloaded * 100) // total))
                progress_dlg.setValue(pct)
                QApplication.processEvents()

        try:
            self.detector = SCRFDDetector(
                model_path="models/scrfd_2.5g_bnkps.onnx",
                progress_callback=_on_progress,
            )
            warmup = np.zeros((320, 320, 3), dtype=np.uint8)
            self.detector.detect(warmup, conf_thresh=0.5)
        except Exception as exc:
            if progress_dlg is not None:
                progress_dlg.close()
            QMessageBox.critical(
                self,
                t("model.init_failed_title"),
                t("model.init_failed_message", error=exc),
            )
            return
        finally:
            if progress_dlg is not None:
                progress_dlg.close()

    # --- 윈도우 전체 영역 드래그 앤 드롭 지원 (dragEnter + dragMove + drop) ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        paths = extract_image_paths_from_mimedata(event.mimeData())
        if paths:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        paths = extract_image_paths_from_mimedata(event.mimeData())
        if paths:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        paths = extract_image_paths_from_mimedata(event.mimeData())
        if paths:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            self.load_images_from_paths(paths)
        else:
            event.ignore()

    # --- 단일 및 다중 사진 로드 ---
    def open_image_dialog(self):
        t = self.i18n.tr
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            t("file_dialog.open_title"),
            "",
            t("file_dialog.open_filter"),
        )
        if file_paths:
            self.load_images_from_paths(file_paths)

    def load_image_from_path(self, file_path: str):
        """단일 파일 경로 로드 (기존 API 호환 및 단일 추가용)."""
        self.load_images_from_paths([file_path])

    def load_images_from_paths(self, file_paths: List[str]):
        """여러 장의 사진 파일을 목록에 추가하고 첫 번째 추가된 사진을 선택한다."""
        if not file_paths:
            return

        if self.detector is None:
            self._init_detector_with_progress()
            if self.detector is None:
                return

        first_added_idx: Optional[int] = None
        existing_map = {
            os.path.normcase(os.path.abspath(entry.file_path)): idx
            for idx, entry in enumerate(self.photo_entries)
        }

        for path in file_paths:
            norm_p = os.path.normcase(os.path.abspath(path))
            if norm_p in existing_map:
                if first_added_idx is None:
                    first_added_idx = existing_map[norm_p]
                continue

            try:
                orig_bgr, exif_bytes = load_image_with_metadata(path)
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    self.i18n.tr("error.open_failed_title"),
                    self.i18n.tr("error.open_failed_message", path=path, error=exc),
                )
                continue

            oh, ow = orig_bgr.shape[:2]
            max_side = max(oh, ow)
            if max_side > MAX_PREVIEW_SIDE:
                scale = float(MAX_PREVIEW_SIDE) / max_side
                pw = max(1, int(round(ow * scale)))
                ph = max(1, int(round(oh * scale)))
                preview_bgr = cv2.resize(orig_bgr, (pw, ph), interpolation=cv2.INTER_AREA)
            else:
                preview_bgr = orig_bgr.copy()

            t0 = time.perf_counter()
            detected_regions = self.detector.detect(preview_bgr, conf_thresh=0.2, nms_thresh=0.4)
            detect_ms = (time.perf_counter() - t0) * 1000.0

            entry = PhotoEntry(
                file_path=path,
                orig_img_bgr=orig_bgr,
                preview_img_bgr=preview_bgr,
                exif_bytes=exif_bytes,
                regions=detected_regions,
                detect_ms=detect_ms,
            )
            new_idx = len(self.photo_entries)
            self.photo_entries.append(entry)
            existing_map[norm_p] = new_idx

            item = QListWidgetItem(
                make_thumbnail_icon(preview_bgr),
                self._format_list_item_text(entry),
            )
            item.setToolTip(path)
            self.photo_list.addItem(item)

            if first_added_idx is None:
                first_added_idx = new_idx

        self._update_photo_list_header()

        if first_added_idx is not None:
            self.select_photo_index(first_added_idx)

    def _format_list_item_text(self, entry: PhotoEntry) -> str:
        name = os.path.basename(entry.file_path)
        if len(name) > 14:
            name = name[:12] + ".."
        active = [r for r in entry.regions if r.is_manual or r.score >= self.conf_threshold]
        blurred = sum(1 for r in active if r.is_blurred)
        summary = self.i18n.tr("photos.item_summary", total=len(active), blurred=blurred)
        return f"{name}\n{summary}"

    def _update_photo_list_header(self):
        count = len(self.photo_entries)
        self.left_photo_group.setTitle(self.i18n.tr("photos.section_title", count=count))
        has_photos = count > 0
        self.btn_remove_photo.setEnabled(has_photos)
        self.btn_clear_photos.setEnabled(has_photos)
        self.btn_all_on.setEnabled(has_photos)
        self.btn_all_off.setEnabled(has_photos)
        self.btn_copy_clipboard.setEnabled(has_photos)
        self.btn_save.setEnabled(has_photos)
        self.btn_batch_save.setEnabled(has_photos)

    def _refresh_all_list_item_labels(self):
        for idx, entry in enumerate(self.photo_entries):
            item = self.photo_list.item(idx)
            if item is not None:
                item.setText(self._format_list_item_text(entry))

    def select_photo_index(self, index: int):
        if index < 0 or index >= len(self.photo_entries):
            return
        self._switching_photo = True
        try:
            self.current_index = index
            self.photo_list.setCurrentRow(index)
            entry = self.photo_entries[index]
            self.current_file_path = entry.file_path
            self.orig_img_bgr = entry.orig_img_bgr
            self.preview_img_bgr = entry.preview_img_bgr
            self.current_exif_bytes = entry.exif_bytes
            self.regions = entry.regions
            self.last_detect_ms = entry.detect_ms
            self._update_photo_list_header()
            self.refresh_preview(reset_view=True)
        finally:
            self._switching_photo = False

    def _on_photo_list_row_changed(self, row: int):
        if self._switching_photo:
            return
        if 0 <= row < len(self.photo_entries):
            self.select_photo_index(row)

    def remove_current_photo(self):
        if self.current_index < 0 or self.current_index >= len(self.photo_entries):
            return
        idx = self.current_index
        self._switching_photo = True
        try:
            self.photo_entries.pop(idx)
            self.photo_list.takeItem(idx)
        finally:
            self._switching_photo = False

        if not self.photo_entries:
            self._reset_empty_state()
        else:
            next_idx = min(idx, len(self.photo_entries) - 1)
            self.select_photo_index(next_idx)

    def clear_all_photos(self):
        self._switching_photo = True
        try:
            self.photo_entries.clear()
            self.photo_list.clear()
        finally:
            self._switching_photo = False
        self._reset_empty_state()

    def _reset_empty_state(self):
        self.current_index = -1
        self.current_file_path = None
        self.orig_img_bgr = None
        self.preview_img_bgr = None
        self.current_exif_bytes = None
        self.regions = []
        self.canvas.clear_canvas()
        self._update_photo_list_header()
        self.btn_clear_manual.setEnabled(False)
        self._set_status_state("status.empty")

    def _sync_current_entry_regions(self):
        if 0 <= self.current_index < len(self.photo_entries):
            self.photo_entries[self.current_index].regions = self.regions
            item = self.photo_list.item(self.current_index)
            if item is not None:
                item.setText(self._format_list_item_text(self.photo_entries[self.current_index]))

    # --- 프리뷰 렌더링 및 상태바 업데이트 ---
    def refresh_preview(self, reset_view: bool = False):
        if self.preview_img_bgr is None:
            return

        self._sync_current_entry_regions()

        rendered = apply_face_blurs(
            img_bgr=self.preview_img_bgr,
            regions=self.regions,
            conf_threshold=self.conf_threshold,
            blur_strength=self.blur_strength,
            mask_scale=self.mask_scale,
            mode=self.blur_mode,
        )
        self.canvas.update_canvas(
            rendered_bgr=rendered,
            regions=self.regions,
            conf_threshold=self.conf_threshold,
            mask_scale=self.mask_scale,
            show_guides=self.show_guides,
            reset_view=reset_view,
        )
        self._update_status_and_buttons()

    def _update_status_and_buttons(self):
        if self.preview_img_bgr is not None:
            self.btn_all_on.setEnabled(True)
            self.btn_all_off.setEnabled(True)
            self.btn_copy_clipboard.setEnabled(True)
            self.btn_save.setEnabled(True)

        active_regions = [
            r for r in self.regions if r.is_manual or r.score >= self.conf_threshold
        ]
        manual_regions = [r for r in self.regions if r.is_manual]
        self.btn_clear_manual.setEnabled(len(manual_regions) > 0)

        total_count = len(active_regions)
        blurred_count = sum(1 for r in active_regions if r.is_blurred)

        if total_count == 0:
            self._set_status_state("status.no_faces")
        else:
            self._set_status_state(
                "status.faces_detected",
                total=total_count,
                blurred=blurred_count,
            )

    # --- UI 컨트롤 이벤트 핸들러 ---
    def _on_canvas_regions_changed(self):
        self.refresh_preview(reset_view=False)

    def _on_btn_all_on_clicked(self):
        self.set_all_blurs(True)

    def _on_btn_all_off_clicked(self):
        self.set_all_blurs(False)

    def set_all_blurs(self, enabled: bool):
        """현재 사진의 모든 검출/수동 영역의 블러를 일괄 켜거나 끈다."""
        if self.preview_img_bgr is None:
            return
        for reg in self.regions:
            reg.is_blurred = bool(enabled)
        self.refresh_preview(reset_view=False)

    def clear_manual_regions(self):
        if self.preview_img_bgr is None:
            return
        self.regions = [r for r in self.regions if not r.is_manual]
        if 0 <= self.current_index < len(self.photo_entries):
            self.photo_entries[self.current_index].regions = self.regions
        self.refresh_preview(reset_view=False)

    def _on_guides_toggled(self, checked: bool):
        self.show_guides = checked
        self.canvas._show_guides = checked
        self.canvas.redraw_guides()

    def _on_strip_metadata_toggled(self, checked: bool):
        self.strip_metadata = checked

    def _on_style_changed(self):
        self.blur_mode = "bokeh" if self.radio_bokeh.isChecked() else "mosaic"
        self.refresh_preview(reset_view=False)

    def _on_strength_changed(self, value: int):
        self.blur_strength = value / 100.0
        self.lbl_strength_val.setText(f"{value}%")
        self.refresh_preview(reset_view=False)

    def _on_scale_changed(self, value: int):
        self.mask_scale = value / 100.0
        self.lbl_scale_val.setText(f"{value}%")
        self.refresh_preview(reset_view=False)

    def _on_conf_changed(self, value: int):
        self.conf_threshold = value / 100.0
        self.lbl_conf_val.setText(f"{self.conf_threshold:.2f}")
        self._refresh_all_list_item_labels()
        self.refresh_preview(reset_view=False)

    # --- 클립보드에 고화질 결과 이미지 바로 복사 ---
    def copy_result_to_clipboard(self, show_dialog: bool = True) -> bool:
        if self.orig_img_bgr is None:
            return False

        full_res_blurred = apply_face_blurs(
            img_bgr=self.orig_img_bgr,
            regions=self.regions,
            conf_threshold=self.conf_threshold,
            blur_strength=self.blur_strength,
            mask_scale=self.mask_scale,
            mode=self.blur_mode,
        )
        h, w = full_res_blurred.shape[:2]
        rgb = np.ascontiguousarray(cv2.cvtColor(full_res_blurred, cv2.COLOR_BGR2RGB))
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()

        clipboard = QApplication.clipboard()
        clipboard.setImage(qimg)

        self._set_status_state("status.copied", w=w, h=h)
        if show_dialog:
            self._show_completion_dialog(
                self.i18n.tr("clipboard.done_title"),
                self.i18n.tr("clipboard.done_message"),
            )
        return True

    # --- 원본 해상도 고화질 저장 (단일 및 전체 일괄 저장) ---
    def save_image_dialog(self):
        if self.orig_img_bgr is None:
            return

        if self.current_file_path:
            p = Path(self.current_file_path)
            default_save_path = str(p.with_name(f"{p.stem}_blurred.jpg"))
        else:
            default_save_path = "photo_blurred.jpg"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.tr("file_dialog.save_title"),
            default_save_path,
            self.i18n.tr("file_dialog.save_filter"),
        )
        if not save_path:
            return

        self.save_to_path(save_path, show_dialog=True)

    def save_to_path(self, save_path: str, show_dialog: bool = False) -> bool:
        if self.orig_img_bgr is None:
            return False

        t = self.i18n.tr
        try:
            full_res_blurred = apply_face_blurs(
                img_bgr=self.orig_img_bgr,
                regions=self.regions,
                conf_threshold=self.conf_threshold,
                blur_strength=self.blur_strength,
                mask_scale=self.mask_scale,
                mode=self.blur_mode,
            )
            ok = save_image_safe(
                save_path,
                full_res_blurred,
                strip_metadata=self.strip_metadata,
                exif_bytes=self.current_exif_bytes,
            )
            if not ok:
                raise RuntimeError(t("error.encode_failed"))

            meta_msg = t("save.meta_stripped") if self.strip_metadata else t("save.meta_kept")
            self._set_status_state(
                "status.saved_single",
                stripped=self.strip_metadata,
                path=save_path,
            )
            if show_dialog:
                self._show_completion_dialog(
                    t("save.done_title"),
                    t("save.done_message", meta_msg=meta_msg, path=save_path),
                    folder_to_open=os.path.dirname(os.path.abspath(save_path)),
                )
            return True
        except Exception as exc:
            if show_dialog:
                QMessageBox.critical(
                    self,
                    t("save.failed_title"),
                    t("save.failed_message", error=exc),
                )
            return False

    def save_all_images_dialog(self):
        """목록에 로드된 모든 사진을 선택한 폴더에 `_blurred.jpg`로 일괄 저장한다."""
        if not self.photo_entries:
            return

        default_dir = (
            os.path.dirname(os.path.abspath(self.photo_entries[0].file_path))
            if self.photo_entries[0].file_path
            else ""
        )
        target_dir = QFileDialog.getExistingDirectory(
            self,
            self.i18n.tr("file_dialog.save_all_title", count=len(self.photo_entries)),
            default_dir,
        )
        if not target_dir:
            return

        saved_count = self.save_all_to_directory(target_dir, show_dialog=True)
        return saved_count

    def save_all_to_directory(self, target_dir: str, show_dialog: bool = False) -> int:
        os.makedirs(target_dir, exist_ok=True)
        saved_count = 0

        for entry in self.photo_entries:
            p = Path(entry.file_path)
            out_name = f"{p.stem}_blurred.jpg"
            out_path = os.path.join(target_dir, out_name)

            # 파일명 중복 방지
            counter = 1
            while os.path.exists(out_path) and os.path.abspath(out_path) == os.path.abspath(entry.file_path):
                out_path = os.path.join(target_dir, f"{p.stem}_blurred_{counter}.jpg")
                counter += 1

            full_res_blurred = apply_face_blurs(
                img_bgr=entry.orig_img_bgr,
                regions=entry.regions,
                conf_threshold=self.conf_threshold,
                blur_strength=self.blur_strength,
                mask_scale=self.mask_scale,
                mode=self.blur_mode,
            )
            if save_image_safe(
                out_path,
                full_res_blurred,
                strip_metadata=self.strip_metadata,
                exif_bytes=entry.exif_bytes,
            ):
                saved_count += 1

        t = self.i18n.tr
        meta_msg = t("save.meta_stripped") if self.strip_metadata else t("save.meta_kept")
        self._set_status_state(
            "status.saved_batch",
            count=saved_count,
            stripped=self.strip_metadata,
            dir=target_dir,
        )
        if show_dialog:
            self._show_completion_dialog(
                t("save_all.done_title"),
                t("save_all.done_message", count=saved_count, meta_msg=meta_msg, dir=target_dir),
                folder_to_open=target_dir,
            )
        return saved_count

    # --- 바탕화면 바로가기 설치 (호환용 메서드 유지) ---
    def install_desktop_shortcut(self):
        t = self.i18n.tr
        if sys.platform != "win32":
            self._show_completion_dialog(
                t("shortcut.win_only_title"),
                t("shortcut.win_only_message"),
            )
            return

        try:
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv and sys.argv[0] else __file__))
            target_exe = os.path.join(base_dir, "QuickFaceBlur.exe")
            if not os.path.exists(target_exe):
                target_exe = sys.executable

            app_short = t("app.short_name")
            app_display = t("app.display_name")
            icon_path = resolve_model_path("assets/icon.ico")
            desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            lnk_path = os.path.join(desktop_dir, f"{app_short}.lnk")
            create_windows_shortcut(
                target_exe=target_exe,
                working_dir=base_dir,
                shortcut_path=lnk_path,
                icon_path=icon_path,
                app_id=APP_USER_MODEL_ID,
                description=app_display,
            )
            notify_shell_icon_cache_updated()
            self._show_completion_dialog(
                t("shortcut.done_title"),
                t("shortcut.done_message", app_name=app_short),
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                t("shortcut.failed_title"),
                t("shortcut.failed_message", error=exc),
            )
