import os
import sys
import urllib.request
from typing import Callable, List, Optional

import cv2
import numpy as np
import onnxruntime as ort

from src.models import FaceRegion

MODEL_URL = "https://huggingface.co/RuteNL/SCRFD-face-detection-ONNX/resolve/main/2.5g_bnkps.onnx"
FALLBACK_MODEL_URLS = [
    MODEL_URL,
    "https://huggingface.co/hsuyabc/scrfd_2.5g_bnkps.onnx/resolve/main/scrfd_2.5g_bnkps.onnx",
    "https://huggingface.co/OwlMaster/AllFilesRope/resolve/main/scrfd_2.5g_bnkps.onnx",
]


def resolve_model_path(model_path: str = "models/scrfd_2.5g_bnkps.onnx") -> str:
    """
    설치형/포터블 실행 환경(PyInstaller _MEIPASS 또는 실행 파일 경로)에서
    번들링된 모델 경로를 우선 탐색하고, 없으면 쓰기 가능한 경로를 반환한다.
    """
    if os.path.isabs(model_path) and os.path.exists(model_path):
        return model_path

    # 1. PyInstaller 번들 리소스 경로 (_MEIPASS) 확인
    if hasattr(sys, "_MEIPASS"):
        bundled_path = os.path.join(getattr(sys, "_MEIPASS"), model_path)
        if os.path.exists(bundled_path):
            return bundled_path

    # 2. 실행 파일 기준 상대 경로 확인
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        exe_model_path = os.path.join(exe_dir, model_path)
        if os.path.exists(exe_model_path):
            return exe_model_path

    # 3. 현재 작업 디렉토리 또는 프로젝트 루트 기준 경로
    if os.path.exists(model_path):
        return model_path

    # 4. 다운로드가 필요한 경우 현재 경로에 쓰기 가능 여부 확인 후 불가 시 LOCALAPPDATA 사용
    target_dir = os.path.dirname(os.path.abspath(model_path)) or "."
    try:
        os.makedirs(target_dir, exist_ok=True)
        test_file = os.path.join(target_dir, ".write_test")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_file)
        return model_path
    except OSError:
        local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        fallback_path = os.path.join(local_app_data, "QuickFaceBlur", model_path)
        os.makedirs(os.path.dirname(fallback_path), exist_ok=True)
        return fallback_path


class SCRFDDetector:
    def __init__(
        self,
        model_path: str = "models/scrfd_2.5g_bnkps.onnx",
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ):
        resolved_path = resolve_model_path(model_path)
        if os.path.dirname(resolved_path):
            os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
        if not os.path.exists(resolved_path):
            def _reporthook(block_num: int, block_size: int, total_size: int):
                if progress_callback is not None:
                    downloaded = block_num * block_size
                    progress_callback(downloaded, total_size)

            last_err = None
            for url in FALLBACK_MODEL_URLS:
                try:
                    urllib.request.urlretrieve(url, resolved_path, reporthook=_reporthook)
                    if os.path.exists(resolved_path) and os.path.getsize(resolved_path) > 100_000:
                        break
                except Exception as exc:
                    last_err = exc
                    if os.path.exists(resolved_path):
                        try:
                            os.remove(resolved_path)
                        except OSError:
                            pass
            if not os.path.exists(resolved_path) and last_err is not None:
                raise last_err
        self.model_path = resolved_path

        providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
        available = ort.get_available_providers()
        active_providers = [p for p in providers if p in available]
        if not active_providers:
            active_providers = available
        self.session = ort.InferenceSession(self.model_path, providers=active_providers)
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = (640, 640)
        self.strides = [8, 16, 32]
        self.num_anchors = 2
        self._center_cache = {}

    def _preprocess(self, img_bgr: np.ndarray):
        h, w = img_bgr.shape[:2]
        target_w, target_h = self.input_size
        im_ratio = float(h) / w
        model_ratio = float(target_h) / target_w
        if im_ratio > model_ratio:
            new_h = target_h
            new_w = int(new_h / im_ratio)
        else:
            new_w = target_w
            new_h = int(new_w * im_ratio)

        det_scale = float(new_h) / h
        resized = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        det_img = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        det_img[:new_h, :new_w, :] = resized

        blob = cv2.dnn.blobFromImage(
            det_img, 1.0 / 128.0, self.input_size, (127.5, 127.5, 127.5), swapRB=True
        )
        return blob, det_scale

    def detect(self, img_bgr: np.ndarray, conf_thresh: float = 0.2, nms_thresh: float = 0.4) -> List[FaceRegion]:
        """
        초기 검출은 낮은 conf_thresh(0.2)로 한 번만 수행하여 캐싱하고,
        UI의 민감도 슬라이더 조작 시에는 재추론 없이 score 필터링만 수행한다.
        """
        h, w = img_bgr.shape[:2]
        blob, det_scale = self._preprocess(img_bgr)
        outputs = self.session.run(None, {self.input_name: blob})

        scores_list, bboxes_list, kps_list = [], [], []
        fmc = len(self.strides)  # 3

        for idx, stride in enumerate(self.strides):
            scores = outputs[idx]
            bbox_preds = outputs[idx + fmc] * stride
            kps_preds = outputs[idx + fmc * 2] * stride

            # 배치 차원이 (1, N, C) 형태인 경우 (N, C)로 평탄화
            scores = scores.reshape(-1, 1)
            bbox_preds = bbox_preds.reshape(-1, 4)
            kps_preds = kps_preds.reshape(-1, 10)

            feat_h = self.input_size[1] // stride
            feat_w = self.input_size[0] // stride
            key = (feat_h, feat_w, stride)

            if key in self._center_cache:
                anchor_centers = self._center_cache[key]
            else:
                anchor_centers = np.stack(np.mgrid[:feat_h, :feat_w][::-1], axis=-1).astype(np.float32)
                anchor_centers = (anchor_centers * stride).reshape((-1, 2))
                anchor_centers = np.stack([anchor_centers] * self.num_anchors, axis=1).reshape((-1, 2))
                self._center_cache[key] = anchor_centers

            pos_inds = np.where(scores[:, 0] >= conf_thresh)[0]
            if len(pos_inds) == 0:
                continue

            pos_scores = scores[pos_inds]
            pos_bbox_preds = bbox_preds[pos_inds]
            pos_kps_preds = kps_preds[pos_inds]
            pos_centers = anchor_centers[pos_inds]

            # Distance to BBox
            x1 = pos_centers[:, 0] - pos_bbox_preds[:, 0]
            y1 = pos_centers[:, 1] - pos_bbox_preds[:, 1]
            x2 = pos_centers[:, 0] + pos_bbox_preds[:, 2]
            y2 = pos_centers[:, 1] + pos_bbox_preds[:, 3]
            bboxes = np.stack([x1, y1, x2, y2], axis=-1)

            # Distance to 5 Keypoints
            kps = np.zeros_like(pos_kps_preds)
            for k in range(0, 10, 2):
                kps[:, k] = pos_centers[:, 0] + pos_kps_preds[:, k]
                kps[:, k + 1] = pos_centers[:, 1] + pos_kps_preds[:, k + 1]

            scores_list.append(pos_scores)
            bboxes_list.append(bboxes)
            kps_list.append(kps)

        if not scores_list:
            return []

        scores = np.vstack(scores_list).ravel()
        bboxes = np.vstack(bboxes_list) / det_scale
        kps = np.vstack(kps_list) / det_scale

        # OpenCV NMSBoxes 적용
        boxes_xywh = bboxes.copy()
        boxes_xywh[:, 2] = bboxes[:, 2] - bboxes[:, 0]
        boxes_xywh[:, 3] = bboxes[:, 3] - bboxes[:, 1]
        indices = cv2.dnn.NMSBoxes(
            boxes_xywh.tolist(), scores.tolist(), conf_thresh, nms_thresh
        )

        regions = []
        if len(indices) > 0:
            for i in np.array(indices).flatten():
                bx1, by1, bx2, by2 = bboxes[i]
                bx1, by1 = np.clip([bx1, by1], 0, [w, h])
                bx2, by2 = np.clip([bx2, by2], 0, [w, h])

                pts = kps[i].reshape(5, 2)
                # 양쪽 눈 좌표로 기울기 각도 계산 (왼눈: pts[0], 오른눈: pts[1])
                dx = pts[1][0] - pts[0][0]
                dy = pts[1][1] - pts[0][1]
                bw = max(bx2 - bx1, 1.0)
                if abs(dx) > bw * 0.12:
                    angle = float(np.clip(np.degrees(np.arctan2(dy, dx)), -45.0, 45.0))
                else:
                    angle = 0.0

                regions.append(
                    FaceRegion(
                        bbox_norm=(float(bx1 / w), float(by1 / h), float(bx2 / w), float(by2 / h)),
                        kps_norm=[(float(px / w), float(py / h)) for px, py in pts],
                        score=float(scores[i]),
                        angle_deg=angle,
                        is_blurred=True,
                        is_manual=False,
                    )
                )
        return regions
