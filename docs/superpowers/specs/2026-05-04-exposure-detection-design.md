# Exposure Detection Design

Date: 2026-05-04
Status: Decisions accepted, implementation-ready draft

## Problem

SwiftCull already has the core exposure analysis code, but users cannot use it yet. The app can compute luminance statistics in `ExposureService`, store exposure fields in SQLite, and run an `ExposureWorker`, but there is no product flow for triggering analysis, filtering photos, showing results, or configuring thresholds.

This spec defines the missing Phase 2 exposure detection design.

## Goals

- Detect common exposure problems: overexposed, underexposed, and likely black frames.
- Store exposure analysis results per photo so filters and overlays are fast.
- Let users filter by exposure state in the left filter panel.
- Show exposure warnings in Grid and Loupe without making the UI noisy.
- Run exposure analysis in the same background style as blur analysis.
- Keep the first implementation deterministic and OpenCV-based. No AI model is needed.
- Ship manual exposure analysis first. Automatic analysis after import comes later, after the manual path is stable.

## Non-Goals

- RAW histogram analysis from sensor data. The first version uses the same decoded preview/image path as the existing services.
- Advanced highlight recovery or camera profile handling.
- Editing photos or changing exposure metadata.
- Auto-rejecting photos based on exposure.
- Exporting exposure results. Export belongs to a separate Phase 2 export design.

## Existing Implementation

Already present:

| Area | Current state |
|------|---------------|
| Model | `Photo.exposure_mean`, `Photo.exposure_overexposed`, `Photo.exposure_underexposed` |
| DB | `photos.exposure_mean`, `photos.exposure_overexposed`, `photos.exposure_underexposed` migrations |
| Repository | `PhotoRepository.update_exposure_scores()` |
| Service | `ExposureService.compute_scores()` returns mean brightness and clipped highlight/shadow fractions |
| Worker | `ExposureWorker` and `ExposureController` exist |
| Tests | `tests/core/test_exposure_service.py` covers core scoring and threshold helpers |

Missing:

- No `GridView.start_exposure_analysis()`.
- No manual trigger.
- No stable automatic import-finished trigger.
- No exposure filter in `FilterService`.
- No EXPOSURE section in `FilterPanel`.
- No Loupe or Grid exposure overlay.
- No settings dialog or persisted thresholds.
- No repository helper for unanalyzed exposure rows.
- No integration tests for filtering or UI-facing workflow.

## Detection Model

The first version should classify photos from three stored values:

| Field | Meaning |
|-------|---------|
| `exposure_mean` | Mean grayscale brightness, range 0 to 255 |
| `exposure_overexposed` | Fraction of pixels at or above highlight clipping threshold |
| `exposure_underexposed` | Fraction of pixels at or below shadow clipping threshold |

The current `ExposureService` uses:

- Highlight threshold: `gray >= 250`
- Shadow threshold: `gray <= 5`
- Default clipped-pixel threshold: `0.01` or 1 percent

Recommended classification:

| State | Rule |
|-------|------|
| `unanalyzed` | Any exposure field is `NULL` |
| `overexposed` | `exposure_overexposed > exposure_clip_threshold` |
| `underexposed` | `exposure_underexposed > exposure_clip_threshold` |
| `black_frame` | `exposure_mean <= exposure_black_mean_threshold` and `exposure_underexposed > exposure_black_shadow_threshold` |
| `normal` | Analyzed and none of the above states match |

Recommended defaults:

| Setting | Default | Rationale |
|---------|---------|-----------|
| `exposure_clip_threshold` | `0.01` | More than 1 percent clipped pixels is worth surfacing |
| `exposure_black_mean_threshold` | `8.0` | Near-black mean brightness |
| `exposure_black_shadow_threshold` | `0.90` | At least 90 percent crushed shadows |

Classification should allow multiple problem states internally. A black frame is an underexposed subtype:

- Selecting only `underexposed` includes black frames.
- Selecting only `black_frame` includes only black frames.
- Selecting both `underexposed` and `black_frame` is valid and still uses OR semantics.
- Display priority is `black_frame`, then `overexposed`, then `underexposed`, then `normal`, then `unanalyzed`.

Mixed overexposed and underexposed photos are allowed. They match both filters. For the single compact UI display, `overexposed` has priority over `underexposed` unless `black_frame` also matches.

Threshold boundary semantics are intentionally strict, matching the current `ExposureService.is_*` helpers:

- `overexposed` requires `exposure_overexposed > exposure_clip_threshold`.
- `underexposed` requires `exposure_underexposed > exposure_clip_threshold`.
- `black_frame` requires `exposure_mean <= exposure_black_mean_threshold` and `exposure_underexposed > exposure_black_shadow_threshold`.

Centralize the classification in a pure helper. Do not duplicate these rules in `FilterService`, Grid, and Loupe.

Recommended helper API:

```python
def exposure_states(
    photo: Photo,
    clip_threshold: float = 0.01,
    black_mean_threshold: float = 8.0,
    black_shadow_threshold: float = 0.90,
) -> set[str]:
    """Return all matching exposure states for a photo."""

def exposure_display_state(
    photo: Photo,
    clip_threshold: float = 0.01,
    black_mean_threshold: float = 8.0,
    black_shadow_threshold: float = 0.90,
) -> str:
    """Return the single highest-priority exposure state for UI display."""
```

These helpers can live in `ExposureService` as static methods or in a small core module imported by both services and UI. The important constraint is that all consumers call the same classifier.

## Data Design

Keep the existing DB fields:

```sql
exposure_mean REAL
exposure_overexposed REAL
exposure_underexposed REAL
```

Add repository helpers:

```python
def get_exposure_unanalyzed_ids(self) -> list[int]:
    """Return IDs where any exposure analysis field is NULL."""

def clear_exposure_scores(self, photo_id: int) -> None:
    """Clear stored exposure analysis after a source file changes."""
```

Do not add a stored `exposure_state` column in the first version. State depends on thresholds, so deriving it at filter/display time avoids stale classifications.

`clear_exposure_scores()` is required, not optional. Modified-file import must clear exposure fields before or during metadata refresh, otherwise "analyze missing only" will skip changed images with stale scores. If this work touches shared quality-analysis behavior, also consider clearing `blur_score` for modified images so blur and exposure behave consistently.

## Settings

Use `SettingsDB`, matching blur settings.

Recommended keys:

| Key | Type | Default |
|-----|------|---------|
| `exposure_clip_threshold` | float | `0.01` |
| `exposure_black_mean_threshold` | float | `8.0` |
| `exposure_black_shadow_threshold` | float | `0.90` |
| `exposure_auto_after_import` | bool | `false` |

Manual analysis is the MVP default. `exposure_auto_after_import` exists for the later automatic phase and should remain `false` until manual analysis is stable.

Do not add relative mode in the first implementation. Relative thresholds are useful for ranking, but exposure clipping is easier to reason about as an absolute quality warning. Relative mode can be added later if real photo sets show too many false positives.

## Filter Design

Extend `FilterService.filter()`:

```python
def filter(
    self,
    statuses: Optional[List[str]] = None,
    colors: Optional[List[str]] = None,
    blur: Optional[List[str]] = None,
    exposure: Optional[List[str]] = None,
    blur_fixed_threshold: float = 100.0,
    exposure_clip_threshold: float = 0.01,
    exposure_black_mean_threshold: float = 8.0,
    exposure_black_shadow_threshold: float = 0.90,
) -> List[Photo]:
```

Exposure filter values:

- `overexposed`
- `underexposed`
- `black_frame`
- `normal`
- `unanalyzed`

Filtering semantics:

- STATUS, COLOR, BLUR, and EXPOSURE dimensions combine with AND.
- Values inside EXPOSURE combine with OR.
- `underexposed` includes `black_frame` because black frame is an underexposed subtype.
- `black_frame` alone matches only black frames.
- `normal` should match only analyzed photos with no exposure issue.
- `unanalyzed` should match only rows where any exposure field is `NULL`.

`FilterService` should call the shared exposure classifier rather than reimplementing the rules.

## UI Design

### Filter Panel

Add an EXPOSURE section below BLUR:

```text
EXPOSURE                 gear
[ ] Overexposed
[ ] Underexposed
[ ] Black frame
[ ] Normal
[ ] Unanalyzed
```

The full design includes a gear that opens an `ExposureSettingsDialog`. MVP may omit the gear or show it disabled until the settings dialog is implemented in the Next stage.

`FilterPanel.filter_changed` currently emits `(statuses, colors, blur)`. Change it to emit:

```python
Signal(list, list, list, list)  # statuses, colors, blur, exposure
```

Then update `GridView` and `LoupeView` call sites.

The filter panel should become scrollable before or during this change. It is currently fixed-width and can overflow on shorter windows once EXPOSURE is added. Clear Filters must clear exposure checkboxes along with status, color, and blur.

### Grid

Expose exposure status through thumbnail tile badges, not a large overlay.

Recommended badge priority:

1. Black frame
2. Overexposed
3. Underexposed
4. Normal or unanalyzed: no badge by default

Suggested badge text:

- `EXP+` for overexposed
- `EXP-` for underexposed
- `BLACK` for black frame

If this feels too technical in UI, use icons later. The first version can keep text badges because it is faster to implement and easier to test.

Badge implementation belongs in `ThumbnailItem` / `ThumbnailGrid`, not only `GridView`:

- `ThumbnailItem` owns badge painting and should get explicit exposure state storage.
- `ThumbnailGrid` should expose a method to update one visible item's exposure state.
- `GridView.photo_exposure_updated` handling should call that explicit method, not reuse `update_item_tag()` as a generic repaint hook.

Exact placement must avoid existing tile overlays. Recommended placement is bottom-right above the filename band. Existing missing-file overlays remain higher priority and may cover exposure badges when a file is missing.

### Loupe

Replace the single top-right blur label with a compact analysis stack:

```text
Blur: 123.4
Exposure: Over 2.4%
```

Display rules:

- Unanalyzed: `Exposure: --`
- Overexposed: show clipped highlight percentage
- Underexposed: show clipped shadow percentage
- Black frame: show `Exposure: Black`
- Normal: show `Exposure: OK`

Use color coding:

| State | Color |
|-------|-------|
| Overexposed | warm amber |
| Underexposed | cool blue |
| Black frame | red |
| Normal | muted green |
| Unanalyzed | muted gray |

Add theme constants instead of hardcoding colors in widgets.

Loupe navigation must preserve the Grid's active blur and exposure context. Current Loupe filtering only carries status/color filters; that would drop blur and exposure filters when the top Loupe filter bar changes.

Implementation requirement:

- Pass current blur and exposure filters from `GridView` into `LoupeView`.
- When Loupe recomputes its photo list after status/color changes, call `FilterService.filter()` with the preserved blur and exposure filters.
- Loupe does not need blur/exposure controls in MVP, but it must not lose the parent Grid context.

## Analysis Flow

### MVP: Manual Trigger

Add a toolbar button:

```text
Analyze Exposure
```

Default behavior:

- Analyze only photos where any exposure field is `NULL`.
- Disable the exposure button while exposure analysis is running.
- Keep the existing import progress bar pattern if practical, otherwise a small label is acceptable.
- Manual analysis ignores `exposure_auto_after_import`; the setting gates only automatic import-triggered analysis in the later phase.

Optional later behavior:

- Shift-click or settings option for full reanalysis.

### Later: After Import

Automatic exposure analysis after import is intentionally deferred until manual analysis is stable.

When enabled later through `exposure_auto_after_import`, `MainWindow._on_import_finished()` should ask `GridView` to run quality analysis after import. Recommended order:

1. End import UI.
2. Start blur analysis.
3. Start exposure analysis.

However, running both QThreads at the same time can increase I/O and CPU contention. For the first version, prefer sequential orchestration in `GridView`:

1. Start blur analysis.
2. When blur finishes, start exposure analysis.
3. Re-enable analysis buttons when both are done.

This requires an explicit GridView state machine:

- Track `_blur_ctrl` and `_exposure_ctrl`.
- Track whether an import-triggered quality chain should continue from blur to exposure.
- Do not re-enable analysis controls in `_on_blur_finished()` if exposure is queued.
- Re-enable controls only after the active quality-analysis chain is done.

If this makes import completion feel too slow, add a combined queue/controller later.

## Worker Design

Reuse `ExposureController`, but align it with the safer blur worker behavior:

- Add logging around start/finish/errors.
- Do not store zero-valued results when the image cannot be decoded. Return `None` from the service instead.
- Emit per-photo updates so the grid can update visible badges.
- Match the current `BlurController` lifecycle: lazy `QThread` creation in `start()`, guarded start, worker cleanup on thread finish, exception logging, and no thread move in `__init__`.
- Provide a close/cancel path compatible with `MainWindow.closeEvent()` if exposure analysis can still be running when the app closes.

Recommended service change:

```python
def compute_scores(self, root_path: str, relative_path: str) -> Optional[ExposureResult]:
    ...
    if img is None:
        return None
```

This keeps unsupported RAW/failed reads as `unanalyzed`, instead of incorrectly classifying them as black or normal.

Existing tests that expect missing files to return zero-valued `ExposureResult` must be updated to expect `None`.

## File-Level Implementation Plan

| File | Change |
|------|--------|
| `app/core/exposure_service.py` | Return `Optional[ExposureResult]` on decode failure; add shared exposure classifier helpers |
| `app/core/exposure_worker.py` | Skip DB update on `None`; improve logging; mirror `BlurController` lifecycle exactly |
| `app/core/filter_service.py` | Add exposure filter values and threshold parameters; call shared classifier |
| `app/core/models.py` | No new fields needed |
| `app/core/import_worker.py` | Clear exposure scores for modified images before they can be reanalyzed |
| `app/db/photo_repository.py` | Add `get_exposure_unanalyzed_ids()` and required `clear_exposure_scores()` |
| `app/ui/exposure_settings_dialog.py` | New settings dialog using `SettingsDB` |
| `app/ui/filter_panel.py` | Add EXPOSURE section and emit exposure filters |
| `app/ui/grid_view.py` | Add exposure controller, manual trigger, filter propagation, quality-analysis state machine |
| `app/ui/thumbnail_item.py` | Paint exposure badge with explicit exposure state |
| `app/ui/thumbnail_grid.py` | Store/update exposure state for visible thumbnail items |
| `app/ui/loupe_view.py` | Show exposure label alongside blur label; preserve parent blur/exposure filter context |
| `app/utils/theme.py` | Add exposure state colors |
| `app/ui/main_window.py` | Later phase: trigger exposure analysis after import only when `exposure_auto_after_import` is enabled |

## Testing Plan

Unit tests:

- `ExposureService.compute_scores()` returns `None` for unreadable files.
- Shared classifier returns expected states and display priority.
- Boundary tests cover exact threshold equality for clip, black mean, and black shadow thresholds.
- Mixed overexposed and underexposed photos match both states and display the documented priority.
- `PhotoRepository.get_exposure_unanalyzed_ids()` returns rows with any exposure field missing.
- `PhotoRepository.clear_exposure_scores()` clears all exposure fields.
- `FilterService` filters `overexposed`, `underexposed`, `black_frame`, `normal`, and `unanalyzed`.
- Exposure filter values use OR semantics inside the exposure dimension.
- `underexposed` includes `black_frame`, while `black_frame` alone does not include all underexposed photos.
- Exposure combines with status/color/blur filters using AND semantics.
- `ExposureWorker` skips DB writes when `compute_scores()` returns `None`.

Integration or UI-adjacent tests:

- Manual exposure analysis only analyzes missing rows.
- Modified-file import clears stale exposure fields.
- Later phase: import completion calls exposure analysis only when `exposure_auto_after_import` is enabled.
- Loupe label renders the expected text for each exposure state.
- Loupe navigation preserves parent Grid blur/exposure filter context.
- Thumbnail badge priority renders black frame before overexposed before underexposed.
- Settings are persisted in `SettingsDB`.

Manual smoke test:

1. Open a folder with normal, white, black, and dark JPEG samples.
2. Import finishes; exposure does not auto-start in MVP.
3. Click `Analyze Exposure`.
4. EXPOSURE filter appears in the left panel.
5. Overexposed filter shows the white sample.
6. Underexposed filter shows the dark sample and the black sample.
7. Black frame filter shows only the black sample.
8. Loupe shows exposure state and percentages.
9. Change a sample file, re-import modified files, and confirm exposure fields are cleared and can be reanalyzed.

## Accepted Decisions

1. Manual exposure analysis ships first. Automatic after-import analysis comes later after the manual path is stable.
2. Classification logic must be centralized in a shared helper.
3. `black_frame` is a separate filter and also an underexposed subtype.
4. Loupe must preserve the parent Grid's blur/exposure filter context.
5. Grid badge work must include `thumbnail_item.py` and `thumbnail_grid.py`.
6. Modified images must clear stale exposure scores.
7. `ExposureController` must adopt the current `BlurController` lifecycle.
8. The full design can stay documented, but the implementation should be staged clearly.

## Implementation Stages

### MVP

1. Keep absolute thresholds only.
2. Add shared classifier helpers.
3. Update `ExposureService.compute_scores()` to return `None` on decode failure.
4. Add repository helpers for unanalyzed rows and clearing exposure scores.
5. Clear exposure scores for modified images.
6. Add exposure filter support.
7. Add EXPOSURE filter UI.
8. Add manual `Analyze Exposure` button.
9. Show exposure text in Loupe.
10. Preserve blur/exposure context during Loupe navigation.
11. Add focused tests for classifier, repository helpers, filter semantics, and worker skip-on-`None`.

### Next

1. Add `ExposureSettingsDialog`.
2. Add Grid exposure badges through `ThumbnailItem` and `ThumbnailGrid`.
3. Add richer progress/status UI for quality analysis.
4. Enable `exposure_auto_after_import` only after manual analysis is stable and performance is acceptable.
5. Add sequential blur-then-exposure orchestration for automatic quality analysis.
6. Consider relative exposure thresholds if real photo sets show too many false positives.
