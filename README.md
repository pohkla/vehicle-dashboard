# Vehicle Dashboard System

FastAPI + Static Dashboard พร้อม Company KPI Grid แบบ cumulative

## Features
- Company Cards: RVP, ERGO, TPB, รวม
- แสดงจำนวนรถ, ยอดสุทธิรวม, ยอดเก็บจริงรวม, ชนิดรถ, Share %
- Excel Preview + Validation header
- Text legacy import
- Save แบบ Replace All ไปที่ GitHub JSON หรือ local `data.json`

## Deploy on Render
1. Push โฟลเดอร์นี้ขึ้น GitHub
2. Render > New > Blueprint หรือ Web Service
3. ตั้ง Environment Variables:
   - `GITHUB_REPO=owner/repo`
   - `GITHUB_TOKEN=github_pat_...` ต้องมีสิทธิ์ Contents Read/Write
   - `GITHUB_BRANCH=main`
   - `GITHUB_DB_PATH=data/vehicle-dashboard.json`
4. Deploy

## Local Run
```bash
pip install -r requirements.txt
uvicorn app:app --reload
```
เปิด `http://127.0.0.1:8000`
