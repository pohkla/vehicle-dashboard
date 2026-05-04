# Vehicle Dashboard v6.9 - Production Excel Import Flow Fix

## Fixed
- Added explicit endpoints:
  - `POST /api/import/excel`
  - `POST /api/import/text`
- Excel import is blocked from the legacy `/api/import` endpoint to prevent fallback into Text logic.
- Excel records are saved with:
  - `import_type = "excel"`
  - `net_amount`
  - `collected_amount`
- Added Excel validation for required headers:
  - วันที่
  - ประเภทรถ
  - บริษัท
  - รหัส / เลขกรมธรรม์ / รายการ
  - ยอดสุทธิ
  - ยอดเก็บจริง
- Added production debug data:
  - parsed row count
  - detected headers
  - sheet stats
  - first parsed row
  - GitHub write and verify status
- Added GitHub read-back verification after write.
- Fixed `/api/health` undefined variable bug.

## Debug endpoints
- `/api/debug/company-summary`
- `/api/debug/import-flow`
- `/api/github/test`
- `/api/health`

## Deploy
Use the existing Render service and redeploy this package. Required env vars:
- `ADMIN_TOKEN`
- `GITHUB_TOKEN`
- `GITHUB_REPO`
- `GITHUB_FILE`
- `GITHUB_BRANCH`
