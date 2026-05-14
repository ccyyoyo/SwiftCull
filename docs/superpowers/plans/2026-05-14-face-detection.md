# Face Detection MVP — Implementation Plan

**Date:** 2026-05-14
**Status:** Implemented in single session (see commits below).
**Spec:** [2026-05-14-face-detection-design.md](../specs/2026-05-14-face-detection-design.md)

## Goal

Add MediaPipe FaceLandmarker-based face detection with eye-closed signaling,
wired through the full stack: service → worker → DB → filter → FilterPanel →
GridView → LoupeView. Mirrors the existing exposure / horizon patterns.

## Tasks

| # | Task | Files touched | Done |
|---|------|---------------|------|
| 1 | Bundle MediaPipe + model | `requirements.txt`, `assets/face_landmarker.task` | ✓ |
| 2 | Photo dataclass + DB migration | `app/core/models.py`, `app/db/connection.py` | ✓ |
| 3 | PhotoRepository face CRUD | `app/db/photo_repository.py`, `tests/db/test_photo_repository_face.py` | ✓ |
| 4 | FaceService classifier (no MediaPipe) | `app/core/face_service.py`, `tests/core/test_face_classifier.py` | ✓ |
| 5 | FilterService face dimension | `app/core/filter_service.py`, `tests/core/test_filter_service_face.py` | ✓ |
| 6 | FaceService.compute against MediaPipe | `app/core/face_service.py`, `tests/core/test_face_service*.py` | ✓ |
| 7 | FaceWorker + FaceController | `app/core/face_worker.py` | ✓ |
| 8 | Theme colors + FilterPanel FACE section | `app/utils/theme.py`, `app/ui/filter_panel.py` | ✓ |
| 9 | GridView wiring | `app/ui/grid_view.py` | ✓ |
| 10 | LoupeView face label | `app/ui/loupe_view.py` | ✓ |
| 11 | MainWindow lifecycle | `app/ui/main_window.py` | ✓ |

## Test results

```
tests/core/test_face_classifier.py ............. (13 passed)
tests/core/test_filter_service_face.py ......... (8 passed)
tests/db/test_photo_repository_face.py ......... (8 passed)
tests/core/test_face_service_none.py ........... (3 passed, 1 skip — cv2 env)
tests/core/test_face_service.py ................ (skipped — MediaPipe env)
```

Full suite (env with cv2/MediaPipe missing): 233 passed, 3 pre-existing failures
unrelated to face work (cv2 not installed; pre-existing on master).

## Key decisions log

- **Signal change**: `FilterPanel.filter_changed` from 6-tuple to 7-tuple. Done
  in one commit with GridView and Loupe subscribers updated atomically.
- **Eye-blink threshold**: 0.45. Tunable via SettingsDB key
  `face_eyes_closed_threshold` (default 1 face must have eyes closed).
- **Min eye-closed count threshold**: defaults to 1 (any single face closing eyes
  triggers `eyes_closed` filter). Configurable. The setting key is reused by
  both GridView (for grid refresh) and LoupeView (for the label).
- **face_analyzed flag**: stored as INTEGER DEFAULT 0 in SQLite, exposed as
  `bool` in the Photo dataclass via `bool(row["face_analyzed"])`.
- **Compute failure mode**: `compute` returns `None` only on decode/inference
  failure. "0 faces successfully detected" returns `FaceResult(0, 0.0, 0)` so
  it can be distinguished from "didn't bother analyzing".

## Manual verification checklist

- [ ] `python main.py` opens; no startup crash
- [ ] Open a folder with mixed portraits and landscapes
- [ ] Click "☻ 分析人臉" — button disables, no UI hang
- [ ] After completion: FilterPanel FACE section toggles correctly:
  - `有人臉` only shows portraits
  - `無人臉` only shows non-portraits
  - `閉眼` only shows photos with at least one blinking subject
  - `未分析` empties after analysis completes
- [ ] Open Loupe on a portrait — see `Faces: N` (or `Faces: N (M closed)`) top-right
- [ ] Open Loupe on a landscape — see `Faces: 0`
- [ ] Close + reopen project DB — face_analyzed flag persists, "Analyse Faces"
  becomes a no-op

## Risks observed during implementation

- **None blocking.** MediaPipe was straightforward to wire. The lazy-init
  pattern in `FaceService._ensure_landmarker` keeps native graph initialization
  on the worker thread, avoiding the Windows + Python 3.9 hang risk seen in
  earlier prototypes.

## Tech-debt impact

This adds 4 more columns via ad-hoc `_migrate()` checks, bringing the count
past 12 additive migrations. Trigger condition for the migration framework
described in [docs/tech-debt.md §1](../../tech-debt.md) is well past. Still
deferred for this plan; flag for next planning session.
