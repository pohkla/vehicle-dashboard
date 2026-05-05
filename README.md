# Vehicle Dashboard v6.9.1 Excel Import Production Fix

พร้อม Deploy ต่อจาก `vehicle-dashboard-v6-4-company-finance-grid-ready-deploy.zip`

## สิ่งที่เพิ่ม/แก้

1. แยก endpoint ชัดเจน
   - `POST /api/import/excel` สำหรับ Excel เท่านั้น
   - `POST /api/import/text` สำหรับ Text เท่านั้น
   - `POST /api/import` ยังเก็บไว้แบบ legacy แต่กัน Excel ไม่ให้หลุดเข้า Text logic

2. Excel Import รองรับไฟล์รูปแบบตารางตามตัวอย่าง
   - วันที่
   - ประเภทรถ
   - บริษัท
   - รหัส
   - ยอดสุทธิ
   - ยอดเก็บจริง

3. Fix bug สำคัญของ Excel
   - หากในไฟล์มีตารางสรุปด้านขวาที่ใช้ header ซ้ำ เช่น `ยอดสุทธิ` / `ยอดเก็บจริง` ระบบจะใช้ column ซ้ายสุดของตารางหลักเท่านั้น
   - แปลงปี พ.ศ. เป็น ค.ศ. สำหรับ `iso_date`
   - บันทึก `net_amount` และ `collected_amount` ลง `data.json` จริง
   - บังคับ `import_type = excel`

4. เพิ่ม Debug / Verify
   - Log header ที่เจอใน Excel
   - Log จำนวน rows ที่ parse ได้ต่อ sheet
   - Log ก่อนเขียน GitHub และหลังอ่านกลับ
   - Verify หลังเขียน GitHub ว่าจำนวน records ตรง และมี field เงินครบ

5. เพิ่มข้อความ Version บนหน้า Admin และ Dashboard
   - `v6.9.1 Excel Import Production Fix`

## Debug Endpoints

- `/api/debug/import-flow`
- `/api/debug/company-summary`
- `/api/debug/raw-store`
- `/api/health`

## Deploy

อัปโหลดไฟล์ทั้งหมดใน ZIP นี้ไปแทนของเดิมใน repo `vehicle-dashboard` แล้วกด Manual Deploy บน Render

## ENV ที่ต้องมีบน Render

```env
ADMIN_TOKEN=your-admin-token
GITHUB_TOKEN=your-github-token
GITHUB_REPO=owner/repo
GITHUB_FILE=data.json
GITHUB_BRANCH=main
CACHE_TTL_SECONDS=20
```
