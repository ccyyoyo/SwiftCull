# Phase 2 模糊偵測 — 實作計劃與進度報告

**日期：** 2026-04-29  
**功能：** Blur Detection（模糊偵測）  
**測試狀態：** 43/43 通過  

---

## 目標摘要

為 SwiftCull 加入模糊偵測能力：
- 匯入照片後自動計算模糊分數（Laplacian variance）
- 支援手動重新分析
- 可設定閾值模式（固定值 或 相對底部%）
- 篩選面板支援「模糊 / 清晰 / 未分析」篩選
- 全螢幕 Loupe 顯示 blur 分數與顏色提示

---

## 架構決策

| 決策 | 說明 |
|------|------|
| 演算法 | OpenCV Laplacian variance（分數越高越清晰）|
| 執行方式 | 獨立 BlurWorker + BlurController（QThread，鏡像 ImportWorker 模式）|
| 觸發時機 | 匯入完成後自動觸發；使用者也可手動重新分析 |
| 閾值模式 | Fixed（絕對值）或 Relative（底部 X%）；設定存 settings.json |
| 資料存放 | `photos.blur_score REAL`（SQLite，安全 migration）|

---

## 任務清單與進度

| # | 任務 | 檔案 | 狀態 | Commit |
|---|------|------|------|--------|
| 1 | Photo model + DB migration | `app/core/models.py`, `app/db/connection.py`, `app/db/photo_repository.py` | ✅ 完成 | `1a07ee8` |
| 2 | BlurService | `app/core/blur_service.py` | ✅ 完成 | `3bab1a7` |
| 3 | BlurWorker / BlurController | `app/core/blur_worker.py` | ✅ 完成 | `2b3ae39` |
| 4 | FilterService blur 篩選 | `app/core/filter_service.py` | ✅ 完成 | `2596c9b` |
| 5 | Theme 顏色常數 | `app/utils/theme.py` | ✅ 完成 | `157a586` |
| 6 | BlurSettingsDialog | `app/ui/blur_settings_dialog.py` | ✅ 完成 | `84457a7` |
| 7 | FilterPanel BLUR 區塊 | `app/ui/filter_panel.py` | ✅ 完成 | `2388a4e` |
| 8 | LoupeView blur 分數顯示 | `app/ui/loupe_view.py` | ✅ 完成 | `f564ffe` |
| 9 | GridView 接線 | `app/ui/grid_view.py` | ⏳ 待做 | — |
| 10 | MainWindow 接線 | `app/ui/main_window.py` | ⏳ 待做 | — |
| 11 | 完整測試 + smoke test | — | ⏳ 待做 | — |

**進度：8 / 11 任務完成（72%）**

---

## 已完成任務詳情

### Task 1：Photo model + DB migration
- `Photo` dataclass 新增 `blur_score: Optional[float] = None`
- `init_db` 加入安全 migration：`ALTER TABLE photos ADD COLUMN blur_score REAL`（已存在則忽略）
- `PhotoRepository` 新增 `update_blur_score(photo_id, score)` 方法
- `_row_to_photo` 讀取新欄位
- 新增測試：`test_update_blur_score`、`test_blur_score_defaults_none`

### Task 2：BlurService
- `compute_score(root_path, relative_path) -> float`：使用 OpenCV Laplacian variance
- `is_blurry_fixed(score, threshold) -> bool`：固定閾值判斷
- `relative_threshold(scores, bottom_percent) -> float`：計算相對百分位閾值
- 修正：索引 off-by-one bug；加 epsilon 讓邊界照片正確分類
- 5 個測試全通過

### Task 3：BlurWorker / BlurController
- 完全鏡像 `ImportWorker` / `ImportController` 模式
- `BlurWorker`：訊號 `photo_blur_updated(int, float)`, `progress(int, int)`, `finished()`
- `BlurController`：擁有 QThread + BlurWorker，提供 `start()` / `cancel()`

### Task 4：FilterService blur 篩選
- 新增參數：`blur: Optional[List[str]] = None`、`blur_threshold: float = 100.0`
- 支援值：`"blurry"`（分數 < 閾值）、`"sharp"`（分數 >= 閾值）、`"unanalyzed"`（無分數）
- 注意：多值 blur list 使用 AND-exclusion 語意（UI 設計為單選，不影響使用）
- 2 個新測試全通過

### Task 5：Theme 顏色常數
```python
BLUR_BLURRY  = "#FF6B6B"  # 紅色警示
BLUR_SHARP   = "#3ddc84"  # 綠色（清晰）
BLUR_UNKNOWN = "#555555"  # 灰色（未分析）
```

### Task 6：BlurSettingsDialog
- 模式選擇：Fixed（固定閾值）/ Relative（相對底部%）
- 設定儲存至 `%APPDATA%\SwiftCull\settings.json`
- 鍵值：`blur_mode`、`blur_fixed_threshold`、`blur_relative_percent`
- 訊號：`settings_changed(mode: str, threshold: float)`

### Task 7：FilterPanel BLUR 區塊
- `filter_changed` 訊號從 `Signal(list, list)` 改為 `Signal(list, list, list)`
- 新增 BLUR 區塊：齒輪按鈕（⚙）+ 三個 checkbox（模糊 / 清晰 / 未分析）
- 齒輪按鈕開啟 `BlurSettingsDialog`
- `_emit_filter`、`_clear_all` 皆已更新

### Task 8：LoupeView blur 分數顯示
- 右上角絕對定位 `_blur_label`（200×30 px）
- `resizeEvent` 動態重新定位（`width - 210, 16`）
- `_update_blur_label()`：讀取 `photo.blur_score`，根據閾值顯示顏色
  - 紅色（BLUR_BLURRY）：分數 < 閾值
  - 綠色（BLUR_SHARP）：分數 >= 閾值
  - 灰色（BLUR_UNKNOWN）：未分析
- 讀取 settings.json 取得使用者設定的閾值

---

## 待完成任務詳情

### Task 9：GridView 接線
**檔案：** `app/ui/grid_view.py`

需要：
1. `__init__` 加 `self._current_blur = None`
2. `_on_filter_changed(statuses, colors, blur)` — 接收新第三參數
3. `_refresh(statuses, colors, blur)` — 傳遞 blur 給 FilterService
4. `_on_loupe` — 傳遞 `blur=self._current_blur` 給 FilterService
5. 新增 `start_blur_analysis(db_path)` 方法 — 建立 BlurController，連接 `photo_blur_updated`
6. 新增 `_on_photo_blur_updated(photo_id, score)` — 呼叫 `self._grid.update_item_tag(photo_id)`

### Task 10：MainWindow 接線
**檔案：** `app/ui/main_window.py`

需要：
- `_on_import_finished` 加一行：`self._grid_view.start_blur_analysis(self._db_path)`

### Task 11：完整測試 + smoke test
- `python -m pytest -v` 全部通過
- 手動驗證：
  1. 開啟資料夾 → 匯入完成 → 自動開始 blur 分析
  2. 篩選面板顯示 BLUR 區塊（⚙ + 3 個 checkbox）
  3. ⚙ 開啟設定對話框，可切換模式儲存
  4. 勾選「模糊」篩選正確
  5. Loupe 顯示 `Blur: 123.4`（正確顏色）
  6. 重新掃描重新觸發 blur 分析

---

## 測試現狀

```
43 passed in 1.34s（2026-04-29）

新增測試：
  tests/db/test_photo_repository.py::test_update_blur_score        ✅
  tests/db/test_photo_repository.py::test_blur_score_defaults_none ✅
  tests/core/test_blur_service.py::test_compute_score_*            ✅ (5 tests)
  tests/core/test_filter_service.py::test_filter_blur_blurry       ✅
  tests/core/test_filter_service.py::test_filter_blur_unanalyzed   ✅
```

---

## 已知限制與未來改進

| 項目 | 說明 |
|------|------|
| BlurWorker 無 error signal | 失敗時靜默忽略，未來可加 `error = Signal(str, str)` |
| 重新分析重算所有照片 | 目前每次 import 後全部重算；未來可只分析未計算的 |
| Relative mode 未整合 UI 篩選 | 設定可存 relative 模式，但 FilterService 目前只用 `blur_threshold`（fixed 值）傳入 |
| 不支援 RAW 格式的 blur 分析 | OpenCV 無法直接讀 RAW，分數回傳 0.0 |

---

## 審查補充：目前發現的問題

### 1. Settings 寫入邏輯不一致，可能覆蓋 blur 設定
- `BlurSettingsDialog` 會 merge 現有 `settings.json` 再寫回。
- `MainWindow` 的 `_save_settings({"last_folder": folder_path})` 目前是直接覆寫整份 JSON。
- 結果：`blur_mode`、`blur_fixed_threshold`、`blur_relative_percent` 可能在重新開啟資料夾或下次啟動時被洗掉。

### 2. Relative mode 目前屬於「可儲存但未真正生效」
- UI 可切換 `fixed / relative` 並寫入設定。
- 但目前 Loupe 顏色判定只讀 `blur_fixed_threshold`，FilterService 也只吃外部傳入的 `blur_threshold`。
- 結果：使用者切到 relative mode 後，畫面與篩選結果仍不會依底部百分比運作。

### 3. RAW 檔 blur 分數語意有誤，容易被錯判為 blurry
- 匯入流程支援 RAW 副檔名。
- `BlurService.compute_score()` 在 OpenCV 讀不到圖時回傳 `0.0`，`BlurWorker` 會把 `0.0` 寫入資料庫。
- 結果：RAW 或讀取失敗的檔案會被當成「已分析且非常模糊」，而不是「未分析」。

### 4. BLUR 篩選 UI 與 FilterService 語意不一致
- UI 目前是 3 個可複選 checkbox：`模糊 / 清晰 / 未分析`。
- `FilterService` 的實作是交集式排除邏輯，不是 OR 邏輯。
- 實測：同時勾選 `blurry + sharp` 或 `blurry + unanalyzed` 會得到空結果。
- 若產品設計預期為單選，UI 應改成單選控制；若預期可複選，service 邏輯需要改為 OR。

### 5. 「手動重新分析」目前尚未看到實際入口
- 進度報告的目標摘要有提到支援手動重新分析。
- 但目前完成項目中只看到 `BlurSettingsDialog` 與待做的 `GridView/MainWindow` 接線，尚未看到明確 UI 入口或 action。
- 若接線後只在 import 完成時自動觸發，既有 project 可能沒有補算路徑。

### 6. 測試全綠，但尚未覆蓋上述 UI / persistence 問題
- `python -m pytest` 目前為 `43 passed`。
- 但現有新增測試主要覆蓋 repository、service 與 filter 的基本情境，尚未涵蓋：
  - settings 持久化
  - relative mode 真正生效
  - RAW 失敗路徑的分類語意
  - BLUR UI 多選行為

**審查者：GitHub Copilot - GPT5.4**  
**審查日期：** 2026-04-29
