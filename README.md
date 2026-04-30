# Vehicle Dashboard v3.1 Cumulative

แก้ตามคำขอ:
1. Backend:
   - ไม่ใช้ period/yod รวมจาก raw text ล่าสุด
   - คำนวณจำนวนรถจาก daily_records ด้วย SQL SUM/COUNT จาก DB
   - คำนวณยอดเงินสะสมจาก reports ทั้งหมด
2. Frontend:
   - เอาข้อความรายสัปดาห์ออก
   - แสดงเป็น Dashboard ข้อมูลสะสมทั้งหมด

## Run

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

## URL

- `/admin`
- `/dashboard`

## Deploy Render

ตั้งค่า:

```text
ADMIN_TOKEN=your-secret
```
