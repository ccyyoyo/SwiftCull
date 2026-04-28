# ROADMAP.md

## Phase 1 — MVP

目標：可用的照片瀏覽與手動標記工具。

### 匯入
- 資料夾拖放匯入，子資料夾遞迴掃描
- RAW 快速預覽（內嵌 JPEG thumbnail）
- 主流 RAW 格式支援（rawpy）
- JPEG / PNG / TIFF / WebP 支援
- 開啟時直接載入上次 session
- 背景靜默比對 mtime，發現新檔案 → 右下角通知，使用者選擇是否匯入
- EXIF 背景讀取，縮圖優先顯示

### 空狀態
- 歡迎畫面：簡介 + 操作說明（拖放資料夾 / 開啟現有專案）

### 縮圖 Grid
- 滑桿調整縮圖大小（小/中/大）
- 縮圖下方：檔名 + 標記狀態 icon
- 縮圖角落：顏色小標籤

### Loupe 全螢幕檢視
- 進入：雙擊縮圖 或 Space
- 切換照片：左右方向鍵
- 標記：P/R/M 快捷鍵
- 右下角 auto-hide 標記按鈕（hover 才顯示）
- 頂部 auto-hide 篩選 toolbar（hover 才顯示）

### 標記
- Pick / Reject / Maybe 三態標記
- 顏色標籤
- 批次標記：Ctrl+點擊、Shift+點擊、框選
- 批次操作確認 dialog（可勾選 "Don't ask again"）

### 篩選
- 條件：標記狀態 + 顏色標籤
- 多條件邏輯：AND
- 一般模式：左側 auto-hide 側邊欄（hover 顯示）
- Loupe 模式：頂部 auto-hide toolbar（hover 顯示）

### 資料
- SQLite 儲存所有 metadata 與標記（WAL mode）
- 不修改原始檔案
- 專案位置：`%LOCALAPPDATA%\SwiftCull\projects\{name}\project.db`
- 縮圖快取：`%LOCALAPPDATA%\SwiftCull\projects\{name}\cache\`
- 全域設定：`%LOCALAPPDATA%\SwiftCull\settings.db`

## Phase 2 — 偵測與匯出

目標：AI 輔助篩選與外部工具整合。

- 模糊偵測（Laplacian variance）
- 曝光問題偵測（histogram）
- 高噪點偵測（FFT/SNR）
- 地平線歪斜偵測（Hough Line）
- 閉眼偵測（MediaPipe FaceMesh）
- 人臉對焦評分
- 頭部姿勢偵測
- 主體偵測（YOLOv8）
- 相似/重複照片分組（pHash）
- 場景自動分組（時間戳 + pHash）
- Burst 連拍識別（EXIF 時間戳）
- 每組自動選最佳張
- Lightroom XMP 匯出
- Capture One / Darktable 匯出
- CSV / JSON 報告匯出
- Picked 照片移動/複製
- HEIC 支援

## Phase 3 — 進階功能

目標：個人化與進階工作流程。

- Undo / Redo（JSONL append-only）
- 臉部識別，跨照片追蹤同一人（InsightFace）
- 重要主體設定（face embedding）
- 個人化設定
- 多組設定檔
