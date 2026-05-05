# Vehicle Dashboard v6.3 Excel Import + No Admin Token

## สิ่งที่อัปเดตจาก v6.2
- เพิ่ม Import Excel ผ่าน `POST /api/import/excel`
- แยก Import Text ผ่าน `POST /api/import/text`
- Legacy `POST /api/import` ยังรองรับ Text เดิมเพื่อไม่ให้ flow เก่าพัง
- หน้า `/admin` ไม่ต้องกรอก Admin Token แล้ว
- เพิ่มข้อความ Version บนหน้า Admin และ Dashboard
- Excel parser ตรวจ header หลัก: วันที่, ประเภทรถ, บริษัท, รหัส, ยอดสุทธิ, ยอดเก็บจริง
- บันทึก `net_amount`, `collected_amount`, `import_type = excel`, `source_sheet`, `source_row` ลง `data.json`
- หลังเขียน GitHub จะ read-back verify ว่าข้อมูลถูกเขียนจริง

## ENV บน Render
```env
GITHUB_TOKEN=xxxxx
GITHUB_REPO=pohkla/vehicle-dashboard-data
GITHUB_FILE=data.json
GITHUB_BRANCH=main
CACHE_TTL_SECONDS=20
```

## Endpoints
- `/admin` หน้า Import
- `/dashboard` หน้า Dashboard
- `POST /api/import/excel` Import Excel
- `POST /api/import/text` Import Text
- `GET /api/health` ตรวจสถานะระบบ
- `GET /api/debug/raw-store` ดูข้อมูล sample จาก GitHub JSON

## Deploy
อัปโหลดไฟล์ชุดนี้ขึ้น GitHub repo ของ Web App แล้วให้ Render redeploy จาก branch ที่ใช้งาน
