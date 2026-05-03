# Vehicle Dashboard System - Company KPI Grid Ready

## สิ่งที่แก้แล้ว
- Company KPI Grid แสดง RVP / ERGO / TPB / รวม เสมอ แม้ไม่มีข้อมูล
- แสดงจำนวนรถทั้งหมด, ยอดสุทธิรวม, ยอดเก็บจริงรวม, Share %
- แสดงจำนวนรถแยกตามประเภทรถภายในแต่ละบริษัท
- Backend aggregate แบบ cumulative จากข้อมูลทั้งหมด
- รองรับ Excel หลาย Sheet, merge cell ด้วย forward fill, และ Text legacy
- แก้ปัญหา Render `Directory 'static' does not exist` โดยใช้ path แบบ absolute และแนบโฟลเดอร์ static ในโปรเจกต์

## Deploy Render
1. แตก zip แล้ว push ขึ้น GitHub
2. Render > New > Web Service > เลือก repo
3. ใช้ค่าใน `render.yaml` หรือกำหนดเอง:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. Environment variables สำหรับ GitHub JSON DB ถ้าต้องการ:
   - `GITHUB_TOKEN` = token ที่มีสิทธิ์ write contents
   - `GITHUB_REPO` = owner/repo
   - `GITHUB_BRANCH` = main
   - `GITHUB_FILE_PATH` = vehicle_data.json

## API
- `GET /api/summary`
- `GET /api/data`
- `POST /api/import/preview`
- `POST /api/import/save`
- `DELETE /api/data`

## Excel Headers ที่ต้องมี
- วันที่
- ประเภทรถ
- บริษัท
- ยอดเก็บจริง

แนะนำให้มีเพิ่ม:
- ยอดสุทธิ
- รหัส หรือ ทะเบียน
