# Blur Detection Completion — Design Spec

**日期：** 2026-04-30
**範圍：** Tasks 9–11 接線 + 6 個 bug 修正 + Relative mode 完整實作

---

## 背景

Tasks 1–8 已完成（43 tests passing）。剩餘工作：

- Task 9：GridView 接線（blur filter、BlurController、手動重新分析按鈕）
- Task 10：MainWindow 接線（import 完成後自動觸發 blur 分析）
- Task 11：全套測試 + smoke test
- Bug 修正 6 項（見下方）

---

## Bug 清單與修法

### Bug 1：Settings 覆蓋問題

**現況：** `BlurSettingsDialog` 讀寫 `%APPDATA%\SwiftCull\settings.json`（舊格式）。`MainWindow` 已改用 `SettingsDB`（SQLite，`%LOCALAPPDATA%\SwiftCull\settings.db`）。兩者分離，blur 設定在重新開啟時可能遺失。

**修法：** `BlurSettingsDialog` 改用 `SettingsDB`。移除 `_load_settings()` / `_save_settings()` 函式，改注入 `SettingsDB` 實例（從 `MainWindow` 傳入）。Keys 不變：`blur_mode`、`blur_fixed_threshold`、`blur_relative_percent`。

---

### Bug 2：Relative mode 未生效

**現況：** UI 可切換 fixed/relative 並存檔，但 `FilterService` 只接受固定 `blur_threshold`，`LoupeView` 也只讀 `blur_fixed_threshold`。

**修法（完整實作）：**

`FilterService.filter()` 新增參數：
```
blur_mode: str = "fixed"           # "fixed" | "relative"
blur_fixed_threshold: float = 100.0
blur_relative_percent: float = 20.0
```

當 `blur_mode == "relative"` 時，`FilterService` 自行從所有已分析照片計算百分位閾值（呼叫 `BlurService.relative_threshold()`），再套用 blurry/sharp 判斷。

`GridView` 在每次 `_emit_filter` 前從 `SettingsDB` 讀取 mode/percent，傳入 `FilterService.filter()`。

`LoupeView._update_blur_label()` 同樣從 `SettingsDB` 讀取 mode，並在 relative mode 時先取所有分數計算動態閾值。

---

### Bug 3：RAW 檔誤判為「非常模糊」

**現況：** `BlurService.compute_score()` 在 OpenCV 讀不到圖（RAW 格式）時回傳 `0.0`。`BlurWorker` 把 `0.0` 寫入 DB，被篩選為「模糊」。

**修法：** `BlurService.compute_score()` 在 `img is None` 時回傳 `None`（非 `0.0`）。`BlurWorker` 收到 `None` 時跳過 `update_blur_score`，讓該照片保持 `blur_score IS NULL`（未分析）。

```python
def compute_score(self, root_path: str, relative_path: str) -> Optional[float]:
    ...
    img = cv2.imread(abs_path)
    if img is None:
        return None   # ← 改這行
```

相應修改 `BlurWorker._run_inner()`：
```python
score = svc.compute_score(self._folder, photo.relative_path)
if score is not None:
    repo.update_blur_score(photo_id, score)
    self.photo_blur_updated.emit(photo_id, score)
```

---

### Bug 4：Blur 篩選 OR 邏輯

**現況：** `FilterService` 的 blur 判斷使用 AND-exclusion，導致同時勾選「模糊 + 清晰」得到空結果。

**修法：** 改為 OR 邏輯：photo 符合 `blur` list 中任一條件即通過。

```python
if blur:
    score = photo.blur_score
    passes = False
    if "unanalyzed" in blur and score is None:
        passes = True
    if "blurry" in blur and score is not None and score < effective_threshold:
        passes = True
    if "sharp" in blur and score is not None and score >= effective_threshold:
        passes = True
    if not passes:
        continue
```

---

### Bug 5：手動重新分析無 UI 入口

**現況：** 只有 import 完成後自動觸發全部重算，既有專案重開後無法補算。

**修法：**

1. `PhotoRepository` 新增 `get_unanalyzed_ids() -> list[int]`：
   ```sql
   SELECT id FROM photos WHERE blur_score IS NULL
   ```

2. `GridView` 新增 `reanalyze_missing_blur(db_path)` 方法：只取 `get_unanalyzed_ids()`，傳給 `BlurController`。

3. GridView toolbar 新增按鈕「⊙ 分析模糊」：
   - 平時顯示，點擊觸發 `reanalyze_missing_blur`
   - 分析進行中時 disable（與 import 共用 progress bar 顯示）

4. `start_blur_analysis(db_path)`（import 後觸發）維持全部重算行為，確保更新過的照片也重算。

---

### Bug 6：補充測試

新增測試涵蓋：
- `BlurService.compute_score()` 對無法讀取的檔案回傳 `None`
- `FilterService.filter()` blur OR 邏輯（blurry+sharp 同時勾選不得空）
- `FilterService.filter()` relative mode 正確計算百分位閾值
- `PhotoRepository.get_unanalyzed_ids()` 回傳正確 id 清單
- `BlurSettingsDialog` 讀寫 `SettingsDB`（unit test mock）

---

## 架構變更

### 新增 / 修改檔案

| 動作 | 檔案 | 說明 |
|------|------|------|
| Modify | `app/core/blur_service.py` | `compute_score` 回傳 `Optional[float]`，失敗回 `None` |
| Modify | `app/core/blur_worker.py` | 收到 `None` score 時跳過寫入 |
| Modify | `app/core/filter_service.py` | OR 邏輯；新增 `blur_mode` / `blur_relative_percent` 參數；呼叫 `BlurService.relative_threshold()` |
| Modify | `app/db/photo_repository.py` | 新增 `get_unanalyzed_ids()` |
| Modify | `app/ui/blur_settings_dialog.py` | 移除 JSON 讀寫，改注入 `SettingsDB` |
| Modify | `app/ui/grid_view.py` | 接線 blur filter、BlurController、toolbar 按鈕 |
| Modify | `app/ui/loupe_view.py` | `_update_blur_label` 支援 relative mode |
| Modify | `app/ui/main_window.py` | import 完成後觸發 blur；傳 `SettingsDB` 給 `BlurSettingsDialog` |

### 不修改

- `app/core/blur_service.py` 的 `relative_threshold()` — 邏輯已正確，只是新增呼叫方
- `app/ui/filter_panel.py` — blur section 已完成，只更新 signal 處理
- `app/db/connection.py` / `app/db/tag_repository.py` — 不動

---

## FilterService 介面（修改後）

```python
def filter(
    self,
    statuses: Optional[List[str]] = None,
    colors: Optional[List[str]] = None,
    blur: Optional[List[str]] = None,
    blur_mode: str = "fixed",
    blur_fixed_threshold: float = 100.0,
    blur_relative_percent: float = 20.0,
) -> List[Photo]:
```

當 `blur_mode == "relative"` 且有 blur filter 時：
1. 取出所有 `Photo` 的非 None `blur_score` 清單
2. 呼叫 `BlurService().relative_threshold(scores, blur_relative_percent)`
3. 以計算結果作為 `effective_threshold`

---

## GridView blur 設定讀取時機

每次 `_emit_filter` 呼叫時從 `SettingsDB` 讀取，而非快取，確保設定變更立即生效：

```python
def _on_filter_changed(self, statuses, colors, blur):
    self._current_blur = blur or None
    mode = self._settings.get("blur_mode", "fixed")
    threshold = float(self._settings.get("blur_fixed_threshold", 100.0))
    percent = float(self._settings.get("blur_relative_percent", 20.0))
    self._refresh(statuses or None, colors or None, blur or None,
                  blur_mode=mode, blur_fixed_threshold=threshold,
                  blur_relative_percent=percent)
```

`GridView.__init__` 新增 `settings: SettingsDB` 參數，由 `MainWindow` 傳入。

---

## BlurSettingsDialog 介面（修改後）

```python
class BlurSettingsDialog(QDialog):
    settings_changed = Signal(str, float)  # mode, effective_threshold

    def __init__(self, settings: SettingsDB, parent=None):
        ...
```

不再讀寫 `settings.json`，改用 `self._settings.get(...)` / `self._settings.set(...)`。

---

## Toolbar 按鈕規格

| 項目 | 規格 |
|------|------|
| 文字 | `⊙  分析模糊` |
| 位置 | 現有 `↻ 重新掃描` 按鈕右側 |
| 狀態 | 分析進行中或 import 進行中時 disable |
| 點擊行為 | 呼叫 `reanalyze_missing_blur(self._db_path)` |
| 完成後 | 自動 enable（`BlurController.finished` signal） |

---

## 測試策略

| 類型 | 目標 |
|------|------|
| Unit | `BlurService.compute_score` 回傳 `None` on unreadable file |
| Unit | `FilterService` blur OR 邏輯（多選不空） |
| Unit | `FilterService` relative mode 百分位計算 |
| Unit | `PhotoRepository.get_unanalyzed_ids` |
| Unit | `BlurSettingsDialog` 讀寫 SettingsDB（mock） |
| Integration | 全套 pytest（目標 55+ tests passing） |
| Manual | Smoke test 6 項（見 Task 11） |

---

## 不在本次範圍

- Undo/Redo（Phase 3）
- RAW 格式 blur 分析（需要 rawpy 解碼後再丟 OpenCV）
- BlurWorker error signal（已知 limitation，保留靜默忽略）
- 排序切換 UI
