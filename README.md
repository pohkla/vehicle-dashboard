# Vehicle Dashboard v5 Hybrid SQLite Cache

Hybrid Mode: SQLite + Persistent Disk + Cache + Performance PRAGMA

## เพิ่มอะไรบ้าง
- SQLite path ผ่าน `SQLITE_DB_PATH`
- ใช้ `/var/data/vehicle_dashboard.db` สำหรับ Render Persistent Disk
- WAL mode เพื่อ performance ดีขึ้น
- Dashboard API cache TTL 20 วินาที
- Import แล้ว clear cache อัตโนมัติ
- `/api/health` สำหรับเช็ค DB path และจำนวน records
- `/api/cache/clear` สำหรับ clear cache เอง

## สำคัญ
ถ้าใช้ Render แล้วต้องการให้ข้อมูลไม่หาย ต้องใช้ Persistent Disk หรือแผนที่รองรับ Disk

## Local Run
```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

## URLs
- `/admin`
- `/dashboard`
- `/api/health`

## Environment Variables
```text
ADMIN_TOKEN=your-secret-token
DATA_DIR=/var/data
SQLITE_DB_PATH=/var/data/vehicle_dashboard.db
CACHE_TTL_SECONDS=20
```
