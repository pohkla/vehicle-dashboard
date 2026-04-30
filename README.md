# Vehicle Dashboard v4 Chart UI

อัปเกรดจาก v3.3:
1. กราฟซ้าย: Stacked Bar + Trend Line รวมทั้งหมด
2. กราฟขวา: เปลี่ยน Donut เป็น Hybrid Breakdown Card
3. UI Premium:
   - Gradient background
   - Glow shadow
   - Hover effects
   - Focus state
   - Better visual hierarchy

## Import Logic
ยังคงใช้ Replace All:
- Import ใหม่จะล้างข้อมูลเก่าทั้งหมด
- Dashboard เท่ากับข้อมูลชุดล่าสุด

## Run

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

## URL
- `/admin`
- `/dashboard`
