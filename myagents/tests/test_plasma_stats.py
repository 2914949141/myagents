"""
血浆库存小工具 — pytest 单元测试
覆盖 F1(数据加载校验)、F2(多维统计)、F3(临期预警)、F4(库存汇总)
"""

import pytest
import csv
import os
import tempfile
from datetime import date
from collections import OrderedDict

# 导入被测模块
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from plasma_stats import (
    load_csv, deduplicate,
    stats_by_station, stats_by_status, cross_table,
    stats_by_blood_type,
    find_expiring, summarize_expiring,
    build_overview, build_station_detail,
    REQUIRED_COLUMNS,
)


# ──────────────────── Fixture: 构造测试数据 ────────────────────

@pytest.fixture
def sample_rows():
    """构造小数据集（5条记录，含不同站点和状态）。
    采集日期分布：
      B001 上饶 2025-06-15 QUA   → 距2026-06-25 = 375天
      B002 上饶 2025-02-15 TRC   → 距2026-06-25 = 495天
      B003 宜春 2025-02-15 QUA   → 距2026-06-25 = 495天
      B004 宜春 2026-04-15 EXP1  → 距2026-06-25 = 71天
      B005 开阳 2026-01-10 TRC   → 距2026-06-25 = 176天
    """
    return [
        {"station_name": "上饶", "station_no": "206", "bag_no": "B001",
         "collect_time": "2025-06-15", "donor_no": "D001", "quality_status": "QUA"},
        {"station_name": "上饶", "station_no": "206", "bag_no": "B002",
         "collect_time": "2025-02-15", "donor_no": "D002", "quality_status": "TRC"},
        {"station_name": "宜春", "station_no": "205", "bag_no": "B003",
         "collect_time": "2025-02-15", "donor_no": "D003", "quality_status": "QUA"},
        {"station_name": "宜春", "station_no": "205", "bag_no": "B004",
         "collect_time": "2026-04-15", "donor_no": "D004", "quality_status": "EXP1"},
        {"station_name": "开阳", "station_no": "751", "bag_no": "B005",
         "collect_time": "2026-01-10", "donor_no": "D005", "quality_status": "TRC"},
    ]


@pytest.fixture
def sample_csv_file(sample_rows):
    """将 sample_rows 写入临时 CSV 文件，返回路径。"""
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False,
                                       encoding='utf-8', newline='')
    writer = csv.DictWriter(tmp, fieldnames=REQUIRED_COLUMNS)
    writer.writeheader()
    writer.writerows(sample_rows)
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def duplicate_rows():
    """含重复 bag_no 的数据集。"""
    return [
        {"station_name": "上饶", "station_no": "206", "bag_no": "B001",
         "collect_time": "2025-06-15", "donor_no": "D001", "quality_status": "QUA"},
        {"station_name": "上饶", "station_no": "206", "bag_no": "B001",
         "collect_time": "2025-06-15", "donor_no": "D001", "quality_status": "QUA"},
        {"station_name": "宜春", "station_no": "205", "bag_no": "B002",
         "collect_time": "2025-02-15", "donor_no": "D002", "quality_status": "TRC"},
    ]


@pytest.fixture
def missing_col_csv():
    """缺少必需列的 CSV 文件。"""
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False,
                                       encoding='utf-8', newline='')
    writer = csv.DictWriter(tmp, fieldnames=["station_name", "bag_no"])
    writer.writeheader()
    writer.writerows([
        {"station_name": "上饶", "bag_no": "B001"},
    ])
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def blood_type_csv_file():
    """含 blood_type 扩展列的 CSV 文件。"""
    columns = REQUIRED_COLUMNS + ["blood_type"]
    rows = [
        {"station_name": "上饶", "station_no": "206", "bag_no": "B001",
         "collect_time": "2025-06-15", "donor_no": "D001", "quality_status": "QUA",
         "blood_type": "A"},
        {"station_name": "宜春", "station_no": "205", "bag_no": "B002",
         "collect_time": "2025-02-15", "donor_no": "D002", "quality_status": "TRC",
         "blood_type": "O"},
        {"station_name": "开阳", "station_no": "751", "bag_no": "B003",
         "collect_time": "2026-01-10", "donor_no": "D003", "quality_status": "QUA",
         "blood_type": "A"},
    ]
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False,
                                       encoding='utf-8', newline='')
    writer = csv.DictWriter(tmp, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


# ──────────────────── F1: 数据加载与校验 ────────────────────

class TestLoadCSV:
    """测试 CSV 加载与列校验。"""

    def test_load_normal_csv(self, sample_csv_file):
        """正常加载 CSV，返回三元组 (valid_rows, invalid_rows, extra_columns)。"""
        valid_rows, invalid_rows, extra_columns = load_csv(sample_csv_file)
        assert len(valid_rows) == 5
        assert len(invalid_rows) == 0
        assert extra_columns == []

    def test_load_missing_columns_raises_value_error(self, missing_col_csv):
        """缺少必需列时，load_csv 应抛出 ValueError。"""
        with pytest.raises(ValueError):
            load_csv(missing_col_csv)

    def test_load_nonexistent_file_raises_file_not_found_error(self):
        """文件不存在时，load_csv 应抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            load_csv("/nonexistent/path/bag_info.csv")

    def test_load_with_blood_type_column(self, blood_type_csv_file):
        """含扩展列 blood_type 时，extra_columns 应包含该列。"""
        valid_rows, invalid_rows, extra_columns = load_csv(blood_type_csv_file)
        assert "blood_type" in extra_columns
        assert len(valid_rows) == 3


class TestDeduplicate:
    """测试按 bag_no 去重。"""

    def test_deduplicate_removes_duplicates(self, duplicate_rows):
        """重复 bag_no 应被去除，仅保留首条。"""
        unique_rows, dup_rows = deduplicate(duplicate_rows)
        assert len(unique_rows) == 2
        bag_nos = [r["bag_no"] for r in unique_rows]
        assert bag_nos == ["B001", "B002"]
        assert len(dup_rows) == 1

    def test_deduplicate_no_duplicates(self, sample_rows):
        """无重复数据时，去重后数量不变，重复列表为空。"""
        unique_rows, dup_rows = deduplicate(sample_rows)
        assert len(unique_rows) == 5
        assert len(dup_rows) == 0


# ──────────────────── F2: 多维统计 ────────────────────

class TestStatsByStation:
    """测试按站点统计袋数。"""

    def test_station_counts(self, sample_rows):
        """各站点袋数统计正确。"""
        result = stats_by_station(sample_rows)
        assert result == {"上饶": 2, "宜春": 2, "开阳": 1}

    def test_station_counts_empty(self):
        """空数据返回空字典。"""
        result = stats_by_station([])
        assert result == {}


class TestStatsByStatus:
    """测试按质量状态统计袋数及占比。"""

    def test_status_counts_and_ratio(self, sample_rows):
        """各状态袋数和占比正确（返回 {status: {"count": n, "ratio": "xx%"}}）。"""
        result = stats_by_status(sample_rows)
        # QUA: 2/5=40%, TRC: 2/5=40%, EXP1: 1/5=20%
        assert result["QUA"]["count"] == 2
        assert result["QUA"]["ratio"] == "40.0%"
        assert result["TRC"]["count"] == 2
        assert result["TRC"]["ratio"] == "40.0%"
        assert result["EXP1"]["count"] == 1
        assert result["EXP1"]["ratio"] == "20.0%"

    def test_status_counts_empty(self):
        """空数据时各状态 count=0, ratio=0.0%。"""
        result = stats_by_status([])
        for status in ["QUA", "TRC", "EXP1"]:
            assert result[status]["count"] == 0
            assert result[status]["ratio"] == "0.0%"


class TestCrossTable:
    """测试站点×质量状态交叉统计。"""

    def test_cross_table_values(self, sample_rows):
        """交叉表各单元格数值正确。"""
        cross = cross_table(sample_rows)
        assert cross["上饶"]["QUA"] == 1
        assert cross["上饶"]["TRC"] == 1
        assert cross["宜春"]["QUA"] == 1
        assert cross["宜春"]["EXP1"] == 1
        assert cross["开阳"]["TRC"] == 1

    def test_cross_table_empty(self):
        """空数据返回空字典。"""
        cross = cross_table([])
        assert len(cross) == 0


class TestStatsByBloodType:
    """测试血型统计。"""

    def test_blood_type_stats_with_column(self, blood_type_csv_file):
        """含 blood_type 列时，按血型统计正确。"""
        valid_rows, _, _ = load_csv(blood_type_csv_file)
        result = stats_by_blood_type(valid_rows)
        assert result["A"] == 2
        assert result["O"] == 1

    def test_blood_type_stats_without_column(self, sample_rows):
        """无 blood_type 列时，返回空字典。"""
        result = stats_by_blood_type(sample_rows)
        assert result == {}


# ──────────────────── F3: 临期预警 ────────────────────

class TestFindExpiring:
    """测试临期判定逻辑。"""

    def test_expiring_with_base_date(self, sample_rows):
        """以指定日期为基准，超过 365 天的记录被判定临期。
        base_date=2026-06-25, warn_days=365:
          B001 上饶 2025-06-15 → 375天 > 365 → 临期 ✓
          B002 上饶 2025-02-15 → 495天 > 365 → 临期 ✓
          B003 宜春 2025-02-15 → 495天 > 365 → 临期 ✓
          B004 宜春 2026-04-15 → 71天 → 不临期（但EXP1状态会被纳入）
          B005 开阳 2026-01-10 → 176天 → 不临期
        注意：EXP1 状态的记录会被 find_expiring 纳入，所以 B004 也算临期。
        共 4 条临期（3条超365天 + 1条EXP1）。
        """
        ref = date(2026, 6, 25)
        result = find_expiring(sample_rows, 365, base_date=ref)
        assert len(result) == 4
        bag_nos = {e["bag_no"] for e in result}
        assert bag_nos == {"B001", "B002", "B003", "B004"}

    def test_expiring_only_by_days(self, sample_rows):
        """仅按天数判定（不含EXP1自动纳入），warn_days=500时无超期记录。
        但 EXP1 状态仍会被纳入，所以 B004 仍算临期。
        """
        ref = date(2026, 6, 25)
        result = find_expiring(sample_rows, 500, base_date=ref)
        # B004 是 EXP1 状态，会被纳入
        assert len(result) == 1
        assert result[0]["bag_no"] == "B004"

    def test_expiring_zero_threshold(self, sample_rows):
        """阈值设为 0 时，所有有采集日期的记录都临期（days_elapsed > 0）。"""
        ref = date(2026, 6, 25)
        result = find_expiring(sample_rows, 0, base_date=ref)
        assert len(result) == 5

    def test_expiring_empty_data(self):
        """空数据返回空列表。"""
        result = find_expiring([], 365)
        assert result == []


class TestSummarizeExpiring:
    """测试临期汇总。"""

    def test_summarize_expiring(self):
        """各站点临期袋数汇总正确。"""
        expiring = [
            {"bag_no": "B001", "station_name": "上饶", "collect_time": "2025-06-15", "days_elapsed": 375},
            {"bag_no": "B002", "station_name": "上饶", "collect_time": "2025-02-15", "days_elapsed": 495},
            {"bag_no": "B003", "station_name": "宜春", "collect_time": "2025-02-15", "days_elapsed": 495},
        ]
        result = summarize_expiring(expiring)
        assert result == {"上饶": 2, "宜春": 1}

    def test_summarize_empty(self):
        """空临期清单返回空字典。"""
        result = summarize_expiring([])
        assert result == {}


# ──────────────────── F4: 库存汇总 ────────────────────

class TestBuildOverview:
    """测试库存总览。"""

    def test_overview_values(self, sample_rows):
        """总览各项数值正确。
        临期4条（B001/B002/B003超365天 + B004为EXP1），合格2，待检2，过期1。
        """
        ref = date(2026, 6, 25)
        expiring = find_expiring(sample_rows, 365, base_date=ref)
        ov = build_overview(sample_rows, len(expiring))
        assert ov["total"] == 5
        assert ov["qua"] == 2
        assert ov["trc"] == 2
        assert ov["exp1"] == 1
        assert ov["expiring"] == 4
        assert ov["station_count"] == 3
        assert ov["time_range"] == "2025-02-15 ~ 2026-04-15"

    def test_overview_empty(self):
        """空数据总览数值为 0。"""
        ov = build_overview([], 0)
        assert ov["total"] == 0
        assert ov["qua"] == 0
        assert ov["expiring"] == 0
        assert ov["time_range"] == "无数据"


class TestBuildStationDetail:
    """测试站点明细（合格率/临期率）。"""

    def test_station_detail_values(self, sample_rows):
        """各站点合格率、临期率计算正确。
        ref=2026-06-25, warn_days=365:
          上饶: 2袋, QUA=1 → 50.0%, 临期2袋(B001+B002) → 100.0%
          宜春: 2袋, QUA=1 → 50.0%, 临期2袋(B003超365天+B004为EXP1) → 100.0%
          开阳: 1袋, QUA=0 → 0.0%, 临期0袋 → 0.0%
        """
        ref = date(2026, 6, 25)
        expiring = find_expiring(sample_rows, 365, base_date=ref)
        detail = build_station_detail(sample_rows, expiring)

        shangrao = [d for d in detail if d["station_name"] == "上饶"][0]
        yichun   = [d for d in detail if d["station_name"] == "宜春"][0]
        kaiyang  = [d for d in detail if d["station_name"] == "开阳"][0]

        assert shangrao["total"] == 2
        assert shangrao["qua_rate"] == "50.0%"
        assert shangrao["exp_rate"] == "100.0%"

        assert yichun["total"] == 2
        assert yichun["qua_rate"] == "50.0%"
        assert yichun["exp_rate"] == "100.0%"

        assert kaiyang["total"] == 1
        assert kaiyang["qua_rate"] == "0.0%"
        assert kaiyang["exp_rate"] == "0.0%"

    def test_station_detail_empty(self):
        """空数据返回空列表。"""
        detail = build_station_detail([], [])
        assert detail == []
