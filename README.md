# Vehicle Dashboard v4.5 Smart Cards

อัปเกรดส่วนรายการแยกรายวันตามคำขอ:

1. Compact Mode
   - เพิ่มปุ่ม Detail / Compact
   - Compact แสดงการ์ดแบบสั้น อ่านเร็ว

2. Highlight สีตามจำนวน
   - Peak Day มีแถบสีและ tag
   - วันที่สูงเด่นมี highlight
   - วันที่ต่ำมี Low tag / opacity ลดลง

3. Quick Summary ใน Card
   - แสดง 🏍 🚛 🚗 ในหัวการ์ดทันที
   - ไม่ต้องเปิดก็เห็นจำนวนแต่ละประเภท

4. Animation
   - Card hover lift/scale
   - Smooth expand/collapse ด้วย max-height
   - Chevron rotate
   - item hover slide

5. Lazy Render
   - Detail ของวันจะยังไม่ render จนกว่าจะกดเปิด card
   - การ์ด 2 ใบแรกใน Detail Mode เปิดอัตโนมัติและ render ไว้
   - Compact Mode ไม่ render detail เพื่อลดโหลด

ยังคงไว้:
- Replace All import mode
- Export PDF/Excel พร้อม Summary
- Stacked Bar + Trend Line
- Hybrid Breakdown Card
