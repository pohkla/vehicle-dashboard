# Vehicle Dashboard v3.2 Replace Dates

แก้ logic ตามคำขอ:
- เวลานำเข้าข้อมูลใหม่ ระบบจะดูวันที่ที่อยู่ในไฟล์
- ลบข้อมูลเดิมของวันนั้นออกจาก `daily_records`
- ใส่ข้อมูลใหม่เข้าไปแทน
- ไม่บวกซ้ำเมื่ออัปโหลดข้อมูลวันเดิม
- Weekly summary ใช้ `weekly_summaries` และ replace ตาม period เดิม

## Run

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

## URL

- `/admin`
- `/dashboard`

## Deploy Render

ตั้ง Environment Variable:

```text
ADMIN_TOKEN=your-secret
```
