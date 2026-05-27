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


## v14.10 Datepicker Dark Mode Fix
- Fixed Flatpickr calendar contrast in Dark Mode.
- Improved selected/range/day/month/year readability.


## v14.17 Dashboard UI Balance Fix
- อัปเกรด UI/UX หน้า `/dashboard`, `/admin`, `/executive` ให้เป็น Modern AI Product style ตามแนว blocks.so/ai
- ปรับ Glass Card, Sticky Toolbar, Compact Controls, Mobile Responsive และ Table overflow สำหรับจอเล็ก
- ไม่เปลี่ยน logic การคำนวณรายได้/รายจ่ายหลัก เพื่อลดความเสี่ยงข้อมูลผิดเพี้ยน
