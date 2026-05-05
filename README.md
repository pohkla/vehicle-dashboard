# Vehicle Dashboard v6.4 Excel Import Stable Restore

Base: v6.2 company KPI hover.

Changes:
- Keep original GitHub JSON read/write layer from v6.2.
- Add `/api/import/excel` for Excel `.xlsx/.xls` upload.
- Add `/api/import/text` and keep legacy `/api/import` for text import.
- Remove Admin Token input from `/admin` import UI.
- Show system version on `/admin` and `/dashboard` title.
- Excel parser requires headers: วันที่, ประเภทรถ, บริษัท, รหัส, ยอดสุทธิ, ยอดเก็บจริง.
- Excel records include `net_amount`, `collected_amount`, and `import_type: excel`.

Deploy on Render with existing ENV:
- GITHUB_TOKEN
- GITHUB_REPO
- GITHUB_FILE
- GITHUB_BRANCH
