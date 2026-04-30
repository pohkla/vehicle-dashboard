# Vehicle Dashboard v4.3 Sparkline Hover Animation

เพิ่มตามคำขอ:
1. Sparkline ใน KPI ทุกใบ
2. Hover Highlight บนกราฟหลัก
   - Hover วันเดียวแล้ววันอื่น dim ลง
   - Tooltip แสดงยอดรวมของวันนั้น
3. Animation / Micro Interaction
   - KPI count animation
   - KPI hover glow
   - Card hover lift + scale
   - Expand animation
   - List item hover

ยังคงใช้:
- Replace All import mode
- Stable PDF Export ผ่าน Browser Print
- Export Excel
- Auto refresh 30 วินาที

## Run

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

## URLs
- `/admin`
- `/dashboard`
