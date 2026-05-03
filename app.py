from __future__ import annotations

import os
import json
import base64
import time
import urllib.request
import urllib.error
import openpyxl
from datetime import datetime, date
from pathlib import Path
from typing import Any
from io import BytesIO

from fastapi import FastAPI, Form, HTTPException, Query, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-this-token")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")
GITHUB_FILE = os.getenv("GITHUB_FILE", "data.json")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "20"))
DASHBOARD_CACHE: dict[str, Any] = {"key": None, "data": None, "created_at": 0.0}

app = FastAPI(title="Vehicle Dashboard v6.5 Excel Money Import Status")


def github_enabled() -> bool:
    return bool(GITHUB_TOKEN and GITHUB_REPO and GITHUB_FILE)


def github_api_url() -> str:
    return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"


def github_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "vehicle-dashboard",
    }


def github_request(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=github_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            body = res.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise HTTPException(status_code=500, detail=f"GitHub API error {e.code}: {detail}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub connection error: {str(e)}")


def empty_store() -> dict[str, Any]:
    return {"version": 1, "updated_at": None, "daily_records": [], "weekly_summaries": []}


def read_github_store() -> tuple[dict[str, Any], str | None]:
    if not github_enabled():
        raise HTTPException(status_code=500, detail="ยังไม่ได้ตั้งค่า GITHUB_TOKEN / GITHUB_REPO / GITHUB_FILE")
    url = github_api_url() + f"?ref={GITHUB_BRANCH}"
    try:
        res = github_request("GET", url)
    except HTTPException as e:
        if "GitHub API error 404" in str(e.detail):
            return empty_store(), None
        raise
    content = base64.b64decode(res.get("content", "")).decode("utf-8")
    data = json.loads(content) if content.strip() else empty_store()
    data.setdefault("daily_records", [])
    data.setdefault("weekly_summaries", [])
    return data, res.get("sha")


def write_github_store(data: dict[str, Any], sha: str | None, message: str) -> None:
    content = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")).decode("utf-8")
    payload: dict[str, Any] = {"message": message, "content": content, "branch": GITHUB_BRANCH}
    if sha:
        payload["sha"] = sha
    github_request("PUT", github_api_url(), payload)


def make_cache_key(start: str | None, end: str | None, q: str | None) -> str:
    return f"start={start or ''}|end={end or ''}|q={q or ''}"


def clear_dashboard_cache() -> None:
    DASHBOARD_CACHE["key"] = None
    DASHBOARD_CACHE["data"] = None
    DASHBOARD_CACHE["created_at"] = 0.0


def get_cached_dashboard(key: str) -> dict[str, Any] | None:
    if DASHBOARD_CACHE["key"] != key or DASHBOARD_CACHE["data"] is None:
        return None
    if time.time() - float(DASHBOARD_CACHE["created_at"] or 0) > CACHE_TTL_SECONDS:
        return None
    return DASHBOARD_CACHE["data"]


def set_cached_dashboard(key: str, data: dict[str, Any]) -> None:
    DASHBOARD_CACHE["key"] = key
    DASHBOARD_CACHE["data"] = data
    DASHBOARD_CACHE["created_at"] = time.time()


@app.on_event("startup")
def startup() -> None:
    pass


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
                    "companyGroup": map_company_group(current_meta["key"], current_company or ""),
                    "item": item_text,
                    "netAmount": 0,
                    "collectedAmount": 0,
                }
            )

    for period, summary in weekly_summaries.items():
        if not summary["total"]:
            summary["total"] = summary["car"] + summary["motorcycle"]

    return {
        "rows": rows,
        "weeklySummaries": weekly_summaries,
    }


def normalize_header(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("\n", "").replace("\r", "")
    text = text.replace(" ", "").replace("\u00a0", "")
    text = text.replace("ํ", "")  # normalize rare Thai mark typo in บริษํท
    return text


def find_header_row(ws) -> tuple[int | None, dict[str, int]]:
    required_aliases = {
        "date": ["วันที่", "วันที"],
        "vehicle_type": ["ประเภทรถ", "ประเภท"],
        "company": ["บริษัท", "บริษํท"],
        "item": ["รหัส", "เลขกรมธรรม์", "รายการ"],
        "net_amount": ["ยอดสุทธิ", "สุทธิ", "ยอดเงินสุทธิ", "Net", "net"],
        "collected_amount": ["ยอดเก็บจริง", "ยอดเก็บ", "เก็บจริง", "ยอดรับจริง", "Collected", "collected"],
    }

    for row_idx in range(1, min(ws.max_row, 20) + 1):
        header_map: dict[str, int] = {}
        normalized = {
            normalize_header(ws.cell(row_idx, col_idx).value): col_idx
            for col_idx in range(1, ws.max_column + 1)
        }

        for key, aliases in required_aliases.items():
            for alias in aliases:
                alias_norm = normalize_header(alias)
                if alias_norm in normalized:
                    header_map[key] = normalized[alias_norm]
                    break

        must_have = ["date", "vehicle_type", "company", "item", "collected_amount"]
        if all(key in header_map for key in must_have):
            return row_idx, header_map

    return None, {}


def parse_excel_date(value: Any) -> tuple[str, str]:
    if value is None or value == "":
        return "", ""

    if isinstance(value, datetime):
        y = value.year + 543 if value.year < 2400 else value.year
        return f"{value.day:02d}/{value.month:02d}/{y}", f"{value.year:04d}-{value.month:02d}-{value.day:02d}"

    if isinstance(value, date):
        y = value.year + 543 if value.year < 2400 else value.year
        return f"{value.day:02d}/{value.month:02d}/{y}", f"{value.year:04d}-{value.month:02d}-{value.day:02d}"

    text = str(value).strip()
    if not text:
        return "", ""

    text = text.replace("-", "/").replace(".", "/")
    parts = [p for p in text.split("/") if p]
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        d, m, y = [int(p) for p in parts]
        iso_y = y - 543 if y > 2400 else y
        display_y = y if y > 2400 else y + 543
        return f"{d:02d}/{m:02d}/{display_y}", f"{iso_y:04d}-{m:02d}-{d:02d}"

    return text, ""


def to_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("บาท", "").strip()
    try:
        return float(text)
    except Exception:
        return only_number(text)


def map_excel_vehicle_type(value: Any) -> dict[str, str] | None:
    text = str(value or "").strip()
    if not text:
        return None
    if "มอเตอร์" in text or "จักรยานยนต์" in text:
        return {"key": "motorcycle", "icon": "🏍", "title": "รถจักรยานยนต์"}
    if "กระบะ" in text:
        return {"key": "pickup", "icon": "🚛", "title": "รถกระบะ"}
    if "เก๋ง" in text or "รถยนต์" in text:
        return {"key": "sedan", "icon": "🚗", "title": "รถยนต์เก๋ง"}
    return {"key": "unknown", "icon": "❔", "title": text}


def map_company_group(vehicle_type: str, company: str) -> str:
    c = (company or "").lower()
    if vehicle_type == "motorcycle":
        return "RVP"
    if "ergo" in c:
        return "ERGO"
    if "ไทยไพบูลย์" in c or "tpb" in c:
        return "TPB"
    return "UNKNOWN"


def parse_excel_report(file_bytes: bytes) -> dict[str, Any]:
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    rows: list[dict[str, Any]] = []
    sheet_stats: list[dict[str, Any]] = []

    for ws in wb.worksheets:
        header_row, col = find_header_row(ws)
        if not header_row:
            preview_headers = []
            for rr in range(1, min(ws.max_row, 5) + 1):
                preview_headers.append([str(ws.cell(rr, cc).value or "").strip() for cc in range(1, min(ws.max_column, 8) + 1)])
            sheet_stats.append({"sheet": ws.title, "status": "skipped", "reason": "ไม่พบ header ที่จำเป็น", "preview": preview_headers})
            continue

        last_date_text = ""
        last_iso_date = ""
        last_vehicle_text = ""
        last_company = ""
        inserted = 0

        for r in range(header_row + 1, ws.max_row + 1):
            raw_date = ws.cell(r, col["date"]).value
            raw_vehicle = ws.cell(r, col["vehicle_type"]).value
            raw_company = ws.cell(r, col["company"]).value
            raw_item = ws.cell(r, col["item"]).value
            raw_net = ws.cell(r, col.get("net_amount", col["collected_amount"])).value
            raw_collected = ws.cell(r, col["collected_amount"]).value

            date_text, iso_date = parse_excel_date(raw_date)
            if date_text and iso_date:
                last_date_text = date_text
                last_iso_date = iso_date
            else:
                date_text = last_date_text
                iso_date = last_iso_date

            vehicle_text = str(raw_vehicle).strip() if raw_vehicle not in (None, "") else last_vehicle_text
            if raw_vehicle not in (None, ""):
                last_vehicle_text = vehicle_text

            company = str(raw_company).strip() if raw_company not in (None, "") else last_company
            if raw_company not in (None, ""):
                last_company = company

            item = str(raw_item or "").strip().replace("_", " ")
            if not item or not iso_date or not vehicle_text:
                continue

            meta = map_excel_vehicle_type(vehicle_text)
            if not meta:
                continue

            net_amount = to_float(raw_net)
            collected_amount = to_float(raw_collected)

            rows.append({
                "date": date_text,
                "isoDate": iso_date,
                "vehicleType": meta["key"],
                "vehicleTitle": meta["title"],
                "icon": meta["icon"],
                "company": company,
                "companyGroup": map_company_group(meta["key"], company),
                "item": item,
                "netAmount": net_amount,
                "collectedAmount": collected_amount,
                "sourceSheet": ws.title,
            })
            inserted += 1

        sheet_stats.append({"sheet": ws.title, "status": "imported", "rows": inserted})

    if not rows:
        raise HTTPException(status_code=400, detail="อ่าน Excel ไม่สำเร็จ: ไม่พบชีตที่มี header และข้อมูลที่ใช้งานได้")

    return {"rows": rows, "sheetStats": sheet_stats}


def make_summaries_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = datetime.utcnow().isoformat()
    vehicle_summary = {"car": 0.0, "motorcycle": 0.0, "total": 0.0}
    company_summary = {"RVP": 0.0, "ERGO": 0.0, "TPB": 0.0, "UNKNOWN": 0.0}

    for row in rows:
        amount = float(row.get("collectedAmount", 0) or 0)
        vehicle_type = row.get("vehicleType", "")
        company_group = row.get("companyGroup") or map_company_group(vehicle_type, row.get("company", ""))

        if vehicle_type == "motorcycle":
            vehicle_summary["motorcycle"] += amount
        elif vehicle_type in ("pickup", "sedan"):
            vehicle_summary["car"] += amount
        vehicle_summary["total"] += amount
        company_summary.setdefault(company_group, 0.0)
        company_summary[company_group] += amount

    return [
        {
            "period_key": "EXCEL_IMPORT_TOTAL",
            "car_amount": round(vehicle_summary["car"], 2),
            "motorcycle_amount": round(vehicle_summary["motorcycle"], 2),
            "total_amount": round(vehicle_summary["total"], 2),
            "company_amounts": {k: round(v, 2) for k, v in company_summary.items()},
            "updated_at": now,
        }
    ]




def save_records_replace_all(rows: list[dict[str, Any]], summaries: list[dict[str, Any]], import_type: str, sheet_stats: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not rows:
        raise HTTPException(status_code=400, detail="ไม่พบรายการสำหรับนำเข้า")

    now = datetime.utcnow().isoformat()
    imported_dates = sorted({row["isoDate"] for row in rows if row.get("isoDate")})
    store, sha = read_github_store()

    old_record_count = len(store.get("daily_records", []))
    old_summary_count = len(store.get("weekly_summaries", []))

    records = []
    for row in rows:
        vehicle_type = row.get("vehicleType", "")
        company = row.get("company", "")
        records.append({
            "date_text": row.get("date", ""),
            "iso_date": row.get("isoDate", ""),
            "vehicle_type": vehicle_type,
            "vehicle_title": row.get("vehicleTitle", ""),
            "icon": row.get("icon", ""),
            "company": company,
            "company_group": row.get("companyGroup") or map_company_group(vehicle_type, company),
            "item": row.get("item", ""),
            "net_amount": float(row.get("netAmount", 0) or 0),
            "collected_amount": float(row.get("collectedAmount", 0) or 0),
            "source_sheet": row.get("sourceSheet", ""),
            "created_at": now,
        })

    store = {
        "version": 2,
        "updated_at": now,
        "import_type": import_type,
        "daily_records": records,
        "weekly_summaries": summaries,
        "sheet_stats": sheet_stats or [],
        "import_summary": build_company_summary([
            {
                "vehicle_type": r.get("vehicleType", ""),
                "company": r.get("company", ""),
                "company_group": r.get("companyGroup") or map_company_group(r.get("vehicleType", ""), r.get("company", "")),
                "net_amount": r.get("netAmount", 0),
                "collected_amount": r.get("collectedAmount", 0),
            }
            for r in rows
        ]),
    }

    write_github_store(store, sha, f"update vehicle dashboard data {import_type} {now}")
    clear_dashboard_cache()

    return {
        "report_id": 0,
        "import_type": import_type,
        "imported_dates": len(imported_dates),
        "deleted_records": int(old_record_count or 0),
        "deleted_summaries": int(old_summary_count or 0),
        "inserted": len(records),
        "replaced_summaries": len(summaries),
        "parsed_rows": len(rows),
        "duplicated": 0,
        "sheet_stats": sheet_stats or [],
    }


def save_import_replace_all(raw_text: str) -> dict[str, Any]:
    parsed = parse_report(raw_text)
    rows = parsed["rows"]
    weekly_summaries = parsed["weeklySummaries"]
    if not rows:
        raise HTTPException(status_code=400, detail="อ่านข้อมูลไม่สำเร็จ: ไม่พบรายการรายวัน")

    summaries = []
    now = datetime.utcnow().isoformat()
    for period, summary in weekly_summaries.items():
        summaries.append({
            "period_key": period,
            "car_amount": summary["car"],
            "motorcycle_amount": summary["motorcycle"],
            "total_amount": summary["total"],
            "company_amounts": {},
            "updated_at": now,
        })

    return save_records_replace_all(rows, summaries, "text", [])


def save_excel_import_replace_all(file_bytes: bytes) -> dict[str, Any]:
    parsed = parse_excel_report(file_bytes)
    rows = parsed["rows"]
    summaries = make_summaries_from_rows(rows)
    return save_records_replace_all(rows, summaries, "excel", parsed["sheetStats"])


def get_money_totals_from_weekly_summaries(store: dict[str, Any]) -> dict[str, Any]:
    summaries = store.get("weekly_summaries", [])
    car = sum(float(s.get("car_amount", 0) or 0) for s in summaries)
    motorcycle = sum(float(s.get("motorcycle_amount", 0) or 0) for s in summaries)
    total = sum(float(s.get("total_amount", 0) or 0) for s in summaries)

    company_amounts = {"RVP": 0.0, "ERGO": 0.0, "TPB": 0.0, "UNKNOWN": 0.0}
    for s in summaries:
        for k, v in (s.get("company_amounts") or {}).items():
            company_amounts[k] = company_amounts.get(k, 0.0) + float(v or 0)

    # Fallback for older text-only data without company amount
    if not any(company_amounts.values()):
        company_amounts["RVP"] = motorcycle

    return {
        "car": round(car, 2),
        "motorcycle": round(motorcycle, 2),
        "total": round(total, 2),
        "company": {k: round(v, 2) for k, v in company_amounts.items()},
    }



def build_company_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "RVP": {"count": 0, "net": 0.0, "collected": 0.0, "vehicles": {"motorcycle": 0, "pickup": 0, "sedan": 0}},
        "ERGO": {"count": 0, "net": 0.0, "collected": 0.0, "vehicles": {"motorcycle": 0, "pickup": 0, "sedan": 0}},
        "TPB": {"count": 0, "net": 0.0, "collected": 0.0, "vehicles": {"motorcycle": 0, "pickup": 0, "sedan": 0}},
        "UNKNOWN": {"count": 0, "net": 0.0, "collected": 0.0, "vehicles": {"motorcycle": 0, "pickup": 0, "sedan": 0}},
    }

    for row in rows:
        vehicle_type = row.get("vehicle_type", "")
        company = row.get("company", "")
        group = row.get("company_group") or map_company_group(vehicle_type, company)
        if group not in summary:
            group = "UNKNOWN"

        summary[group]["count"] += 1
        summary[group]["net"] += float(row.get("net_amount", 0) or 0)
        summary[group]["collected"] += float(row.get("collected_amount", 0) or 0)
        if vehicle_type in summary[group]["vehicles"]:
            summary[group]["vehicles"][vehicle_type] += 1

    total = {
        "count": sum(v["count"] for v in summary.values()),
        "net": sum(v["net"] for v in summary.values()),
        "collected": sum(v["collected"] for v in summary.values()),
        "vehicles": {
            "motorcycle": sum(v["vehicles"]["motorcycle"] for v in summary.values()),
            "pickup": sum(v["vehicles"]["pickup"] for v in summary.values()),
            "sedan": sum(v["vehicles"]["sedan"] for v in summary.values()),
        },
    }

    for group in summary:
        summary[group]["net"] = round(summary[group]["net"], 2)
        summary[group]["collected"] = round(summary[group]["collected"], 2)

    total["net"] = round(total["net"], 2)
    total["collected"] = round(total["collected"], 2)
    summary["TOTAL"] = total
    return summary


def get_dashboard_data(start: str | None = None, end: str | None = None, q: str | None = None) -> dict[str, Any]:
    store, _ = read_github_store()
    all_rows = store.get("daily_records", [])
    q_lower = (q or "").strip().lower()

    filtered_rows = []
    for row in all_rows:
        iso_date = row.get("iso_date", "")
        if start and iso_date < start:
            continue
        if end and iso_date > end:
            continue
        if q_lower:
            haystack = " ".join([row.get("item", ""), row.get("company", ""), row.get("vehicle_title", ""), row.get("date_text", "")]).lower()
            if q_lower not in haystack:
                continue
        filtered_rows.append(row)

    days: dict[str, Any] = {}
    for row in sorted(filtered_rows, key=lambda r: (r.get("iso_date", ""), r.get("item", ""))):
        day_key = row.get("iso_date", "")
        if day_key not in days:
            days[day_key] = {"date": row.get("date_text", ""), "isoDate": row.get("iso_date", ""), "motorcycle": 0, "pickup": 0, "sedan": 0, "groups": {}}
        day = days[day_key]
        vehicle_type = row.get("vehicle_type", "")
        company = row.get("company", "") or ""
        group_key = f"{vehicle_type}|{company}"
        if group_key not in day["groups"]:
            day["groups"][group_key] = {"key": vehicle_type, "icon": row.get("icon", ""), "title": row.get("vehicle_title", ""), "company": company, "items": []}
        day["groups"][group_key]["items"].append(row.get("item", ""))
        if vehicle_type in ("motorcycle", "pickup", "sedan"):
            day[vehicle_type] += 1

    daily_data = []
    for day in days.values():
        groups = []
        for group in day["groups"].values():
            group["count"] = len(group["items"])
            groups.append(group)
        day["groups"] = groups
        daily_data.append(day)

    motorcycle = sum(1 for r in filtered_rows if r.get("vehicle_type") == "motorcycle")
    pickup = sum(1 for r in filtered_rows if r.get("vehicle_type") == "pickup")
    sedan = sum(1 for r in filtered_rows if r.get("vehicle_type") == "sedan")
    money_totals = get_money_totals_from_weekly_summaries(store)
    iso_dates = [r.get("iso_date", "") for r in all_rows if r.get("iso_date")]

    return {
        "period": "📊 Dashboard ข้อมูลสะสมทั้งหมด",
        "amounts": money_totals,
        "dailyData": daily_data,
        "totals": {"motorcycle": int(motorcycle or 0), "pickup": int(pickup or 0), "sedan": int(sedan or 0), "all": int((motorcycle or 0) + (pickup or 0) + (sedan or 0))},
        "dateRange": {"start": min(iso_dates) if iso_dates else None, "end": max(iso_dates) if iso_dates else None},
        "recordCount": len(filtered_rows),
        "storage": "github_json",
        "updated_at": store.get("updated_at"),
        "companyAmounts": money_totals.get("company", {}),
        "importType": store.get("import_type", ""),
        "companySummary": build_company_summary(filtered_rows),
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
        <input type="file" id="file" accept=".txt,.xlsx,.xls,text/plain,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel">
      </div>
      <textarea id="raw_text" placeholder="วางข้อมูล Text เดิม หรือเลือกไฟล์ Excel (.xlsx) เพื่อ Import ได้เลย..."></textarea>
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
  const name = file.name.toLowerCase();
  if(name.endsWith('.txt')){
    rawText.value = await file.text();
  }else if(name.endsWith('.xlsx') || name.endsWith('.xls')){
    statusBox.textContent = 'เลือกไฟล์ Excel แล้ว: ' + file.name + '\nระบบจะอ่านทุกชีตที่มี header ถูกต้อง และข้ามชีต Dropdown อัตโนมัติ';
  }
});
form.addEventListener('submit', async event => {
  event.preventDefault();
  const fd = new FormData();
  fd.append('raw_text', rawText.value);
  fd.append('token', document.getElementById('token').value);
  const file = fileInput.files && fileInput.files[0];
  if(file){ fd.append('file', file); }
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
<link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
<style>
:root{--bg:#f3f6fb;--card:#fff;--text:#172033;--muted:#667085;--blue:#2563eb;--green:#16a34a;--orange:#f97316;--cyan:#14b8a6;--dark:#111827;--line:#e5e7eb;--shadow:0 18px 42px rgba(15,23,42,.08);--glow:0 18px 40px rgba(37,99,235,.16);--radius:24px}
*{box-sizing:border-box}body{margin:0;font-family:Prompt,sans-serif;background:radial-gradient(circle at top left,#dbeafe 0,transparent 30%),radial-gradient(circle at top right,#ccfbf1 0,transparent 26%),linear-gradient(180deg,#f8fafc,var(--bg));color:var(--text)}.page{width:min(1280px,94vw);margin:0 auto;padding:32px 0 48px}
.hero{display:grid;grid-template-columns:1.5fr 1fr;gap:20px;margin-bottom:22px}.hero-card{background:linear-gradient(135deg,#0f172a 0%,#1d4ed8 58%,#14b8a6 100%);color:#fff;border-radius:32px;padding:32px;box-shadow:0 24px 60px rgba(37,99,235,.26);position:relative;overflow:hidden}.hero-card:before{content:"";position:absolute;width:340px;height:340px;border-radius:999px;right:-86px;top:-120px;background:rgba(255,255,255,.13)}.hero-card>*{position:relative;z-index:1}.hero-card h1{margin:0 0 10px;font-size:clamp(28px,4vw,46px);letter-spacing:-.6px}.hero-card p{opacity:.92}.period-pill{display:inline-flex;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.28);padding:8px 14px;border-radius:999px;margin-bottom:18px;font-weight:700;box-shadow:inset 0 1px 0 rgba(255,255,255,.24)}
.total-card,.panel,.kpi,.day-card,.toolbar,.hybrid-card{background:rgba(255,255,255,.94);box-shadow:var(--shadow);border:1px solid rgba(229,231,235,.9);backdrop-filter:blur(12px)}.total-card{border-radius:30px;padding:26px;transition:.22s}.total-card:hover,.panel:hover,.toolbar:hover{transform:translateY(-2px);box-shadow:0 22px 50px rgba(15,23,42,.11)}.label{color:var(--muted)}.amount{font-size:46px;font-weight:800;color:var(--blue);margin:8px 0}.summary-table{width:100%;border-collapse:collapse}.summary-table th,.summary-table td{padding:14px 12px;border-bottom:1px solid var(--line);text-align:left}.summary-table td:last-child,.summary-table th:last-child{text-align:right;font-weight:800}
.toolbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:14px;margin:0 0 16px;padding:16px;border-radius:var(--radius);transition:.22s}.filter-group{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.date-input,.date-select,.search-input{border:1px solid var(--line);border-radius:14px;padding:10px 14px;font-family:Prompt,sans-serif;background:#fff;outline:none;transition:.2s}.date-input:focus,.date-select:focus,.search-input:focus{border-color:#60a5fa;box-shadow:0 0 0 4px rgba(37,99,235,.1)}.search-input{min-width:250px}.btn{border:0;border-radius:14px;padding:10px 16px;font-family:Prompt,sans-serif;font-weight:800;color:#fff;background:linear-gradient(135deg,#2563eb,#14b8a6);cursor:pointer;box-shadow:0 12px 24px rgba(37,99,235,.18);transition:.2s}.btn:hover{transform:translateY(-2px);box-shadow:0 18px 32px rgba(37,99,235,.24)}.btn2{color:#1d4ed8;background:#eff6ff;box-shadow:none}.btnDark{background:#111827}.btnToggle{background:#f8fafc;color:#1d4ed8;border:1px solid #dbeafe;box-shadow:none}.btnToggle.active{background:linear-gradient(135deg,#2563eb,#14b8a6);color:#fff;border:0;box-shadow:0 12px 24px rgba(37,99,235,.18)}
.status-pill{display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border-radius:999px;background:#ecfeff;color:#155e75;font-size:13px;font-weight:800}.dot{width:8px;height:8px;border-radius:99px;background:#22c55e;box-shadow:0 0 0 5px rgba(34,197,94,.12)}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:22px}.kpi{border-radius:var(--radius);padding:20px;transition:transform .24s ease,box-shadow .24s ease,border-color .24s ease;position:relative;overflow:hidden;animation:fadeUp .42s ease both}.kpi:nth-child(2){animation-delay:.05s}.kpi:nth-child(3){animation-delay:.1s}.kpi:nth-child(4){animation-delay:.15s}.kpi:after{content:"";position:absolute;width:120px;height:120px;border-radius:999px;right:-48px;top:-48px;background:radial-gradient(circle,rgba(37,99,235,.13),rgba(20,184,166,.04));transition:.24s}.kpi:hover{transform:translateY(-7px) scale(1.015);box-shadow:0 0 0 2px rgba(37,99,235,.1),0 24px 52px rgba(37,99,235,.18);border-color:#bfdbfe}.kpi .icon{font-size:28px;margin-bottom:8px}.kpi .value{font-size:30px;font-weight:800}.kpi .title{color:var(--muted);font-size:14px}
.section-grid{display:grid;grid-template-columns:1.2fr .8fr;gap:18px;margin-bottom:22px}.panel{border-radius:var(--radius);padding:22px;transition:.22s}.panel h2{margin:0 0 12px}.chart-wrap{height:340px}.hybrid-card{border-radius:var(--radius);padding:22px;height:100%;transition:.22s}.hybrid-card:hover{transform:translateY(-2px);box-shadow:0 22px 50px rgba(15,23,42,.11)}.hybrid-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:18px}.hybrid-total{font-size:42px;font-weight:800;color:var(--blue);line-height:1}.hybrid-label{color:var(--muted);font-size:14px;margin-top:6px}.breakdown-list{display:grid;gap:12px}.breakdown-row{display:grid;grid-template-columns:1.2fr auto;gap:12px;align-items:center;padding:13px 14px;border:1px solid #edf2f7;border-radius:18px;background:linear-gradient(180deg,#fff,#f8fafc);transition:.18s}.breakdown-row:hover{transform:translateX(4px);border-color:#bfdbfe;box-shadow:0 12px 26px rgba(37,99,235,.08)}.break-left{display:flex;align-items:center;gap:10px;font-weight:800}.break-meta{display:flex;align-items:center;gap:10px;font-weight:800}.percent{color:var(--muted);font-size:13px}.bar-track{grid-column:1/-1;height:8px;border-radius:99px;background:#eef2f7;overflow:hidden}.bar-fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#2563eb,#14b8a6);width:0%;transition:width .5s}.bar-fill.orange{background:linear-gradient(90deg,#f97316,#fb923c)}.bar-fill.green{background:linear-gradient(90deg,#16a34a,#22c55e)}
.daily-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}.daily-grid.compact{display:grid;grid-template-columns:1fr;gap:10px}.day-card{border-radius:var(--radius);overflow:hidden;transition:transform .25s ease,box-shadow .25s ease,border-color .25s ease,background .25s ease;animation:fadeUp .36s ease both;position:relative}.day-card:hover{transform:translateY(-7px) scale(1.01);box-shadow:0 26px 56px rgba(15,23,42,.14);border-color:#bfdbfe}.day-card.high{border-color:#93c5fd;background:linear-gradient(180deg,#eff6ff,#fff)}.day-card.low{opacity:.82}.day-card.peak:before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:linear-gradient(180deg,#2563eb,#14b8a6)}.day-card.compact-card{border-radius:18px}.day-head{width:100%;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:18px 20px;border:0;background:linear-gradient(180deg,#fff,#fbfdff);cursor:pointer;font-family:Prompt,sans-serif;text-align:left}.compact-card .day-head{padding:14px 16px}.day-main{display:grid;gap:7px}.day-title{font-size:18px;font-weight:800}.compact-card .day-title{font-size:16px}.quick-summary{display:flex;flex-wrap:wrap;gap:8px;color:#475467;font-size:13px;font-weight:800}.mini-chip{display:inline-flex;align-items:center;gap:4px;padding:4px 9px;border-radius:999px;background:#f8fafc;border:1px solid #edf2f7}.day-tags{display:flex;gap:8px;align-items:center;justify-content:flex-end;flex-wrap:wrap}.badge{background:#eff6ff;color:#1d4ed8;border-radius:999px;padding:6px 12px;font-size:13px;font-weight:800;white-space:nowrap}.tag-peak{background:#fff7ed;color:#c2410c}.tag-low{background:#f3f4f6;color:#667085}.tag-high{background:#ecfeff;color:#0f766e}.chev{font-size:18px;color:#667085;transition:.2s}.day-card.open .chev{transform:rotate(180deg)}.day-body{max-height:0;overflow:hidden;opacity:0;transition:max-height .32s ease,opacity .25s ease,padding .25s ease;border-top:1px solid transparent;padding:0 20px}.day-card.open .day-body{max-height:900px;opacity:1;padding:0 20px 20px;border-top-color:var(--line)}.vehicle-group{margin-top:14px}.vehicle-title{font-weight:800;margin-bottom:8px}.company{display:inline-flex;margin:6px 0 4px;padding:4px 10px;border-radius:999px;background:#f3f4f6;font-size:12px;font-weight:800}ul{list-style:none;padding:0;margin:0;display:grid;gap:7px}li{background:#f9fafb;border:1px solid #eef2f7;border-radius:14px;padding:9px 11px;font-size:13px;transition:.18s}li:hover{background:#eff6ff;border-color:#bfdbfe;transform:translateX(3px)}.pagination{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:center;margin:20px 0}.page-info{color:var(--muted);font-weight:700}
@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}.company-kpi .company-dot{width:12px;height:12px;border-radius:999px;display:inline-block;margin-right:6px}
.company-kpi .company-meta{display:flex;justify-content:space-between;margin-top:10px;color:var(--muted);font-size:13px;font-weight:800}
.company-kpi .company-progress{height:8px;border-radius:999px;background:#eef2f7;overflow:hidden;margin-top:8px}
.company-kpi .company-progress span{display:block;height:100%;border-radius:999px;width:0%;transition:width .45s ease}
.company-money{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}
.money-box{border:1px solid #edf2f7;background:#f8fafc;border-radius:14px;padding:8px 10px}
.money-label{font-size:11px;color:var(--muted);font-weight:800}
.money-value{font-size:14px;font-weight:900;margin-top:2px}
.vehicle-mini{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.vehicle-mini span{display:inline-flex;align-items:center;gap:4px;padding:5px 8px;border-radius:999px;background:#f8fafc;border:1px solid #edf2f7;font-size:12px;font-weight:900;color:#475467}
.company-kpi[data-company="RVP"]{border-left:5px solid #2563eb}
.company-kpi[data-company="ERGO"]{border-left:5px solid #dc2626}
.company-kpi[data-company="TPB"]{border-left:5px solid #0ea5e9}
.company-kpi[data-company="TOTAL"]{border-left:5px solid #111827}
.company-kpi.active{transform:translateY(-8px) scale(1.025);box-shadow:0 0 0 3px rgba(37,99,235,.12),0 28px 60px rgba(37,99,235,.2);border-color:#bfdbfe}
.company-kpi.dim{opacity:.58}
@media(max-width:980px){.hero,.section-grid,.daily-grid{grid-template-columns:1fr}.kpi-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:560px){.kpi-grid{grid-template-columns:1fr}.filter-group,.date-input,.date-select,.search-input,.btn{width:100%}.amount,.hybrid-total{font-size:38px}.day-head{align-items:flex-start}.day-tags{justify-content:flex-start}}
</style></head>
<body><main class="page">
<section class="hero"><div class="hero-card"><div class="period-pill" id="period">📊 Dashboard ข้อมูลสะสมทั้งหมด</div><h1>Vehicle Cumulative Dashboard</h1><p>Dashboard Only สำหรับข้อมูลสะสมทั้งหมดจากฐานข้อมูล</p><div style="margin-top:18px"><span class="status-pill"><span class="dot"></span><span id="refreshStatus">Auto refresh ทุก 30 วิ</span></span></div></div><div class="total-card"><div class="label">ยอดรวมทั้งหมด</div><div class="amount" id="totalAmount">0</div><table class="summary-table"><tr><th>หมวด</th><th>ยอด</th></tr><tr><td>🚛 🚗 รถยนต์</td><td id="carAmount">0 บาท</td></tr><tr><td>🏍 รถจักรยานยนต์</td><td id="motorAmount">0 บาท</td></tr></table></div></section>
<section class="toolbar"><h2>เลือกช่วงวันที่ Dashboard</h2><div class="filter-group"><input class="date-input" id="startDate" type="date"><input class="date-input" id="endDate" type="date"><button class="btn" id="applyBtn">แสดงช่วงวันที่</button><button class="btn btn2" id="resetBtn">ดูทั้งหมด</button></div></section>
<section class="kpi-grid">
 <div class="kpi company-kpi" data-company="RVP" onmouseenter="highlightCompany('RVP')" onmouseleave="highlightCompany(null)">
   <div class="icon"><span class="company-dot" style="background:#2563eb"></span>RVP</div>
   <div class="value" id="rvpCount">0</div>
   <div class="title">บริษัทกลาง RVP</div>
   <div class="company-money"><div class="money-box"><div class="money-label">ยอดสุทธิ</div><div class="money-value" id="rvpNet">0 บาท</div></div><div class="money-box"><div class="money-label">ยอดเก็บจริง</div><div class="money-value" id="rvpCollected">0 บาท</div></div></div>
   <div class="vehicle-mini"><span id="rvpMotor">🏍 0</span><span id="rvpPickup">🚛 0</span><span id="rvpSedan">🚗 0</span></div>
   <div class="company-meta"><span>Share</span><span id="rvpPercent">0%</span></div>
   <div class="company-progress"><span id="rvpBar" style="background:linear-gradient(90deg,#2563eb,#14b8a6)"></span></div>
 </div>
 <div class="kpi company-kpi" data-company="ERGO" onmouseenter="highlightCompany('ERGO')" onmouseleave="highlightCompany(null)">
   <div class="icon"><span class="company-dot" style="background:#dc2626"></span>ERGO</div>
   <div class="value" id="ergoCount">0</div>
   <div class="title">ERGO</div>
   <div class="company-money"><div class="money-box"><div class="money-label">ยอดสุทธิ</div><div class="money-value" id="ergoNet">0 บาท</div></div><div class="money-box"><div class="money-label">ยอดเก็บจริง</div><div class="money-value" id="ergoCollected">0 บาท</div></div></div>
   <div class="vehicle-mini"><span id="ergoMotor">🏍 0</span><span id="ergoPickup">🚛 0</span><span id="ergoSedan">🚗 0</span></div>
   <div class="company-meta"><span>Share</span><span id="ergoPercent">0%</span></div>
   <div class="company-progress"><span id="ergoBar" style="background:linear-gradient(90deg,#dc2626,#f97316)"></span></div>
 </div>
 <div class="kpi company-kpi" data-company="TPB" onmouseenter="highlightCompany('TPB')" onmouseleave="highlightCompany(null)">
   <div class="icon"><span class="company-dot" style="background:#0ea5e9"></span>TPB</div>
   <div class="value" id="tpbCount">0</div>
   <div class="title">ไทยไพบูลย์ TPB</div>
   <div class="company-money"><div class="money-box"><div class="money-label">ยอดสุทธิ</div><div class="money-value" id="tpbNet">0 บาท</div></div><div class="money-box"><div class="money-label">ยอดเก็บจริง</div><div class="money-value" id="tpbCollected">0 บาท</div></div></div>
   <div class="vehicle-mini"><span id="tpbMotor">🏍 0</span><span id="tpbPickup">🚛 0</span><span id="tpbSedan">🚗 0</span></div>
   <div class="company-meta"><span>Share</span><span id="tpbPercent">0%</span></div>
   <div class="company-progress"><span id="tpbBar" style="background:linear-gradient(90deg,#0ea5e9,#22d3ee)"></span></div>
 </div>
 <div class="kpi company-kpi" data-company="TOTAL" onmouseenter="highlightCompany('TOTAL')" onmouseleave="highlightCompany(null)">
   <div class="icon"><span class="company-dot" style="background:#111827"></span>รวม</div>
   <div class="value" id="companyTotalCount">0</div>
   <div class="title">จำนวนรถรวมทั้งหมด</div>
   <div class="company-money"><div class="money-box"><div class="money-label">ยอดสุทธิ</div><div class="money-value" id="totalNet">0 บาท</div></div><div class="money-box"><div class="money-label">ยอดเก็บจริง</div><div class="money-value" id="totalCollected">0 บาท</div></div></div>
   <div class="vehicle-mini"><span id="totalMotor">🏍 0</span><span id="totalPickup">🚛 0</span><span id="totalSedan">🚗 0</span></div>
   <div class="company-meta"><span>Share</span><span>100%</span></div>
   <div class="company-progress"><span style="width:100%;background:linear-gradient(90deg,#111827,#64748b)"></span></div>
 </div>
</section>
<section class="section-grid"><div class="panel"><h2>จำนวนรถรายวัน แยกตามบริษัท</h2><div class="chart-wrap"><canvas id="dailyChart"></canvas></div></div><div class="hybrid-card"><div class="hybrid-head"><div><h2 style="margin:0">สัดส่วนประเภทรถ</h2></div><div><div class="hybrid-total" id="hybridTotal">0</div><div class="hybrid-label">คันทั้งหมด</div></div></div><div class="breakdown-list" id="breakdownList"></div></div></section>
<section class="toolbar"><h2>รายการแยกรายวัน</h2><div class="filter-group"><input class="search-input" id="searchBox" placeholder="ค้นหาทะเบียน / เลขกรมธรรม์ / บริษัท"><select class="date-select" id="dateFilter"><option value="all">ดูทั้งหมด</option></select><button class="btn" id="showDateBtn">แสดงวันที่เลือก</button><button class="btn btn2" id="showAllBtn">ดูทั้งหมด</button><button class="btn btnToggle active" id="detailModeBtn">📄 Detail</button><button class="btn btnToggle" id="compactModeBtn">⚡ Compact</button><button class="btn btnDark" id="exportPdfBtn">Export PDF</button><button class="btn btnDark" id="exportExcelBtn">Export Excel</button></div></section>
<section class="daily-grid" id="cards"></section><div class="pagination"><button class="btn btn2" id="prevPageBtn">ก่อนหน้า</button><span class="page-info" id="pageInfo">Page 1</span><button class="btn btn2" id="nextPageBtn">ถัดไป</button></div><p class="status-pill" id="status">Loading...</p>
</main>
<script>
let report=null,allDays=[],filteredDays=[],viewDays=[],dailyChart=null;let currentPage=1,pageSize=8,viewMode='detail',activeSelected='all';const box=id=>document.getElementById(id);const money=n=>Math.round(n||0).toLocaleString('th-TH');function destroy(){if(dailyChart)dailyChart.destroy()}function setupRange(){const dates=allDays.map(d=>d.isoDate).filter(Boolean).sort();box('startDate').value=dates[0]||'';box('endDate').value=dates[dates.length-1]||''}function flattenRows(days){const rows=[];days.forEach(day=>day.groups.forEach(g=>g.items.forEach(item=>rows.push({date:day.date,type:g.title,company:g.company||'',item}))));return rows}
function animateNumber(el,target){const end=Number(target)||0;const start=Number((el.textContent||'0').replace(/,/g,''))||0;const duration=420;const t0=performance.now();function tick(now){const p=Math.min(1,(now-t0)/duration);const eased=1-Math.pow(1-p,3);el.textContent=money(start+(end-start)*eased);if(p<1)requestAnimationFrame(tick);else el.textContent=money(end)}requestAnimationFrame(tick)}
function colorWithAlpha(hex,alpha){const map={'#2563eb':'37,99,235','#f97316':'249,115,22','#dc2626':'220,38,38','#16a34a':'22,163,74','#0ea5e9':'14,165,233','#111827':'17,24,39'};return `rgba(${map[hex]||'37,99,235'},${alpha})`}function applyChartHighlight(index){if(!dailyChart)return;const colors=['#2563eb','#f97316','#16a34a'];dailyChart.data.datasets.forEach((ds,di)=>{if(ds.type==='line'){ds.borderColor=index==null?'#111827':colorWithAlpha('#111827',.95);ds.backgroundColor=ds.borderColor;ds.pointBackgroundColor=ds.data.map((_,i)=>index==null||i===index?'#111827':colorWithAlpha('#111827',.18));return}ds.backgroundColor=ds.data.map((_,i)=>index==null||i===index?colors[di]:colorWithAlpha(colors[di],.18))});dailyChart.update('none')}
function getCompanyData(){
 return filteredDays.map(day=>{
   let RVP=0, ERGO=0, TPB=0, UNKNOWN=0;
   (day.groups||[]).forEach(g=>{
     const company=(g.company||'').toLowerCase();
     const count=(g.items&&g.items.length)?g.items.length:(g.count||0);
     if(g.key==='motorcycle'){
       RVP += count;
     }else if(company.includes('ergo')){
       ERGO += count;
     }else if(company.includes('ไทยไพบูลย์') || company.includes('tpb')){
       TPB += count;
     }else{
       UNKNOWN += count;
     }
   });
   return {date:day.date,label:day.date.slice(0,5),RVP,ERGO,TPB,UNKNOWN,total:RVP+ERGO+TPB+UNKNOWN};
 });
}

function getCompanySummary(){
 const companyData=getCompanyData();
 return companyData.reduce((acc,d)=>{acc.RVP+=d.RVP;acc.ERGO+=d.ERGO;acc.TPB+=d.TPB;acc.UNKNOWN+=(d.UNKNOWN||0);acc.total+=d.total;return acc;},{RVP:0,ERGO:0,TPB:0,UNKNOWN:0,total:0});
}
function setCompanyKPI(){
 const cs=report.companySummary||{};
 const get=(k)=>cs[k]||{count:0,net:0,collected:0,vehicles:{motorcycle:0,pickup:0,sedan:0}};
 const R=get('RVP'), E=get('ERGO'), T=get('TPB'), A=get('TOTAL');
 const total=A.count||0;
 const pct=(v)=>total?Math.round((v/total)*100):0;
 const setText=(id,val)=>{if(box(id))box(id).textContent=val};
 const setMoney=(id,val)=>setText(id,money(val||0)+' บาท');
 const setVehicle=(prefix,obj)=>{
   const v=obj.vehicles||{};
   setText(prefix+'Motor','🏍 '+(v.motorcycle||0));
   setText(prefix+'Pickup','🚛 '+(v.pickup||0));
   setText(prefix+'Sedan','🚗 '+(v.sedan||0));
 };
 animateNumber(box('rvpCount'),R.count||0);animateNumber(box('ergoCount'),E.count||0);animateNumber(box('tpbCount'),T.count||0);animateNumber(box('companyTotalCount'),A.count||0);
 setMoney('rvpNet',R.net);setMoney('rvpCollected',R.collected);
 setMoney('ergoNet',E.net);setMoney('ergoCollected',E.collected);
 setMoney('tpbNet',T.net);setMoney('tpbCollected',T.collected);
 setMoney('totalNet',A.net);setMoney('totalCollected',A.collected);
 setVehicle('rvp',R);setVehicle('ergo',E);setVehicle('tpb',T);setVehicle('total',A);
 setText('rvpPercent',pct(R.count||0)+'%');setText('ergoPercent',pct(E.count||0)+'%');setText('tpbPercent',pct(T.count||0)+'%');
 if(box('rvpBar'))box('rvpBar').style.width=pct(R.count||0)+'%';
 if(box('ergoBar'))box('ergoBar').style.width=pct(E.count||0)+'%';
 if(box('tpbBar'))box('tpbBar').style.width=pct(T.count||0)+'%';
}
function colorWithAlpha(hex,alpha){const map={'#2563eb':'37,99,235','#f97316':'249,115,22','#dc2626':'220,38,38','#16a34a':'22,163,74','#0ea5e9':'14,165,233','#111827':'17,24,39','#94a3b8':'148,163,184'};return `rgba(${map[hex]||'37,99,235'},${alpha})`}
function setCompanyCardsState(company){document.querySelectorAll('.company-kpi').forEach(card=>{const c=card.dataset.company;card.classList.toggle('active',!!company&&c===company);card.classList.toggle('dim',!!company&&c!==company&&company!=='TOTAL')})}
function highlightCompany(company){
 setCompanyCardsState(company);
 if(!dailyChart)return;
 const colorMap={RVP:'#2563eb',ERGO:'#dc2626',TPB:'#0ea5e9',UNKNOWN:'#94a3b8'};
 dailyChart.data.datasets.forEach(ds=>{
   const label=ds.label||'';
   if(ds.type==='line'){const active=!company||company==='TOTAL';ds.borderColor=active?'#111827':colorWithAlpha('#111827',.18);ds.backgroundColor=ds.borderColor;ds.pointBackgroundColor=ds.data.map(()=>active?'#111827':colorWithAlpha('#111827',.18));return}
   let key='UNKNOWN';if(label.includes('RVP'))key='RVP';if(label.includes('ERGO'))key='ERGO';if(label.includes('TPB'))key='TPB';
   const active=!company||company==='TOTAL'||company===key;const base=colorMap[key]||'#94a3b8';ds.backgroundColor=ds.data.map(()=>active?base:colorWithAlpha(base,.16));
 });
 dailyChart.update('none');
}
function renderCharts(){
 destroy();
 const companyData=getCompanyData();
 const totalLine=companyData.map(d=>d.total);
 const datasets=[
   {label:'🔵 RVP',data:companyData.map(d=>d.RVP),backgroundColor:'#2563eb',borderRadius:8,stack:'company'},
   {label:'🟠 ERGO',data:companyData.map(d=>d.ERGO),backgroundColor:'#dc2626',borderRadius:8,stack:'company'},
   {label:'🟢 TPB',data:companyData.map(d=>d.TPB),backgroundColor:'#0ea5e9',borderRadius:8,stack:'company'}
 ];
 if(companyData.some(d=>d.UNKNOWN>0)){
   datasets.push({label:'⚪ ไม่ระบุบริษัท',data:companyData.map(d=>d.UNKNOWN),backgroundColor:'#94a3b8',borderRadius:8,stack:'company'});
 }
 datasets.push({type:'line',label:'⚫ รวมทั้งหมด',data:totalLine,borderColor:'#111827',backgroundColor:'#111827',pointBackgroundColor:'#111827',borderWidth:3,pointRadius:4,pointHoverRadius:6,tension:.35,yAxisID:'y'});
 dailyChart=new Chart(box('dailyChart'),{
   type:'bar',
   data:{labels:companyData.map(d=>d.label),datasets},
   options:{
     responsive:true,
     maintainAspectRatio:false,
     interaction:{mode:'index',intersect:false},
     onHover:(event,elements)=>{if(elements&&elements.length){applyChartHighlight(elements[0].index)}else{applyChartHighlight(null)}},
     plugins:{
       legend:{position:'top',labels:{font:{family:'Prompt',weight:'700'},usePointStyle:true,boxWidth:10}},
       tooltip:{
         bodyFont:{family:'Prompt'},
         titleFont:{family:'Prompt',weight:'700'},
         callbacks:{afterBody:(items)=>{if(!items.length)return '';const i=items[0].dataIndex;const d=companyData[i];return ['รวม: '+d.total+' คัน','RVP: '+d.RVP+' คัน','ERGO: '+d.ERGO+' คัน','TPB: '+d.TPB+' คัน'];}}
       }
     },
     scales:{
       x:{stacked:true,grid:{color:'rgba(15,23,42,.06)'},ticks:{font:{family:'Prompt'}}},
       y:{stacked:true,beginAtZero:true,grid:{color:'rgba(15,23,42,.08)'},ticks:{precision:0,font:{family:'Prompt'}}}
     }
   }
 });
 box('dailyChart').addEventListener('mouseleave',()=>applyChartHighlight(null));
}
function renderBreakdown(motor,pickup,sedan,total){box('hybridTotal').textContent=money(total);const rows=[{icon:'🏍',label:'รถจักรยานยนต์',value:motor,cls:''},{icon:'🚛',label:'รถกระบะ',value:pickup,cls:'orange'},{icon:'🚗',label:'รถยนต์เก๋ง',value:sedan,cls:'green'}];box('breakdownList').innerHTML=rows.map(r=>{const pct=total?Math.round((r.value/total)*100):0;return `<div class="breakdown-row"><div class="break-left"><span>${r.icon}</span><span>${r.label}</span></div><div class="break-meta"><span>${money(r.value)}</span><span class="percent">${pct}%</span></div><div class="bar-track"><div class="bar-fill ${r.cls}" style="width:${pct}%"></div></div></div>`}).join('')}
function render(selected='all'){
 const t=report.totals||{};
 const motor=t.motorcycle||0,pickup=t.pickup||0,sedan=t.sedan||0,total=t.all||0;
 box('period').textContent='📊 Dashboard ข้อมูลสะสมทั้งหมด';
 box('totalAmount').textContent=money(report.amounts.total);
 box('carAmount').textContent=money(report.amounts.car)+' บาท';
 box('motorAmount').textContent=money(report.amounts.motorcycle)+' บาท';
 box('dateFilter').innerHTML='<option value="all">ดูทั้งหมด</option>'+filteredDays.map(d=>`<option value="${d.date}">${d.date}</option>`).join('');
 renderCharts();
 setCompanyKPI();
 renderBreakdown(motor,pickup,sedan,total);
 currentPage=1;
 renderCards(selected);
 box('status').textContent=`ข้อมูลสะสมทั้งหมด ${total} คัน • แสดง ${filteredDays.length}/${allDays.length} วัน`;
}
function getCardList(selected='all'){const base=selected==='all'?filteredDays:filteredDays.filter(d=>d.date===selected);const q=box('searchBox').value.trim().toLowerCase();if(!q)return base;return base.map(day=>{const groups=day.groups.map(g=>{const items=g.items.filter(i=>(day.date+' '+g.title+' '+(g.company||'')+' '+i).toLowerCase().includes(q));return {...g,items,count:items.length}}).filter(g=>g.items.length);return {...day,groups,motorcycle:groups.filter(g=>g.key==='motorcycle').reduce((s,g)=>s+g.items.length,0),pickup:groups.filter(g=>g.key==='pickup').reduce((s,g)=>s+g.items.length,0),sedan:groups.filter(g=>g.key==='sedan').reduce((s,g)=>s+g.items.length,0)}}).filter(d=>d.groups.length)}
function getDayMeta(list,day){const totals=list.map(d=>d.motorcycle+d.pickup+d.sedan);const max=Math.max(...totals,0),min=Math.min(...totals,0);const total=day.motorcycle+day.pickup+day.sedan;let tags=[],cls=[];if(total===max&&max>0){tags.push('🔥 Peak');cls.push('peak','high')}else if(total>=max*.75&&max>0){tags.push('เด่น');cls.push('high')}if(total===min&&list.length>1){tags.push('Low');cls.push('low')}return {total,tags,cls:cls.join(' ')}}
function buildDetails(day){return day.groups.map(g=>`<div class="vehicle-group"><div class="vehicle-title">${g.icon} ${g.title} (${g.items.length} คัน)</div>${g.company?`<span class="company">${g.company}</span>`:''}<ul>${g.items.map(i=>`<li>${i}</li>`).join('')}</ul></div>`).join('')}
function toggleDay(btn,index){const card=btn.closest('.day-card');const body=card.querySelector('.day-body');if(card.classList.contains('open')){card.classList.remove('open');return}if(!body.dataset.loaded){const day=viewDays[index];body.innerHTML=buildDetails(day);body.dataset.loaded='1'}card.classList.add('open')}
function renderCards(selected='all'){activeSelected=selected;const list=getCardList(selected);viewDays=list;const totalPages=Math.max(1,Math.ceil(list.length/pageSize));if(currentPage>totalPages)currentPage=totalPages;const start=(currentPage-1)*pageSize;const pageItems=list.slice(start,start+pageSize);box('cards').classList.toggle('compact',viewMode==='compact');box('pageInfo').textContent=`หน้า ${currentPage}/${totalPages} • แสดง ${pageItems.length}/${list.length} วัน`;box('prevPageBtn').disabled=currentPage<=1;box('nextPageBtn').disabled=currentPage>=totalPages;if(!pageItems.length){box('cards').innerHTML='<article class="day-card"><button class="day-head"><span class="day-title">ไม่พบข้อมูล</span></button></article>';return}box('cards').innerHTML=pageItems.map((day,idx)=>{const globalIndex=start+idx;const meta=getDayMeta(list,day);const compact=viewMode==='compact';const open=!compact&&idx<2;const tags=meta.tags.map(t=>`<span class="badge ${t.includes('Peak')?'tag-peak':t.includes('Low')?'tag-low':'tag-high'}">${t}</span>`).join('');const summary=`<div class="quick-summary"><span class="mini-chip">🏍 ${day.motorcycle}</span><span class="mini-chip">🚛 ${day.pickup}</span><span class="mini-chip">🚗 ${day.sedan}</span></div>`;const bodyContent=open?buildDetails(day):'';return `<article class="day-card ${meta.cls} ${compact?'compact-card':''} ${open?'open':''}"><button class="day-head" onclick="toggleDay(this,${globalIndex})"><span class="day-main"><span class="day-title">📊 วันที่ ${day.date}</span>${summary}</span><span class="day-tags">${tags}<span class="badge">รวม ${meta.total} คัน</span><span class="chev">⌄</span></span></button><div class="day-body" data-loaded="${open?'1':''}">${bodyContent}</div></article>`}).join('')}
function exportExcel(){const rows=flattenRows(viewDays.length?viewDays:filteredDays);const summaryRows=[{หมวด:'ยอดเงินรวมทั้งหมด',ยอด:box('totalAmount').textContent,หน่วย:'บาท'},{หมวด:'รถยนต์',ยอด:box('carAmount').textContent.replace(' บาท',''),หน่วย:'บาท'},{หมวด:'รถจักรยานยนต์',ยอด:box('motorAmount').textContent.replace(' บาท',''),หน่วย:'บาท'},{หมวด:'รถจักรยานยนต์',ยอด:box('motorCount').textContent,หน่วย:'คัน'},{หมวด:'รถกระบะ',ยอด:box('pickupCount').textContent,หน่วย:'คัน'},{หมวด:'รถยนต์เก๋ง',ยอด:box('sedanCount').textContent,หน่วย:'คัน'},{หมวด:'จำนวนรถรวมทั้งหมด',ยอด:box('allCount').textContent,หน่วย:'คัน'}];const wsSummary=XLSX.utils.json_to_sheet(summaryRows);const wsDetail=XLSX.utils.json_to_sheet(rows.map(r=>({วันที่:r.date,ประเภทรถ:r.type,บริษัท:r.company,รายการ:r.item})));const wb=XLSX.utils.book_new();XLSX.utils.book_append_sheet(wb,wsSummary,'Summary');XLSX.utils.book_append_sheet(wb,wsDetail,'Detail');XLSX.writeFile(wb,'vehicle-dashboard.xlsx')}
function escapeHtml(text){return String(text||'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'","&#039;")}
function exportPDF(){const rows=flattenRows(viewDays.length?viewDays:filteredDays);const printedAt=new Date().toLocaleString('th-TH');const totalAmount=box('totalAmount').textContent,carAmount=box('carAmount').textContent,motorAmount=box('motorAmount').textContent,motorCount=box('motorCount').textContent,pickupCount=box('pickupCount').textContent,sedanCount=box('sedanCount').textContent;const html=['<!DOCTYPE html>','<html lang="th"><head><meta charset="UTF-8"><title>Vehicle Dashboard PDF</title>','<link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">','<style>@page{size:A4 landscape;margin:12mm}body{font-family:Prompt,Arial,sans-serif;color:#172033}h1{font-size:22px;margin:0 0 6px}.meta{font-size:12px;color:#667085;margin-bottom:14px}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px}.card{border:1px solid #e5e7eb;border-radius:12px;padding:10px;background:#f8fafc}.label{font-size:11px;color:#667085}.value{font-size:19px;font-weight:800;color:#2563eb}.sub{font-size:11px;color:#667085}table{width:100%;border-collapse:collapse;font-size:10px}th{background:#2563eb;color:#fff;text-align:left;padding:7px}td{border-bottom:1px solid #e5e7eb;padding:6px;vertical-align:top}tr:nth-child(even) td{background:#f8fafc}.money-table{margin-bottom:14px}.money-table th{background:#111827}.money-table td{font-size:11px}</style></head><body>','<h1>Vehicle Cumulative Dashboard</h1>','<div class="meta">'+escapeHtml(box('status').textContent)+' • Export: '+escapeHtml(printedAt)+'</div>','<div class="summary">','<div class="card"><div class="label">ยอดเงินรวมทั้งหมด</div><div class="value">'+escapeHtml(totalAmount)+'</div><div class="sub">บาท</div></div>','<div class="card"><div class="label">รถจักรยานยนต์</div><div class="value">'+escapeHtml(motorCount)+'</div><div class="sub">คัน</div></div>','<div class="card"><div class="label">รถกระบะ</div><div class="value">'+escapeHtml(pickupCount)+'</div><div class="sub">คัน</div></div>','<div class="card"><div class="label">รถยนต์เก๋ง</div><div class="value">'+escapeHtml(sedanCount)+'</div><div class="sub">คัน</div></div>','</div>','<table class="money-table"><thead><tr><th>หมวดยอดเงิน</th><th>ยอด</th></tr></thead><tbody>','<tr><td>รถยนต์</td><td>'+escapeHtml(carAmount)+'</td></tr>','<tr><td>รถจักรยานยนต์</td><td>'+escapeHtml(motorAmount)+'</td></tr>','<tr><td>รวมทั้งหมด</td><td>'+escapeHtml(totalAmount)+' บาท</td></tr>','</tbody></table>','<table><thead><tr><th>วันที่</th><th>ประเภทรถ</th><th>บริษัท</th><th>รายการ</th></tr></thead><tbody>',rows.map(r=>'<tr><td>'+escapeHtml(r.date)+'</td><td>'+escapeHtml(r.type)+'</td><td>'+escapeHtml(r.company)+'</td><td>'+escapeHtml(r.item)+'</td></tr>').join(''),'</tbody></table></body></html>'].join('');const win=window.open('', '_blank');if(!win){alert('Browser บล็อก popup กรุณาอนุญาต popup แล้วลอง Export PDF อีกครั้ง');return}win.document.open();win.document.write(html);win.document.close();win.focus();setTimeout(()=>win.print(),700)}
async function load(){box('refreshStatus').textContent='กำลังโหลดข้อมูล...';const params=new URLSearchParams();const s=box('startDate').value,e=box('endDate').value,q=box('searchBox').value.trim();if(s)params.set('start',s);if(e)params.set('end',e);if(q)params.set('q',q);const query=params.toString();const url='/api/dashboard'+(query?('?'+query+'&ts='+Date.now()):('?ts='+Date.now()));const res=await fetch(url).catch(()=>null);if(!res||!res.ok){box('status').textContent='ยังไม่มีข้อมูล';box('refreshStatus').textContent='ยังไม่มีข้อมูล';return}report=await res.json();allDays=report.dailyData;filteredDays=[...allDays];if(!s&&!e)setupRange();render(activeSelected);box('refreshStatus').textContent='ข้อมูลล่าสุดแล้ว • '+new Date().toLocaleTimeString('th-TH')}
box('applyBtn').onclick=()=>load();box('resetBtn').onclick=()=>{box('startDate').value='';box('endDate').value='';box('searchBox').value='';activeSelected='all';load()};box('showDateBtn').onclick=()=>{currentPage=1;renderCards(box('dateFilter').value)};box('showAllBtn').onclick=()=>{box('dateFilter').value='all';currentPage=1;renderCards('all')};box('dateFilter').onchange=()=>{currentPage=1;renderCards(box('dateFilter').value)};box('searchBox').oninput=()=>{currentPage=1;clearTimeout(window.searchTimer);window.searchTimer=setTimeout(()=>load(),450)};box('prevPageBtn').onclick=()=>{if(currentPage>1){currentPage--;renderCards(box('dateFilter').value)}};box('nextPageBtn').onclick=()=>{currentPage++;renderCards(box('dateFilter').value)};box('detailModeBtn').onclick=()=>{viewMode='detail';box('detailModeBtn').classList.add('active');box('compactModeBtn').classList.remove('active');renderCards(box('dateFilter').value)};box('compactModeBtn').onclick=()=>{viewMode='compact';box('compactModeBtn').classList.add('active');box('detailModeBtn').classList.remove('active');renderCards(box('dateFilter').value)};box('exportExcelBtn').onclick=exportExcel;box('exportPdfBtn').onclick=exportPDF;load();setInterval(()=>load(),30000);
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
async def api_import(
    token: str = Form(...),
    raw_text: str = Form(""),
    file: UploadFile | None = File(default=None),
) -> JSONResponse:
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Admin token ไม่ถูกต้อง")

    if file and file.filename:
        filename = file.filename.lower()
        content = await file.read()
        if filename.endswith((".xlsx", ".xls")):
            result = save_excel_import_replace_all(content)
            return JSONResponse({"ok": True, **result})
        if filename.endswith(".txt"):
            text = content.decode("utf-8-sig", errors="ignore").strip()
            if not text:
                raise HTTPException(status_code=400, detail="ไฟล์ Text ไม่มีข้อมูล")
            result = save_import_replace_all(text)
            return JSONResponse({"ok": True, **result})

    text = raw_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="ไม่พบข้อมูลรายงาน กรุณาวาง Text หรือเลือกไฟล์ Excel")
    result = save_import_replace_all(text)
    return JSONResponse({"ok": True, **result})


@app.get("/api/dashboard")
def api_dashboard(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> JSONResponse:
    cache_key = make_cache_key(start, end, q)
    cached = get_cached_dashboard(cache_key)
    if cached is not None:
        cached_copy = dict(cached)
        cached_copy["cache"] = {"hit": True, "ttl": CACHE_TTL_SECONDS}
        return JSONResponse(cached_copy)
    data = get_dashboard_data(start=start, end=end, q=q)
    data["cache"] = {"hit": False, "ttl": CACHE_TTL_SECONDS}
    set_cached_dashboard(cache_key, data)
    return JSONResponse(data)



@app.get("/api/health")
def api_health() -> JSONResponse:
    store, _ = read_github_store()
    return JSONResponse({
        "ok": True,
        "storage": "github_json",
        "github_repo": GITHUB_REPO,
        "github_file": GITHUB_FILE,
        "github_branch": GITHUB_BRANCH,
        "daily_records": len(store.get("daily_records", [])),
        "weekly_summaries": len(store.get("weekly_summaries", [])),
        "updated_at": store.get("updated_at"),
        "companyAmounts": money_totals.get("company", {}),
        "importType": store.get("import_type", ""),
        "companySummary": build_company_summary(filtered_rows),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "cache_key": DASHBOARD_CACHE.get("key"),
    })


@app.post("/api/cache/clear")
def api_cache_clear(token: str = Form(...)) -> JSONResponse:
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Admin token ไม่ถูกต้อง")
    clear_dashboard_cache()
    return JSONResponse({"ok": True, "message": "cache cleared"})


@app.get("/api/github/test")
def api_github_test() -> JSONResponse:
    store, sha = read_github_store()
    return JSONResponse({
        "ok": True,
        "repo": GITHUB_REPO,
        "file": GITHUB_FILE,
        "branch": GITHUB_BRANCH,
        "sha_exists": bool(sha),
        "daily_records": len(store.get("daily_records", [])),
        "weekly_summaries": len(store.get("weekly_summaries", [])),
    })


@app.get("/api/report/latest")
def api_latest_report() -> JSONResponse:
    return api_dashboard()
