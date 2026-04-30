# Phase 1 詳細設計

## 匯入流程

1. 使用者拖放資料夾 或 點擊「開啟專案」
2. 程式掃描所有支援格式（RAW / JPEG / PNG / TIFF / WebP），遞迴子資料夾
3. 讀取內嵌 JPEG thumbnail，立刻寫入 SQLite 並顯示縮圖 Grid
4. EXIF 背景讀取，靜默補入 SQLite，不阻塞 UI

**重開已存在專案：**
- 直接載入 SQLite，< 5 秒
- 背景比對 mtime，發現新/修改檔案 → 右下角 toast 通知
- 使用者按「匯入」才實際匯入；按「忽略」或關閉 toast 跳過
- 「修改」檔案會重跑 EXIF + 失效縮圖快取

## 空狀態（第一次開啟）

- 歡迎畫面
- 簡短介紹 SwiftCull
- 操作說明：拖放資料夾建立專案 / 點擊按鈕開啟現有專案

## 縮圖 Grid

- 滑桿調整大小：小 / 中 / 大 三段
- 縮圖下方：檔名 + 標記狀態 icon（P/R/M）
- 縮圖左上角（或右上角）：顏色小標籤
- Lazy load：只渲染可見範圍

## Loupe 全螢幕檢視

| 操作 | 方式 |
|------|------|
| 進入 Loupe | 雙擊縮圖 或 Space |
| 離開 Loupe | Escape 或 Space |
| 切換照片 | 左右方向鍵 |
| 標記 Pick | P |
| 標記 Reject | R |
| 標記 Maybe | M |
| 清除標記 | U |

- 右下角 auto-hide 標記按鈕（Pick/Reject/Maybe），hover 才顯示
- 頂部 auto-hide 篩選 toolbar，hover 才顯示

## 標記系統

| 標記 | 快捷鍵 | 說明 |
|------|--------|------|
| Pick | P | 保留 |
| Reject | R | 刪除候選 |
| Maybe | M | 待決定 |
| 清除 | U | 回到未標記 |

**顏色標籤：** 紅 / 橙 / 黃 / 綠 / 藍 / 紫

**批次標記：**
- 選取：Ctrl+點擊（個別）、Shift+點擊（範圍）、滑鼠框選
- 套用標記後顯示確認 dialog
- Dialog 可勾選「Don't ask again」

## 篩選

- 條件：標記狀態（Pick/Reject/Maybe/未標記）+ 顏色標籤
- 多條件 AND 邏輯
- 一般模式：左側 auto-hide 側邊欄
- Loupe 模式：頂部 auto-hide toolbar

## 資料儲存

| 項目 | 路徑 |
|------|------|
| 專案資料庫 | `%LOCALAPPDATA%\SwiftCull\projects\{name}\project.db` |
| 縮圖快取 | `%LOCALAPPDATA%\SwiftCull\projects\{name}\cache\` |
| 全域設定 | `%LOCALAPPDATA%\SwiftCull\settings.db` |

- SQLite WAL mode
- 路徑用相對路徑存入 DB
- 不修改原始檔案
