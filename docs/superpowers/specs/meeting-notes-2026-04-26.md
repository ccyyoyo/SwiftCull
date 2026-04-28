# SwiftCull 設計討論會議記錄
**日期：** 2026-04-26

---

## 缺口分析 — 使用者決策

| 缺口 | 決策 | 備註 |
|------|------|------|
| **Session / 資料持久化** | 需要 | 格式見下方分析，參考 Lightroom / Capture One |
| **損壞檔案處理** | 跳過 + 警示 | 不中斷整批處理 |
| **空狀態 / Onboarding** | 什麼都不顯示，等使用者操作 | 參考 IDE（VSCode / JetBrains）模式 |
| **批次操作確認** | 每個操作都加確認 dialog | 可讓使用者關閉（"Don't ask again"） |
| **排序 / 篩選 UI** | 需要 | 待設計 |
| **效能分析** | 需要分析各方案效能 | 見下方效能分析 |
| **HEIC 支援** | 先不支援 | 未來版本再加 |
| **目標平台** | Windows only | 未來再討論跨平台 |
| **UI Framework** | 見下方分析 | 多面向比較後決定 |
| **資料儲存格式** | 見下方分析 | 多面向比較後決定 |

---

## UI Framework 多面向比較

### 比較對象：PySide6 vs Tauri vs Electron

| 面向 | PySide6 | Tauri | Electron |
|------|---------|-------|----------|
| **記憶體（idle）** | 150-200 MB | 20-40 MB ✅ | 200-400 MB ❌ |
| **啟動時間** | 2-4 秒 | < 1 秒 ✅ | 3-5 秒 |
| **Python 整合** | ✅ 原生，無延遲 | HTTP sidecar，1-5ms | IPC，0.08ms |
| **圖片 Grid 效能** | ✅ 60FPS QPainter | ✅ GPU 加速 | 45-50FPS |
| **自訂 Overlay 繪製** | ✅ QPainter 最快 2-3ms | Canvas 5-8ms | Canvas 5-8ms |
| **長期維護風險** | ✅ 低（Qt Company 官方） | 中低（基金會） | ✅ 很低（GitHub/MS） |
| **安裝包大小** | ~70 MB | ~15-20 MB ✅ | ~150 MB ❌ |
| **HiDPI / 混合 DPI** | ⚠️ 已知 bug（多螢幕不同 DPI） | ✅ 網頁標準處理 | ✅ 網頁標準處理 |
| **授權** | ✅ LGPL（免費商用） | ✅ MIT | ✅ MIT |
| **無障礙（a11y）** | ⚠️ JAWS/NVDA 有缺陷 | ✅ 網頁標準 ARIA | ✅ 網頁標準 ARIA |
| **測試框架** | pytest-qt（學習曲線） | WebdriverIO（網頁習慣） | Playwright（最成熟）✅ |
| **社群 / 招募** | 困難，Qt 專才少 | 中等，Rust+Web | ✅ 最大社群 |
| **拖放（Explorer→App）** | 所有方案相同，避免 admin 模式 | 同左 | 同左 |
| **Schema 測試** | pytest-qt 直接測 Qt signal | WebDriver | Playwright |

### 結論

**建議：PySide6**
- 理由：Python 直接整合 OpenCV/MediaPipe/InsightFace（無序列化開銷）、QPainter 對圖片密集 UI 最快、LGPL 免費商用、官方 Qt 長期支援
- 已知風險：多螢幕 HiDPI bug → 需設定 `QT_AUTO_SCREEN_SCALE_FACTOR=1` + 測試

**備選：Tauri**（如果未來要最小安裝包 / 招募 Web 開發者）

**不建議：Electron**（記憶體最重、圖片效能差）

---

## 資料儲存多面向比較

### 比較對象：SQLite vs JSONL

| 面向 | SQLite | JSONL |
|------|--------|-------|
| **效能（10k 張查詢）** | ✅ 5-50ms（有索引） | 500ms-2s（全檔掃描） |
| **損壞風險** | 中（WAL 模式可復原） | ⚠️ 寫到一半崩潰 = 壞檔 |
| **崩潰安全** | ✅ 自動 rollback | ❌ 需手動修復 |
| **Schema 升級** | ✅ `ALTER TABLE` 一行 | 需讀全檔、逐筆修改、重寫 |
| **備份 UX** | ✅ 複製一個 .db 檔 | 需複製整個資料夾 |
| **並發保護** | ✅ 檔案鎖，第二個實例報錯 | ❌ 兩個實例同寫 → 靜默資料遺失 |
| **可讀性** | ❌ 需 SQL 工具 | ✅ 純文字 |
| **多機同步** | 兩者都不理想；建議單一寫入端 | 同左 |
| **搜尋篩選** | ✅ SQL 原生支援 | 需載入全部到記憶體再篩選 |
| **路徑可攜性** | 需用相對路徑 | 同左 |

### 結論

**建議：SQLite（主資料庫）+ JSONL（Undo 歷史）**
- SQLite 儲存：照片 metadata、分析結果、標記、分組
- JSONL 儲存：每個操作一行，用於 Undo/Redo（append-only，不怕崩潰）
- 參考：Lightroom 用 SQLite catalog + XMP sidecar，FastRawViewer 用 SQLite cache

**關鍵設定：**
- WAL mode 開啟
- 路徑用相對路徑（`./photos/img001.raw`）
- 快取位置：`%LOCALAPPDATA%\SwiftCull\cache\`

---

## 效能分析

### 速度目標

| 操作 | 目標時間 | 實作方式 |
|------|----------|----------|
| 1000 張初次匯入（縮圖） | < 15 秒 | 內嵌 JPEG thumbnail（rawpy），批次 100 張 |
| Grid 載入（1000 張可見） | < 2 秒 | lazy load + SQLite 快取 |
| Blur + 曝光偵測（10k 張） | < 60 秒 | 縮圖 Laplacian（5-10ms/張），multiprocessing |
| MediaPipe 人臉偵測（10k） | < 90 秒 | 5ms/張，單執行緒 |
| InsightFace embedding（10k） | < 5 分鐘（GPU） / 15 分鐘（CPU） | 批次 32 張 |
| 重開已快取專案 | < 5 秒 | SQLite index + lazy load |

### RAM 使用

| 情境 | 預估 RAM |
|------|----------|
| 單張完整分析（所有模型） | ~500-800 MB |
| 批次 10-20 張（建議） | ~2-3 GB peak |
| 所有模型同時批次 100 張 | ~15 GB（**不建議**） |

**結論：批次大小 10-20 張是最佳平衡點（記憶體 + 效能 + UX）**

### 磁碟瓶頸

- **CPU/GPU 是真正瓶頸**，I/O 影響不大（<10% 差異）
- SSD 改善滾動 UI 響應（縮圖隨機讀取），非必要但建議

### 取消/暫停

- 用 `threading.Event` cooperative cancellation
- 每張照片檢查一次 flag
- 取消延遲：200-500ms（可接受）

### 進度顯示

- **每 20 張更新一次** UI 進度條（sweet spot）
- 同步顯示剩餘時間估計
- 不要每張都更新（太頻繁）也不要整批才更新（太卡）

---

## 快取策略

| 快取類型 | 位置 | 備註 |
|----------|------|------|
| 縮圖 + 分析結果 | `%LOCALAPPDATA%\SwiftCull\cache\`（SQLite） | 參考 Lightroom / FastRawViewer |
| Undo 歷史 | 專案資料夾 `.swiftcull/history.jsonl` | Append-only，可攜 |
| 設定檔 | `%APPDATA%\SwiftCull\` | Windows 慣例 |

**快取失效策略：** 比對檔案 mtime，若 RAW 有更新則重算

---

## 待確認事項

- [x] 確認 UI Framework 最終選擇 → **PySide6**
- [x] 確認資料儲存方案 → **SQLite only**（JSONL Undo 移至 Phase 3）
- [x] 設計篩選 / 排序 UI 細節 → 見下方
- [ ] 確認效能目標數字是否符合預期

---

## 2026-04-27 會議結論

### 框架與儲存

| 議題 | 決定 |
|------|------|
| UI Framework | PySide6 確認 |
| 資料儲存 | SQLite only（Phase 1 起） |
| Undo/JSONL | Phase 3，最後才做 |

### 開發階段

| Phase | 內容 |
|-------|------|
| **Phase 1** | 匯入、縮圖網格、全螢幕 Loupe、Pick/Reject/Maybe、顏色標籤、批次標記、SQLite |
| **Phase 2** | 偵測算法（模糊、曝光、人臉）、AI 功能、匯出 |
| **Phase 3** | Undo/Redo（JSONL）、個人化、進階功能 |

### 篩選 UI

**篩選條件：**
- 標記狀態：Pick / Reject / Maybe / 未標記
- 顏色標籤

**UI 行為：**
- 一般模式 → 左側邊欄，滑鼠 hover 才顯示（auto-hide）
- 全螢幕 Loupe 模式 → 頂部 toolbar，滑鼠 hover 才顯示（auto-hide）

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

- `ui/` → 純介面，不含業務邏輯
- `core/` → 業務邏輯，不依賴 UI
- `db/` → 所有 SQLite 操作集中
- 結構保持彈性，開發中可調整
