import os
import sys
import tempfile
import time
import unittest

import numpy as np
from PIL import Image
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.canvas_widget import extract_image_paths_from_mimedata
from src.detector import SCRFDDetector
from src.main_window import MainWindow, load_image_safe, load_image_with_metadata, save_image_safe
from src.models import FaceRegion


class TestStep4GuiAndIO(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.detector = SCRFDDetector()

    def test_01_korean_path_exif_transpose_and_metadata_strip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            korean_dir = os.path.join(tmpdir, "가족사진_폴더", "2026_가족모임")
            os.makedirs(korean_dir, exist_ok=True)
            img_path = os.path.join(korean_dir, "원본사진_한글테스트.jpg")

            # 가로 400, 세로 200 이미지에 EXIF Orientation=6 및 Make="TestCamera" 부여
            pil_img = Image.new("RGB", (400, 200), color=(60, 120, 180))
            exif = pil_img.getexif()
            exif[0x0112] = 6            # Orientation: Rotate 90 CW
            exif[0x010F] = "TestCamera" # Make
            pil_img.save(img_path, exif=exif.tobytes(), quality=95)

            loaded_bgr, exif_bytes = load_image_with_metadata(img_path)
            self.assertEqual(loaded_bgr.shape, (400, 200, 3), "EXIF Orientation 6이 보정되어 세로 400, 가로 200이어야 합니다.")
            self.assertIsNotNone(exif_bytes)

            # 1) strip_metadata=True (기본): 저장된 파일에 EXIF가 완전히 제거되어야 함
            stripped_path = os.path.join(korean_dir, "원본사진_메타제거.jpg")
            ok_strip = save_image_safe(stripped_path, loaded_bgr, strip_metadata=True, exif_bytes=exif_bytes)
            self.assertTrue(ok_strip)
            with Image.open(stripped_path) as p_strip:
                self.assertEqual(len(p_strip.getexif()), 0, "메타데이터 제거 옵션 활성화 시 EXIF 태그가 0개여야 합니다.")

            # 2) strip_metadata=False: 원본 EXIF(Make 등)가 보존되고 Orientation은 1이어야 함
            kept_path = os.path.join(korean_dir, "원본사진_메타유지.jpg")
            ok_keep = save_image_safe(kept_path, loaded_bgr, strip_metadata=False, exif_bytes=exif_bytes)
            self.assertTrue(ok_keep)
            with Image.open(kept_path) as p_keep:
                kept_exif = p_keep.getexif()
                self.assertEqual(kept_exif.get(0x010F), "TestCamera")
                self.assertEqual(kept_exif.get(0x0112), 1)

            print(f"[검증 Step 4-1] 한글 경로 입출력, EXIF 회전 보정 및 메타데이터 제거/유지 검증 완료")

    def test_02_mainwindow_multi_photo_clipboard_and_controls(self):
        win = MainWindow(detector=self.detector)
        win.show()
        self.app.processEvents()

        # 썸네일 패널이 창 하단으로부터 최소 40px 이상 버퍼(하단 상태바+여백)를 확보하는지 확인 및 최소 크기/스크롤 검증
        left_bottom_y = win.left_photo_group.mapTo(win, win.left_photo_group.rect().bottomLeft()).y()
        bottom_buffer = win.height() - left_bottom_y
        self.assertGreaterEqual(bottom_buffer, 40, f"좌측 썸네일 영역 하단 버퍼({bottom_buffer}px)는 최소 40px 이상이어야 합니다.")
        self.assertEqual((win.minimumWidth(), win.minimumHeight()), (640, 440))
        self.assertEqual((win.photo_list.iconSize().width(), win.photo_list.iconSize().height()), (48, 36))
        win.resize(640, 440)
        self.app.processEvents()
        win.resize(1160, 640)
        self.app.processEvents()

        with tempfile.TemporaryDirectory() as tmpdir:
            # 2장의 고해상도 이미지 생성
            high_res_1 = np.full((3000, 4000, 3), 180, dtype=np.uint8)
            high_res_2 = np.full((1500, 2000, 3), 140, dtype=np.uint8)
            src_path_1 = os.path.join(tmpdir, "단체사진_1.jpg")
            src_path_2 = os.path.join(tmpdir, "단체사진_2.jpg")
            save_image_safe(src_path_1, high_res_1)
            save_image_safe(src_path_2, high_res_2)

            # 드래그 앤 드롭 MimeData 추출 검증 (다중 파일 + 폴더)
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(src_path_1), QUrl.fromLocalFile(tmpdir)])
            extracted = extract_image_paths_from_mimedata(mime)
            self.assertEqual(len(extracted), 2)

            # 여러 장 동시 로드 검증
            win.load_images_from_paths([src_path_1, src_path_2])
            self.assertEqual(len(win.photo_entries), 2)
            self.assertEqual(win.photo_list.count(), 2)
            self.assertEqual(win.current_index, 0)
            self.assertEqual(win.orig_img_bgr.shape, (3000, 4000, 3))
            self.assertEqual(win.preview_img_bgr.shape, (960, 1280, 3))

            # 가짜 자동 검출 얼굴 2개 주입 (하나는 높은 점수, 하나는 낮은 점수)
            face_high = FaceRegion(bbox_norm=(0.4, 0.4, 0.6, 0.6), score=0.9, angle_deg=15.0, is_blurred=True)
            face_low = FaceRegion(bbox_norm=(0.1, 0.1, 0.2, 0.2), score=0.25, angle_deg=0.0, is_blurred=True)
            win.regions = [face_high, face_low]
            win.photo_entries[0].regions = win.regions
            win.refresh_preview(reset_view=True)

            # [전체 끄기] 버튼 클릭 -> 모든 영역의 블러가 꺼져야 함
            win.btn_all_off.click()
            self.assertTrue(all(not r.is_blurred for r in win.regions), "전체 끄기 클릭 시 모든 얼굴의 블러가 꺼져야 합니다.")

            # [전체 켜기] 버튼 클릭 -> 모든 영역의 블러가 켜져야 함
            win.btn_all_on.click()
            self.assertTrue(all(r.is_blurred for r in win.regions), "전체 켜기 클릭 시 모든 얼굴의 블러가 켜져야 합니다.")

            # 캔버스 중심 좌클릭 -> 블러 토글(On -> Off) 검증
            center_view_pt = win.canvas.mapFromScene(QPointF(640.0, 480.0))
            t0 = time.perf_counter()
            press_ev = QMouseEvent(
                QMouseEvent.Type.MouseButtonPress,
                QPointF(center_view_pt),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            release_ev = QMouseEvent(
                QMouseEvent.Type.MouseButtonRelease,
                QPointF(center_view_pt),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
            win.canvas.mousePressEvent(press_ev)
            win.canvas.mouseReleaseEvent(release_ev)
            toggle_ms = (time.perf_counter() - t0) * 1000.0
            print(f"[검증 Step 4-2] 얼굴 좌클릭 토글 소요 시간: {toggle_ms:.2f} ms")
            self.assertFalse(win.regions[0].is_blurred)
            self.assertLess(toggle_ms, 500.0)

            # 클립보드 복사 기능 검증
            copied_ok = win.copy_result_to_clipboard(show_dialog=False)
            self.assertTrue(copied_ok)
            clip_img = QApplication.clipboard().image()
            self.assertFalse(clip_img.isNull())
            self.assertEqual((clip_img.width(), clip_img.height()), (4000, 3000))

            # 사진 2번으로 전환 후 다시 1번으로 돌아왔을 때 상태 유지 검증
            win.select_photo_index(1)
            self.assertEqual(win.orig_img_bgr.shape, (1500, 2000, 3))
            win.select_photo_index(0)
            self.assertFalse(win.regions[0].is_blurred)

            # 전체 사진 일괄 저장 검증
            batch_out_dir = os.path.join(tmpdir, "batch_out")
            saved_cnt = win.save_all_to_directory(batch_out_dir, show_dialog=False)
            self.assertEqual(saved_cnt, 2)
            self.assertTrue(os.path.exists(os.path.join(batch_out_dir, "단체사진_1_blurred.jpg")))
            self.assertTrue(os.path.exists(os.path.join(batch_out_dir, "단체사진_2_blurred.jpg")))
            print(f"[검증 Step 4-3] 다중 사진 목록, 클립보드 복사 및 일괄 저장 검증 완료")

        win.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
