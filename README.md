# Vehicle Dashboard v14.13.1 Expense Render Hotfix

## v14.13.1 Expense Render Hotfix
- เพิ่มการดึง “ยอดค่าใช้จ่าย” จาก Excel
- รองรับค่าใช้จ่ายแบบสรุปท้ายชีต เช่น รถมอเตอร์ไซต์ / รถยนต์
- Dashboard แสดง ค่าใช้จ่ายรวม และ คงเหลือสุทธิ = ยอดเก็บจริง - ค่าใช้จ่าย
- API /api/dashboard คืนค่า amounts.expense และ amounts.profit

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


## v14.13.1 Expense Render Hotfix
- Dashboard version credit, app health version, and admin version are aligned to v14.12.
- Mobile/tablet responsive overrides included for real device layout.

## v14.10 Datepicker Dark Mode Fix
- Fixed Flatpickr calendar contrast in Dark Mode.
- Improved selected/range/day/month/year readability.
