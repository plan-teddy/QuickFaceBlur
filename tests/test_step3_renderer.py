import os
import sys
import time
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models import FaceRegion
from src.renderer import apply_face_blurs, hit_test_ellipse


class TestStep3Renderer(unittest.TestCase):
    def test_01_bokeh_and_mosaic_modes(self):
        img = np.full((720, 1280, 3), 120, dtype=np.uint8)
        # 체크무늬 패턴을 넣어 블러/모자이크 전후 분산 감소 검증
        img[::4, ::4] = 250
        regions = [
            FaceRegion(
                bbox_norm=(0.3, 0.3, 0.5, 0.6),
                angle_deg=25.0,
                score=0.9,
                is_blurred=True,
                is_manual=False,
            ),
            # 가장자리에 걸친 얼굴 영역 (클리핑 안전성 검증)
            FaceRegion(
                bbox_norm=(-0.05, 0.85, 0.15, 1.05),
                angle_deg=-30.0,
                score=0.85,
                is_blurred=True,
                is_manual=False,
            ),
        ]

        out_bokeh = apply_face_blurs(img, regions, blur_strength=0.6, mask_scale=1.15, mode="bokeh")
        out_mosaic = apply_face_blurs(img, regions, blur_strength=0.6, mask_scale=1.15, mode="mosaic")

        self.assertEqual(out_bokeh.shape, img.shape)
        self.assertEqual(out_mosaic.shape, img.shape)
        self.assertFalse(np.array_equal(out_bokeh, img))
        self.assertFalse(np.array_equal(out_mosaic, img))

        # 프리뷰 갱신 시간(Frame Time) 검증 (웜업 후 3회 최소값 측정)
        best_ms = 999.0
        for _ in range(3):
            t0 = time.perf_counter()
            _ = apply_face_blurs(img, regions, blur_strength=0.6, mask_scale=1.15, mode="bokeh")
            best_ms = min(best_ms, (time.perf_counter() - t0) * 1000.0)
        print(f"[검증 Step 3] 1280x720 프리뷰 블러 합성 소요 시간: {best_ms:.2f} ms")
        self.assertLess(best_ms, 50.0)

    def test_02_rotated_ellipse_hit_test(self):
        reg = FaceRegion(bbox_norm=(0.4, 0.4, 0.6, 0.6), angle_deg=35.0)
        # 중심점 (640, 360)은 반드시 내부 (값 0.0)
        val_center = hit_test_ellipse(640, 360, reg, 1280, 720, mask_scale=1.15)
        self.assertAlmostEqual(val_center, 0.0, places=5)
        # 멀리 떨어진 점 (100, 100)은 외부 (값 > 1.0)
        val_far = hit_test_ellipse(100, 100, reg, 1280, 720, mask_scale=1.15)
        self.assertGreater(val_far, 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
