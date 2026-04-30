# Vehicle Dashboard v4.2 Stable PDF Export

เวอร์ชันนี้แก้ปัญหา JavaScript หลุดไปแสดงบนหน้า Dashboard ตอนกด Export PDF

## สิ่งที่แก้
- Export PDF ไม่ใช้ jsPDF
- ไม่ฝัง `<script>` ไว้ใน HTML template string อีกต่อไป
- เปิดหน้าต่างใหม่แล้วสั่ง `window.print()` จากหน้าหลักแทน
- รองรับภาษาไทยผ่าน Browser Print / Save as PDF
- ลดความเสี่ยง HTML/JS string แตก

## วิธีใช้งาน
1. Deploy ไฟล์ชุดนี้แทนของเดิม
2. เปิด `/dashboard`
3. กด `Export PDF`
4. เลือก `Save as PDF`

## URLs
- `/admin`
- `/dashboard`
