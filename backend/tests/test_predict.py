"""머리 검출 지원 — 기준점(몸 = 발 위치, 머리 = 박스 중심)과 가중치 클래스 해석."""
import pytest
from shapely.geometry import Polygon

from cv_api.predict import DetectorNotReady, compute_occupancy, resolve_target

# ROI: 화면 위쪽 절반 (y 0~100)
ROI = Polygon([(0, 0), (200, 0), (200, 100), (0, 100)])


def test_head_box_counts_by_center_person_box_by_foot():
    # 머리 박스는 ROI 안(중심 y=50), 몸 박스로 보면 발 위치(y=140)가 ROI 밖
    box = (40.0, 20.0, 60.0, 140.0, 0.9)
    assert compute_occupancy([box], ROI, capacity=10, count_conf_min=0.4).persons_in_roi == 0
    occ = compute_occupancy([box], ROI, capacity=10, count_conf_min=0.4, target="head")
    assert occ.persons_in_roi == 1
    assert occ.foot_points_in_roi == [(50.0, 80.0)]


def test_head_count_respects_conf_and_capacity():
    heads = [(10.0 * i, 10.0, 10.0 * i + 8, 18.0, 0.8) for i in range(12)] + [(5.0, 50.0, 13.0, 58.0, 0.3)]
    occ = compute_occupancy(heads, ROI, capacity=10, count_conf_min=0.4, target="head")
    assert occ.persons_in_roi == 12
    assert occ.occupied_area_ratio == 100.0 and occ.over_capacity


@pytest.mark.parametrize(
    "names,wanted,expected",
    [
        ({0: "person", 1: "bicycle"}, "auto", ("person", 0)),   # COCO
        ({0: "head"}, "auto", ("head", 0)),                      # scripts/train 머리 가중치
        ({0: "person", 1: "head"}, "auto", ("head", 1)),
        ({0: "person", 1: "head"}, "person", ("person", 0)),
        ({}, "auto", ("person", 0)),                             # 이름 없음 → MODEL_PERSON_CLASS_ID
    ],
)
def test_resolve_target(names, wanted, expected):
    assert resolve_target(names, wanted, 0) == expected


def test_resolve_target_missing_class_is_not_ready():
    with pytest.raises(DetectorNotReady):
        resolve_target({0: "person"}, "head", 0)
