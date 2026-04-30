# Vehicle Weekly Dashboard v2

อัปเกรดตามคำขอ:
- Card รายวันแบบ Collapse/Expand
- Pagination เพื่อรองรับข้อมูลเยอะ
- Export PDF
- Export Excel
- Auto Refresh ทุก 30 วินาที
- UI Premium Polish
- Search รายการรถ / บริษัท / กรมธรรม์

## Run Local

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

## URLs

```text
/admin
/dashboard
```

## Render

ใช้ไฟล์ `render.yaml` ได้เลย แล้วตั้งค่า:

```text
ADMIN_TOKEN=รหัสลับของคุณ
```
