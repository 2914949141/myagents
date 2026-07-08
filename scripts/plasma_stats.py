#!/usr/bin/env python3
"""血浆库存统计脚本 — 实现 M1+M2 里程碑（P0优先级）全部功能。

数据层：load_csv, deduplicate, validate_row
业务层：stats_by_station, stats_by_status, cross_table, stats_by_blood_type,
         find_expiring, summarize_expiring, build_overview, build_station_detail
展示层：_print_table, print_overview, print_station_stats, print_status_stats,
         print_cross_table, print_expiring, print_station_detail
"""

import csv
import datetime
import argparse
import os
from collections import Counter, defaultdict, OrderedDict
from typing import List, Dict, Tuple, Optional, Any


# ============================================================================
# 数据层 — 加载、校验、去重
# ============================================================================

REQUIRED_COLUMNS = [
    "station_name", "station_no", "bag_no",
    "collect_time", "donor_no", "quality_status",
]

VALID_STATUSES = {"QUA", "TRC", "EXP1"}

STATUS_LABELS = {
    "QUA": "合格",
    "TRC": "待检",
    "EXP1": "过期/临期",
}


def load_csv(path: str) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[str]]:
    """加载 CSV 文件，校验必需列，逐行校验数据合法性。

    Args:
        path: CSV 文件路径。

    Returns:
        (valid_rows, invalid_rows, extra_columns)
        - valid_rows: 校验通过的合法行列表
        - invalid_rows: 不合规行列表（含原因标注）
        - extra_columns: 自动发现的扩展列名列表
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"数据文件不存在: {path}")

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        # F1.1 必需列校验
        missing = [c for c in REQUIRED_COLUMNS if c not in headers]
        if missing:
            raise ValueError(f"缺少必需列: {missing}")

        # F1.2 扩展列自动发现
        extra_columns = [c for c in headers if c not in REQUIRED_COLUMNS]

        valid_rows: List[Dict[str, str]] = []
        invalid_rows: List[Dict[str, str]] = []

        for row in reader:
            reason = _validate_row(row)
            if reason:
                row["_invalid_reason"] = reason
                invalid_rows.append(row)
            else:
                valid_rows.append(row)

    return valid_rows, invalid_rows, extra_columns


def _validate_row(row: Dict[str, str]) -> Optional[str]:
    """校验单行数据的合法性，返回不合规原因或 None。

    Args:
        row: 原始行字典。

    Returns:
        不合规原因字符串；合规则返回 None。
    """
    # bag_no 非空
    if not row.get("bag_no", "").strip():
        return "bag_no 为空"

    # collect_time 格式 YYYY-MM-DD
    ct = row.get("collect_time", "").strip()
    try:
        datetime.datetime.strptime(ct, "%Y-%m-%d")
    except ValueError:
        return f"collect_time 格式非法: '{ct}'"

    # quality_status 属于枚举
    qs = row.get("quality_status", "").strip()
    if qs not in VALID_STATUSES:
        return f"quality_status 非法: '{qs}'"

    return None


def deduplicate(rows: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """按 bag_no 去重，保留首次出现记录，后续重复行输出到警告清单。

    Args:
        rows: 合法行列表。

    Returns:
        (unique_rows, duplicate_rows)
        - unique_rows: 去重后的行列表
        - duplicate_rows: 被去除的重复行列表
    """
    seen: Dict[str, Dict[str, str]] = OrderedDict()
    duplicate_rows: List[Dict[str, str]] = []

    for row in rows:
        bag_no = row["bag_no"].strip()
        if bag_no in seen:
            row["_duplicate_of"] = bag_no
            duplicate_rows.append(row)
        else:
            seen[bag_no] = row

    return list(seen.values()), duplicate_rows


# ============================================================================
# 业务层 — 多维统计与临期预警
# ============================================================================

def stats_by_station(rows: List[Dict[str, str]]) -> Dict[str, int]:
    """按站点统计袋数。

    Args:
        rows: 去重后的合法行列表。

    Returns:
        {站点名: 袋数} 字典。
    """
    counter: Counter = Counter()
    for row in rows:
        counter[row["station_name"]] += 1
    return dict(counter)


def stats_by_status(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
    """按质量状态统计袋数及占比。

    Args:
        rows: 去重后的合法行列表。

    Returns:
        {状态码: {"count": 袋数, "ratio": 占比字符串}} 字典。
    """
    total = len(rows)
    counter: Counter = Counter()
    for row in rows:
        counter[row["quality_status"]] += 1

    result: Dict[str, Dict[str, Any]] = {}
    for status in VALID_STATUSES:
        cnt = counter.get(status, 0)
        ratio = f"{cnt / total * 100:.1f}%" if total > 0 else "0.0%"
        result[status] = {"count": cnt, "ratio": ratio}
    return result


def cross_table(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, int]]:
    """站点×质量状态交叉表。

    Args:
        rows: 去重后的合法行列表。

    Returns:
        {站点名: {状态码: 数量}} 二级字典。
    """
    table: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        table[row["station_name"]][row["quality_status"]] += 1
    # 转为普通 dict
    return {k: dict(v) for k, v in table.items()}


def stats_by_blood_type(rows: List[Dict[str, str]]) -> Dict[str, int]:
    """按血型统计袋数（仅当数据源含 blood_type 列时调用）。

    Args:
        rows: 去重后的合法行列表，需含 blood_type 字段。

    Returns:
        {血型: 袋数} 字典。
    """
    counter: Counter = Counter()
    for row in rows:
        bt = row.get("blood_type", "").strip()
        if bt:
            counter[bt] += 1
    return dict(counter)


def find_expiring(
    rows: List[Dict[str, str]],
    warn_days: int = 365,
    base_date: Optional[datetime.date] = None,
) -> List[Dict[str, Any]]:
    """查找采集日期距今超过 warn_days 的血浆袋清单。

    同时纳入 quality_status 为 EXP1 的记录。

    Args:
        rows: 去重后的合法行列表。
        warn_days: 临期判定天数阈值，默认 365。
        base_date: 计算基准日期，默认取当前系统日期。

    Returns:
        临期行列表，每行增加 "days_elapsed" 和 "is_expiring" 字段。
    """
    if base_date is None:
        base_date = datetime.date.today()

    expiring: List[Dict[str, Any]] = []
    for row in rows:
        collect_dt = datetime.datetime.strptime(row["collect_time"], "%Y-%m-%d").date()
        days_elapsed = (base_date - collect_dt).days
        is_expiring = days_elapsed > warn_days or row["quality_status"] == "EXP1"
        if is_expiring:
            enriched = dict(row)
            enriched["days_elapsed"] = days_elapsed
            enriched["is_expiring"] = True
            expiring.append(enriched)
    return expiring


def summarize_expiring(expiring_rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """按站点汇总临期袋数。

    Args:
        expiring_rows: find_expiring 返回的临期行列表。

    Returns:
        {站点名: 临期袋数} 字典。
    """
    counter: Counter = Counter()
    for row in expiring_rows:
        counter[row["station_name"]] += 1
    return dict(counter)


def build_overview(
    rows: List[Dict[str, str]],
    expiring_count: int,
) -> Dict[str, Any]:
    """构建库存总览数据。

    Args:
        rows: 去重后的合法行列表。
        expiring_count: 临期袋数。

    Returns:
        总览字典，含 total/qua/trc/exp1/expiring/station_count/time_range 等字段。
    """
    total = len(rows)
    qua = sum(1 for r in rows if r["quality_status"] == "QUA")
    trc = sum(1 for r in rows if r["quality_status"] == "TRC")
    exp1 = sum(1 for r in rows if r["quality_status"] == "EXP1")

    station_set = set(r["station_name"] for r in rows)
    station_count = len(station_set)

    dates = [datetime.datetime.strptime(r["collect_time"], "%Y-%m-%d").date() for r in rows]
    time_range = f"{min(dates)} ~ {max(dates)}" if dates else "无数据"

    return {
        "total": total,
        "qua": qua,
        "trc": trc,
        "exp1": exp1,
        "expiring": expiring_count,
        "station_count": station_count,
        "time_range": time_range,
    }


def build_station_detail(
    rows: List[Dict[str, str]],
    expiring_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """构建站点明细数据（袋数/合格率/临期率）。

    Args:
        rows: 去重后的合法行列表。
        expiring_rows: find_expiring 返回的临期行列表。

    Returns:
        站点明细列表，每项含 station_name/total/qua/trc/exp1/expiring/qua_rate/exp_rate 字段。
    """
    station_total: Dict[str, int] = defaultdict(int)
    station_qua: Dict[str, int] = defaultdict(int)
    station_trc: Dict[str, int] = defaultdict(int)
    station_exp1: Dict[str, int] = defaultdict(int)

    for row in rows:
        sn = row["station_name"]
        station_total[sn] += 1
        qs = row["quality_status"]
        if qs == "QUA":
            station_qua[sn] += 1
        elif qs == "TRC":
            station_trc[sn] += 1
        elif qs == "EXP1":
            station_exp1[sn] += 1

    expiring_by_station = summarize_expiring(expiring_rows)

    detail: List[Dict[str, Any]] = []
    for sn in sorted(station_total.keys()):
        t = station_total[sn]
        q = station_qua[sn]
        e1 = station_exp1[sn]
        exp_cnt = expiring_by_station.get(sn, 0)
        qua_rate = f"{q / t * 100:.1f}%" if t > 0 else "0.0%"
        exp_rate = f"{exp_cnt / t * 100:.1f}%" if t > 0 else "0.0%"
        detail.append({
            "station_name": sn,
            "total": t,
            "qua": q,
            "trc": station_trc[sn],
            "exp1": e1,
            "expiring": exp_cnt,
            "qua_rate": qua_rate,
            "exp_rate": exp_rate,
        })
    return detail


# ============================================================================
# 展示层 — ASCII 表格打印
# ============================================================================

def _print_table(headers: List[str], rows: List[List[str]], title: str = "") -> None:
    """ASCII 对齐表格打印。

    Args:
        headers: 表头列表。
        rows: 表体行列表，每行为字符串列表。
        title: 表格标题，可选。
    """
    if title:
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}")

    if not headers and not rows:
        print("（无数据）")
        return

    # 计算每列最大宽度
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))
            else:
                col_widths.append(len(str(cell)))

    # 格式化函数
    def fmt(cells: List[str]) -> str:
        parts = []
        for i, w in enumerate(col_widths):
            c = str(cells[i]) if i < len(cells) else ""
            parts.append(c.ljust(w))
        return " | ".join(parts)

    sep = "-+-".join("-" * w for w in col_widths)

    print(fmt(headers))
    print(sep)
    for row in rows:
        print(fmt(row))
    print()


def print_overview(overview: Dict[str, Any]) -> None:
    """打印库存总览表。

    Args:
        overview: build_overview 返回的总览字典。
    """
    total = overview["total"]
    headers = ["指标", "数量", "占比"]
    rows = [
        ["总袋数", str(overview["total"]), "100.0%"],
        ["合格(QUA)", str(overview["qua"]),
         f"{overview['qua'] / total * 100:.1f}%" if total else "0.0%"],
        ["待检(TRC)", str(overview["trc"]),
         f"{overview['trc'] / total * 100:.1f}%" if total else "0.0%"],
        ["过期/临期(EXP1)", str(overview["exp1"]),
         f"{overview['exp1'] / total * 100:.1f}%" if total else "0.0%"],
        ["临期预警袋数", str(overview["expiring"]),
         f"{overview['expiring'] / total * 100:.1f}%" if total else "0.0%"],
        ["站点数", str(overview["station_count"]), "-"],
        ["采集时间范围", overview["time_range"], "-"],
    ]
    _print_table(headers, rows, title="库存总览")


def print_station_stats(station_stats: Dict[str, int]) -> None:
    """打印按站点统计表。

    Args:
        station_stats: stats_by_station 返回的字典。
    """
    headers = ["站点", "袋数"]
    rows = [[sn, str(cnt)] for sn, cnt in sorted(station_stats.items(), key=lambda x: -x[1])]
    _print_table(headers, rows, title="按站点统计")


def print_status_stats(status_stats: Dict[str, Dict[str, Any]]) -> None:
    """打印按质量状态统计表。

    Args:
        status_stats: stats_by_status 返回的字典。
    """
    headers = ["状态", "含义", "袋数", "占比"]
    rows = []
    for status in ["QUA", "TRC", "EXP1"]:
        info = status_stats.get(status, {"count": 0, "ratio": "0.0%"})
        rows.append([status, STATUS_LABELS.get(status, ""), str(info["count"]), info["ratio"]])
    _print_table(headers, rows, title="按质量状态统计")


def print_cross_table(cross: Dict[str, Dict[str, int]]) -> None:
    """打印站点×质量状态交叉表。

    Args:
        cross: cross_table 返回的二级字典。
    """
    status_order = ["QUA", "TRC", "EXP1"]
    headers = ["站点"] + status_order + ["合计"]
    rows = []
    for sn in sorted(cross.keys()):
        row_data = cross[sn]
        line = [sn]
        total = 0
        for s in status_order:
            v = row_data.get(s, 0)
            line.append(str(v))
            total += v
        line.append(str(total))
        rows.append(line)
    _print_table(headers, rows, title="站点 × 质量状态 交叉表")


def print_expiring(expiring_rows: List[Dict[str, Any]]) -> None:
    """打印临期预警清单。

    Args:
        expiring_rows: find_expiring 返回的临期行列表。
    """
    if not expiring_rows:
        print("\n✅ 无临期预警血浆")
        return

    headers = ["站点", "袋号", "采集日期", "距今天数", "质量状态"]
    rows = []
    for row in expiring_rows:
        rows.append([
            row["station_name"],
            row["bag_no"],
            row["collect_time"],
            str(row["days_elapsed"]),
            row["quality_status"],
        ])
    _print_table(headers, rows, title="⚠ 临期预警清单")


def print_station_detail(detail: List[Dict[str, Any]]) -> None:
    """打印站点明细表。

    Args:
        detail: build_station_detail 返回的列表。
    """
    headers = ["站点", "袋数", "合格", "待检", "过期/临期", "临期预警", "合格率", "临期率"]
    rows = []
    for d in detail:
        rows.append([
            d["station_name"],
            str(d["total"]),
            str(d["qua"]),
            str(d["trc"]),
            str(d["exp1"]),
            str(d["expiring"]),
            d["qua_rate"],
            d["exp_rate"],
        ])
    _print_table(headers, rows, title="站点明细")


def print_blood_type_hint() -> None:
    """当数据源不含 blood_type 列时，输出提示信息。"""
    print("\n⚠ 血型数据暂缺，待数据源补充 `blood_type` 列后自动启用")


def print_blood_type_stats(bt_stats: Dict[str, int]) -> None:
    """打印血型统计表。

    Args:
        bt_stats: stats_by_blood_type 返回的字典。
    """
    headers = ["血型", "袋数"]
    rows = [[bt, str(cnt)] for bt, cnt in sorted(bt_stats.items(), key=lambda x: -x[1])]
    _print_table(headers, rows, title="按血型统计")


def print_warnings(
    invalid_rows: List[Dict[str, str]],
    duplicate_rows: List[Dict[str, str]],
) -> None:
    """输出异常行与重复行警告清单。

    Args:
        invalid_rows: 校验不合规行列表。
        duplicate_rows: 去重时被移除的重复行列表。
    """
    if invalid_rows:
        headers = ["行号(顺序)", "bag_no", "异常原因"]
        rows = []
        for i, row in enumerate(invalid_rows, 1):
            rows.append([str(i), row.get("bag_no", ""), row.get("_invalid_reason", "")])
        _print_table(headers, rows, title="⚠ 异常行警告清单")

    if duplicate_rows:
        headers = ["行号(顺序)", "bag_no", "重复标识"]
        rows = []
        for i, row in enumerate(duplicate_rows, 1):
            rows.append([str(i), row.get("bag_no", ""), row.get("_duplicate_of", "")])
        _print_table(headers, rows, title="⚠ 重复行警告清单")

    if not invalid_rows and not duplicate_rows:
        print("\n✅ 数据校验通过，无异常行或重复行")


# ============================================================================
# 主入口 — 命令行参数解析与流程编排
# ============================================================================

def parse_args() -> argparse.Namespace:
    """解析命令行参数。

    Returns:
        argparse.Namespace 对象。
    """
    parser = argparse.ArgumentParser(
        description="血浆库存统计工具 — 自动统计、临期预警、报表输出",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--file",
        type=str,
        default="data/bag_info.csv",
        help="数据源 CSV 文件路径（默认: data/bag_info.csv）",
    )
    parser.add_argument(
        "--warn-days",
        type=int,
        default=365,
        help="临期判定天数阈值（默认: 365）",
    )
    parser.add_argument(
        "--base-date",
        type=str,
        default=None,
        help="临期计算基准日期 YYYY-MM-DD（默认: 今日）",
    )
    parser.add_argument(
        "--station",
        type=str,
        default=None,
        help="筛选指定站点名称（仅统计该站点数据）",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="统计起始采集日期 YYYY-MM-DD",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="统计截止采集日期 YYYY-MM-DD",
    )
    parser.add_argument(
        "--enable-blood-type",
        type=str,
        default="auto",
        choices=["auto", "yes", "no"],
        help="血型统计开关: auto=自动检测列, yes=强制启用, no=禁用（默认: auto）",
    )
    return parser.parse_args()


def main() -> None:
    """主流程：加载 → 校验 → 去重 → 筛选 → 统计 → 预警 → 输出。"""
    args = parse_args()

    # ---- 数据加载与校验 ----
    try:
        valid_rows, invalid_rows, extra_columns = load_csv(args.file)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ 加载失败: {e}")
        return

    # ---- 去重 ----
    unique_rows, duplicate_rows = deduplicate(valid_rows)

    # ---- 输出校验警告 ----
    print_warnings(invalid_rows, duplicate_rows)

    # ---- 站点筛选 ----
    if args.station:
        unique_rows = [r for r in unique_rows if r["station_name"] == args.station]
        print(f"\n🔍 已筛选站点: {args.station}（剩余 {len(unique_rows)} 条记录）")

    # ---- 时间范围筛选 ----
    if args.start_date:
        sd = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
        unique_rows = [r for r in unique_rows
                       if datetime.datetime.strptime(r["collect_time"], "%Y-%m-%d").date() >= sd]
        print(f"🔍 起始日期筛选: >= {args.start_date}（剩余 {len(unique_rows)} 条记录）")
    if args.end_date:
        ed = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date()
        unique_rows = [r for r in unique_rows
                       if datetime.datetime.strptime(r["collect_time"], "%Y-%m-%d").date() <= ed]
        print(f"🔍 截止日期筛选: <= {args.end_date}（剩余 {len(unique_rows)} 条记录）")

    if not unique_rows:
        print("\n⚠ 筛选后无数据，退出统计")
        return

    # ---- 基准日期 ----
    base_date: Optional[datetime.date] = None
    if args.base_date:
        base_date = datetime.datetime.strptime(args.base_date, "%Y-%m-%d").date()

    # ---- 多维统计 ----
    station_stats = stats_by_station(unique_rows)
    status_stats = stats_by_status(unique_rows)
    cross = cross_table(unique_rows)

    # ---- 血型统计 ----
    has_blood_type = "blood_type" in extra_columns
    enable_bt = args.enable_blood_type
    show_blood_type = False
    if enable_bt == "auto" and has_blood_type:
        show_blood_type = True
    elif enable_bt == "yes":
        show_blood_type = True
        if not has_blood_type:
            print("\n⚠ 强制启用血型统计，但数据源不含 blood_type 列，统计结果将为空")

    if show_blood_type:
        bt_stats = stats_by_blood_type(unique_rows)
        print_blood_type_stats(bt_stats)
    else:
        print_blood_type_hint()

    # ---- 临期预警 ----
    expiring_rows = find_expiring(unique_rows, warn_days=args.warn_days, base_date=base_date)
    expiring_summary = summarize_expiring(expiring_rows)

    # ---- 库存汇总报表 ----
    overview = build_overview(unique_rows, len(expiring_rows))
    station_detail = build_station_detail(unique_rows, expiring_rows)

    # ---- 输出 ----
    print_overview(overview)
    print_station_stats(station_stats)
    print_status_stats(status_stats)
    print_cross_table(cross)
    print_expiring(expiring_rows)
    print_station_detail(station_detail)

    # ---- 临期汇总 ----
    if expiring_summary:
        headers = ["站点", "临期袋数"]
        rows = [[sn, str(cnt)] for sn, cnt in sorted(expiring_summary.items(), key=lambda x: -x[1])]
        _print_table(headers, rows, title="临期汇总（按站点）")


if __name__ == "__main__":
    main()
