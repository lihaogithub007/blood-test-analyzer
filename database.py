from __future__ import annotations
import sqlite3
import os
from typing import List, Dict, Optional
import re

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "blood_test.db")

_NAME_SPLIT_RE = re.compile(r"\s*[-—]\s*")

_PAREN_RE = re.compile(r"[（(].*?[)）]")
_NON_ALNUM_RE = re.compile(r"[^0-9a-zA-Z\u4e00-\u9fff%#/]+")


def _norm_key(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    # 去掉括号内容（常见如 (NE%)、(WBC)）
    s = _PAREN_RE.sub("", s)
    s = s.replace("％", "%").replace("＃", "#")
    s = s.replace("—", "-").replace("－", "-")
    s = s.replace("计数", "").replace("含量", "")
    s = _NON_ALNUM_RE.sub("", s)
    return s.lower()


def normalize_item_name(name: str) -> str:
    """
    将报告中的指标名规范化，便于聚合展示。
    例：'白细胞-WBC' -> '白细胞'，'红细胞体积分布宽度-(RDW-CV)' -> '红细胞体积分布宽度'
    """
    if not name:
        return name
    raw = name.strip()
    base = _NAME_SPLIT_RE.split(raw, maxsplit=1)[0].strip()
    base = base or raw

    k = _norm_key(base)

    # ---- CBC 常用字段映射（跨医院统一到同一列/同一条趋势） ----
    # 有些医院会加前缀（如 HR白细胞/WBC），这里优先用“包含关键中文名”的规则兜底
    if "白细胞" in k or k in ("wbc", "whitebloodcell", "whitebloodcells", "白细胞数"):
        return "白细胞"

    # 血细胞比容
    if (
        k in ("hct", "hematocrit", "红细胞压积", "血细胞比容")
        or "红细胞比容" in k
        or "血细胞比容" in k
    ):
        return "红细胞压积"

    # 血小板
    if "血小板" in k or k in ("plt", "platelet", "platelets"):
        return "血小板"

    # 中性粒细胞（嗜中性）绝对值 / 比例
    if "neut" in k or "neu" in k or "中性粒细胞" in k or "嗜中性" in k:
        if "#" in k or "绝对值" in k or "abs" in k or "绝对" in k:
            return "嗜中性粒细胞绝对值"
        if "%" in k or "比例" in k or "百分比" in k or "percent" in k or "pct" in k:
            return "嗜中性粒细胞比例"

    # 淋巴细胞绝对值 / 比例
    if "ly" in k or "lym" in k or "lymph" in k or "淋巴细胞" in k:
        if "#" in k or "绝对值" in k or "abs" in k:
            return "淋巴细胞绝对值"
        if "%" in k or "比例" in k or "百分比" in k or "percent" in k or "pct" in k:
            return "淋巴细胞比例"

    # 单核细胞绝对值 / 比例
    if "mo" in k or "mono" in k or "单核细胞" in k:
        if "#" in k or "绝对值" in k or "abs" in k:
            return "单核细胞绝对值"
        if "%" in k or "比例" in k or "百分比" in k or "percent" in k or "pct" in k:
            return "单核细胞比例"

    # 嗜酸细胞绝对值 / 比例
    if "eo" in k or "eos" in k or "嗜酸" in k or "嗜酸性粒细胞" in k:
        if "#" in k or "绝对值" in k or "abs" in k:
            return "嗜酸性粒细胞绝对值"
        if "%" in k or "比例" in k or "百分比" in k or "percent" in k or "pct" in k:
            return "嗜酸性粒细胞比例"

    # 嗜碱细胞绝对值 / 比例
    if "ba" in k or "baso" in k or "嗜碱" in k or "嗜碱性粒细胞" in k:
        if "#" in k or "绝对值" in k or "abs" in k:
            return "嗜碱性粒细胞绝对值"
        if "%" in k or "比例" in k or "百分比" in k or "percent" in k or "pct" in k:
            return "嗜碱性粒细胞比例"

    # RDW（有些医院写 RDW-CV / RDW-SD）
    if "rdw" in k or "红细胞体积分布宽度" in k:
        if "sd" in k:
            return "红细胞体积分布宽度SD"
        if "cv" in k:
            return "红细胞体积分布宽度CV"
        return "红细胞体积分布宽度"

    # MCV/MCH/MCHC
    if k in ("mcv",) or "平均红细胞体积" in k:
        return "平均红细胞体积"
    if k in ("mch",) or "平均红细胞血红蛋白量" in k:
        return "平均红细胞血红蛋白量"
    if k in ("mchc",) or "平均红细胞血红蛋白浓度" in k:
        return "平均红细胞血红蛋白浓度"

    # 血红蛋白（放在 MCH/MCHC 之后，避免把“平均红细胞血红蛋白量/浓度”误归并）
    if (
        k in ("hgb", "hb", "hemoglobin")
        or (
            "血红蛋白" in k
            and "平均" not in k
            and "浓度" not in k
            and "含量" not in k
            and "mch" not in k
            and "mchc" not in k
        )
    ):
        return "血红蛋白"

    # 红细胞（放在 MCV/MCH/MCHC/HCT/RDW 等规则之后，避免误归类）
    # 只接受 RBC/红细胞数 及“纯红细胞”命名，排除平均值、血红蛋白相关、压积、分布宽度
    if (
        k in ("rbc", "redbloodcell", "红细胞数")
        or (
            "红细胞" in k
            and "平均" not in k
            and "血红蛋白" not in k
            and "分布宽度" not in k
            and "压积" not in k
            and "比容" not in k
            and "hct" not in k
            and "hematocrit" not in k
            and "体积" not in k
            and "浓度" not in k
            and "含量" not in k
        )
    ):
        return "红细胞"

    # 兜底：仍保留原本的“-”分割规范化效果
    return base.strip()


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sex TEXT,
            birthday DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER REFERENCES patients(id) ON DELETE SET NULL,
            filename TEXT NOT NULL,
            report_date DATE NOT NULL,
            report_type TEXT NOT NULL DEFAULT 'cbc',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS test_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            value REAL,
            unit TEXT,
            ref_low REAL,
            ref_high REAL
        );
        CREATE TABLE IF NOT EXISTS report_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            section TEXT,
            key TEXT NOT NULL,
            value_text TEXT,
            value_num REAL,
            unit TEXT,
            ref_low REAL,
            ref_high REAL
        );
    """)
    # 兼容旧库：给 reports 表补列（尽量不破坏已有数据）
    if not _table_has_column(conn, "reports", "patient_id"):
        conn.execute("ALTER TABLE reports ADD COLUMN patient_id INTEGER REFERENCES patients(id) ON DELETE SET NULL")
    if not _table_has_column(conn, "reports", "report_type"):
        conn.execute("ALTER TABLE reports ADD COLUMN report_type TEXT NOT NULL DEFAULT 'cbc'")
    # 将旧数据归档到默认病人名下（如果 patient_id 为空）
    default_pid = _ensure_patient_by_name(conn, "刘晨曦")
    conn.execute(
        "UPDATE reports SET patient_id = ? WHERE patient_id IS NULL",
        (default_pid,),
    )

    # 同人同日同类型唯一：避免重复数据（上传时覆盖）
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_patient_date_type ON reports(patient_id, report_date, report_type)"
    )
    conn.commit()
    conn.close()


def _ensure_patient_by_name(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM patients WHERE name = ? ORDER BY id ASC LIMIT 1", (name,)).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute("INSERT INTO patients (name) VALUES (?)", (name,))
    return int(cur.lastrowid)


def ensure_default_patient() -> int:
    """确保存在一个默认病人（用于兼容旧数据）"""
    conn = _get_conn()
    pid = _ensure_patient_by_name(conn, "刘晨曦")
    conn.commit()
    conn.close()
    return pid


def list_patients() -> List[Dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, name, sex, birthday, created_at FROM patients ORDER BY created_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_patient(name: str, sex: Optional[str] = None, birthday: Optional[str] = None) -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO patients (name, sex, birthday) VALUES (?, ?, ?)",
        (name, sex, birthday),
    )
    pid = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return pid


def save_report(filename: str, report_date: str, items: List[Dict], patient_id: Optional[int] = None, report_type: str = "cbc") -> int:
    """保存报告和指标，返回报告 ID"""
    conn = _get_conn()
    if patient_id is None:
        patient_id = ensure_default_patient()

    # 同人同日同类型：先删旧的，再写新的（覆盖）
    _delete_reports_by_key(conn, patient_id, report_date, report_type)

    cursor = conn.execute(
        "INSERT INTO reports (patient_id, filename, report_date, report_type) VALUES (?, ?, ?, ?)",
        (patient_id, filename, report_date, report_type),
    )
    report_id = cursor.lastrowid

    for item in items:
        conn.execute(
            "INSERT INTO test_items (report_id, name, value, unit, ref_low, ref_high) VALUES (?, ?, ?, ?, ?, ?)",
            (report_id, item["name"], item.get("value"), item.get("unit"), item.get("ref_low"), item.get("ref_high")),
        )

    conn.commit()
    conn.close()
    return report_id


def _delete_reports_by_key(conn: sqlite3.Connection, patient_id: int, report_date: str, report_type: str) -> int:
    """
    删除同人同日同类型的旧报告（级联删除 test_items/report_facts）。
    返回删除的 reports 行数。
    """
    rows = conn.execute(
        "SELECT id FROM reports WHERE patient_id = ? AND report_date = ? AND report_type = ?",
        (patient_id, report_date, report_type),
    ).fetchall()
    if not rows:
        return 0
    ids = [int(r["id"]) for r in rows]
    # 逐条删除，触发 ON DELETE CASCADE
    deleted = 0
    for rid in ids:
        cur = conn.execute("DELETE FROM reports WHERE id = ?", (rid,))
        deleted += cur.rowcount
    return deleted


def save_report_facts(report_id: int, facts: List[Dict]) -> None:
    """保存结构化结论/关键字段（用于骨穿/腰穿/流式/分子/影像等）"""
    if not facts:
        return
    conn = _get_conn()
    for f in facts:
        conn.execute(
            "INSERT INTO report_facts (report_id, section, key, value_text, value_num, unit, ref_low, ref_high) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                report_id,
                f.get("section"),
                f.get("key"),
                f.get("value_text"),
                f.get("value_num"),
                f.get("unit"),
                f.get("ref_low"),
                f.get("ref_high"),
            ),
        )
    conn.commit()
    conn.close()


def get_report_facts(report_id: int) -> List[Dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT section, key, value_text, value_num, unit, ref_low, ref_high FROM report_facts WHERE report_id = ? ORDER BY id ASC",
        (report_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_reports_with_facts(patient_id: Optional[int] = None, report_type: Optional[str] = None) -> List[Dict]:
    """用于时间轴展示：返回报告 + facts（不返回 test_items，避免体积过大）"""
    reports = get_all_reports(patient_id=patient_id, report_type=report_type)
    for r in reports:
        r["facts"] = get_report_facts(r["id"])
    return reports


def get_all_reports(patient_id: Optional[int] = None, report_type: Optional[str] = None) -> List[Dict]:
    """获取所有报告列表"""
    conn = _get_conn()
    where = []
    params: List[object] = []
    if patient_id is not None:
        where.append("patient_id = ?")
        params.append(patient_id)
    if report_type is not None:
        where.append("report_type = ?")
        params.append(report_type)
    sql = "SELECT id, patient_id, report_type, filename, report_date, created_at FROM reports"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY report_date DESC, id DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_chart_data(patient_id: Optional[int] = None, report_type: Optional[str] = None) -> dict:
    """
    获取折线图数据：按指标名分组，每组包含日期和数值序列
    返回: {"指标名": [{"date": "2024-01-01", "value": 5.2, "ref_low": 3.5, "ref_high": 9.5}, ...]}
    """
    conn = _get_conn()
    where = []
    params: List[object] = []
    if patient_id is not None:
        where.append("r.patient_id = ?")
        params.append(patient_id)
    if report_type is not None:
        where.append("r.report_type = ?")
        params.append(report_type)

    sql = """
        SELECT ti.name, r.report_date, ti.value, ti.ref_low, ti.ref_high, ti.unit
        FROM test_items ti
        JOIN reports r ON ti.report_id = r.id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY r.report_date ASC, ti.name"
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    result: Dict[str, Dict] = {}
    for row in rows:
        name = normalize_item_name(row["name"])
        if name not in result:
            result[name] = {
                "unit": row["unit"],
                "ref_low": row["ref_low"],
                "ref_high": row["ref_high"],
                "data": [],
            }
        else:
            # 兼容同名指标在不同报告里单位/参考范围偶发缺失的情况：尽量补全
            if result[name].get("unit") is None and row["unit"] is not None:
                result[name]["unit"] = row["unit"]
            if result[name].get("ref_low") is None and row["ref_low"] is not None:
                result[name]["ref_low"] = row["ref_low"]
            if result[name].get("ref_high") is None and row["ref_high"] is not None:
                result[name]["ref_high"] = row["ref_high"]
        result[name]["data"].append({
            "date": row["report_date"],
            "value": row["value"],
        })

    return result


def delete_report(report_id: int) -> bool:
    """删除报告及其所有指标"""
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_report_detail(report_id: int) -> Optional[Dict]:
    """获取单个报告的详细信息"""
    conn = _get_conn()
    report = conn.execute(
        "SELECT id, patient_id, report_type, filename, report_date, created_at FROM reports WHERE id = ?",
        (report_id,),
    ).fetchone()
    if not report:
        conn.close()
        return None

    items = conn.execute(
        "SELECT name, value, unit, ref_low, ref_high FROM test_items WHERE report_id = ?",
        (report_id,),
    ).fetchall()
    conn.close()

    result = dict(report)
    result["items"] = [{**dict(i), "display_name": normalize_item_name(i["name"])} for i in items]
    result["facts"] = get_report_facts(report_id)
    return result
