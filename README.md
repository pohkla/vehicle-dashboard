# Vehicle Dashboard v6.1 Company Chart

เวอร์ชันพร้อม Deploy

## เปลี่ยนในเวอร์ชันนี้

- ใช้ Storage แบบ GitHub JSON DB เหมือนเดิม
- ปรับเฉพาะกราฟฝั่งซ้ายเป็น Stacked Bar แยกตามบริษัท:
  - RVP = รถจักรยานยนต์
  - ERGO = รถกระบะ + รถยนต์เก๋ง ที่อยู่บริษัท ERGO
  - TPB = รถกระบะ + รถยนต์เก๋ง ที่อยู่บริษัท ไทยไพบูลย์ / TPB
  - เส้นสีดำ = รวมทั้งหมดต่อวัน
- Hybrid Card ฝั่งขวาคงเดิม
- Export PDF / Excel คงเดิม
- Admin import เป็น Replace All ลง GitHub data.json

## ENV บน Render

```text
ADMIN_TOKEN=รหัสสำหรับหน้า admin
GITHUB_TOKEN=token ใหม่จาก GitHub
GITHUB_REPO=pohkla/vehicle-dashboard-data
GITHUB_FILE=data.json
GITHUB_BRANCH=main
CACHE_TTL_SECONDS=20
```

## Test

```text
/api/github/test
/api/health
```
