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
