# Vehicle Weekly Dashboard

ระบบ Dashboard รายสัปดาห์แบบ Production Deploy

## URL

- `/admin` สำหรับวางข้อมูลหรืออัปโหลดข้อมูล
- `/dashboard` สำหรับแชร์ให้คนอื่นดู Dashboard Only
- `/api/report/latest` API ข้อมูลล่าสุด

## Local Run

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

เปิด:

```text
http://127.0.0.1:8000/admin
http://127.0.0.1:8000/dashboard
```

## Render Deploy

1. สร้าง GitHub Repository
2. อัปโหลดไฟล์ทั้งหมด
3. สร้าง Web Service บน Render
4. ตั้ง Environment Variable:

```text
ADMIN_TOKEN=รหัสลับของคุณ
```

5. แชร์ Dashboard:

```text
https://your-app.onrender.com/dashboard
```

หมายเหตุ: Render Free ไม่มี persistent disk ตามค่าเริ่มต้น ข้อมูล SQLite อาจหายเมื่อ redeploy/restart ถ้าใช้งานจริงระยะยาวแนะนำ PostgreSQL หรือ Persistent Disk
