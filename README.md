# Vehicle Dashboard v6 GitHub JSON DB

ใช้ GitHub `data.json` เป็นฐานข้อมูลแทน SQLite เพื่อให้ข้อมูลไม่หายบน Render Free

## ENV บน Render

```text
ADMIN_TOKEN=รหัสหน้า admin
GITHUB_TOKEN=token ใหม่จาก GitHub
GITHUB_REPO=pohkla/vehicle-dashboard-data
GITHUB_FILE=data.json
GITHUB_BRANCH=main
CACHE_TTL_SECONDS=20
```

## data.json เริ่มต้น

```json
{
  "version": 1,
  "updated_at": null,
  "daily_records": [],
  "weekly_summaries": []
}
```

## Test

```text
/api/github/test
/api/health
```
