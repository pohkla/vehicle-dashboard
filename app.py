from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

DB_PATH = Path("vehicle_dashboard.db")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-this-token")

app = FastAPI(title="Vehicle Dashboard v3.3 Replace All")


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL,
                date_text TEXT NOT NULL,
                iso_date TEXT NOT NULL,
                vehicle_type TEXT NOT NULL,
                vehicle_title TEXT NOT NULL,
                icon TEXT NOT NULL,
                company TEXT,
                item TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weekly_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_key TEXT NOT NULL UNIQUE,
                car_amount INTEGER NOT NULL DEFAULT 0,
                motorcycle_amount INTEGER NOT NULL DEFAULT 0,
                total_amount INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_records_iso_date ON daily_records(iso_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_records_vehicle_type ON daily_records(vehicle_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_records_item ON daily_records(item)")
        conn.commit()


@app.on_event("startup")
def startup() -> None:
    init_db()


def only_number(value: str) -> float:
    allowed = "0123456789."
    text = "".join(ch for ch in value.replace(",", "") if ch in allowed)
    return float(text) if text else 0


def extract_date(line: str) -> str:
    for part in line.replace("วันที่", " ").replace("ที่", " ").split():
        if "/" in part:
            bits = part.split("/")
            if len(bits) == 3:
                day, month, year = bits
                if day.isdigit() and month.isdigit() and year.isdigit():
                    return f"{int(day):02d}/{int(month):02d}/{year}"
    return "ไม่พบวันที่"


def thai_date_to_iso(date_text: str) -> str:
    if "/" not in date_text:
        return ""
    day, month, year = date_text.split("/")
    y = int(year)
    if y > 2400:
        y -= 543
    return f"{y:04d}-{int(month):02d}-{int(day):02d}"


def vehicle_meta(line: str) -> dict[str, str] | None:
    if "รถจักรยานยนต์" in line:
        return {"key": "motorcycle", "icon": "🏍", "title": "รถจักรยานยนต์"}
    if "รถกระบะ" in line:
        return {"key": "pickup", "icon": "🚛", "title": "รถกระบะ"}
    if "รถยนต์เก๋ง" in line:
        return {"key": "sedan", "icon": "🚗", "title": "รถยนต์เก๋ง"}
    return None


def parse_period_key(line: str) -> str:
    return line.replace("#", "").strip()


def parse_report(raw_text: str) -> dict[str, Any]:
    lines = [line.strip() for line in raw_text.replace(chr(13), "").splitlines()]
    rows: list[dict[str, Any]] = []
    weekly_summaries: dict[str, dict[str, int]] = {}

    current_date_text = ""
    current_iso_date = ""
    current_meta: dict[str, str] | None = None
    current_company = ""
    current_period = ""

    for line in lines:
        if not line or line.startswith("====") or line.startswith("####"):
            continue

        if "รายสัปดาห์" in line and any(ch.isdigit() for ch in line):
            current_period = parse_period_key(line)
            weekly_summaries.setdefault(
                current_period,
                {"car": 0, "motorcycle": 0, "total": 0},
            )
            continue

        if current_period and "บาท" in line:
            target = line.split("->", 1)[1] if "->" in line else line
            value = round(only_number(target))
            if value:
                if "รวม" in line:
                    weekly_summaries[current_period]["total"] = value
                elif "รถจักรยานยนต์" in line:
                    weekly_summaries[current_period]["motorcycle"] = value
                elif "รถยนต์" in line:
                    weekly_summaries[current_period]["car"] = value
            continue

        if "สรุปยอด" in line and "/" in line:
            current_date_text = extract_date(line)
            current_iso_date = thai_date_to_iso(current_date_text)
            current_meta = None
            current_company = ""
            continue

        if not current_iso_date:
            continue

        meta = vehicle_meta(line)
        if meta:
            current_meta = meta
            current_company = ""
            continue

        if line.startswith("[") and line.endswith("]"):
            current_company = line[1:-1].strip()
            continue

        if line.startswith("•") and current_meta:
            item_text = line[1:].strip().replace("_", " ")
            rows.append(
                {
                    "date": current_date_text,
                    "isoDate": current_iso_date,
                    "vehicleType": current_meta["key"],
                    "vehicleTitle": current_meta["title"],
                    "icon": current_meta["icon"],
                    "company": current_company or "",
                    "item": item_text,
                }
            )

    for period, summary in weekly_summaries.items():
        if not summary["total"]:
            summary["total"] = summary["car"] + summary["motorcycle"]

    return {
        "rows": rows,
        "weeklySummaries": weekly_summaries,
    }


def save_import_replace_all(raw_text: str) -> dict[str, int]:
    """
    Replace All Mode:
    1. Parse imported rows
    2. Clear all existing dashboard data from daily_records and weekly_summaries
    3. Insert only the newest imported data

    This is best when the uploaded text file represents the latest source of truth.
    Result: dashboard always equals the latest uploaded file, never accumulates old data.
    """
    parsed = parse_report(raw_text)
    rows = parsed["rows"]
    weekly_summaries = parsed["weeklySummaries"]

    if not rows:
        raise HTTPException(status_code=400, detail="อ่านข้อมูลไม่สำเร็จ: ไม่พบรายการรายวัน")

    now = datetime.utcnow().isoformat()
    imported_dates = sorted({row["isoDate"] for row in rows if row["isoDate"]})

    with connect_db() as conn:
        cur = conn.execute(
            "INSERT INTO reports (raw_text, created_at) VALUES (?, ?)",
            (raw_text, now),
        )
        report_id = int(cur.lastrowid)

        deleted_records = conn.execute("DELETE FROM daily_records").rowcount
        deleted_summaries = conn.execute("DELETE FROM weekly_summaries").rowcount

        inserted = 0
        for row in rows:
            conn.execute(
                """
                INSERT INTO daily_records
                (report_id, date_text, iso_date, vehicle_type, vehicle_title, icon, company, item, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    row["date"],
                    row["isoDate"],
                    row["vehicleType"],
                    row["vehicleTitle"],
                    row["icon"],
                    row["company"],
                    row["item"],
                    now,
                ),
            )
            inserted += 1

        replaced_summaries = 0
        for period, summary in weekly_summaries.items():
            conn.execute(
                """
                INSERT INTO weekly_summaries
                (period_key, car_amount, motorcycle_amount, total_amount, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    period,
                    summary["car"],
                    summary["motorcycle"],
                    summary["total"],
                    now,
                ),
            )
            replaced_summaries += 1

        conn.commit()

    return {
        "report_id": report_id,
        "imported_dates": len(imported_dates),
        "deleted_records": int(deleted_records or 0),
        "deleted_summaries": int(deleted_summaries or 0),
        "inserted": inserted,
        "replaced_summaries": replaced_summaries,
        "parsed_rows": len(rows),
        "duplicated": 0,
    }


def get_money_totals_from_weekly_summaries() -> dict[str, int]:
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(car_amount), 0) AS car,
                COALESCE(SUM(motorcycle_amount), 0) AS motorcycle,
                COALESCE(SUM(total_amount), 0) AS total
            FROM weekly_summaries
            """
        ).fetchone()

    return {
        "car": int(row["car"] or 0),
        "motorcycle": int(row["motorcycle"] or 0),
        "total": int(row["total"] or 0),
    }


def get_dashboard_data(start: str | None = None, end: str | None = None, q: str | None = None) -> dict[str, Any]:
    where = []
    params: list[Any] = []

    if start:
        where.append("iso_date >= ?")
        params.append(start)
    if end:
        where.append("iso_date <= ?")
        params.append(end)
    if q:
        where.append("(item LIKE ? OR company LIKE ? OR vehicle_title LIKE ? OR date_text LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like, like])

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    with connect_db() as conn:
        rows = conn.execute(
            f"""
            SELECT date_text, iso_date, vehicle_type, vehicle_title, icon, company, item
            FROM daily_records
            {where_sql}
            ORDER BY iso_date ASC, id ASC
            """,
            params,
        ).fetchall()

        total_row = conn.execute(
            f"""
            SELECT
              SUM(CASE WHEN vehicle_type = 'motorcycle' THEN 1 ELSE 0 END) AS motorcycle,
              SUM(CASE WHEN vehicle_type = 'pickup' THEN 1 ELSE 0 END) AS pickup,
              SUM(CASE WHEN vehicle_type = 'sedan' THEN 1 ELSE 0 END) AS sedan,
              COUNT(*) AS all_count
            FROM daily_records
            {where_sql}
            """,
            params,
        ).fetchone()

        range_row = conn.execute(
            """
            SELECT MIN(iso_date) AS min_date, MAX(iso_date) AS max_date
            FROM daily_records
            """
        ).fetchone()

    days: dict[str, Any] = {}
    for row in rows:
        day_key = row["iso_date"]
        if day_key not in days:
            days[day_key] = {
                "date": row["date_text"],
                "isoDate": row["iso_date"],
                "motorcycle": 0,
                "pickup": 0,
                "sedan": 0,
                "groups": {},
            }

        day = days[day_key]
        vehicle_type = row["vehicle_type"]
        company = row["company"] or ""
        group_key = f"{vehicle_type}|{company}"

        if group_key not in day["groups"]:
            day["groups"][group_key] = {
                "key": vehicle_type,
                "icon": row["icon"],
                "title": row["vehicle_title"],
                "company": company,
                "items": [],
            }

        day["groups"][group_key]["items"].append(row["item"])
        day[vehicle_type] += 1

    daily_data = []
    for day in days.values():
        groups = []
        for group in day["groups"].values():
            group["count"] = len(group["items"])
            groups.append(group)
        day["groups"] = groups
        daily_data.append(day)

    money_totals = get_money_totals_from_weekly_summaries()

    return {
        "period": "📊 Dashboard ข้อมูลสะสมทั้งหมด",
        "amounts": money_totals,
        "dailyData": daily_data,
        "totals": {
            "motorcycle": int(total_row["motorcycle"] or 0),
            "pickup": int(total_row["pickup"] or 0),
            "sedan": int(total_row["sedan"] or 0),
            "all": int(total_row["all_count"] or 0),
        },
        "dateRange": {
            "start": range_row["min_date"] if range_row else None,
            "end": range_row["max_date"] if range_row else None,
        },
        "recordCount": len(rows),
    }


ADMIN_HTML = """
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Admin Dashboard Input</title>
<link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#f5f7fb;--card:#fff;--text:#172033;--muted:#667085;--blue:#2563eb;--cyan:#14b8a6;--line:#e5e7eb;--shadow:0 16px 40px rgba(15,23,42,.08)}
*{box-sizing:border-box}body{margin:0;font-family:Prompt,sans-serif;background:radial-gradient(circle at top left,#dbeafe 0,transparent 28%),var(--bg);color:var(--text)}.wrap{width:min(980px,94vw);margin:auto;padding:32px 0}.card{background:rgba(255,255,255,.9);backdrop-filter:blur(12px);border-radius:28px;padding:26px;box-shadow:var(--shadow);border:1px solid rgba(229,231,235,.9)}.hero{background:linear-gradient(135deg,#0f172a,#1d4ed8 62%,#14b8a6);color:#fff;border-radius:28px;padding:28px;margin-bottom:18px;box-shadow:var(--shadow)}.hero h1{margin:0 0 8px;font-size:34px}.hero p{margin:0;opacity:.9}.nav{display:flex;gap:10px;margin-bottom:16px}.nav a{padding:10px 14px;border-radius:14px;background:#fff;color:#1d4ed8;text-decoration:none;font-weight:700;border:1px solid var(--line)}textarea{width:100%;height:440px;border:1px solid var(--line);border-radius:18px;padding:14px;font-family:Prompt,sans-serif;font-size:14px;line-height:1.65;box-shadow:inset 0 1px 2px rgba(15,23,42,.04)}input{padding:12px 14px;border:1px solid var(--line);border-radius:14px;font-family:Prompt,sans-serif}.row{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.btn{border:0;border-radius:14px;padding:12px 18px;font-family:Prompt,sans-serif;font-weight:700;cursor:pointer;color:#fff;background:linear-gradient(135deg,var(--blue),var(--cyan));box-shadow:0 12px 22px rgba(37,99,235,.18);transition:.2s}.btn:hover{transform:translateY(-1px)}.btn2{background:#eff6ff;color:#1d4ed8;box-shadow:none}.status{margin-top:12px;color:var(--muted);white-space:pre-wrap}.hint{padding:12px 14px;background:#eff6ff;color:#1d4ed8;border-radius:14px;margin:12px 0;font-size:14px}.danger{background:#fff7ed;color:#9a3412}
</style>
</head>
<body>
<div class="wrap">
  <div class="nav"><a href="/admin">Admin</a><a href="/dashboard" target="_blank">Dashboard Only</a></div>
  <div class="hero"><h1>Vehicle Dashboard Admin</h1><p>นำเข้าข้อมูลแบบ Replace All: ระบบจะล้างข้อมูลเดิมทั้งหมด แล้วใช้เฉพาะข้อมูลชุดล่าสุดแทน</p></div>
  <div class="card">
    <h2>นำเข้าข้อมูลรายงาน</h2>
    <div class="hint danger">โหมดนี้ไม่บวกสะสม: ทุกครั้งที่นำเข้า ระบบจะเคลียร์ข้อมูลเดิมทั้งหมด แล้วบันทึกเฉพาะข้อมูลล่าสุดในไฟล์นี้</div>
    <form id="form">
      <div class="row" style="margin-bottom:12px">
        <input type="password" id="token" placeholder="Admin Token" required>
        <input type="file" id="file" accept=".txt,text/plain">
      </div>
      <textarea id="raw_text" placeholder="วางข้อมูลรายสัปดาห์หลายชุดต่อกันได้ตรงนี้..."></textarea>
      <div class="row">
        <button class="btn" type="submit">เคลียร์ข้อมูลเดิมทั้งหมดและบันทึกชุดใหม่</button>
        <a class="btn btn2" href="/dashboard" target="_blank">เปิด Dashboard Only</a>
      </div>
    </form>
    <div class="status" id="status">พร้อมใช้งาน</div>
  </div>
</div>
<script>
const fileInput = document.getElementById('file');
const rawText = document.getElementById('raw_text');
const form = document.getElementById('form');
const statusBox = document.getElementById('status');
fileInput.addEventListener('change', async event => {
  const file = event.target.files[0];
  if(!file) return;
  rawText.value = await file.text();
});
form.addEventListener('submit', async event => {
  event.preventDefault();
  const fd = new FormData();
  fd.append('raw_text', rawText.value);
  fd.append('token', document.getElementById('token').value);
  statusBox.textContent = 'กำลังเคลียร์ข้อมูลเดิมทั้งหมด และบันทึกข้อมูลชุดใหม่...';
  const res = await fetch('/api/import', {method:'POST', body:fd});
  const data = await res.json();
  if(!res.ok){statusBox.textContent = data.detail || 'บันทึกไม่สำเร็จ';return;}
  statusBox.textContent =
    'อัปเดตสำเร็จ\\n' +
    'Report ID: ' + data.report_id + '\\n' +
    'จำนวนวันที่ในไฟล์: ' + data.imported_dates + ' วัน\\n' +
    'ลบข้อมูลเดิม: ' + data.deleted_records + ' รายการ\\n' +
    'บันทึกข้อมูลใหม่: ' + data.inserted + ' รายการ\\n' +
    'อัปเดตยอดสรุปรายสัปดาห์: ' + data.replaced_summaries + ' ชุด';
});
</script>
</body>
</html>
"""

# Dashboard HTML reuse from v3.1 with no change except status text
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vehicle Dashboard Only</title>
<link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script><script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script><script src="https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js"></script><script src="https://cdn.jsdelivr.net/npm/jspdf-autotable@3.8.4/dist/jspdf.plugin.autotable.min.js"></script>
<style>
:root{--bg:#f3f6fb;--card:#fff;--text:#172033;--muted:#667085;--blue:#2563eb;--green:#16a34a;--orange:#f97316;--cyan:#14b8a6;--line:#e5e7eb;--shadow:0 18px 42px rgba(15,23,42,.08);--radius:24px}*{box-sizing:border-box}body{margin:0;font-family:Prompt,sans-serif;background:radial-gradient(circle at top left,#dbeafe 0,transparent 28%),linear-gradient(180deg,#f8fafc,var(--bg));color:var(--text)}.page{width:min(1280px,94vw);margin:0 auto;padding:32px 0 48px}.hero{display:grid;grid-template-columns:1.5fr 1fr;gap:20px;margin-bottom:22px}.hero-card{background:linear-gradient(135deg,#0f172a,#1d4ed8 62%,#14b8a6);color:#fff;border-radius:30px;padding:30px;box-shadow:var(--shadow)}.hero-card h1{margin:0 0 10px;font-size:clamp(28px,4vw,46px)}.period-pill{display:inline-flex;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.24);padding:8px 14px;border-radius:999px;margin-bottom:18px;font-weight:600}.total-card,.panel,.kpi,.day-card,.toolbar{background:rgba(255,255,255,.94);box-shadow:var(--shadow);border:1px solid rgba(229,231,235,.9);backdrop-filter:blur(10px)}.total-card{border-radius:30px;padding:26px}.label{color:var(--muted)}.amount{font-size:46px;font-weight:800;color:var(--blue);margin:8px 0}.summary-table{width:100%;border-collapse:collapse}.summary-table th,.summary-table td{padding:14px 12px;border-bottom:1px solid var(--line);text-align:left}.summary-table td:last-child,.summary-table th:last-child{text-align:right;font-weight:700}.toolbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:14px;margin:0 0 16px;padding:16px;border-radius:var(--radius)}.filter-group{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.date-input,.date-select,.search-input{border:1px solid var(--line);border-radius:14px;padding:10px 14px;font-family:Prompt,sans-serif;background:#fff;outline:none}.search-input{min-width:250px}.btn{border:0;border-radius:14px;padding:10px 16px;font-family:Prompt,sans-serif;font-weight:700;color:#fff;background:linear-gradient(135deg,#2563eb,#14b8a6);cursor:pointer}.btn2{color:#1d4ed8;background:#eff6ff}.btnDark{background:#111827}.status-pill{display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border-radius:999px;background:#ecfeff;color:#155e75;font-size:13px;font-weight:700}.dot{width:8px;height:8px;border-radius:99px;background:#22c55e;box-shadow:0 0 0 5px rgba(34,197,94,.12)}.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:22px}.kpi{border-radius:var(--radius);padding:20px}.kpi .icon{font-size:28px;margin-bottom:8px}.kpi .value{font-size:30px;font-weight:800}.kpi .title{color:var(--muted);font-size:14px}.section-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:22px}.panel{border-radius:var(--radius);padding:22px}.chart-wrap{height:310px}.daily-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}.day-card{border-radius:var(--radius);overflow:hidden}.day-head{width:100%;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:18px 20px;border:0;background:#fff;cursor:pointer;font-family:Prompt,sans-serif;text-align:left}.day-title{font-size:18px;font-weight:800}.badge{background:#eff6ff;color:#1d4ed8;border-radius:999px;padding:6px 12px;font-size:13px;font-weight:800;white-space:nowrap}.chev{font-size:18px;color:#667085}.day-body{display:none;padding:0 20px 20px;border-top:1px solid var(--line)}.day-card.open .day-body{display:block}.vehicle-group{margin-top:14px}.vehicle-title{font-weight:800;margin-bottom:8px}.company{display:inline-flex;margin:6px 0 4px;padding:4px 10px;border-radius:999px;background:#f3f4f6;font-size:12px;font-weight:800}ul{list-style:none;padding:0;margin:0;display:grid;gap:7px}li{background:#f9fafb;border:1px solid #eef2f7;border-radius:14px;padding:9px 11px;font-size:13px}.pagination{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:center;margin:20px 0}.page-info{color:var(--muted);font-weight:700}@media(max-width:980px){.hero,.section-grid,.daily-grid{grid-template-columns:1fr}.kpi-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:560px){.kpi-grid{grid-template-columns:1fr}.filter-group,.date-input,.date-select,.search-input,.btn{width:100%}.amount{font-size:38px}}
</style></head>
<body><main class="page">
<section class="hero"><div class="hero-card"><div class="period-pill" id="period">📊 Dashboard ข้อมูลสะสมทั้งหมด</div><h1>Vehicle Cumulative Dashboard</h1><p>Dashboard Only สำหรับข้อมูลสะสมทั้งหมดจากฐานข้อมูล</p><div style="margin-top:18px"><span class="status-pill"><span class="dot"></span><span id="refreshStatus">Auto refresh ทุก 30 วิ</span></span></div></div><div class="total-card"><div class="label">ยอดรวมทั้งหมด</div><div class="amount" id="totalAmount">0</div><table class="summary-table"><tr><th>หมวด</th><th>ยอด</th></tr><tr><td>🚛 🚗 รถยนต์</td><td id="carAmount">0 บาท</td></tr><tr><td>🏍 รถจักรยานยนต์</td><td id="motorAmount">0 บาท</td></tr></table></div></section>
<section class="toolbar"><h2>เลือกช่วงวันที่ Dashboard</h2><div class="filter-group"><input class="date-input" id="startDate" type="date"><input class="date-input" id="endDate" type="date"><button class="btn" id="applyBtn">แสดงช่วงวันที่</button><button class="btn btn2" id="resetBtn">ดูทั้งหมด</button></div></section>
<section class="kpi-grid"><div class="kpi"><div class="icon">🏍</div><div class="value" id="motorCount">0</div><div class="title">รถจักรยานยนต์</div></div><div class="kpi"><div class="icon">🚛</div><div class="value" id="pickupCount">0</div><div class="title">รถกระบะ</div></div><div class="kpi"><div class="icon">🚗</div><div class="value" id="sedanCount">0</div><div class="title">รถยนต์เก๋ง</div></div><div class="kpi"><div class="icon">🚘</div><div class="value" id="allCount">0</div><div class="title">จำนวนรถรวมทั้งหมด</div></div></section>
<section class="section-grid"><div class="panel"><h2>จำนวนรถรายวัน</h2><div class="chart-wrap"><canvas id="dailyChart"></canvas></div></div><div class="panel"><h2>สัดส่วนประเภทรถ</h2><div class="chart-wrap"><canvas id="typeChart"></canvas></div></div></section>
<section class="toolbar"><h2>รายการแยกรายวัน</h2><div class="filter-group"><input class="search-input" id="searchBox" placeholder="ค้นหาทะเบียน / เลขกรมธรรม์ / บริษัท"><select class="date-select" id="dateFilter"><option value="all">ดูทั้งหมด</option></select><button class="btn" id="showDateBtn">แสดงวันที่เลือก</button><button class="btn btn2" id="showAllBtn">ดูทั้งหมด</button><button class="btn btnDark" id="exportPdfBtn">Export PDF</button><button class="btn btnDark" id="exportExcelBtn">Export Excel</button></div></section>
<section class="daily-grid" id="cards"></section><div class="pagination"><button class="btn btn2" id="prevPageBtn">ก่อนหน้า</button><span class="page-info" id="pageInfo">Page 1</span><button class="btn btn2" id="nextPageBtn">ถัดไป</button></div><p class="status-pill" id="status">Loading...</p>
</main>
<script>
let report=null,allDays=[],filteredDays=[],viewDays=[],dailyChart=null,typeChart=null;let currentPage=1,pageSize=8;const box=id=>document.getElementById(id);const money=n=>Math.round(n||0).toLocaleString('th-TH');function destroy(){if(dailyChart)dailyChart.destroy();if(typeChart)typeChart.destroy()}function setupRange(){const dates=allDays.map(d=>d.isoDate).filter(Boolean).sort();box('startDate').value=dates[0]||'';box('endDate').value=dates[dates.length-1]||''}function flattenRows(days){const rows=[];days.forEach(day=>day.groups.forEach(g=>g.items.forEach(item=>rows.push({date:day.date,type:g.title,company:g.company||'',item}))));return rows}
function renderCharts(motor,pickup,sedan){destroy();dailyChart=new Chart(box('dailyChart'),{type:'bar',data:{labels:filteredDays.map(d=>d.date.slice(0,5)),datasets:[{label:'🏍 รถจักรยานยนต์',data:filteredDays.map(d=>d.motorcycle),backgroundColor:'#2563eb',borderRadius:10},{label:'🚛 รถกระบะ',data:filteredDays.map(d=>d.pickup),backgroundColor:'#f97316',borderRadius:10},{label:'🚗 รถยนต์เก๋ง',data:filteredDays.map(d=>d.sedan),backgroundColor:'#16a34a',borderRadius:10}]},options:{responsive:true,maintainAspectRatio:false,scales:{y:{beginAtZero:true}}}});typeChart=new Chart(box('typeChart'),{type:'doughnut',data:{labels:['รถจักรยานยนต์','รถกระบะ','รถยนต์เก๋ง'],datasets:[{data:[motor,pickup,sedan],backgroundColor:['#2563eb','#f97316','#16a34a'],borderWidth:0}]},options:{responsive:true,maintainAspectRatio:false,cutout:'66%'}})}
function render(selected='all'){const t=report.totals||{};const motor=t.motorcycle||0,pickup=t.pickup||0,sedan=t.sedan||0,total=t.all||0;box('period').textContent='📊 Dashboard ข้อมูลสะสมทั้งหมด';box('totalAmount').textContent=money(report.amounts.total);box('carAmount').textContent=money(report.amounts.car)+' บาท';box('motorAmount').textContent=money(report.amounts.motorcycle)+' บาท';box('motorCount').textContent=motor;box('pickupCount').textContent=pickup;box('sedanCount').textContent=sedan;box('allCount').textContent=total;box('dateFilter').innerHTML='<option value="all">ดูทั้งหมด</option>'+filteredDays.map(d=>`<option value="${d.date}">${d.date}</option>`).join('');renderCharts(motor,pickup,sedan);currentPage=1;renderCards(selected);box('status').textContent=`ข้อมูลสะสมทั้งหมด ${total} คัน • แสดง ${filteredDays.length}/${allDays.length} วัน`}
function getCardList(selected='all'){const base=selected==='all'?filteredDays:filteredDays.filter(d=>d.date===selected);const q=box('searchBox').value.trim().toLowerCase();if(!q)return base;return base.map(day=>{const groups=day.groups.map(g=>{const items=g.items.filter(i=>(day.date+' '+g.title+' '+(g.company||'')+' '+i).toLowerCase().includes(q));return {...g,items,count:items.length}}).filter(g=>g.items.length);return {...day,groups,motorcycle:groups.filter(g=>g.key==='motorcycle').reduce((s,g)=>s+g.items.length,0),pickup:groups.filter(g=>g.key==='pickup').reduce((s,g)=>s+g.items.length,0),sedan:groups.filter(g=>g.key==='sedan').reduce((s,g)=>s+g.items.length,0)}}).filter(d=>d.groups.length)}
function renderCards(selected='all'){const list=getCardList(selected);viewDays=list;const totalPages=Math.max(1,Math.ceil(list.length/pageSize));if(currentPage>totalPages)currentPage=totalPages;const start=(currentPage-1)*pageSize;const pageItems=list.slice(start,start+pageSize);box('pageInfo').textContent=`หน้า ${currentPage}/${totalPages} • แสดง ${pageItems.length}/${list.length} วัน`;box('prevPageBtn').disabled=currentPage<=1;box('nextPageBtn').disabled=currentPage>=totalPages;if(!pageItems.length){box('cards').innerHTML='<article class="day-card"><button class="day-head"><span class="day-title">ไม่พบข้อมูล</span></button></article>';return}box('cards').innerHTML=pageItems.map((day,idx)=>{const total=day.motorcycle+day.pickup+day.sedan;const groups=day.groups.map(g=>`<div class="vehicle-group"><div class="vehicle-title">${g.icon} ${g.title} (${g.items.length} คัน)</div>${g.company?`<span class="company">${g.company}</span>`:''}<ul>${g.items.map(i=>`<li>${i}</li>`).join('')}</ul></div>`).join('');const open=idx<2?' open':'';return `<article class="day-card${open}"><button class="day-head" onclick="this.parentElement.classList.toggle('open')"><span class="day-title">📊 วันที่ ${day.date}</span><span class="badge">รวม ${total} คัน</span><span class="chev">⌄</span></button><div class="day-body">${groups}</div></article>`}).join('')}
function exportExcel(){const rows=flattenRows(viewDays.length?viewDays:filteredDays);const ws=XLSX.utils.json_to_sheet(rows.map(r=>({วันที่:r.date,ประเภทรถ:r.type,บริษัท:r.company,รายการ:r.item})));const wb=XLSX.utils.book_new();XLSX.utils.book_append_sheet(wb,ws,'Dashboard');XLSX.writeFile(wb,'vehicle-dashboard.xlsx')}function exportPDF(){const rows=flattenRows(viewDays.length?viewDays:filteredDays).map(r=>[r.date,r.type,r.company,r.item]);const{jsPDF}=window.jspdf;const doc=new jsPDF({orientation:'landscape'});doc.setFontSize(16);doc.text('Vehicle Cumulative Dashboard',14,16);doc.setFontSize(10);doc.text(box('status').textContent,14,24);doc.autoTable({head:[['Date','Type','Company','Item']],body:rows,startY:30,styles:{fontSize:8,cellPadding:2},headStyles:{fillColor:[37,99,235]}});doc.save('vehicle-dashboard.pdf')}
async function load(){box('refreshStatus').textContent='กำลังโหลดข้อมูล...';const params=new URLSearchParams();const s=box('startDate').value,e=box('endDate').value,q=box('searchBox').value.trim();if(s)params.set('start',s);if(e)params.set('end',e);if(q)params.set('q',q);const query=params.toString();const url='/api/dashboard'+(query?('?'+query+'&ts='+Date.now()):('?ts='+Date.now()));const res=await fetch(url).catch(()=>null);if(!res||!res.ok){box('status').textContent='ยังไม่มีข้อมูล';box('refreshStatus').textContent='ยังไม่มีข้อมูล';return}report=await res.json();allDays=report.dailyData;filteredDays=[...allDays];if(!s&&!e)setupRange();render();box('refreshStatus').textContent='ข้อมูลล่าสุดแล้ว • '+new Date().toLocaleTimeString('th-TH')}
box('applyBtn').onclick=()=>load();box('resetBtn').onclick=()=>{box('startDate').value='';box('endDate').value='';box('searchBox').value='';load()};box('showDateBtn').onclick=()=>{currentPage=1;renderCards(box('dateFilter').value)};box('showAllBtn').onclick=()=>{box('dateFilter').value='all';currentPage=1;renderCards('all')};box('dateFilter').onchange=()=>{currentPage=1;renderCards(box('dateFilter').value)};box('searchBox').oninput=()=>{currentPage=1;clearTimeout(window.searchTimer);window.searchTimer=setTimeout(()=>load(),450)};box('prevPageBtn').onclick=()=>{if(currentPage>1){currentPage--;renderCards(box('dateFilter').value)}};box('nextPageBtn').onclick=()=>{currentPage++;renderCards(box('dateFilter').value)};box('exportExcelBtn').onclick=exportExcel;box('exportPdfBtn').onclick=exportPDF;load();setInterval(()=>load(),30000);
</script></body></html>
"""


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/dashboard")


@app.get("/admin", response_class=HTMLResponse)
def admin_page() -> str:
    return ADMIN_HTML


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page() -> str:
    return DASHBOARD_HTML


@app.post("/api/import")
def api_import(token: str = Form(...), raw_text: str = Form("")) -> JSONResponse:
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Admin token ไม่ถูกต้อง")
    text = raw_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="ไม่พบข้อมูลรายงาน")
    result = save_import_replace_all(text)
    return JSONResponse({"ok": True, **result})


@app.get("/api/dashboard")
def api_dashboard(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> JSONResponse:
    return JSONResponse(get_dashboard_data(start=start, end=end, q=q))


@app.get("/api/report/latest")
def api_latest_report() -> JSONResponse:
    return api_dashboard()
