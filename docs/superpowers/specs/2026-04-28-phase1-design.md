# SwiftCull Phase 1 設計文件

**日期：** 2026-04-28  
**範圍：** Phase 1 MVP — 匯入、縮圖 Grid、Loupe、標記、篩選、SQLite

---

## 1. 架構

### 分層原則

| 層 | 模組 | 職責 |
|----|------|------|
| 入口 | `main.py` | 啟動 app，設定環境變數 |
| UI | `app/ui/` | 純介面，不含業務邏輯 |
| Core | `app/core/` | 業務邏輯，不依賴 UI |
| DB | `app/db/` | 所有 SQLite 操作集中於此 |
| Utils | `app/utils/` | 共用工具（file_utils） |

### 專案結構

```
SwiftCull/
├── main.py
├── app/
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── grid_view.py
│   │   ├── loupe_view.py
│   │   └── filter_panel.py
│   ├── core/
│   │   ├── importer.py
│   │   ├── thumbnail.py
│   │   └── tagger.py
│   ├── db/
│   │   ├── database.py
│   │   └── models.py
│   └── utils/
│       └── file_utils.py
├── tests/
└── assets/
```

### 環境設定

`main.py` 啟動時設定：
```python
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
```

---

## 2. 資料層

### 資料庫路徑

| 項目 | 路徑 |
|------|------|
| 專案 DB | `%LOCALAPPDATA%\SwiftCull\projects\{name}\project.db` |
| 縮圖快取 | `%LOCALAPPDATA%\SwiftCull\projects\{name}\cache\` |
| 全域設定 | `%LOCALAPPDATA%\SwiftCull\settings.db` |

### SQLite 設定

- WAL mode 開啟
- 路徑用相對路徑（相對於專案根目錄）

### Schema

#### photos

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

#### tags

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | INTEGER PK | |
| photo_id | INTEGER FK → photos.id | |
| status | TEXT | "pick" / "reject" / "maybe" / null |
| color | TEXT | "red" / "orange" / "yellow" / "green" / "blue" / "purple" / null |
| updated_at | TEXT | ISO8601 |

#### groups

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | INTEGER PK | |
| name | TEXT | |
| type | TEXT | "burst" / "scene" / "similar" / "manual" |
| created_at | TEXT | ISO8601 |

#### photo_groups

| 欄位 | 型別 | 說明 |
|------|------|------|
| photo_id | INTEGER FK → photos.id | |
| group_id | INTEGER FK → groups.id | |
| is_best | INTEGER | 1 = 組內最佳張 |

---

## 3. 匯入流程

### 首次匯入

1. 使用者拖放資料夾 或 點擊「開啟專案」
2. 遞迴掃描支援格式：RAW（rawpy）、JPEG、PNG、TIFF、WebP
3. 每張照片：讀取內嵌 JPEG thumbnail → 立刻寫入 SQLite → 顯示 Grid
4. EXIF 背景執行緒讀取，靜默補入 SQLite，不阻塞 UI

**效能目標：** 1000 張初次匯入縮圖 < 15 秒

### 重開已存在專案

1. 直接載入 SQLite（目標 < 5 秒）
2. 背景掃描比對所有檔案 mtime
3. 發現差異 → 彈出 dialog：「發現 N 個新/修改檔案，是否匯入？」
4. 使用者選「是」→ 匯入；選「否」→ 略過

### 損壞檔案處理

- 跳過損壞檔案，不中斷整批處理
- 累積錯誤清單，匯入完成後一次顯示警示

### 排序

- 固定檔名字母順序（`filename ASC`）
- Phase 1 不提供切換排序 UI

---

## 4. 空狀態

**條件：** 無任何專案（第一次開啟）

**顯示：**
- 歡迎畫面居中
- 簡短介紹 SwiftCull
- 拖放目標區 + 說明文字「拖放資料夾以建立專案」
- 「開啟現有專案」按鈕

**有專案時：** 直接載入上次 session，跳過歡迎畫面

---

## 5. 縮圖 Grid

### 顯示

- Lazy load：只渲染可見範圍
- 縮圖大小：小 / 中 / 大 三段滑桿
- 縮圖下方：檔名 + 標記狀態 icon（P / R / M）
- 縮圖角落：顏色小標籤（有顏色才顯示）

### 選取

| 操作 | 行為 |
|------|------|
| 單擊 | 單選 |
| Ctrl + 點擊 | 個別多選 |
| Shift + 點擊 | 範圍選取 |
| 滑鼠框選 | 拖拉選取 |

### 進入 Loupe

- 雙擊縮圖
- 或按 Space

---

## 6. Loupe 全螢幕檢視

### 進出

| 操作 | 行為 |
|------|------|
| 雙擊縮圖 / Space | 進入 Loupe |
| Escape / Space | 離開 Loupe |

### 導航

| 操作 | 行為 |
|------|------|
| ← | 上一張 |
| → | 下一張 |

### 標記快捷鍵

| 鍵 | 動作 |
|----|------|
| P | Pick |
| R | Reject |
| M | Maybe |
| U | 清除標記 |

### Auto-hide 元素

| 元素 | 位置 | 觸發 |
|------|------|------|
| 標記按鈕（Pick/Reject/Maybe） | 右下角 | hover 才顯示 |
| 篩選 toolbar | 頂部 | hover 才顯示 |

---

## 7. 標記系統

### 三態標記

| 標記 | 快捷鍵 | 說明 |
|------|--------|------|
| Pick | P | 保留 |
| Reject | R | 刪除候選 |
| Maybe | M | 待決定 |
| 清除 | U | 回到未標記 |

### 顏色標籤

紅 / 橙 / 黃 / 綠 / 藍 / 紫（可與三態標記並存）

### 批次標記

1. 選取多張（Ctrl+點擊 / Shift+點擊 / 框選）
2. 套用標記
3. 彈出確認 dialog
4. Dialog 有「Don't ask again」勾選選項

### 資料邏輯

- 標記寫入 `tags` table
- 顏色標籤存於獨立欄位（`color`）
- 每次變更更新 `updated_at`

---

## 8. 篩選

### 篩選條件

| 類型 | 選項 |
|------|------|
| 標記狀態 | Pick / Reject / Maybe / 未標記（可多選） |
| 顏色標籤 | 紅/橙/黃/綠/藍/紫（可多選） |

- 多條件邏輯：AND
- 篩選即時反映 Grid 內容
- 篩選狀態存於記憶體，不持久化到 DB

### UI 位置

| 模式 | 篩選 UI |
|------|---------|
| 一般模式 | 左側 auto-hide 側邊欄，hover 才顯示 |
| Loupe 模式 | 頂部 auto-hide toolbar，hover 才顯示 |

---

## 9. 效能目標

| 操作 | 目標 |
|------|------|
| 1000 張初次匯入縮圖 | < 15 秒 |
| Grid 載入（1000 張可見） | < 2 秒 |
| 重開已快取專案 | < 5 秒 |

---

## 10. 不在 Phase 1 範圍

- 排序切換 UI
- AI / 偵測算法（Phase 2）
- Undo / Redo（Phase 3）
- HEIC 支援
- 匯出功能
- 跨平台支援
