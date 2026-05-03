import base64
import io
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
LOCAL_DB = BASE_DIR / "vehicle_data.json"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip()  # owner/repo
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
GITHUB_FILE_PATH = os.getenv("GITHUB_FILE_PATH", "vehicle_data.json").strip()

COMPANY_ORDER = ["RVP", "ERGO", "TPB"]
COMPANY_LABELS = {
    "RVP": "บริษัทกลาง RVP",
    "ERGO": "ERGO",
    "TPB": "ไทยไพบูลย์ TPB",
}
REQUIRED_EXCEL_HEADERS = ["วันที่", "ประเภทรถ", "บริษัท", "ยอดเก็บจริง"]
OPTIONAL_NET_HEADERS = ["ยอดสุทธิ", "ยอดเงินสุทธิ", "สุทธิ"]

app = FastAPI(title="Vehicle Dashboard System", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class SavePayload(BaseModel):
    rows: List[Dict[str, Any]]
    replace_all: bool = True


def to_float(value: Any) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    text = str(value).strip().replace(",", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in ("", ".", "-", "-"):
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def clean_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def normalize_company(company: Any, vehicle_type: Any = "") -> str:
    c = clean_text(company).upper()
    vt = clean_text(vehicle_type)
    if any(x in c for x in ["RVP", "บริษัทกลาง", "กลาง"]):
        return "RVP"
    if any(x in c for x in ["ERGO", "เออร์โก"]):
        return "ERGO"
    if any(x in c for x in ["TPB", "ไทยไพบูลย์", "ไพบูลย์"]):
        return "TPB"
    if "มอเตอร์" in vt or "จักรยาน" in vt or "motor" in vt.lower():
        return "RVP"
    return c if c in COMPANY_ORDER else "TPB"


def normalize_vehicle_type(value: Any) -> str:
    text = clean_text(value)
    low = text.lower()
    if any(k in text for k in ["มอเตอร์", "จักรยาน"]) or "motor" in low:
        return "รถจักรยานยนต์"
    if "กระบะ" in text or "pickup" in low:
        return "รถกระบะ"
    if any(k in text for k in ["เก๋ง", "รถยนต์", "ยนต์"]):
        return "รถยนต์/เก๋ง"
    if "บรรทุก" in text or "truck" in low:
        return "รถบรรทุก"
    return text or "ไม่ระบุประเภทรถ"


def normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    vehicle_type = normalize_vehicle_type(row.get("ประเภทรถ") or row.get("vehicle_type"))
    company = normalize_company(row.get("บริษัท") or row.get("company"), vehicle_type)
    net_total = to_float(row.get("ยอดสุทธิ") or row.get("net_total") or row.get("ยอดเงินสุทธิ"))
    collected_total = to_float(row.get("ยอดเก็บจริง") or row.get("collected_total") or row.get("ยอดเงิน"))
    return {
        "date": clean_text(row.get("วันที่") or row.get("date")),
        "vehicle_type": vehicle_type,
        "company": company,
        "code": clean_text(row.get("รหัส") or row.get("code") or row.get("ทะเบียน")),
        "net_total": net_total,
        "collected_total": collected_total,
        "source": clean_text(row.get("source")),
        "imported_at": clean_text(row.get("imported_at")) or datetime.utcnow().isoformat(),
    }


def read_local() -> List[Dict[str, Any]]:
    if not LOCAL_DB.exists():
        return []
    try:
        data = json.loads(LOCAL_DB.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("rows", [])
    except Exception:
        return []


def github_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_url() -> str:
    return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"


def read_github() -> Optional[List[Dict[str, Any]]]:
    if not (GITHUB_TOKEN and GITHUB_REPO):
        return None
    r = requests.get(github_url(), headers=github_headers(), params={"ref": GITHUB_BRANCH}, timeout=20)
    if r.status_code == 404:
        return []
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub read failed: {r.status_code} {r.text}")
    content = base64.b64decode(r.json()["content"]).decode("utf-8")
    data = json.loads(content)
    return data if isinstance(data, list) else data.get("rows", [])


def write_storage(rows: List[Dict[str, Any]]) -> None:
    LOCAL_DB.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    if not (GITHUB_TOKEN and GITHUB_REPO):
        return
    sha = None
    get = requests.get(github_url(), headers=github_headers(), params={"ref": GITHUB_BRANCH}, timeout=20)
    if get.status_code == 200:
        sha = get.json().get("sha")
    elif get.status_code not in (404,):
        raise HTTPException(status_code=502, detail=f"GitHub get sha failed: {get.status_code} {get.text}")
    payload = {
        "message": f"Update vehicle dashboard data {datetime.utcnow().isoformat()}",
        "content": base64.b64encode(json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii"),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    put = requests.put(github_url(), headers=github_headers(), json=payload, timeout=30)
    if put.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub write failed: {put.status_code} {put.text}")


def load_rows() -> List[Dict[str, Any]]:
    gh = read_github()
    if gh is not None:
        return [normalize_row(r) for r in gh]
    return [normalize_row(r) for r in read_local()]


def build_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    normalized = [normalize_row(r) for r in rows]
    total_count = len(normalized)
    companies = {}
    all_vehicle_types = defaultdict(int)
    total_net = 0.0
    total_collected = 0.0

    for key in COMPANY_ORDER:
        companies[key] = {
            "company": key,
            "label": COMPANY_LABELS[key],
            "vehicle_count": 0,
            "net_total": 0.0,
            "collected_total": 0.0,
            "share_percent": 0.0,
            "vehicle_types": {},
        }

    for row in normalized:
        company = row["company"] if row["company"] in COMPANY_ORDER else "TPB"
        vehicle_type = row["vehicle_type"] or "ไม่ระบุประเภทรถ"
        net = float(row.get("net_total") or 0)
        collected = float(row.get("collected_total") or 0)
        companies[company]["vehicle_count"] += 1
        companies[company]["net_total"] += net
        companies[company]["collected_total"] += collected
        companies[company]["vehicle_types"][vehicle_type] = companies[company]["vehicle_types"].get(vehicle_type, 0) + 1
        all_vehicle_types[vehicle_type] += 1
        total_net += net
        total_collected += collected

    for key in COMPANY_ORDER:
        companies[key]["share_percent"] = round((companies[key]["vehicle_count"] / total_count * 100), 2) if total_count else 0
        companies[key]["net_total"] = round(companies[key]["net_total"], 2)
        companies[key]["collected_total"] = round(companies[key]["collected_total"], 2)

    total_card = {
        "company": "TOTAL",
        "label": "รวมทั้งหมด",
        "vehicle_count": total_count,
        "net_total": round(total_net, 2),
        "collected_total": round(total_collected, 2),
        "share_percent": 100 if total_count else 0,
        "vehicle_types": dict(all_vehicle_types),
    }

    return {
        "companies": [companies[k] for k in COMPANY_ORDER] + [total_card],
        "total": total_card,
        "updated_at": datetime.utcnow().isoformat(),
    }


def find_header_row(df: pd.DataFrame) -> int:
    for i in range(min(15, len(df))):
        values = [clean_text(v) for v in df.iloc[i].tolist()]
        if all(h in values for h in REQUIRED_EXCEL_HEADERS):
            return i
    return -1


def parse_excel(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    skipped_sheets: List[str] = []

    for sheet in xls.sheet_names:
        raw = pd.read_excel(xls, sheet_name=sheet, header=None, dtype=object)
        header_idx = find_header_row(raw)
        if header_idx < 0:
            skipped_sheets.append(sheet)
            continue
        headers = [clean_text(v) for v in raw.iloc[header_idx].tolist()]
        data = raw.iloc[header_idx + 1:].copy()
        data.columns = headers
        data = data.loc[:, [c for c in data.columns if c]]
        data = data.ffill()
        missing = [h for h in REQUIRED_EXCEL_HEADERS if h not in data.columns]
        if missing:
            errors.append({"sheet": sheet, "row": header_idx + 1, "error": f"Missing headers: {', '.join(missing)}"})
            continue
        net_col = next((c for c in OPTIONAL_NET_HEADERS if c in data.columns), None)
        for idx, record in data.iterrows():
            date = clean_text(record.get("วันที่"))
            vehicle_type = clean_text(record.get("ประเภทรถ"))
            company = clean_text(record.get("บริษัท"))
            collected = record.get("ยอดเก็บจริง")
            if not any([date, vehicle_type, company, clean_text(collected)]):
                continue
            if not vehicle_type:
                errors.append({"sheet": sheet, "row": int(idx) + 1, "error": "ไม่พบประเภทรถ"})
                continue
            if clean_text(collected) == "":
                errors.append({"sheet": sheet, "row": int(idx) + 1, "error": "ไม่พบยอดเก็บจริง"})
                continue
            rows.append(normalize_row({
                "วันที่": date,
                "ประเภทรถ": vehicle_type,
                "บริษัท": company,
                "ยอดสุทธิ": record.get(net_col) if net_col else 0,
                "ยอดเก็บจริง": collected,
                "รหัส": record.get("รหัส") or record.get("ทะเบียน") or "",
                "source": filename,
            }))
    return {"rows": rows, "errors": errors, "skipped_sheets": skipped_sheets, "summary": build_summary(rows)}


def parse_text(text: str) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    current_date = ""
    current_type = ""
    current_company = ""
    errors = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        mdate = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", line)
        if "วันที่" in line and mdate:
            current_date = mdate.group(1)
            continue
        if any(k in line for k in ["รถจักรยานยนต์", "รถมอเตอร์", "รถกระบะ", "รถยนต์", "รถเก๋ง"]):
            current_type = normalize_vehicle_type(line)
            if "(" in current_type:
                current_type = current_type.split("(")[0].strip()
            continue
        if line.startswith("[") and line.endswith("]"):
            current_company = normalize_company(line.strip("[]"), current_type)
            continue
        if line.startswith("•") or re.search(r"\d", line):
            code = line.lstrip("•").strip()
            if len(code) < 3:
                continue
            rows.append(normalize_row({
                "วันที่": current_date,
                "ประเภทรถ": current_type or "ไม่ระบุประเภทรถ",
                "บริษัท": current_company or normalize_company("", current_type),
                "ยอดสุทธิ": 0,
                "ยอดเก็บจริง": 0,
                "รหัส": code,
                "source": "legacy_text",
            }))
    return {"rows": rows, "errors": errors, "skipped_sheets": [], "summary": build_summary(rows)}


@app.get("/")
def index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse({"ok": True, "message": "Vehicle Dashboard API is running"})
    return FileResponse(index_file)


@app.get("/api/health")
def health():
    return {"ok": True, "static_dir": str(STATIC_DIR), "static_exists": STATIC_DIR.exists()}


@app.get("/api/data")
def api_data():
    rows = load_rows()
    return {"rows": rows, "count": len(rows)}


@app.get("/api/summary")
def api_summary():
    return build_summary(load_rows())


@app.post("/api/import/preview")
async def import_preview(file: Optional[UploadFile] = File(None), text: str = Form("")):
    if file:
        content = await file.read()
        name = file.filename or "upload"
        if name.lower().endswith((".xlsx", ".xls")):
            return parse_excel(content, name)
        if name.lower().endswith((".txt", ".csv")):
            return parse_text(content.decode("utf-8-sig", errors="ignore"))
        raise HTTPException(status_code=400, detail="รองรับเฉพาะ Excel, TXT, CSV")
    if text.strip():
        return parse_text(text)
    raise HTTPException(status_code=400, detail="กรุณาอัปโหลดไฟล์หรือใส่ข้อความ")


@app.post("/api/import/save")
def import_save(payload: SavePayload):
    new_rows = [normalize_row(r) for r in payload.rows]
    rows = new_rows if payload.replace_all else load_rows() + new_rows
    write_storage(rows)
    return {"ok": True, "count": len(rows), "summary": build_summary(rows)}


@app.delete("/api/data")
def clear_data():
    write_storage([])
    return {"ok": True, "count": 0}
