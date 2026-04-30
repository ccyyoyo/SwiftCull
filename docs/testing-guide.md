# SwiftCull 測試手冊

> 對象：開發者、Phase release 前的 QA、回歸測試
> 範圍：Phase 1 MVP（匯入、Grid、Loupe、標記、篩選、Toast、最近專案）

本文件分四層：

1. **自動測試** — 開發循環中的快速回饋
2. **效能基準** — 對照 spec 的數字目標
3. **手動煙霧測試** — 按使用情境逐項驗證
4. **邊界情境 / 壓力測試** — 釋出前再跑

---

## 0. 測試環境

| 項目 | 要求 |
|------|------|
| OS | Windows 10/11（spec：Windows-only） |
| Python | 3.9+ |
| 必要套件 | `PySide6`、`Pillow`、`piexif`、`rawpy`、`pytest` |
| 測試資料 | 推薦準備一個 1000+ 張的真實照片資料夾（含 RAW + JPEG 混合） |
| 螢幕 | 1920×1080 起跳，HiDPI 機器另測一輪 |

```bash
pip install -r requirements.txt
pip install pytest
```

---

## 1. 自動測試

### 1.1 跑全套單元 / 整合測試

```bash
# Windows
python -m pytest -q

# 帶詳細輸出
python -m pytest -v
```

預期：**103 passed**（含 PySide6 環境）；無 PySide6 時 `tests/core/test_batch_confirm.py` 會 collect 失敗，加 `--ignore=tests/core/test_batch_confirm.py`。

### 1.2 已涵蓋（自動）

| 模組 | 測試檔 | 重點 |
|------|--------|------|
| `ImportService` | `tests/core/test_import_service.py` | 副檔名過濾、minimal vs enrich、mtime 捕捉 |
| `ScanService` | `tests/core/test_scan_service.py` | new/modified/missing 三桶、mtime epsilon、legacy null mtime、混合情境 |
| `ThumbnailService` | `tests/core/test_thumbnail_service.py` | 快取命中、`invalidate` |
| `TagService` | `tests/core/test_tag_service.py` | set/clear status、color 保留、batch、None 寫入語意 |
| `FilterService` | `tests/core/test_filter_service.py` | status/color 組合、untagged 邏輯 |
| `RecentProjects` | `tests/core/test_recent_projects.py` | dedupe、上限、prune missing、壞值容錯 |
| `preview_loader` | `tests/core/test_preview_loader.py` | RAW 嵌入 JPEG、標準格式、錯誤路徑 |
| `PhotoRepository` | `tests/db/test_photo_repository.py` | insert / update / mtime 欄位 / mtime map |
| `TagRepository` | `tests/db/test_tag_repository.py` | upsert（含 None 寫入修正） |
| `connection.init_db` | `tests/db/test_connection.py` | schema、migration 加 `mtime`、idempotence |
| `SettingsDB` | `tests/db/test_settings_db.py` | KV、自動從 `settings.json` 匯入、壞 JSON 容錯 |
| `format_scan_message` | `tests/utils/test_messages.py` | 5 種 new/modified/missing 組合 |
| 端到端 | `tests/integration/test_import_to_filter_flow.py` | scan → import → tag → filter |

### 1.3 未涵蓋（必須手動驗）

- 任何 Qt widget 的繪製、事件處理、跨 thread signal
- `LoupeView`、`ThumbnailGrid`、`ThumbnailItem`、`Toast`、`WelcomeView`、`MainWindow`、`GridView`、`FilterPanel`、`BatchConfirmDialog`
- `ImportWorker` / `ScanWorker` 的 cancel 行為（與 QThread 強耦合，目前以人工驗證）
- 顏色/字體 theme 的視覺正確性
- 拖放、右鍵選單、鍵盤焦點

> 規則：UI 程式碼若可純邏輯化（例如把訊息字串拉到 `app/utils/messages.py`），**就要拉**，並補單元測試。不能拉的部分走第 3 節手動 checklist。

---

## 2. 效能基準

### 2.1 跑法

```bash
python tools/benchmark_phase1.py --count 1000 --dim 1024 --workers 4
```

旗標：`--count` / `--dim` / `--workers` / `--keep` / `--workdir <path>`

### 2.2 Spec 目標 vs 基線（合成資料，2026-04-30）

| 目標 | Spec | 基線 | 結果 |
|------|------|------|------|
| 1000 張初次匯入（資料管線） | < 15 s | 1.37 s | PASS |
| 重開掃描 | < 5 s | 0.05 s | PASS |
| Grid 載入 1000 縮圖 | < 2 s | 需實機 | 手動驗證 |

詳細數字見 `docs/perf-baseline-2026-04-30.md`。

### 2.3 何時要重跑

- 改 `ImportService` / `ScanService` / `PhotoRepository` / `ThumbnailService`
- 升 SQLite / Pillow / piexif / rawpy 主版號
- 換目標機（不同硬碟、不同 CPU）
- 任何 PR 提到「優化」必須附前後對照

### 2.4 真實 RAW 驗證（非合成）

合成 JPEG 的 I/O 是真 RAW 的 1/30~1/100。**Phase 1 release 前必須用實拍 RAW 跑一次：**

1. 準備 1000 張真 RAW（CR2/NEF/ARW 等任一）的資料夾
2. `python tools/benchmark_phase1.py --workdir <path-with-real-raws> --count 1000 --keep`
3. **手動跑 GUI**：開啟該資料夾，從點擊到 Grid 顯示完成的牆鐘時間應 < 15 s

如果失敗，瓶頸通常在：
- 磁碟（HDD / 網路磁碟 vs NVMe）
- `rawpy.extract_thumb` 嵌入預覽萃取
- `piexif` 解析

---

## 3. 手動煙霧測試（每個 release 必跑）

### 3.1 測前準備

- [ ] 清空 `%LOCALAPPDATA%\SwiftCull\` 與 `%APPDATA%\SwiftCull\`，模擬全新安裝
- [ ] 準備兩個照片資料夾：
  - **A**：100 張小 JPEG，含 1 個子資料夾
  - **B**：含 RAW（任一格式）+ JPEG 混合，至少 50 張
- [ ] 啟動：`python main.py`

### 3.2 第一次開啟（Welcome → Grid）

| # | 步驟 | 期望 |
|---|------|------|
| 1 | 啟動 app | 看到 Welcome 頁面、無「最近專案」區塊（首次開啟） |
| 2 | 拖放資料夾 A 到視窗中央區塊 | 自動切到 Grid 視圖、開始匯入、頂部顯示「匯入中 X / 100」進度條 |
| 3 | 等匯入完成 | 進度條消失、Grid 顯示 100 張縮圖、`%LOCALAPPDATA%\SwiftCull\projects\<name>\project.db` 存在 |
| 4 | 重啟 app | Welcome 頁的「最近專案」出現 A 的條目，且自動載入 A（last_folder 行為） |

### 3.3 重開掃描 + Toast

> 先關閉 app，再對資料夾 A 在 Explorer 操作後重啟。

| # | 修改 | 期望 toast 行為 |
|---|------|-----------------|
| 1 | 不改任何東西 | 重啟後**無 toast**，立即看到 Grid |
| 2 | 加 3 張新 JPEG 到 A | 重啟後右下角 toast：「發現 3 個新增 檔案，是否匯入？」+「匯入 / 忽略」鈕 |
| 3 | 點「匯入」 | 進度條跑、新縮圖出現在 Grid、toast 消失 |
| 4 | 修改既有檔案的內容（例：在 Photoshop 重存一張） | toast：「發現 1 個修改 檔案…」、按匯入後該縮圖**強制重新生成**（看到視覺更新） |
| 5 | 刪除 A 內 5 張 JPEG | toast：「有 5 個檔案找不到。」（無「匯入」鈕、有「知道了」、8 秒自動消失） |
| 6 | 同時加新 + 刪舊 | toast 一行包兩件事：「發現 N 個新增 檔案；另有 M 個檔案找不到。是否匯入？」 |
| 7 | toast 顯示時點「忽略」 | toast 消失，無匯入；下次重啟仍會偵測到 |
| 8 | toast 顯示時 resize 視窗 | toast 跟著貼右下角 |

### 3.4 找不到原檔的 UI 表現

| # | 步驟 | 期望 |
|---|------|------|
| 1 | 在 app 開啟 A 後，從 Explorer 刪 5 張並按 Grid 工具列「↻ 重新掃描」 | 那 5 個 tile 變半透明黑 + 中央紅色「✕ 找不到原檔」膠囊 + tooltip「原檔不存在」 |
| 2 | 雙擊一個 missing tile 進 Loupe | Loupe 中央顯示紅字「✕ 原檔不存在 / <relative_path> / 請檢查檔案是否被移動或刪除」 |
| 3 | 把那 5 張**還原到原位**（複製回去）並重新掃描 | tile 視覺回到正常、tooltip 清掉 |

### 3.5 Loupe 操作

> 雙擊 Grid 任一張進 Loupe。

| # | 操作 | 期望 |
|---|------|------|
| 1 | 滑鼠移到頂部 | 頂部出現篩選 toolbar（status checkboxes + 顏色點），2 秒後自動隱藏 |
| 2 | 滑鼠移到底部 | 底部出現操作 toolbar（P/R/M/U + 顏色 + 關閉），2 秒後自動隱藏 |
| 3 | 按 P / R / M | 中央左上角狀態圖示 + 文字立刻更新 |
| 4 | 按 U | 狀態清除（圖示消失） |
| 5 | 點顏色按鈕 | 左上角狀態旁出現對應顏色點 |
| 6 | 點「✕ 顏色」 | 顏色點消失，但狀態保留 |
| 7 | 左 / 右方向鍵 | 切換上 / 下一張 |
| 8 | 滑鼠滾輪上下 | 切換上 / 下一張 |
| 9 | Ctrl + 滾輪 | 縮放中心點，10% ~ 800% 範圍 |
| 10 | 在頂部 toolbar 勾「pick」 | Loupe 內的照片清單即時縮減為 picks；目前照片若不在新清單，跳到第一張；若全空顯示「沒有符合篩選的照片」 |
| 11 | 按 Esc | 回 Grid，且**側邊 FilterPanel 的勾選同步**（Loupe 內改的篩選反映回 Grid） |
| 12 | 對 RAW 檔案進 Loupe | 顯示嵌入式 JPEG 預覽（不能黑屏） |
| 13 | 對檔案被刪掉的列雙擊 | 顯示「✕ 原檔不存在…」訊息（同 3.4） |

### 3.6 Grid 多選 + 批次標記

| # | 操作 | 期望 |
|---|------|------|
| 1 | 單擊一張 | 該 tile 邊框變色 |
| 2 | Ctrl + 單擊另一張 | 兩張都選取 |
| 3 | Shift + 單擊（在現選之後另一張） | 範圍選取 |
| 4 | 在背景空白處按下並拖曳 | 出現橡皮筋（QRubberBand）矩形，框內 tile 即時 highlight |
| 5 | 放開拖曳 | 選取定位於框內 tile |
| 6 | Ctrl + 拖曳 | 在原選取**基礎上**加進框內 tile |
| 7 | 在背景空白處點一下（小拖曳 < 4 px） | 清空選取 |
| 8 | 多選 + 按 P | 跳出「將 N 張照片標記為「Pick」？」對話框，含「之後不再詢問」 checkbox |
| 9 | 多選 + 按 U | 對話框「清除 N 張照片的標記？」 |
| 10 | 確認後 | 所有 tile 同步顯示新狀態，**color 不被清掉** |
| 11 | 勾「之後不再詢問」並確認 | 之後同 status 的批次操作不再彈窗 |
| 12 | 按空白鍵（剛好選 1 張時） | 進 Loupe |

### 3.7 篩選

| # | 操作 | 期望 |
|---|------|------|
| 1 | 側邊 FilterPanel 勾「pick」 | Grid 只剩 picks |
| 2 | 同時勾「red」 | Grid 剩 pick + red |
| 3 | 勾「untagged」 | Grid 剩沒被標記的 |
| 4 | 點「清除」 | 所有 checkbox 取消、Grid 顯示全部 |
| 5 | 篩選有結果時匯入新檔 | 新進的 tile **不會**自動加進當前篩選結果（除非符合條件） |

### 3.8 Welcome / 最近專案

| # | 操作 | 期望 |
|---|------|------|
| 1 | 第一次開啟 | 沒有「最近專案」區塊 |
| 2 | 開啟資料夾 A 後重啟 | 「最近專案」顯示 A，名字 + 完整路徑 |
| 3 | 再開資料夾 B 後重啟 | 清單按時間排序，B 在最上 |
| 4 | 同一資料夾連開兩次 | 清單只有一筆，且置頂 |
| 5 | 開超過 10 個不同資料夾 | 清單上限 10 筆，最舊的被擠掉 |
| 6 | 把清單中某資料夾改名（Explorer） | 該條目顯示紅色「找不到」badge、滑鼠指標非 pointer、點擊**無反應** |
| 7 | 點該條目右側「移除」 | 條目消失（resilient：當 settings.db 持久化） |
| 8 | 點存在的條目 | 直接載入該專案 |

### 3.9 設定 DB migration（升級舊版本場景）

| # | 步驟 | 期望 |
|---|------|------|
| 1 | 手動建立 `%APPDATA%\SwiftCull\settings.json`，內容：`{"last_folder": "D:/some/path"}` | — |
| 2 | 確保 `%LOCALAPPDATA%\SwiftCull\settings.db` 不存在 | — |
| 3 | 啟動 app | 自動建 settings.db、把 last_folder 帶進去；若 path 還在會直接載入 |
| 4 | 修改設定（例如再開另一個資料夾） | settings.db 更新；下次啟動時**不會**再被舊 settings.json 蓋掉 |

### 3.10 匯入取消

| # | 操作 | 期望 |
|---|------|------|
| 1 | 開啟一個含 1000+ 張照片的新資料夾 | 進度條跑「匯入中 0 / 1000」，旁邊出現「取消」鈕 |
| 2 | 進度約 30% 時點「取消」 | 跳出 QMessageBox：「確定取消匯入？已匯入 X / Y 張，已匯入的檔案會保留。」+「取消匯入 / 繼續匯入」（預設 = 繼續匯入，防誤觸） |
| 3 | 點「繼續匯入」 | 對話框關，繼續匯入 |
| 4 | 再點「取消」→「取消匯入」 | label 改「取消中… X / Y」，cancel 按鈕變 disabled「取消中…」、進度凍結 |
| 5 | 等 worker 結束 | toast「已取消匯入。完成 X / Y 張，未處理的會在下次掃描時偵測。」（6 秒自動消失） |
| 6 | 重啟 app（同資料夾） | 重開 scan 偵測到剩下未匯入的，toast 顯示「N 個新增」 |

### 3.11 錯誤處理

| # | 步驟 | 期望 |
|---|------|------|
| 1 | 資料夾內放一個壞掉的 JPEG（用 hex editor 截斷） | 匯入過程不中斷；其他照片正常匯入；狀態列右側出現紅色錯誤計數 |
| 2 | 點該錯誤計數 | 顯示錯誤檔清單（modal 或 panel） |
| 3 | 重新掃描 | 壞檔仍會被列出但不再阻塞流程 |

### 3.12 視窗尺寸 / 多螢幕

| # | 操作 | 期望 |
|---|------|------|
| 1 | 縮小視窗到 800×600 | Grid 縮欄、FilterPanel 不被擠掉 |
| 2 | 全螢幕（F11 或最大化） | Loupe 預設全螢幕、Grid 用滿空間 |
| 3 | 在副螢幕開啟 Loupe | 顯示在當前主視窗所在螢幕 |
| 4 | HiDPI（150% 縮放） | 字體不糊、icon 不模糊（PySide6 需 `Qt.AA_EnableHighDpiScaling`，main.py 已處理） |

---

## 4. 邊界情境 / 壓力測試

### 4.1 空 / 怪資料夾

| 情境 | 期望 |
|------|------|
| 空資料夾 | Grid 顯示「0 photos」、無 toast |
| 只有 .txt / .pdf | scan_folder 跳過、視為空、Grid 空 |
| 只有 0 byte 的 JPEG | 匯入時各別失敗，列入錯誤清單 |
| 含 5 層深的子資料夾 | 全部遞迴掃到 |
| 路徑含中文 / 空格 / emoji | 全程正常（DB 用相對路徑） |
| 路徑超過 260 字元（Windows MAX_PATH） | 至少能 graceful skip + 列入錯誤 |

### 4.2 資源狀態

| 情境 | 期望 |
|------|------|
| 開到一半外接硬碟拔掉 | Loupe 顯示「✕ 原檔不存在」、後續操作不 crash |
| 同一專案被兩個 app 實例同時開 | SQLite WAL mode 容許讀；寫衝突的 graceful 處理（目前 acceptable：second instance 可能看到 stale 資料，重啟即可） |
| 磁碟空間不足（cache 寫入失敗） | 縮圖工作 fail 但其他操作不 crash |
| 撤銷照片資料夾的讀權限 | scan_folder 跳過、不 crash |

### 4.3 大量資料

| 情境 | 期望 |
|------|------|
| 5000 張 | 匯入 < 75 s（線性外推自基線）；Grid 滾動順暢；filter 切換 < 100 ms |
| 10000 張 | 仍可運作；若 GUI 反應遲鈍則回頭看是否需要 Grid virtualization |
| 單張 100 MB+ RAW | Loupe 能載入嵌入預覽（非全 RAW 解碼） |

### 4.4 並發

| 情境 | 期望 |
|------|------|
| 匯入中切換篩選 | Grid 即時更新 / 不卡 |
| 匯入中進 Loupe | 可進，已匯入的可瀏覽 |
| 匯入中關 app | 觸發 cancel + 等 worker 結束（最多 3 s）後關 |
| 掃描中再點「重新掃描」 | 已開始的掃描跑完，第二次不重複觸發（按鈕應 disabled） |

---

## 5. 釋出檢查表

每個 minor release 至少：

- [ ] `pytest -q` 全綠
- [ ] `python tools/benchmark_phase1.py --count 1000` PASS 兩個 spec 目標
- [ ] 用真 RAW 1000+ 張資料夾跑一次第 3.2 + 3.3 + 3.10 節
- [ ] 跑完整第 3 節手動 checklist
- [ ] 用全新 user 環境（清空 `%LOCALAPPDATA%`、`%APPDATA%`）跑一次第 3.2 + 3.8 + 3.9 節
- [ ] 視覺檢查：Loupe 上下 chrome、Grid tile、Toast 在不同 DPI 下顯示正確
- [ ] 檢查 git log 沒有未文檔化的破壞性變更

---

## 6. 已知限制 / 不測試的東西

- **跨平台行為**：Phase 1 是 Windows only。macOS/Linux 不測。
- **HEIC**：Phase 1 不支援，含 HEIC 的資料夾應 graceful skip。
- **Undo / Redo**：Phase 1 沒有，操作即生效。
- **網路 / 雲端同步**：完全無，所有處理本地。
- **AI 偵測 / 人臉識別**：Phase 2 範疇。
- **Grid virtualization**：目前所有 tile 都實體化；> 5000 張可能拖慢初次 layout，但匯入跟篩選不受影響。

---

## 7. 補充：Bug 回報範本

回報前請附：

1. SwiftCull 版本（git short hash：`git rev-parse --short HEAD`）
2. 重現步驟（對應到本手冊哪一節最佳）
3. 預期 vs 實際
4. 環境：OS 版本、Python 版本、螢幕解析度與縮放
5. 相關檔案：`%LOCALAPPDATA%\SwiftCull\projects\<proj>\project.db`、stack trace（若 crash）
6. 必要時附 screenshot / 錄影
