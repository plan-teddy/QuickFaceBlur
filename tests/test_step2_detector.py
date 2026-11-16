import os
import sys
import time
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.detector import SCRFDDetector
from src.models import FaceRegion


class TestStep2Detector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model_path = os.path.join("models", "scrfd_2.5g_bnkps.onnx")
        cls.detector = SCRFDDetector(model_path=cls.model_path)

    def test_01_model_downloaded_and_exists(self):
        self.assertTrue(os.path.exists(self.model_path), "ONNX 모델 파일이 존재해야 합니다.")
        file_size = os.path.getsize(self.model_path)
        print(f"[검증 1] 모델 파일 확인 완료: {self.model_path} ({file_size / (1024 * 1024):.2f} MB)")
        self.assertGreater(file_size, 2_000_000, "모델 파일 크기가 2MB 이상이어야 합니다.")

    def test_02_raw_onnx_output_tensor_shapes(self):
        dummy_img = np.zeros((720, 1280, 3), dtype=np.uint8)
        blob, det_scale = self.detector._preprocess(dummy_img)
        self.assertEqual(blob.shape, (1, 3, 640, 640))
        self.assertAlmostEqual(det_scale, 360.0 / 720.0, places=5)

        outputs = self.detector.session.run(None, {self.detector.input_name: blob})
        self.assertEqual(len(outputs), 9, "SCRFD-2.5GF(bnkps)는 총 9개의 출력 텐서를 반환해야 합니다.")

        expected_anchors = [
            (640 // 8) * (640 // 8) * 2,    # 12800
            (640 // 16) * (640 // 16) * 2,  # 3200
            (640 // 32) * (640 // 32) * 2,  # 800
        ]
        fmc = 3
        for idx, num_a in enumerate(expected_anchors):
            s_shape = outputs[idx].reshape(-1, 1).shape
            b_shape = outputs[idx + fmc].reshape(-1, 4).shape
            k_shape = outputs[idx + fmc * 2].reshape(-1, 10).shape
            print(
                f"[검증 2] Stride {self.detector.strides[idx]} 텐서 형태: "
                f"scores={s_shape}, bboxes={b_shape}, kps={k_shape}"
            )
            self.assertEqual(s_shape, (num_a, 1))
            self.assertEqual(b_shape, (num_a, 4))
            self.assertEqual(k_shape, (num_a, 10))

    def test_03_detect_on_dummy_and_latency(self):
        dummy_img = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
        # 웜업 1회
        _ = self.detector.detect(dummy_img, conf_thresh=0.2)

        t0 = time.perf_counter()
        regions = self.detector.detect(dummy_img, conf_thresh=0.2)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        print(f"[검증 3] 더미 이미지(1920x1080) 추론 소요 시간: {elapsed_ms:.2f} ms, 반환 타입: list (len={len(regions)})")
        self.assertIsInstance(regions, list)
        self.assertLess(elapsed_ms, 250.0, "추론 소요 시간 검증")
        for r in regions:
            self.assertIsInstance(r, FaceRegion)

    def test_04_detect_real_face_and_landmarks(self):
        import urllib.request
        import cv2

        url = "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/lena.jpg"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            arr = np.frombuffer(resp.read(), dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        regions = self.detector.detect(img, conf_thresh=0.2)
        self.assertGreaterEqual(len(regions), 1, "샘플 인물 사진에서 최소 1개 이상의 얼굴이 검출되어야 합니다.")
        face = regions[0]
        self.assertEqual(len(face.bbox_norm), 4)
        self.assertEqual(len(face.kps_norm), 5)
        self.assertGreater(face.score, 0.5)
        self.assertTrue(-45.0 <= face.angle_deg <= 45.0)
        print(
            f"[검증 4] 실제 얼굴 검출 성공: score={face.score:.3f}, "
            f"angle={face.angle_deg:.2f}°, bbox_norm={tuple(round(v, 3) for v in face.bbox_norm)}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
