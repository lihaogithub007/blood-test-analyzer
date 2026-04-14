from database import normalize_item_name


def test_normalize_item_name_splits_dash():
    assert normalize_item_name("白细胞-WBC") == "白细胞"
    assert normalize_item_name("白细胞 — WBC") == "白细胞"


def test_normalize_item_name_neut_absolute():
    assert normalize_item_name("NEUT#") == "嗜中性粒细胞绝对值"
    assert normalize_item_name("嗜中性粒细胞绝对值") == "嗜中性粒细胞绝对值"


def test_normalize_item_name_neut_percent():
    assert normalize_item_name("NEUT%") == "嗜中性粒细胞比例"


def test_normalize_item_name_avoid_rbc_rdw_collision():
    assert normalize_item_name("红细胞体积分布宽度-(RDW-CV)") == "红细胞体积分布宽度CV"
    assert normalize_item_name("红细胞") == "红细胞"

