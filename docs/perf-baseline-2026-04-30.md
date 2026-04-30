# SwiftCull Phase 1 — Performance Baseline (2026-04-30)

Snapshot of headless data-pipeline performance against the spec's perf
budget. Run with `python tools/benchmark_phase1.py --count 1000`.

## Test conditions

| Item | Value |
|------|-------|
| Photos | 1000 synthetic JPEGs, 1024×1024 px, q=85, EXIF embedded |
| Avg file size | 55.1 KB / photo (~54 MB total) |
| Layout | 4 subfolders (`day_00 … day_03`), 250 photos each |
| Hardware | Local Windows machine (chy's dev box) |
| Python | 3.9.13 (Pillow + piexif installed) |
| Storage | Whatever `%TEMP%` resolves to (NVMe SSD assumed) |

Synthetic JPEGs are roughly the size of an *embedded preview* extracted
from a RAW file — which is what the import pipeline actually decodes.
Real RAW files are 30–100x larger on disk, so I/O on a slow drive could
shift these numbers.

## Spec targets vs. measured

| Target | Spec | Measured | Result |
|--------|------|----------|--------|
| 1000-photo initial import (data pipeline) | < 15 s | **1.37 s** | PASS, ~11× headroom |
| Re-open scan over populated DB | < 5 s | **0.05 s** | PASS, ~100× headroom |
| Grid load of 1000 visible thumbnails | < 2 s | *not measured here* | requires GUI |

Spec targets requiring the GUI weren't captured (no PySide6 in the bench
environment). The Grid-load target is pure UI cost: the data is already
in memory after `_refresh()`, so the budget is dominated by Qt's tile
layout pass, not anything the bench can simulate.

## Phase breakdown (1000 photos)

```
scan_folder (recursive walk)               0.037 s   (0.04 ms/item)
build_photo_minimal (stat per file)        0.042 s   (0.04 ms/item)
PhotoRepository.insert (one row at a time) 0.385 s   (0.39 ms/item)
FULL initial import end-to-end             1.370 s   (1.37 ms/item)
re-open scan (DB read + walk + compare)    0.055 s   (0.06 ms/item)
thumbnails serial @ 256px                  8.202 s   (8.20 ms/item)
thumbnails parallel x4 @ 256px             2.652 s   (2.65 ms/item)
filter_svc.filter (avg per query)         24.43 ms (~p95 26 ms)
```

### Initial-import sub-phases

| Phase | Cost | Notes |
|-------|------|-------|
| `scan_folder` | 0.046 s | OS-bound directory walk — limited by FS, not us |
| `build_photo_minimal` + `insert` | 0.413 s | one `commit()` per row currently |
| `enrich_photo` | 0.901 s | EXIF parse via `piexif` + dimensions via PIL |

## Bottlenecks ranked

1. **Thumbnail generation** — biggest CPU cost by far. Sequential 8.2 s,
   parallel-4 at 2.65 s (3.1× speedup, GIL-bounded). The grid worker
   (`_ThumbRunnable` via `QThreadPool`) already uses parallel decoding,
   so this maps to actual runtime behaviour.
2. **EXIF enrichment** — 0.9 s for 1000 photos (~0.9 ms each). `piexif`
   does a full parse even for the few fields we care about. Could swap
   to `Pillow.ExifTags` / `exifread` if this ever becomes a problem,
   but at <1 s it's not worth touching.
3. **Per-row commits** — `PhotoRepository.insert` commits inside the
   loop, adding ~0.4 ms per row. Wrapping the import loop in a single
   transaction would cut this to ~50 ms total. Free future win.
4. **Filter queries** — ~24 ms per `filter_svc.filter` call against
   1000 photos. UI redraw runs after each filter change, total well
   under 100 ms — feels instant.

## Reproducibility

```bash
python tools/benchmark_phase1.py --count 1000 --dim 1024 --workers 4
```

Flags:
- `--count` — number of synthetic photos (default 1000)
- `--dim` — square dimension in px (default 1024)
- `--workers` — parallel thumbnail thread count (default 4)
- `--keep` — keep the temp working dir for inspection
- `--workdir <path>` — explicit working dir instead of `%TEMP%`
