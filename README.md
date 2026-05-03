# Vehicle Dashboard v6.3 Excel Import + Company Money

พร้อม Deploy

## เพิ่มใหม่
1. Import Excel (.xlsx/.xls)
   - ยัง Import Text เดิมได้เหมือนเดิม
   - ถ้าเลือกไฟล์ Excel ระบบจะอ่านไฟล์ Excel ก่อน
   - ถ้าเลือกไฟล์ .txt ระบบจะอ่าน Text
   - ถ้าไม่เลือกไฟล์ ระบบจะใช้ข้อความใน textarea

2. Excel Parser
   - ข้ามชีตที่ไม่มี header ถูกต้องอัตโนมัติ เช่น ชีต Dropdown
   - ตรวจ header ก่อนใช้งาน
   - รองรับ merge cell โดย fill down วันที่ / ประเภทรถ / บริษัท
   - รวมข้อมูลทุกชีตที่เป็น data sheet
   - รองรับ columns: วันที่, ประเภทรถ, บริษัท, รหัส, ยอดสุทธิ, ยอดเก็บจริง

3. Company KPI + Money
   - RVP = รถจักรยานยนต์
   - ERGO = รถกระบะ + รถเก๋ง ของ ERGO
   - TPB = รถกระบะ + รถเก๋ง ของไทยไพบูลย์ TPB
   - รวมยอดเงินต่อบริษัทจากยอดเก็บจริง

4. Storage
   - ใช้ GitHub JSON DB เหมือนเดิม
   - Replace All ทุกครั้งที่ Import

## ENV บน Render
```text
ADMIN_TOKEN=...
GITHUB_TOKEN=...
GITHUB_REPO=pohkla/vehicle-dashboard-data
GITHUB_FILE=data.json
GITHUB_BRANCH=main
CACHE_TTL_SECONDS=20
```

## Deploy
อัปโหลดไฟล์ทั้งหมดใน ZIP นี้ไปแทนของเดิมใน repo `vehicle-dashboard`
แล้วกด Manual Deploy บน Render
