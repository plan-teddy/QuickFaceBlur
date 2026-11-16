import math
import os
from typing import List, Optional

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QSizePolicy,
    QWidget,
)

from src.i18n import I18nManager, get_i18n
from src.models import FaceRegion
from src.renderer import get_ellipse_geometry, hit_test_ellipse
from src.win_shell import FONT_FALLBACK_FAMILIES, load_bundled_pretendard_fonts

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def extract_image_paths_from_mimedata(mime_data) -> List[str]:
    """
    드래그 앤 드롭된 QMimeData에서 유효한 이미지 파일 경로 목록을 추출한다.
    폴더가 드롭된 경우 폴더 내부의 이미지 파일들도 함께 수집한다.
    """
    if not mime_data.hasUrls():
        return []

    collected: List[str] = []
    for url in mime_data.urls():
        local_path = url.toLocalFile()
        if not local_path:
            continue
        if os.path.isdir(local_path):
            for root, _, files in os.walk(local_path):
                for fname in sorted(files):
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in SUPPORTED_EXTENSIONS:
                        collected.append(os.path.join(root, fname))
        elif os.path.isfile(local_path):
            ext = os.path.splitext(local_path)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                collected.append(local_path)

    # 중복 제거 (순서 유지)
    seen = set()
    unique_paths = []
    for p in collected:
        norm_p = os.path.normcase(os.path.abspath(p))
        if norm_p not in seen:
            seen.add(norm_p)
            unique_paths.append(p)
    return unique_paths


class FaceBlurCanvasWidget(QGraphicsView):
    """
    QGraphicsView 기반 인터랙티브 프리뷰 캔버스.
    - 단일/다중 이미지 파일 및 폴더 드래그 앤 드롭 로드
    - 검출된 얼굴 및 수동 영역 타원 가이드 오버레이 표시
    - 얼굴 타원 내부 좌클릭 시 블러 On/Off 즉시 토글 (역회전 타원 방정식 Hit-Test)
    - 빈 공간 마우스 좌/우클릭 드래그 시 수동 타원 블러 영역 생성
    - 수동 생성된 타원 위에서 우클릭 시 해당 수동 영역 삭제
    """

    fileDropped = Signal(str)
    filesDropped = Signal(list)
    regionsChanged = Signal()
    statusMessageRequested = Signal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        i18n: Optional[I18nManager] = None,
    ):
        super().__init__(parent)
        self.i18n: I18nManager = i18n or get_i18n()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setStyleSheet(
            """
            QGraphicsView {
                background-color: #F1F5F9;
                border: 2px dashed #94A3B8;
                border-radius: 12px;
            }
            """
        )

        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._guide_items: List[QGraphicsEllipseItem] = []
        self._drag_preview_item: Optional[QGraphicsEllipseItem] = None
        self._placeholder_item: Optional[QGraphicsTextItem] = None

        self._img_w: int = 0
        self._img_h: int = 0
        self._regions: List[FaceRegion] = []
        self._conf_threshold: float = 0.35
        self._mask_scale: float = 1.15
        self._show_guides: bool = True

        # 마우스 드래그 상태
        self._is_pressing: bool = False
        self._press_button: Qt.MouseButton = Qt.MouseButton.NoButton
        self._press_scene_pos: QPointF = QPointF()
        self._press_view_pos: QPointF = QPointF()
        self._is_dragging_manual: bool = False

        self._show_placeholder()

    def _show_placeholder(self):
        self._scene.clear()
        self._pixmap_item = None
        self._guide_items.clear()
        self._drag_preview_item = None
        self._img_w = 0
        self._img_h = 0

        text = self.i18n.tr("canvas.placeholder")
        item = QGraphicsTextItem(text)
        primary_family = load_bundled_pretendard_fonts()
        font = QFont(primary_family)
        families = [primary_family] + [f for f in FONT_FALLBACK_FAMILIES if f != primary_family]
        font.setFamilies(families)
        font.setPixelSize(21)
        font.setBold(True)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        item.setFont(font)
        item.setDefaultTextColor(QColor("#1E293B"))
        self._scene.addItem(item)
        self._placeholder_item = item
        self._scene.setSceneRect(item.boundingRect().adjusted(-40, -40, 40, 40))

    def retranslate_ui(self):
        if self._pixmap_item is None:
            self._show_placeholder()
            self._scene.update()
            self.viewport().update()

    def clear_canvas(self):
        self._show_placeholder()
        self._scene.update()
        self.viewport().update()

    def set_regions_ref(self, regions: List[FaceRegion]):
        self._regions = regions

    def update_canvas(
        self,
        rendered_bgr: np.ndarray,
        regions: List[FaceRegion],
        conf_threshold: float,
        mask_scale: float,
        show_guides: bool,
        reset_view: bool = False,
    ):
        self._regions = regions
        self._conf_threshold = conf_threshold
        self._mask_scale = mask_scale
        self._show_guides = show_guides

        h, w = rendered_bgr.shape[:2]
        size_changed = (w != self._img_w) or (h != self._img_h)
        self._img_w, self._img_h = w, h

        rgb = np.ascontiguousarray(cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB))
        bytes_per_line = 3 * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(qimg)

        if self._placeholder_item is not None:
            self._scene.clear()
            self._placeholder_item = None
            self._pixmap_item = None
            self._guide_items.clear()

        if self._pixmap_item is None:
            self._pixmap_item = self._scene.addPixmap(pixmap)
            self._pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            self._pixmap_item.setZValue(0)
        else:
            self._pixmap_item.setPixmap(pixmap)
            self._pixmap_item.update()

        self._scene.setSceneRect(QRectF(-16.0, -16.0, float(w + 32), float(h + 32)))
        self.redraw_guides()

        if reset_view or size_changed:
            self._fit_image_in_view()
            QTimer.singleShot(0, self, self._fit_image_in_view)

        self._scene.update()
        self.viewport().update()

    def redraw_guides(self):
        for item in self._guide_items:
            self._scene.removeItem(item)
        self._guide_items.clear()

        if not self._show_guides or self._img_w <= 0 or self._img_h <= 0:
            self._scene.update()
            self.viewport().update()
            return

        # 이미지 해상도에 비례하는 선 두께 계산
        stroke_w = max(2.0, min(self._img_w, self._img_h) * 0.0032)

        for reg in self._regions:
            if not reg.is_manual and reg.score < self._conf_threshold:
                continue

            cx, cy, a, b, angle_deg = get_ellipse_geometry(
                reg, self._img_w, self._img_h, self._mask_scale
            )
            rect = QRectF(-a, -b, a * 2.0, b * 2.0)
            ellipse_item = QGraphicsEllipseItem(rect)
            ellipse_item.setPos(cx, cy)
            ellipse_item.setRotation(angle_deg)
            ellipse_item.setZValue(10)

            if reg.is_blurred:
                # 블러 켜진 상태: 초록색(자동) 또는 하늘색(수동) 실선 가이드
                color = QColor("#38BDF8") if reg.is_manual else QColor("#22C55E")
                pen = QPen(color, stroke_w, Qt.PenStyle.SolidLine)
                fill = QColor(color)
                fill.setAlpha(18)
                ellipse_item.setBrush(QBrush(fill))
            else:
                # 블러 꺼진 상태: 점선 가이드 (클릭 시 다시 켜짐 암시)
                pen = QPen(QColor("#F59E0B"), stroke_w, Qt.PenStyle.DashLine)
                ellipse_item.setBrush(Qt.BrushStyle.NoBrush)

            pen.setCosmetic(False)
            ellipse_item.setPen(pen)
            self._scene.addItem(ellipse_item)
            self._guide_items.append(ellipse_item)

        self._scene.update()
        self.viewport().update()

    def _fit_image_in_view(self):
        try:
            if self._pixmap_item is not None and self._img_w > 0 and self._img_h > 0:
                padded_rect = QRectF(-16.0, -16.0, float(self._img_w + 32), float(self._img_h + 32))
                self.fitInView(padded_rect, Qt.AspectRatioMode.KeepAspectRatio)
        except RuntimeError:
            pass

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._fit_image_in_view()

    # --- 드래그 앤 드롭 이벤트 처리 (QGraphicsScene 기본 무시 동작 오버라이드) ---
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
            self.fileDropped.emit(paths[0])
        else:
            event.ignore()

    # --- 마우스 클릭 토글 및 드래그 수동 추가/삭제 ---
    def _find_hit_region(self, px: float, py: float, manual_only: bool = False) -> Optional[FaceRegion]:
        best_reg: Optional[FaceRegion] = None
        best_val = 1.0  # 1.0 이하만 타원 내부

        # 나중에 추가된(위에 그려진) 영역을 우선 검사
        for reg in reversed(self._regions):
            if manual_only and not reg.is_manual:
                continue
            if not reg.is_manual and reg.score < self._conf_threshold:
                continue

            val = hit_test_ellipse(px, py, reg, self._img_w, self._img_h, self._mask_scale)
            if val <= best_val:
                best_val = val
                best_reg = reg

        return best_reg

    def mousePressEvent(self, event: QMouseEvent):
        if self._pixmap_item is None or self._img_w <= 0 or self._img_h <= 0:
            super().mousePressEvent(event)
            return

        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self._is_pressing = True
            self._press_button = event.button()
            self._press_view_pos = event.position()
            self._press_scene_pos = self.mapToScene(event.position().toPoint())
            self._is_dragging_manual = False
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self._is_pressing or self._pixmap_item is None:
            super().mouseMoveEvent(event)
            return

        cur_view_pos = event.position()
        dist_view = math.hypot(
            cur_view_pos.x() - self._press_view_pos.x(),
            cur_view_pos.y() - self._press_view_pos.y(),
        )

        if dist_view >= 8.0:
            self._is_dragging_manual = True
            cur_scene_pos = self.mapToScene(event.position().toPoint())

            x1 = float(np.clip(min(self._press_scene_pos.x(), cur_scene_pos.x()), 0, self._img_w))
            y1 = float(np.clip(min(self._press_scene_pos.y(), cur_scene_pos.y()), 0, self._img_h))
            x2 = float(np.clip(max(self._press_scene_pos.x(), cur_scene_pos.x()), 0, self._img_w))
            y2 = float(np.clip(max(self._press_scene_pos.y(), cur_scene_pos.y()), 0, self._img_h))

            rect = QRectF(x1, y1, max(2.0, x2 - x1), max(2.0, y2 - y1))
            if self._drag_preview_item is None:
                self._drag_preview_item = QGraphicsEllipseItem(rect)
                stroke_w = max(2.0, min(self._img_w, self._img_h) * 0.0035)
                pen = QPen(QColor("#38BDF8"), stroke_w, Qt.PenStyle.DashLine)
                fill = QColor("#38BDF8")
                fill.setAlpha(45)
                self._drag_preview_item.setPen(pen)
                self._drag_preview_item.setBrush(QBrush(fill))
                self._drag_preview_item.setZValue(20)
                self._scene.addItem(self._drag_preview_item)
            else:
                self._drag_preview_item.setRect(rect)

        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if not self._is_pressing or self._pixmap_item is None:
            super().mouseReleaseEvent(event)
            return

        if self._drag_preview_item is not None:
            self._scene.removeItem(self._drag_preview_item)
            self._drag_preview_item = None

        rel_scene_pos = self.mapToScene(event.position().toPoint())
        sx, sy = self._press_scene_pos.x(), self._press_scene_pos.y()
        ex, ey = rel_scene_pos.x(), rel_scene_pos.y()

        was_dragging = self._is_dragging_manual
        btn = self._press_button
        self._is_pressing = False
        self._is_dragging_manual = False
        self._press_button = Qt.MouseButton.NoButton

        if not was_dragging:
            # 1) 우클릭 단발: 수동 추가 영역 삭제
            if btn == Qt.MouseButton.RightButton:
                hit_manual = self._find_hit_region(ex, ey, manual_only=True)
                if hit_manual is not None:
                    self._regions.remove(hit_manual)
                    self.regionsChanged.emit()
                event.accept()
                return

            # 2) 좌클릭 단발: 얼굴 또는 수동 영역 블러 On/Off 토글
            if btn == Qt.MouseButton.LeftButton:
                hit_reg = self._find_hit_region(ex, ey, manual_only=False)
                if hit_reg is not None:
                    hit_reg.is_blurred = not hit_reg.is_blurred
                    self.regionsChanged.emit()
                event.accept()
                return
        else:
            # 3) 좌클릭 또는 우클릭 드래그: 새로운 수동 타원 블러 영역 생성
            x1 = float(np.clip(min(sx, ex), 0, self._img_w))
            y1 = float(np.clip(min(sy, ey), 0, self._img_h))
            x2 = float(np.clip(max(sx, ex), 0, self._img_w))
            y2 = float(np.clip(max(sy, ey), 0, self._img_h))

            if (x2 - x1) >= max(8.0, self._img_w * 0.01) and (y2 - y1) >= max(8.0, self._img_h * 0.01):
                new_region = FaceRegion(
                    bbox_norm=(
                        x1 / self._img_w,
                        y1 / self._img_h,
                        x2 / self._img_w,
                        y2 / self._img_h,
                    ),
                    kps_norm=[],
                    score=1.0,
                    angle_deg=0.0,
                    is_blurred=True,
                    is_manual=True,
                )
                self._regions.append(new_region)
                self.regionsChanged.emit()
            event.accept()
            return

        super().mouseReleaseEvent(event)
