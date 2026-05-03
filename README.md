# Vehicle Dashboard v6.6 Company Money Status Fix

พร้อม Deploy

## แก้ไข
1. แก้ยอดเงินใน Company Grid ไม่ขึ้น
   - คำนวณยอดสุทธิ / ยอดเก็บจริงจาก daily_records โดยตรง
   - รองรับ key ทั้ง `net_amount` / `netAmount`
   - รองรับ key ทั้ง `collected_amount` / `collectedAmount`

2. หลัง Upload มีสรุปผลนำเข้าชัดเจนขึ้น
   - สรุป RVP / ERGO / TPB / รวม
   - แสดงจำนวนรถ
   - แสดงยอดสุทธิ
   - แสดงยอดเก็บจริง
   - แสดงจำนวนรถแยกชนิด

3. เพิ่ม debug endpoint
   - `/api/debug/company-summary`
   - ใช้ตรวจว่าข้อมูลใน GitHub JSON มียอดเงินหรือไม่

## หลัง Deploy ให้ทดสอบ
1. Upload Excel ใหม่ที่ `/admin`
2. ดู status ใต้ปุ่ม upload
3. เปิด `/api/debug/company-summary`
4. เปิด `/dashboard`
