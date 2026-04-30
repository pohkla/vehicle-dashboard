from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

DB_PATH = Path("vehicle_dashboard.db")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-this-token")

app = FastAPI(title="Vehicle Weekly Dashboard")


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


@app.on_event("startup")
def startup() -> None:
    init_db()


def save_report(raw_text: str) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO reports (raw_text, created_at) VALUES (?, ?)",
            (raw_text, datetime.utcnow().isoformat()),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_latest_report() -> dict[str, Any] | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, raw_text, created_at FROM reports ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


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


def count_from_header(line: str) -> int:
    if "(" not in line or "คัน" not in line:
        return 0
    text = line.split("(", 1)[1].split("คัน", 1)[0]
    return int(only_number(text) or 0)


def parse_amounts(lines: list[str]) -> dict[str, int]:
    result = {"car": 0, "motorcycle": 0, "total": 0}
    for line in lines:
        if "บาท" not in line:
            continue
        target = line.split("->", 1)[1] if "->" in line else line
        value = round(only_number(target))
        if not value:
            continue
        if "รวม" in line:
            result["total"] = value
        elif "รถจักรยานยนต์" in line:
            result["motorcycle"] = value
        elif "รถยนต์" in line:
            result["car"] = value
    if not result["total"]:
        result["total"] = result["car"] + result["motorcycle"]
    return result


def parse_period(lines: list[str]) -> str:
    for line in lines:
        if "รายสัปดาห์" in line and any(ch.isdigit() for ch in line):
            return line.replace("#", "").strip()
    return "📊 รายสัปดาห์"


def parse_report(raw_text: str) -> dict[str, Any]:
    lines = [line.strip() for line in raw_text.replace(chr(13), "").splitlines()]
    daily_data: list[dict[str, Any]] = []
    current_day: dict[str, Any] | None = None
    current_group: dict[str, Any] | None = None
    current_company = ""

    for line in lines:
        if not line or line.startswith("====") or line.startswith("####"):
            continue

        if "สรุปยอด" in line and "/" in line:
            date_text = extract_date(line)
            current_day = {
                "date": date_text,
                "isoDate": thai_date_to_iso(date_text),
                "motorcycle": 0,
                "pickup": 0,
                "sedan": 0,
                "groups": [],
            }
            daily_data.append(current_day)
            current_group = None
            current_company = ""
            continue

        if current_day is None:
            continue

        meta = vehicle_meta(line)
        if meta:
            current_group = {
                "key": meta["key"],
                "icon": meta["icon"],
                "title": meta["title"],
                "count": count_from_header(line),
                "company": "",
                "items": [],
            }
            current_day["groups"].append(current_group)
            current_company = ""
            continue

        if line.startswith("[") and line.endswith("]"):
            current_company = line[1:-1].strip()
            if current_group and not current_group["items"]:
                current_group["company"] = current_company
            continue

        if line.startswith("•") and current_group:
            item_text = line[1:].strip().replace("_", " ")
            if (
                current_company
                and current_group.get("company")
                and current_group["company"] != current_company
                and current_group["items"]
            ):
                current_group = {
                    "key": current_group["key"],
                    "icon": current_group["icon"],
                    "title": current_group["title"],
                    "count": 0,
                    "company": current_company,
                    "items": [],
                }
                current_day["groups"].append(current_group)

            if current_company and not current_group.get("company"):
                current_group["company"] = current_company

            current_group["items"].append(item_text)
            current_group["count"] = len(current_group["items"])
            key = current_group["key"]
            current_day[key] = sum(
                len(group["items"])
                for group in current_day["groups"]
                if group["key"] == key
            )

    daily_data = [day for day in daily_data if day["groups"]]
    return {
        "period": parse_period(lines),
        "amounts": parse_amounts(lines),
        "dailyData": daily_data,
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
body{margin:0;font-family:Prompt,sans-serif;background:#f5f7fb;color:#172033}.wrap{width:min(960px,94vw);margin:auto;padding:32px 0}.card{background:#fff;border-radius:24px;padding:24px;box-shadow:0 16px 40px rgba(15,23,42,.08);border:1px solid #e5e7eb}.nav{display:flex;gap:10px;margin-bottom:16px}.nav a{padding:10px 14px;border-radius:14px;background:#fff;color:#1d4ed8;text-decoration:none;font-weight:700;border:1px solid #e5e7eb}textarea{width:100%;height:430px;border:1px solid #e5e7eb;border-radius:16px;padding:14px;font-family:Prompt,sans-serif;font-size:14px;line-height:1.65;box-sizing:border-box}input{padding:11px 14px;border:1px solid #e5e7eb;border-radius:14px;font-family:Prompt,sans-serif}.row{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.btn{border:0;border-radius:14px;padding:11px 18px;font-family:Prompt,sans-serif;font-weight:700;cursor:pointer;color:#fff;background:linear-gradient(135deg,#2563eb,#14b8a6)}.btn2{background:#eff6ff;color:#1d4ed8}.status{margin-top:12px;color:#667085}
</style>
</head>
<body>
<div class="wrap">
  <div class="nav"><a href="/admin">Admin</a><a href="/dashboard" target="_blank">Dashboard Only</a></div>
  <div class="card">
    <h1>หน้าสร้าง Dashboard</h1>
    <p>วางข้อความรายงาน หรืออัปโหลดไฟล์ .txt จากนั้นกดบันทึก ระบบจะอัปเดตหน้า Dashboard Only ทันที</p>
    <form id="form">
      <input type="password" id="token" placeholder="Admin Token" required>
      <input type="file" id="file" accept=".txt,text/plain">
      <div style="height:12px"></div>
      <textarea id="raw_text" placeholder="วางข้อมูลรายสัปดาห์ตรงนี้...">{{raw_text}}</textarea>
      <div class="row">
        <button class="btn" type="submit">บันทึกและสร้าง Dashboard</button>
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
  const res = await fetch('/api/report', {method:'POST', body:fd});
  const data = await res.json();
  if(!res.ok){statusBox.textContent = data.detail || 'บันทึกไม่สำเร็จ';return;}
  statusBox.textContent = 'บันทึกสำเร็จ Report ID: ' + data.id;
});
</script>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vehicle Dashboard Only</title>
<link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root{--bg:#f5f7fb;--card:#fff;--text:#172033;--muted:#667085;--blue:#2563eb;--green:#16a34a;--orange:#f97316;--line:#e5e7eb;--shadow:0 16px 40px rgba(15,23,42,.08);--radius:22px}*{box-sizing:border-box}body{margin:0;font-family:Prompt,sans-serif;background:radial-gradient(circle at top left,#dbeafe 0,transparent 28%),var(--bg);color:var(--text)}.page{width:min(1280px,94vw);margin:0 auto;padding:32px 0 48px}.hero{display:grid;grid-template-columns:1.5fr 1fr;gap:20px;margin-bottom:22px}.hero-card{background:linear-gradient(135deg,#0f172a,#1d4ed8 62%,#14b8a6);color:#fff;border-radius:30px;padding:30px;box-shadow:var(--shadow)}.hero-card h1{margin:0 0 10px;font-size:clamp(26px,4vw,44px)}.period-pill{display:inline-flex;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.24);padding:8px 14px;border-radius:999px;margin-bottom:18px;font-weight:500}.total-card,.panel,.kpi,.day-card,.toolbar{background:var(--card);box-shadow:var(--shadow);border:1px solid rgba(229,231,235,.8)}.total-card{border-radius:30px;padding:26px}.label{color:var(--muted)}.amount{font-size:46px;font-weight:700;color:var(--blue);margin:8px 0}.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:22px}.kpi{border-radius:var(--radius);padding:20px}.kpi .icon{font-size:28px;margin-bottom:8px}.kpi .value{font-size:30px;font-weight:700}.kpi .title{color:var(--muted);font-size:14px}.section-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:22px}.panel{border-radius:var(--radius);padding:22px}.chart-wrap{height:310px}.toolbar{display:flex;flex-wrap:wrap;justify-content:space-between;gap:14px;margin:0 0 16px;padding:16px;border-radius:var(--radius)}.filter-group{display:flex;flex-wrap:wrap;gap:10px}.date-input,.date-select{border:1px solid var(--line);border-radius:14px;padding:10px 14px;font-family:Prompt,sans-serif}.btn{border:0;border-radius:14px;padding:10px 16px;font-family:Prompt,sans-serif;font-weight:700;color:#fff;background:linear-gradient(135deg,#2563eb,#14b8a6);cursor:pointer}.btn2{color:#1d4ed8;background:#eff6ff}.daily-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}.day-card{border-radius:var(--radius);padding:20px}.day-header{display:flex;justify-content:space-between;gap:10px;border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:14px}.badge{background:#eff6ff;color:#1d4ed8;border-radius:999px;padding:6px 12px;font-size:13px;font-weight:700}.vehicle-group{margin-top:14px}.vehicle-title{font-weight:700;margin-bottom:8px}.company{display:inline-flex;margin:6px 0 4px;padding:4px 10px;border-radius:999px;background:#f3f4f6;font-size:12px;font-weight:700}ul{list-style:none;padding:0;margin:0;display:grid;gap:7px}li{background:#f9fafb;border:1px solid #eef2f7;border-radius:14px;padding:9px 11px;font-size:13px}.summary-table{width:100%;border-collapse:collapse}.summary-table th,.summary-table td{padding:14px 12px;border-bottom:1px solid var(--line);text-align:left}.summary-table td:last-child,.summary-table th:last-child{text-align:right;font-weight:700}.status{color:var(--muted);font-size:13px}@media(max-width:980px){.hero,.section-grid,.daily-grid{grid-template-columns:1fr}.kpi-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:560px){.kpi-grid{grid-template-columns:1fr}.filter-group,.date-input,.date-select,.btn{width:100%}}
</style>
</head>
<body>
<main class="page">
<section class="hero"><div class="hero-card"><div class="period-pill" id="period">📊 รายสัปดาห์</div><h1>Vehicle Weekly Dashboard</h1><p>Dashboard Only สำหรับแชร์ให้ผู้เกี่ยวข้องดูข้อมูลล่าสุด</p></div><div class="total-card"><div class="label">ยอดรวมทั้งหมด</div><div class="amount" id="totalAmount">0</div><table class="summary-table"><tr><th>หมวด</th><th>ยอด</th></tr><tr><td>🚛 🚗 รถยนต์</td><td id="carAmount">0 บาท</td></tr><tr><td>🏍 รถจักรยานยนต์</td><td id="motorAmount">0 บาท</td></tr></table></div></section>
<section class="toolbar"><h2>เลือกช่วงวันที่ Dashboard</h2><div class="filter-group"><input class="date-input" id="startDate" type="date"><input class="date-input" id="endDate" type="date"><button class="btn" id="applyBtn">แสดงช่วงวันที่</button><button class="btn btn2" id="resetBtn">ดูทั้งหมด</button></div></section>
<section class="kpi-grid"><div class="kpi"><div class="icon">🏍</div><div class="value" id="motorCount">0</div><div class="title">รถจักรยานยนต์</div></div><div class="kpi"><div class="icon">🚛</div><div class="value" id="pickupCount">0</div><div class="title">รถกระบะ</div></div><div class="kpi"><div class="icon">🚗</div><div class="value" id="sedanCount">0</div><div class="title">รถยนต์เก๋ง</div></div><div class="kpi"><div class="icon">🚘</div><div class="value" id="allCount">0</div><div class="title">จำนวนรถรวม</div></div></section>
<section class="section-grid"><div class="panel"><h2>จำนวนรถรายวัน</h2><div class="chart-wrap"><canvas id="dailyChart"></canvas></div></div><div class="panel"><h2>สัดส่วนประเภทรถ</h2><div class="chart-wrap"><canvas id="typeChart"></canvas></div></div></section>
<section class="toolbar"><h2>รายการแยกรายวัน</h2><div class="filter-group"><select class="date-select" id="dateFilter"><option value="all">ดูทั้งหมด</option></select><button class="btn" id="showDateBtn">แสดงวันที่เลือก</button><button class="btn btn2" id="showAllBtn">ดูทั้งหมด</button></div></section>
<section class="daily-grid" id="cards"></section><p class="status" id="status">Loading...</p>
</main>
<script>
let report=null, allDays=[], filteredDays=[], dailyChart=null, typeChart=null;
const box=id=>document.getElementById(id);
const money=n=>Math.round(n||0).toLocaleString('th-TH');
function inRange(d,s,e){if(s&&d.isoDate<s)return false;if(e&&d.isoDate>e)return false;return true;}
function destroy(){if(dailyChart)dailyChart.destroy();if(typeChart)typeChart.destroy();}
function setupRange(){const dates=allDays.map(d=>d.isoDate).filter(Boolean).sort();box('startDate').value=dates[0]||'';box('endDate').value=dates[dates.length-1]||'';}
function render(selected='all'){
 const motor=filteredDays.reduce((s,d)=>s+d.motorcycle,0), pickup=filteredDays.reduce((s,d)=>s+d.pickup,0), sedan=filteredDays.reduce((s,d)=>s+d.sedan,0), total=motor+pickup+sedan;
 box('period').textContent=report.period;box('totalAmount').textContent=money(report.amounts.total);box('carAmount').textContent=money(report.amounts.car)+' บาท';box('motorAmount').textContent=money(report.amounts.motorcycle)+' บาท';box('motorCount').textContent=motor;box('pickupCount').textContent=pickup;box('sedanCount').textContent=sedan;box('allCount').textContent=total;
 box('dateFilter').innerHTML='<option value="all">ดูทั้งหมด</option>'+filteredDays.map(d=>`<option value="${d.date}">${d.date}</option>`).join('');
 destroy();dailyChart=new Chart(box('dailyChart'),{type:'bar',data:{labels:filteredDays.map(d=>d.date.slice(0,5)),datasets:[{label:'🏍 รถจักรยานยนต์',data:filteredDays.map(d=>d.motorcycle),backgroundColor:'#2563eb',borderRadius:10},{label:'🚛 รถกระบะ',data:filteredDays.map(d=>d.pickup),backgroundColor:'#f97316',borderRadius:10},{label:'🚗 รถยนต์เก๋ง',data:filteredDays.map(d=>d.sedan),backgroundColor:'#16a34a',borderRadius:10}]},options:{responsive:true,maintainAspectRatio:false,scales:{y:{beginAtZero:true}}}});
 typeChart=new Chart(box('typeChart'),{type:'doughnut',data:{labels:['รถจักรยานยนต์','รถกระบะ','รถยนต์เก๋ง'],datasets:[{data:[motor,pickup,sedan],backgroundColor:['#2563eb','#f97316','#16a34a'],borderWidth:0}]},options:{responsive:true,maintainAspectRatio:false,cutout:'66%'}});
 renderCards(selected);box('status').textContent=`แสดงข้อมูล ${filteredDays.length}/${allDays.length} วัน / ${total} คัน`;
}
function renderCards(selected='all'){
 const list=selected==='all'?filteredDays:filteredDays.filter(d=>d.date===selected);
 if(!list.length){box('cards').innerHTML='<article class="day-card">ไม่พบข้อมูล</article>';return;}
 box('cards').innerHTML=list.map(day=>{const total=day.motorcycle+day.pickup+day.sedan;const groups=day.groups.map(g=>`<div class="vehicle-group"><div class="vehicle-title">${g.icon} ${g.title} (${g.items.length} คัน)</div>${g.company?`<span class="company">${g.company}</span>`:''}<ul>${g.items.map(i=>`<li>${i}</li>`).join('')}</ul></div>`).join('');return `<article class="day-card"><div class="day-header"><h3>📊 วันที่ ${day.date}</h3><span class="badge">รวม ${total} คัน</span></div>${groups}</article>`}).join('');
}
async function load(){const res=await fetch('/api/report/latest');if(!res.ok){box('status').textContent='ยังไม่มีข้อมูล';return;}report=await res.json();allDays=report.dailyData;filteredDays=[...allDays];setupRange();render();}
box('applyBtn').onclick=()=>{filteredDays=allDays.filter(d=>inRange(d,box('startDate').value,box('endDate').value));render('all')};
box('resetBtn').onclick=()=>{filteredDays=[...allDays];setupRange();render('all')};
box('showDateBtn').onclick=()=>renderCards(box('dateFilter').value);
box('showAllBtn').onclick=()=>{box('dateFilter').value='all';renderCards('all')};
box('dateFilter').onchange=()=>renderCards(box('dateFilter').value);
load();
</script>
</body>
</html>
"""

@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/dashboard")


@app.get("/admin", response_class=HTMLResponse)
def admin_page() -> str:
    latest = get_latest_report()
    raw_text = latest["raw_text"] if latest else ""
    safe_text = raw_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return ADMIN_HTML.replace("{{raw_text}}", safe_text)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page() -> str:
    return DASHBOARD_HTML


@app.post("/api/report")
def api_save_report(token: str = Form(...), raw_text: str = Form("")) -> JSONResponse:
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Admin token ไม่ถูกต้อง")
    text = raw_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="ไม่พบข้อมูลรายงาน")
    parsed = parse_report(text)
    if not parsed["dailyData"]:
        raise HTTPException(status_code=400, detail="อ่านข้อมูลไม่สำเร็จ: ไม่พบรายการรายวัน")
    report_id = save_report(text)
    return JSONResponse({"ok": True, "id": report_id, "parsed": parsed})


@app.get("/api/report/latest")
def api_latest_report() -> JSONResponse:
    latest = get_latest_report()
    if not latest:
        raise HTTPException(status_code=404, detail="ยังไม่มีข้อมูล Dashboard")
    parsed = parse_report(latest["raw_text"])
    parsed["id"] = latest["id"]
    parsed["created_at"] = latest["created_at"]
    return JSONResponse(parsed)
