# CLAUDE.md

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

## 專案結構

```
SwiftCull/
├── main.py
├── app/
│   ├── ui/       # 純介面，不含業務邏輯
│   ├── core/     # 業務邏輯，不依賴 UI
│   ├── db/       # 所有 SQLite 操作
│   └── utils/
├── tests/
└── assets/
```

## 核心原則

- 不修改原始照片檔案，所有標記寫入 SQLite
- `ui/` 不含業務邏輯，`core/` 不依賴 UI
- 路徑一律用相對路徑存入資料庫
- 快取位置：`%LOCALAPPDATA%\SwiftCull\cache\`
- 設定檔位置：`%APPDATA%\SwiftCull\`

## 不做的事

- 不修改原始檔案
- 不支援 HEIC（未來版本再加）
- 不做跨平台（Windows only）
- Phase 1 不做 Undo/Redo
- Phase 1 不做偵測算法與 AI 功能
