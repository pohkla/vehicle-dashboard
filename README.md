# Vehicle Dashboard v6.5 Excel Money Import Status

พร้อม Deploy

## แก้ไขในเวอร์ชันนี้

1. แก้ Excel Import ให้จับหัวคอลัมน์ยอดเงินได้แข็งขึ้น
   - ยอดสุทธิ / สุทธิ / Net
   - ยอดเก็บจริง / ยอดเก็บ / เก็บจริง / Collected
   - normalize กรณีหัวคอลัมน์มีช่องว่าง/บรรทัดใหม่/อักขระไทยผิด

2. Company KPI Grid แสดง
   - จำนวนรถ
   - ยอดสุทธิ
   - ยอดเก็บจริง
   - จำนวนรถแยกชนิด 🏍 🚛 🚗

3. เพิ่มสถานะหลัง Upload / Import
   - ประเภท Import
   - จำนวนวันที่
   - จำนวน record ที่บันทึก
   - สรุป RVP / ERGO / TPB / รวม
   - รายงานว่าแต่ละ Sheet ถูก import หรือ skipped

4. ยังรองรับ
   - Import Excel
   - Import Text เดิม
   - GitHub JSON DB
   - Replace All mode

## Deploy
อัปโหลดไฟล์ทั้งหมดใน ZIP นี้ไปแทนของเดิมใน repo `vehicle-dashboard`
แล้วกด Manual Deploy บน Render
