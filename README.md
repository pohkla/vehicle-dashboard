# Vehicle Dashboard v6.8 Import Flow Final Fix

พร้อม Deploy

## แก้ Flow Import Excel

เพิ่ม endpoint ใหม่:

```text
POST /api/import/excel-final
GET  /api/debug/import-flow
```

## วิธีใช้งานหลัง Deploy

1. เปิด `/admin`
2. เลือกไฟล์ Excel
3. กด `Import Excel`
4. ต้องเห็น:
   - `ประเภท Import: excel`
   - `Verify GitHub: excel / xx records`

## เช็กผล

เปิด:

```text
/api/debug/import-flow
/api/debug/company-summary
```

ต้องเห็น:

```text
import_type = excel
has_amount_fields = true
net / collected > 0
```
