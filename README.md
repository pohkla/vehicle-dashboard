# Vehicle Weekly Dashboard v3 Production

Production Data Model:
- `reports` เก็บ raw text ที่นำเข้า
- `daily_records` เก็บข้อมูลรายคัน
- Deduplicate ด้วย `date + vehicle_type + company + item`
- Dashboard query จาก daily_records โดยตรง
- รองรับข้อมูลสะสมหลายสัปดาห์/หลายเดือน/หลายปี

## Features
- Append import
- Deduplication
- Cross-week date filtering
- Search server-side
- Collapse/Expand cards
- Pagination
- Export PDF
- Export Excel
- Auto Refresh 30s

## Run Local

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

## URLs

```text
/admin
/dashboard
/api/dashboard
```

## Deploy Render

ตั้ง Environment Variable:

```text
ADMIN_TOKEN=your-secret-token
```
