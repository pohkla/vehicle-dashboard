import base64
import json
import os
import re
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import load_workbook

APP_TITLE = "Vehicle Dashboard System"
DB_FILE = "data.json"
REQUIRED_HEADERS = ["วันที่", "ประเภทรถ", "บริษัท", "ยอดสุทธิ", "ยอดเก็บจริง"]
COMPANIES = ["RVP", "ERGO", "TPB"]
COMPANY_META = {
    "RVP": {"name": "RVP", "label": "บริษัทกลาง RVP", "color": "blue"},
    "ERGO": {"name": "ERGO", "label": "ERGO", "color": "red"},
    "TPB": {"name": "TPB", "label": "ไทยไพบูลย์ TPB", "color": "cyan"},
}

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")  # owner/repo
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
GITHUB_DB_PATH = os.getenv("GITHUB_DB_PATH", "data/vehicle-dashboard.json")

app = FastAPI(title=APP_TITLE)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")


def to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in ("", ".", "-", "-"):
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def clean_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_company(company: str, vehicle_type: str = "") -> str:
    raw = f"{company} {vehicle_type}".upper()
    if "RVP" in raw or "มอเตอร์" in raw or "จักรยานยนต์" in raw:
        return "RVP"
    if "ERGO" in raw:
        return "ERGO"
    if "TPB" in raw or "ไทยไพบูลย์" in raw:
        return "TPB"
    return clean_text(company).upper() or "UNKNOWN"


def normalize_record(row: Dict[str, Any], row_no: Optional[int] = None, source: str = "") -> Dict[str, Any]:
    vehicle_type = clean_text(row.get("ประเภทรถ"))
    company = normalize_company(clean_text(row.get("บริษัท")), vehicle_type)
    return {
        "date": clean_text(row.get("วันที่")),
        "vehicle_type": vehicle_type or "ไม่ระบุ",
        "company": company,
        "net_total": to_float(row.get("ยอดสุทธิ")),
        "collected_total": to_float(row.get("ยอดเก็บจริง")),
        "raw_code": clean_text(row.get("รหัส")),
        "source": source,
        "row_no": row_no,
    }


def empty_summary() -> Dict[str, Any]:
    company_cards = {}
    for code in COMPANIES:
        meta = COMPANY_META[code]
        company_cards[code] = {
            "code": code,
            "name": meta["name"],
            "label": meta["label"],
            "color": meta["color"],
            "vehicle_count": 0,
            "net_total": 0.0,
            "collected_total": 0.0,
            "vehicle_types": {},
            "share": 0.0,
        }
    company_cards["TOTAL"] = {
        "code": "TOTAL",
        "name": "รวม",
        "label": "จำนวนรถรวมทั้งหมด",
        "color": "dark",
        "vehicle_count": 0,
        "net_total": 0.0,
        "collected_total": 0.0,
        "vehicle_types": {},
        "share": 100.0,
    }
    return {"companies": company_cards, "updated_at": datetime.now().isoformat()}


def build_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = empty_summary()
    total_count = 0
    for rec in records:
        company = rec.get("company") if rec.get("company") in COMPANIES else "TPB"
        vehicle_type = rec.get("vehicle_type") or "ไม่ระบุ"
        net = to_float(rec.get("net_total"))
        collected = to_float(rec.get("collected_total"))
        for key in (company, "TOTAL"):
            card = summary["companies"][key]
            card["vehicle_count"] += 1
            card["net_total"] += net
            card["collected_total"] += collected
            card["vehicle_types"][vehicle_type] = card["vehicle_types"].get(vehicle_type, 0) + 1
        total_count += 1
    for code in COMPANIES:
        count = summary["companies"][code]["vehicle_count"]
        summary["companies"][code]["share"] = round((count / total_count * 100), 2) if total_count else 0.0
    return summary


async def github_get() -> List[Dict[str, Any]]:
    if not (GITHUB_TOKEN and GITHUB_REPO):
        return []
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_DB_PATH}?ref={GITHUB_BRANCH}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, headers=headers)
    if r.status_code == 404:
        return []
    if r.status_code >= 400:
        raise HTTPException(502, f"GitHub read failed: {r.status_code} {r.text}")
    content = base64.b64decode(r.json()["content"]).decode("utf-8")
    payload = json.loads(content)
    return payload.get("records", payload if isinstance(payload, list) else [])


async def github_save(records: List[Dict[str, Any]]) -> None:
    if not (GITHUB_TOKEN and GITHUB_REPO):
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump({"records": records, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
        return
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_DB_PATH}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(timeout=20) as client:
        current = await client.get(f"{url}?ref={GITHUB_BRANCH}", headers=headers)
        sha = current.json().get("sha") if current.status_code == 200 else None
        payload = {
            "message": "Update vehicle dashboard JSON DB",
            "branch": GITHUB_BRANCH,
            "content": base64.b64encode(json.dumps({"records": records, "updated_at": datetime.now().isoformat()}, ensure_ascii=False, indent=2).encode()).decode(),
        }
        if sha:
            payload["sha"] = sha
        r = await client.put(url, headers=headers, json=payload)
    if r.status_code >= 400:
        raise HTTPException(502, f"GitHub save failed: {r.status_code} {r.text}")


async def load_records() -> List[Dict[str, Any]]:
    if GITHUB_TOKEN and GITHUB_REPO:
        return await github_get()
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("records", [])


def parse_excel(content: bytes, filename: str) -> Dict[str, Any]:
    wb = load_workbook(BytesIO(content), data_only=True)
    records, errors = [], []
    skipped_sheets = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        header_idx, headers = None, []
        for idx, row in enumerate(rows[:20]):
            values = [clean_text(v) for v in row]
            if all(h in values for h in ["วันที่", "ประเภทรถ", "บริษัท", "ยอดเก็บจริง"]):
                header_idx, headers = idx, values
                break
        if header_idx is None:
            skipped_sheets.append(ws.title)
            continue
        missing = [h for h in REQUIRED_HEADERS if h not in headers]
        if missing:
            errors.append({"sheet": ws.title, "row": header_idx + 1, "error": f"Missing header: {', '.join(missing)}"})
            continue
        col = {h: headers.index(h) for h in REQUIRED_HEADERS if h in headers}
        last_date = ""
        for excel_row_no, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
            if not any(row):
                continue
            date_val = row[col["วันที่"]] if col.get("วันที่") is not None and col["วันที่"] < len(row) else None
            if date_val:
                last_date = clean_text(date_val)
            data = {h: (row[col[h]] if col[h] < len(row) else None) for h in col}
            data["วันที่"] = data.get("วันที่") or last_date
            if not data.get("ประเภทรถ") and not data.get("บริษัท"):
                continue
            if not data.get("วันที่"):
                errors.append({"sheet": ws.title, "row": excel_row_no, "error": "วันที่ว่าง และไม่สามารถ fill down ได้"})
                continue
            records.append(normalize_record(data, excel_row_no, f"excel:{filename}:{ws.title}"))
    return {"records": records, "errors": errors, "skipped_sheets": skipped_sheets}


def parse_text(text: str) -> Dict[str, Any]:
    records, errors = [], []
    current_date, current_type, current_company = "", "", ""
    for i, line in enumerate(text.splitlines(), start=1):
        s = line.strip()
        if not s:
            continue
        m = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", s)
        if "สรุปยอด" in s and m:
            current_date = m.group(1)
            continue
        if "รถจักรยานยนต์" in s or "มอเตอร์" in s:
            current_type = "รถจักรยานยนต์"; current_company = "RVP"; continue
        if "รถกระบะ" in s:
            current_type = "รถกระบะ"; continue
        if "รถยนต์" in s or "เก๋ง" in s:
            current_type = "รถยนต์ เก๋ง"; continue
        if "ERGO" in s.upper():
            current_company = "ERGO"; continue
        if "ไทยไพบูลย์" in s or "TPB" in s.upper():
            current_company = "TPB"; continue
        if s.startswith("•") or "_" in s:
            if not current_date:
                errors.append({"row": i, "error": "ไม่พบวันที่ก่อนรายการรถ"})
            records.append(normalize_record({
                "วันที่": current_date,
                "ประเภทรถ": current_type or "ไม่ระบุ",
                "บริษัท": current_company,
                "ยอดสุทธิ": 0,
                "ยอดเก็บจริง": 0,
                "รหัส": s.lstrip("• "),
            }, i, "text"))
    return {"records": records, "errors": errors, "skipped_sheets": []}


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/summary")
async def api_summary():
    records = await load_records()
    return build_summary(records)


@app.get("/api/details")
async def api_details(company: Optional[str] = None):
    records = await load_records()
    if company and company.upper() != "TOTAL":
        records = [r for r in records if r.get("company") == company.upper()]
    return {"records": records, "count": len(records)}


@app.post("/api/import/preview")
async def import_preview(file: Optional[UploadFile] = File(None), text: Optional[str] = Form(None)):
    if file:
        content = await file.read()
        if file.filename.lower().endswith((".xlsx", ".xlsm")):
            result = parse_excel(content, file.filename)
        else:
            result = parse_text(content.decode("utf-8", errors="ignore"))
    elif text:
        result = parse_text(text)
    else:
        raise HTTPException(400, "กรุณาอัปโหลดไฟล์ หรือใส่ข้อความ")
    result["summary"] = build_summary(result["records"])
    result["valid"] = len(result["errors"]) == 0
    return result


@app.post("/api/import/save")
async def import_save(payload: Dict[str, Any]):
    records = payload.get("records", [])
    if not isinstance(records, list):
        raise HTTPException(400, "records ต้องเป็น list")
    await github_save(records)
    return {"ok": True, "count": len(records), "summary": build_summary(records)}


@app.get("/health")
async def health():
    return {"ok": True, "app": APP_TITLE}
