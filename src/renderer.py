import math
import cv2
import numpy as np

from src.models import FaceRegion


def apply_face_blurs(
    img_bgr: np.ndarray,
    regions: list[FaceRegion],
    conf_threshold: float = 0.35,
    blur_strength: float = 0.6,    # 0.1 ~ 1.0
    mask_scale: float = 1.15,      # 0.8 ~ 1.5
    mode: str = "bokeh"            # "bokeh" or "mosaic"
) -> np.ndarray:
    out = img_bgr.copy()
    h, w = out.shape[:2]

    for reg in regions:
        if not reg.is_media_eligible if hasattr(reg, "is_media_eligible") else False:
            pass
        if not reg.is_manual and reg.score < conf_threshold:
            continue
        if not reg.is_blurred:
            continue

        x1, y1, x2, y2 = (
            reg.bbox_norm[0] * w,
            reg.bbox_norm[1] * h,
            reg.bbox_norm[2] * w,
            reg.bbox_norm[3] * h,
        )
        cx, cy = (x1 + x2) * 0.5, (y1 + y2) * 0.5
        bw, bh = (x2 - x1) * mask_scale, (y2 - y1) * mask_scale

        # 회전 및 페더링 여유 공간을 포함한 패치 ROI 산출
        pad = max(bw, bh) * 0.75
        rx1 = max(0, int(cx - pad))
        ry1 = max(0, int(cy - pad))
        rx2 = min(w, int(cx + pad))
        ry2 = min(h, int(cy + pad))

        pw, ph = rx2 - rx1, ry2 - ry1
        if pw < 4 or ph < 4:
            continue

        roi = out[ry1:ry2, rx1:rx2]

        # 1. 다운스케일 후 보케/가우시안 블러 또는 모자이크 생성
        if mode == "mosaic":
            blocks = max(6, int(18 * (1.1 - blur_strength)))
            small = cv2.resize(roi, ( blocks, max(1, int(blocks * ph / pw)) ), interpolation=cv2.INTER_LINEAR)
            blurred_roi = cv2.resize(small, (pw, ph), interpolation=cv2.INTER_NEAREST)
        else:
            # Downscale-Blur-Upscale 파이프라인 (고속 연산 + 부드러운 보케 질감)
            down_factor = max(2.0, min(8.0, (max(bw, bh) / 28.0) * (0.5 + blur_strength)))
            sw = max(4, int(pw / down_factor))
            sh = max(4, int(ph / down_factor))
            small = cv2.resize(roi, (sw, sh), interpolation=cv2.INTER_AREA)

            ksize = int(max(5, (blur_strength * 18))) | 1  # 홀수 보장
            small_blur = cv2.GaussianBlur(small, (ksize, ksize), 0)
            blurred_roi = cv2.resize(small_blur, (pw, ph), interpolation=cv2.INTER_CUBIC)

        # 2. 회전 타원 마스크 생성 및 가장자리 알파 페더링
        mask = np.zeros((ph, pw), dtype=np.float32)
        local_center = (int(cx - rx1), int(cy - ry1))
        axes = (max(2, int(bw * 0.52)), max(2, int(bh * 0.58)))
        cv2.ellipse(mask, local_center, axes, reg.angle_deg, 0, 360, 1.0, -1, lineType=cv2.LINE_AA)

        feather_k = int(max(7, min(pw, ph) * 0.25)) | 1
        mask = cv2.GaussianBlur(mask, (feather_k, feather_k), 0)
        alpha = mask[:, :, np.newaxis]

        # 3. 알파 블렌딩 합성
        blended = (alpha * blurred_roi.astype(np.float32) + (1.0 - alpha) * roi.astype(np.float32)).astype(np.uint8)
        out[ry1:ry2, rx1:rx2] = blended

    return out


def get_ellipse_geometry(reg: FaceRegion, width: int, height: int, mask_scale: float = 1.15):
    """
    FaceRegion의 정규화 좌표와 mask_scale을 바탕으로
    픽셀 단위의 타원 중심 (cx, cy), 반장축/반단축 (a, b), 회전 각도 angle_deg를 반환한다.
    """
    x1 = reg.bbox_norm[0] * width
    y1 = reg.bbox_norm[1] * height
    x2 = reg.bbox_norm[2] * width
    y2 = reg.bbox_norm[3] * height
    cx = (x1 + x2) * 0.5
    cy = (y1 + y2) * 0.5
    bw = (x2 - x1) * mask_scale
    bh = (y2 - y1) * mask_scale
    a = max(2.0, bw * 0.52)
    b = max(2.0, bh * 0.58)
    return cx, cy, a, b, reg.angle_deg


def hit_test_ellipse(
    px: float,
    py: float,
    reg: FaceRegion,
    width: int,
    height: int,
    mask_scale: float = 1.15,
) -> float:
    """
    클릭 좌표 (px, py)를 타원 중심 기준으로 -theta만큼 역회전시킨 뒤
    타원 방정식 (dx^2 / a^2) + (dy^2 / b^2) 값을 반환한다.
    반환값이 1.0 이하이면 타원 내부 클릭으로 판정한다.
    """
    cx, cy, a, b, angle_deg = get_ellipse_geometry(reg, width, height, mask_scale)
    dx = px - cx
    dy = py - cy
    theta = -math.radians(angle_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    rx = dx * cos_t - dy * sin_t
    ry = dx * sin_t + dy * cos_t
    return (rx * rx) / (a * a) + (ry * ry) / (b * b)
