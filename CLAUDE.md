# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案簡介

SwiftCull 是 Windows-only 本地照片 culling 桌面工具。目標用戶為攝影師。所有處理完全 local，不上傳照片。

## 技術選型（不可更改）

| 項目 | 選擇 |
|------|------|
| UI Framework | PySide6 |
| 資料儲存 | SQLite（WAL mode） |
| 圖片處理 | OpenCV、rawpy、Pillow |
| 人臉偵測 | MediaPipe |
| 人臉識別 | InsightFace |
| 物件偵測 | YOLOv8 |
| 目標平台 | Windows only |

## 開發指令

```bash
# 安裝依賴
pip install -r requirements.txt

# 啟動應用程式
python main.py

# 執行所有測試
pytest

# 執行單一測試檔案
pytest tests/core/test_import_service.py

# 執行單一測試函式
pytest tests/core/test_import_service.py::test_function_name
```

## 架構

```
main.py
    ↓
app/
├── ui/              # 純介面層，不含業務邏輯
├── core/            # 業務邏輯，不依賴 UI
├── db/              # 所有 SQLite 操作
└── utils/
    └── theme.py     # 所有深色主題顏色與樣式（集中定義）
```

**UI 層 (`app/ui/`)：** `MainWindow` 控制 stacked widget 在 `WelcomeView`（拖放資料夾）與 `GridView`（縮圖格柵 + 篩選面板 + 預覽）之間切換。`LoupeView` 提供全螢幕單張檢視。

**Core 層 (`app/core/`)：** `ImportService` 掃描資料夾並解析 EXIF；`ImportWorker` 用 QThread 在背景執行，透過 signals 與 UI 溝通。`TagService` 處理標記狀態（pick/reject/maybe）與色彩標籤。`ThumbnailService` 負責生成與快取縮圖。`BlurService` 用 OpenCV Laplacian 計算模糊分數（`Optional[float]`，None 代表無法讀取）；`BlurWorker` 在背景執行分析。`FilterService` 過濾照片，支援 status/color/blur 多選 OR 邏輯與固定閾值（`blur_fixed_threshold`）模糊篩選。`ScanService`/`ScanWorker` 背景偵測資料夾變更（新增/修改/消失）。

**DB 層 (`app/db/`)：** `PhotoRepository` 與 `TagRepository` 封裝 SQL 操作。`connection.py` 初始化 WAL 模式 schema。`SettingsDB` 提供全域 key-value 設定儲存。Tags 採用 upsert 模式。

## 重要模式

**兩階段匯入：** 先快速建立 Photo 記錄（僅檔名＋大小），背景 worker 再補充 EXIF 與尺寸。

**資料持久化：**
- 全域設定（上次開啟資料夾、模糊偵測設定）→ `%LOCALAPPDATA%\SwiftCull\settings.db`（SQLite key-value）
- 專案資料（photos、tags）→ `%LOCALAPPDATA%\SwiftCull\projects\{name}\project.db`
- 縮圖快取 → 專案的 cache 目錄
- 路徑一律以相對路徑存入資料庫

**執行緒模型：** 主執行緒跑 PySide6 事件迴圈；匯入跑獨立 QThread；用 signals 安全傳遞資料。

## 核心原則

- 不修改原始照片檔案，所有標記寫入 SQLite
- `ui/` 不含業務邏輯，`core/` 不依賴 UI

## 不做的事

- 不修改原始檔案
- 不支援 HEIC（未來版本再加）
- 不做跨平台（Windows only）
- Phase 1 不做 Undo/Redo
- Phase 1 不做偵測算法與 AI 功能
