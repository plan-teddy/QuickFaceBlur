# [PRD & Tech Spec] QuickFaceBlur — 저사양 PC 최적화 고성능 얼굴 블러 데스크톱 앱

- **문서 버전:** v1.0.0
- **타겟 환경:** Windows 10 / 11 (구형·저사양 CPU 및 내장 그래픽 노트북 최적화)
- **코어 AI 모델:** InsightFace `SCRFD-2.5GF` (`scrfd_2.5g_bnkps.onnx`, 5-Point 랜드마크 포함, ~3.2MB)
- **목표 수준:** Windows 11 기본 사진(Photos) 앱의 얼굴 블러 대비 **검출 정밀도(측면·소형 얼굴) 우위** 및 **UI 반응 속도 5배 이상 향상**

---

## 1. 프로젝트 기술 개요 및 추천 스택

초기 비용 0원(오픈소스 및 로컬 추론 100%) 원칙을 준수하며, 보급형 노트북(저사양 듀얼/쿼드코어 CPU + 인텔 UHD 등 내장 그래픽)에서 별도 런타임 설치 없이 단독 실행(`.exe` / `.app`) 가능한 두 가지 옵션을 비교하여 **옵션 A**를 최종 채택한다.

| 구분 | 옵션 A: Python + PySide6 데스크톱 (채택) | 옵션 B: Tauri + React + ONNX Web (대안) |
| :--- | :--- | :--- |
| **프론트엔드 / GUI** | `PySide6` (`QGraphicsView` 하드웨어 가속 캔버스) | React + TypeScript + HTML5 Canvas |
| **추론 엔진 (BE)** | `onnxruntime` (CPU / DirectML 가속) | `onnxruntime-web` (WASM / WebGL) |
| **영상 처리** | `opencv-python-headless`, `numpy`, `Pillow` | `OpenCV.js` (WASM) |
| **배포 및 패키징** | `PyInstaller` (단일 폴더 또는 단일 `.exe`) | Tauri Bundler (WebView2 의존) |
| **선정 사유** | OpenCV C++ 네이티브 행렬 연산과 ONNX 추론 속도가 가장 빠르며, 단일 프로젝트 내에서 AI 코딩 에이전트가 디버깅·빌드하기 가장 명확함 | 실행 파일 크기는 작으나 WASM 메모리 제한으로 4000x3000급 고해상도 원본 다중 처리 시 GC 스파이크 발생 가능 |

---

## 2. 프로젝트 핵심 기능 명세 (User Stories & Acceptance Criteria)

### 기능 1 [P0]: SCRFD-2.5GF 기반 초고속 얼굴 및 5점 랜드마크 자동 검출
> **사용자 스토리:** "사용자로서 나는 사진을 앱으로 드래그 앤 드롭했을 때 0.1초 이내에 사진 속 모든 얼굴(작은 얼굴, 옆모습 포함)이 자동 감지되기를 원한다. 그래서 일일이 얼굴을 찾는 수고를 덜 수 있다."

- **인수 조건 (Acceptance Criteria):**
  - **Given:** 사용자가 로컬 이미지를 드래그 앤 드롭하거나 '열기' 버튼으로 로드했을 때
  - **When:** 앱이 이미지를 `640x640` 레터박스(비율 유지 패딩) 텐서로 변환해 `scrfd_2.5g_bnkps.onnx` 모델로 추론하면
  - **Then:** 100ms 이내에 모든 얼굴의 바운딩 박스 `[x1, y1, x2, y2, score]`와 5점 랜드마크(양쪽 눈, 코, 양쪽 입꼬리)가 검출되고, 기본값으로 모든 얼굴에 블러가 활성화된 프리뷰가 화면에 표시되어야 한다.
- **예외 처리 및 엣지 케이스:**
  - **모델 파일 부재 시:** 앱 최초 실행 시 `models/scrfd_2.5g_bnkps.onnx` 파일이 없으면 HuggingFace 미러 URL에서 자동 다운로드하며 진행률 프로그레스 바를 표시한다.
  - **검출된 얼굴이 0개일 때:** 앱이 크래시하지 않고 상단 상태바에 `"감지된 얼굴이 없습니다. 마우스로 드래그하여 직접 블러 영역을 추가해 보세요."` 안내 문구를 표시한다.
  - **스마트폰 사진 회전(EXIF Orientation) 이슈:** 이미지 로드 시 반드시 EXIF 방향 태그를 해석(`ImageOps.exif_transpose`)하여 사진이 90도/180도 돌아간 채로 검출되는 현상을 방지한다.

### 기능 2 [P0]: 5점 랜드마크 회전 타원(Rotated Ellipse) 페더링 & 다운스케일 보케 블러
> **사용자 스토리:** "사용자로서 나는 고개가 기울어진 얼굴도 각도에 맞춰 자연스러운 타원형으로 부드럽게 블러 처리되기를 원한다. 그래서 네모난 모자이크처럼 이질감이 들지 않는 고품질 사진을 얻을 수 있다."

- **인수 조건 (Acceptance Criteria):**
  - **Given:** 검출된 얼굴의 양쪽 눈 좌표 `(left_eye, right_eye)`와 바운딩 박스가 주어졌을 때
  - **When:** 블러 렌더링 파이프라인이 동작하면
  - **Then:** 두 눈의 각도 $\theta = \text{atan2}(\Delta y, \Delta x)$만큼 회전된 타원 마스크를 생성하고, 경계선 알파 페더링(Feathering)과 다운스케일 보케(Downscale-Blur-Upscale) 알고리즘을 통해 경계선 자국 없이 부드럽게 블러 처리되어야 한다.
- **예외 처리 및 엣지 케이스:**
  - **이미지 가장자리에 걸친 얼굴:** 얼굴 ROI가 이미지 경계(`0` 또는 `width/height`) 밖으로 넘어갈 경우 배열 인덱스 에러(`IndexError`)가 나지 않도록 좌표를 클리핑(`np.clip`) 처리한다.
  - **90도 완전 측면 얼굴:** 양쪽 눈의 X좌표 거리가 극도로 가까워 각도가 왜곡될 수 있는 경우(눈 사이 거리가 박스 너비의 12% 미만일 때), 회전 각도 $\theta$를 `0.0`으로 고정하여 타원이 비정상적으로 뒤틀리는 현상을 방지한다.

### 기능 3 [P0]: 원클릭 얼굴 블러 토글(On/Off) 및 마우스 드래그 수동 블러 추가
> **사용자 스토리:** "사용자로서 나는 가족 얼굴은 클릭 한 번으로 블러를 끄고, AI가 놓친 뒷모습이나 특정 사물(차량 번호판 등)은 마우스 드래그로 직접 블러 원을 추가할 수 있다. 그래서 원하는 대상만 완벽하게 가릴 수 있다."

- **인수 조건 (Acceptance Criteria):**
  - **Given:** 프리뷰 캔버스에 검출된 얼굴 영역들이 점선 또는 반투명 가이드 테두리로 표시된 상태에서
  - **When:** 사용자가 특정 얼굴 영역 안쪽을 **좌클릭**하면
  - **Then:** 해당 얼굴의 `is_blurred` 상태가 즉시 토글(On ↔ Off)되고, **0.02초(20ms) 이내**에 프리뷰 화면이 갱신되어야 한다.
  - **When:** 사용자가 얼굴이 없는 빈 영역에서 **마우스 좌클릭 드래그(또는 우클릭 드래그)**를 수행하면
  - **Then:** 드래그 시작점과 끝점을 감싸는 새로운 수동 타원 블러 객체(`is_manual=True`, `is_blurred=True`)가 생성되어 즉시 블러가 적용되며, 수동 생성된 원 위에서 **우클릭(또는 삭제 버튼 클릭)** 시 해당 수동 영역이 삭제된다.

### 기능 4 [P1]: 이중 해상도(Dual-Resolution) 실시간 슬라이더 및 원본 고화질 저장
> **사용자 스토리:** "사용자로서 나는 구형 노트북에서도 블러 강도 슬라이더를 움직일 때 끊김 없이 결과를 확인하고, 저장할 때는 원본 화질 그대로 저장할 수 있다. 그래서 답답함 없이 빠르게 사진을 편집할 수 있다."

- **인수 조건 (Acceptance Criteria):**
  - **Given:** 4000x3000 이상의 고해상도 원본 이미지가 로드되었을 때
  - **When:** 사용자가 '블러 강도(1~100)', '마스크 크기 비율(0.8x~1.5x)', '검출 민감도(0.2~0.8)' 슬라이더를 조절하면
  - **Then:** 화면 조작 중에는 최대 긴 변 `1280px`로 축소된 **프리뷰 버퍼**에서만 블러 합성을 수행하여 60fps에 준하는 반응성을 유지하고, **'저장하기(Save)'** 클릭 시에만 정규화 좌표(Normalized Coordinates, `0.0~1.0`)를 원본 해상도에 투영해 원본 화질로 저장한다.
- **예외 처리 및 엣지 케이스:**
  - **원본 파일 덮어쓰기 방지:** 저장 시 기본 파일명을 `{원본파일명}_blurred.jpg`로 자동 제안하여 원본 사진이 실수로 유실되는 것을 막는다.
  - **한글 경로 호환성:** Windows 환경에서 한글 폴더명/파일명(`C:\바탕화면\가족사진\...`)을 읽고 쓸 때 OpenCV `cv2.imread`/`cv2.imwrite`가 실패하지 않도록 반드시 `np.fromfile`과 `cv2.imdecode` / `cv2.imencode`를 사용한다.

---

## 3. 주요 화면 설계 및 사용자 플로우 (Screens & User Flow)

### 3.1 단일 윈도우 레이아웃 구성 (어르신 친화적 고대비·큼직한 UI)
- **상단 툴바 (Top Bar):**
  - `[📂 사진 열기]` (큰 버튼, 폰트 14pt 이상)
  - `[👁️ 전체 켜기]` / `[🙈 전체 끄기]`
  - `[🔍 가이드 점선 표시 체크박스]` (체크 해제 시 저장될 깨끗한 결과물 미리보기)
  - `[💾 고화질 저장]` (강조 색상 버튼)
- **중앙 메인 캔버스 (Interactive Preview Canvas):**
  - 이미지 드래그 앤 드롭 지원 영역.
  - 블러가 켜진 얼굴(`is_blurred=True`): 부드러운 보케 블러 렌더링 + 얇은 초록색(또는 파란색) 타원 가이드라인.
  - 블러가 꺼진 얼굴(`is_blurred=False`): 원본 얼굴 노출 + 점선 회색 타원 가이드라인(클릭 시 다시 켜짐을 암시).
- **우측(또는 하단) 컨트롤 패널:**
  - **블러 스타일 라디오 버튼:** `부드러운 보케 블러 (기본)` / `모자이크 (픽셀화)`
  - **블러 강도 슬라이더:** `10% ~ 100%` (기본값 `60%`)
  - **영역 크기 슬라이더:** `80% ~ 150%` (기본값 `115%` — 얼굴 전체와 귀 일부를 자연스럽게 덮는 크기)
  - **얼굴 감지 민감도 슬라이더:** `0.20 ~ 0.80` (기본값 `0.35` — 낮출수록 작은 얼굴 추가 검출, 높일수록 오검출 감소)
  - **하단 상태 표시줄:** `"총 N명의 얼굴 감지됨 (블러 적용: M명) | 💡 얼굴 클릭: 블러 켜기/끄기 | 빈 곳 드래그: 직접 블러 추가 | 수동 영역 우클릭: 삭제"`

### 3.2 단계별 유저 플로우 (Step-by-Step User Flow)
1. **실행 및 사진 로드:** 바탕화면의 아이콘을 더블클릭해 앱을 켜고 사진을 창 안으로 끌어다 놓는다.
2. **자동 검출 및 블러 확인:** 0.1초 만에 모든 사람의 얼굴에 자연스러운 회전 타원 블러가 씌워진 화면이 나타난다.
3. **선별적 해제/추가:** 본인이나 가족 얼굴을 마우스로 톡 클릭해 블러를 끄고, 혹시 안 가려진 옆모습이 있다면 마우스로 드래그해 블러 원을 씌운다.
4. **즉시 저장:** `[💾 고화질 저장]` 버튼을 누르면 원본 폴더에 `_blurred`가 붙은 고해상도 사진이 즉시 생성된다.

---

## 4. 데이터 모델 및 코어 알고리즘 명세 (Antigravity 구현 필수 준수)

에이전트는 아래 데이터 구조와 수학적 디코딩 로직을 임의로 축소하거나 생략하지 말고 그대로 코드에 반영해야 한다.

### 4.1 얼굴 영역 상태 데이터 모델 (`FaceRegion`)
모든 좌표는 프리뷰 이미지와 원본 이미지 간의 해상도 독립성을 위해 **`0.0 ~ 1.0` 정규화 비율(Normalized Coordinates)**로 저장한다.

```python
from dataclasses import dataclass, field
from typing import List, Tuple
import uuid

@dataclass
class FaceRegion:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    # 정규화 바운딩 박스 (0.0 ~ 1.0): (x1, y1, x2, y2)
    bbox_norm: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    # 정규화 5점 랜드마크 [(x, y) * 5]: 왼눈, 오른눈, 코, 왼입꼬리, 오른입꼬리
    kps_norm: List[Tuple[float, float]] = field(default_factory=list)
    score: float = 1.0
    angle_deg: float = 0.0          # 양쪽 눈 기준 회전 각도 (-45.0 ~ +45.0 클리핑)
    is_blurred: bool = True         # 클릭 시 True <-> False 토글
    is_manual: bool = False         # 마우스 드래그로 수동 추가된 영역 여부
```

### 4.2 `SCRFD-2.5GF` (`scrfd_2.5g_bnkps.onnx`) 정확한 앵커 디코더 구현
`scrfd_2.5g_bnkps.onnx` 모델은 입력으로 `(1, 3, 640, 640)` 텐서를 받으며, 출력으로 **총 9개의 텐서**(Stride `8, 16, 32` 각각에 대해 `scores(N, 1)`, `bboxes(N, 4)`, `kps(N, 10)`)를 반환한다. 각 위치당 앵커 개수(`num_anchors`)는 **2개**이다.

```python
import os
import urllib.request
import cv2
import numpy as np
import onnxruntime as ort

MODEL_URL = "[https://huggingface.co/RuteNL/SCRFD-face-detection-ONNX/resolve/main/scrfd_2.5g_bnkps.onnx](https://huggingface.co/RuteNL/SCRFD-face-detection-ONNX/resolve/main/scrfd_2.5g_bnkps.onnx)"

class SCRFDDetector:
    def __init__(self, model_path: str = "models/scrfd_2.5g_bnkps.onnx"):
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        if not os.path.exists(model_path):
            urllib.request.urlretrieve(MODEL_URL, model_path)

        providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
        available = ort.get_available_providers()
        active_providers = [p for p in providers if p in available]
        self.session = ort.InferenceSession(model_path, providers=active_providers)
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

    def detect(self, img_bgr: np.ndarray, conf_thresh: float = 0.2, nms_thresh: float = 0.4):
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
                        bbox_norm=(bx1 / w, by1 / h, bx2 / w, by2 / h),
                        kps_norm=[(float(px / w), float(py / h)) for px, py in pts],
                        score=float(scores[i]),
                        angle_deg=angle,
                        is_blurred=True,
                        is_manual=False,
                    )
                )
        return regions
```

### 4.3 회전 타원 페더링 & 다운스케일 보케 블러 합성 엔진
전체 이미지를 매번 블러 처리하면 저사양 CPU에서 느려지므로, **각 얼굴의 ROI(관심 영역) 패치만 잘라내어 국소 연산(Local Patch Blending)**을 수행한다.

```python
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
```

---

## 5. 타겟 사용자 가치 검증 (Target User Fit)

| 저사양 보급형 노트북 사용 시 주요 페인 포인트 | 본 설계의 해결 방식 |
| :--- | :--- |
| **윈도우 기본 사진 앱의 초기 구동 및 AI 로딩 지연** | 무거운 WinUI 3 런타임을 배제하고 3.2MB ONNX 단일 모델만 로드하여 콜드 스타트 시간을 1.5초 이내로 단축 |
| **단체 사진에서 작은 얼굴·측면 얼굴 누락** | WIDER FACE Hard 세트 77.9% 성능의 `SCRFD-2.5GF`를 적용하고 민감도 슬라이더 실시간 필터링 및 마우스 드래그 수동 추가 제공 |
| **슬라이더 조작 시 화면 멈춤(버벅임)** | 검출(1회 캐싱)과 렌더링(프리뷰 버퍼 국소 ROI 연산)을 완전히 분리하여 슬라이더 조작 시 10ms 내외로 즉시 반응 |
| **어색한 사각형 모자이크 경계선** | 5점 랜드마크 눈 각도를 반영한 회전 타원 + 가우시안 알파 페더링으로 인물 사진에 자연스럽게 녹아드는 블러 구현 |

---

## 6. 핵심 성공 지표 (KPI) 및 성능 검증 기준

- **초기 얼굴 검출 소요 시간 (Inference Latency):** 인텔 내장 그래픽 노트북 CPU 기준 사진 1장당 **80ms 이하**.
- **인터랙션 반응 속도 (UI Frame Time):** 얼굴 클릭 토글 또는 슬라이더 조절 시 프리뷰 갱신 시간 **16ms 이하 (60fps 방어)**.
- **단독 실행 패키지 안정성:** 파이썬이 설치되지 않은 클린 Windows 10/11 PC에서 외부 의존성 오류 없이 100% 단독 실행.

---

## 7. 주요 리스크 및 완화 방안

1. **PyInstaller 패키징 시 불필요한 라이브러리 포함으로 인한 용량 비대화:**
   - **완화 방안:** 가상환경(`venv`)을 새로 생성하여 `PySide6`, `onnxruntime`, `opencv-python-headless`, `numpy`, `Pillow` 딱 5개 패키지만 설치한 상태에서 빌드한다(`torch`, `scipy`, `matplotlib` 절대 설치 금지).
2. **회전된 타원 안쪽의 클릭 판정(Hit-Test) 오차:**
   - **완화 방안:** 사용자가 얼굴을 클릭할 때 단순 직사각형 판정이 아니라, 클릭 좌표를 타원 중심 기준으로 $-\theta$만큼 역회전시킨 뒤 타원 방정식 $\frac{\Delta x^2}{a^2} + \frac{\Delta y^2}{b^2} \le 1.0$을 만족하는지 검사하여 정확한 클릭 토글을 구현한다.

---

## 8. 프로젝트 디렉토리 구조 및 Antigravity 실행 지침

### 8.1 권장 디렉토리 구조
```text
quick-face-blur/
├── models/
│   └── scrfd_2.5g_bnkps.onnx      # 최초 실행 시 자동 다운로드 및 번들링 포함
├── src/
│   ├── __init__.py
│   ├── models.py                  # FaceRegion 데이터클래스 및 상태 관리
│   ├── detector.py                # SCRFDDetector (ONNX 추론 및 5점 랜드마크 디코딩)
│   ├── renderer.py                # 회전 타원 알파 페더링 & 다운스케일 보케 블러 엔진
│   ├── canvas_widget.py           # QGraphicsView 기반 클릭 토글 / 드래그 수동 추가 캔버스
│   └── main_window.py             # 어르신 친화적 메인 GUI 및 파일 입출력(EXIF/한글경로 처리)
├── main.py                        # 엔트리포인트 (High-DPI 스케일링 설정 포함)
├── requirements.txt               # 최소 의존성 목록
└── build_exe.py                   # PyInstaller 포터블 빌드 스크립트
```

### 8.2 Antigravity 에이전트 구현 순서 (Step-by-Step)
1. **Step 1:** `requirements.txt`를 생성하고(`PySide6`, `onnxruntime`, `opencv-python-headless`, `numpy`, `Pillow`) 패키지를 설치한다.
2. **Step 2:** `src/models.py`와 `src/detector.py`를 위 4.2절 명세대로 작성하고, 더미 이미지로 `scrfd_2.5g_bnkps.onnx` 다운로드 및 텐서 출력 형태를 검증하는 단위 테스트를 통과시킨다.
3. **Step 3:** `src/renderer.py`를 4.3절 명세대로 작성하여 국소 패치 기반 회전 타원 보케 블러와 모자이크 모드를 구현한다.
4. **Step 4:** `src/canvas_widget.py`와 `src/main_window.py`를 구현한다. 드래그 앤 드롭, 좌클릭 얼굴 토글, 빈 공간 드래그 시 수동 블러 원 추가, 우클릭 시 수동 원 삭제, 슬라이더 실시간 반영, 한글 경로 안전 저장(`cv2.imencode`)을 모두 연결한다.
5. **Step 5:** `build_exe.py` 및 `build_macos.py`를 작성하여 별도 런타임 없이 바로 실행 가능한 Windows `dist/QuickFaceBlur` 포터블 폴더·설치 파일 및 macOS `dist/QuickFaceBlur.app`·`.dmg` 빌드 명령을 제공한다.

---

## 9. 다국어 로컬라이제이션 (Localization / i18n) 명세

- **지원 언어 (8개국어):** 영어(`en`, 기본 폴백 언어), 독일어(`de`), 일본어(`ja`), 프랑스어(`fr`), 스페인어(`es`), 베트남어(`vi`), 태국어(`th`), 한국어(`ko`).
- **초기 구동 시 시스템 언어 자동 감지:** 설정값이 `system`(기본값)일 때 OS 디스플레이 언어(`QLocale.system().uiLanguages()`, Windows `GetUserDefaultUILanguage`, POSIX 환경 변수)를 감지하여 지원 언어에 자동 매핑하며, 미지원 언어 환경에서는 기본값인 영어(`en`)로 표시한다.
- **실시간 언어 변경 및 영구 저장:** 상단 툴바 `[⚙️ Settings]` 대화상자(`src/settings_dialog.py`) 및 우측 컨트롤 패널의 언어 선택기를 통해 앱 재시작 없이 전체 UI 문구·툴팁·상태바·플레이스홀더를 즉시 전환하며, 사용자별 설정 파일(`settings.json`)에 영구 저장한다.
