# Vehicle Dashboard v3.3 Replace All

เวอร์ชันนี้เปลี่ยน logic ตาม workflow ล่าสุด:

## Import Mode: Replace All

ทุกครั้งที่กด Import:
1. อ่านข้อมูลจากไฟล์/ข้อความใหม่
2. ล้างข้อมูลเดิมทั้งหมดใน `daily_records`
3. ล้างยอดสรุปเดิมทั้งหมดใน `weekly_summaries`
4. บันทึกเฉพาะข้อมูลชุดล่าสุดเข้าไปใหม่

ผลลัพธ์:
- Dashboard จะตรงกับไฟล์ล่าสุด 100%
- อัปโหลดข้อมูลชุดเดิมซ้ำ ไม่บวกเพิ่ม
- อัปโหลดสัปดาห์ใหม่ จะไม่เอาข้อมูลเก่ามารวมผิด
- เหมาะกับกรณีที่ไฟล์ล่าสุดคือ Source of Truth

## Run

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

## URLs

- `/admin`
- `/dashboard`

## Render

ตั้งค่า Environment Variable:

```text
ADMIN_TOKEN=your-secret
```
