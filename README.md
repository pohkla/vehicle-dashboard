# Vehicle Dashboard v6.4 Company Finance Grid

พร้อม Deploy

## แก้ตาม Requirement ล่าสุด

1. Company KPI Grid แสดงข้อมูลครบทุกบริษัท
   - RVP
   - ERGO
   - TPB
   - รวมทั้งหมด

2. แต่ละบริษัทแสดง
   - จำนวนรถทั้งหมด
   - ยอดสุทธิ
   - ยอดเก็บจริง
   - จำนวนรถแยกตามชนิด: มอเตอร์ไซต์ / กระบะ / เก๋ง
   - Share %

3. สีบริษัท
   - RVP = น้ำเงิน
   - ERGO = แดง
   - TPB = ฟ้า
   - รวม = ดำ/เทาเข้ม

4. รองรับ Excel Import และ Text Import เดิม
   - Excel ใช้ยอดสุทธิและยอดเก็บจริงต่อรายการ
   - Text เดิมยังใช้ได้ แต่ถ้า Text ไม่มียอดต่อบริษัท จะคำนวณเงินต่อบริษัทได้เท่าที่ข้อมูลมี

## Deploy
อัปโหลดไฟล์ทั้งหมดใน ZIP นี้ไปแทนของเดิมใน repo `vehicle-dashboard`
แล้วกด Manual Deploy บน Render
