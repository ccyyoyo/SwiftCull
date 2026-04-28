# DATA_MODEL.md

> 初版 schema，開發中可調整。

## SQLite 設定

- WAL mode 開啟
- 路徑用相對路徑（相對於專案根目錄）

## Tables

### photos

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | INTEGER PK | |
| relative_path | TEXT UNIQUE | 相對路徑 |
| filename | TEXT | |
| file_size | INTEGER | bytes |
| shot_at | TEXT | EXIF 拍攝時間（ISO8601） |
| imported_at | TEXT | 匯入時間（ISO8601） |
| width | INTEGER | 原始寬度 |
| height | INTEGER | 原始高度 |
| camera_model | TEXT | EXIF |
| lens_model | TEXT | EXIF |
| iso | INTEGER | EXIF |
| aperture | REAL | EXIF f-number |
| shutter_speed | TEXT | EXIF（例如 "1/250"） |
| focal_length | REAL | EXIF mm |

### tags

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | INTEGER PK | |
| photo_id | INTEGER FK → photos.id | |
| status | TEXT | "pick" / "reject" / "maybe" / null |
| color | TEXT | "red" / "orange" / "yellow" / "green" / "blue" / "purple" / null |
| updated_at | TEXT | ISO8601 |

### groups

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | INTEGER PK | |
| name | TEXT | |
| type | TEXT | "burst" / "scene" / "similar" / "manual" |
| created_at | TEXT | ISO8601 |

### photo_groups

| 欄位 | 型別 | 說明 |
|------|------|------|
| photo_id | INTEGER FK → photos.id | |
| group_id | INTEGER FK → groups.id | |
| is_best | INTEGER | 1 = 組內最佳張 |
