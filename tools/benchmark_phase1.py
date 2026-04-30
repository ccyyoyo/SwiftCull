"""Phase 1 performance benchmark — headless data pipeline only.

Run:  python tools/benchmark_phase1.py [--count 1000] [--workers 4] [--keep]

Spec targets we can validate from this script (no Qt required):
    1000 photo initial import (DB writes + EXIF)  : < 15 s
    Re-open scan vs populated DB                  : < 5 s   (subset of "重開 < 5 s")

Spec targets we CANNOT validate here (need PySide6 / actual GUI):
    Grid 載入（1000 visible thumbnails）          : < 2 s

Synthetic test data: small JPEGs (~50–80 KB) with embedded EXIF. That's the
same order of magnitude as the *embedded preview* extracted from a RAW file,
which is what the import pipeline actually decodes. Real RAW files are
30–100x larger on disk so I/O scales accordingly, but the per-file CPU work
is dominated by the embedded JPEG, not the raw sensor data.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Make `app.*` importable when running this from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

import piexif  # noqa: E402

from app.core.filter_service import FilterService  # noqa: E402
from app.core.import_service import ImportService  # noqa: E402
from app.core.scan_service import ScanService  # noqa: E402
from app.core.tag_service import TagService  # noqa: E402
from app.core.thumbnail_service import ThumbnailService  # noqa: E402
from app.db.connection import get_connection, init_db  # noqa: E402
from app.db.photo_repository import PhotoRepository  # noqa: E402
from app.db.tag_repository import TagRepository  # noqa: E402


# ---------------------------------------------------------------------------
# Test data generation
# ---------------------------------------------------------------------------

_PALETTE = [
    (200, 80, 80), (80, 200, 100), (60, 120, 220),
    (220, 180, 60), (180, 80, 200), (60, 200, 200),
    (140, 140, 140),
]


def _make_exif_bytes(idx: int) -> bytes:
    zeroth = {
        piexif.ImageIFD.Make: b"SwiftCullBench",
        piexif.ImageIFD.Model: f"Synth-{idx % 7}".encode("ascii"),
    }
    exif = {
        piexif.ExifIFD.DateTimeOriginal: f"2026:04:30 12:{idx % 60:02d}:00".encode("ascii"),
        piexif.ExifIFD.ISOSpeedRatings: 100 + (idx * 13) % 6300,
        piexif.ExifIFD.FNumber: (28, 10),  # f/2.8
        piexif.ExifIFD.ExposureTime: (1, 200),
        piexif.ExifIFD.FocalLength: (50, 1),
    }
    return piexif.dump({"0th": zeroth, "Exif": exif})


def _generate_photos(folder: Path, count: int, *, dim: int = 1024,
                     subdirs: int = 4) -> None:
    """Write `count` JPEGs split across a few subfolders."""
    for i in range(subdirs):
        (folder / f"day_{i:02d}").mkdir(parents=True, exist_ok=True)
    for i in range(count):
        sub = folder / f"day_{i % subdirs:02d}"
        path = sub / f"img_{i:05d}.jpg"
        color = _PALETTE[i % len(_PALETTE)]
        # A bit of structure beats a flat color: PIL+JPEG would compress flat
        # images down to a few hundred bytes which isn't representative.
        img = Image.new("RGB", (dim, dim), color=color)
        for stripe in range(0, dim, 16):
            band = (color[0] ^ stripe & 0xFF,
                    color[1] ^ stripe & 0xFF,
                    color[2] ^ stripe & 0xFF)
            for y in range(stripe, min(stripe + 8, dim)):
                for x in range(0, dim, 32):
                    img.putpixel((x, y), band)
        img.save(path, "JPEG", quality=85, exif=_make_exif_bytes(i))


# ---------------------------------------------------------------------------
# Phase timers
# ---------------------------------------------------------------------------

class Phase:
    __slots__ = ("name", "elapsed_s", "n", "extra")

    def __init__(self, name: str, elapsed_s: float, n: int = 0, extra=""):
        self.name = name
        self.elapsed_s = elapsed_s
        self.n = n
        self.extra = extra

    @property
    def per_item_ms(self) -> float:
        return (self.elapsed_s * 1000.0 / self.n) if self.n else 0.0


def _time(label: str, fn, *, n: int = 0, extra: str = "") -> Phase:
    t0 = time.perf_counter()
    fn()
    dt = time.perf_counter() - t0
    return Phase(label, dt, n, extra)


# ---------------------------------------------------------------------------
# Benchmark phases
# ---------------------------------------------------------------------------

def bench_scan_folder(svc: ImportService, folder: str, count: int) -> tuple[Phase, list]:
    paths_holder: list[str] = []

    def run():
        paths_holder[:] = svc.scan_folder(folder)

    p = _time("scan_folder (recursive walk)", run, n=count)
    return p, paths_holder


def bench_build_minimal(svc: ImportService, folder: str, paths: list) -> tuple[Phase, list]:
    photos: list = []

    def run():
        for rel in paths:
            photos.append(svc.build_photo_minimal(folder, rel))

    p = _time("build_photo_minimal (stat per file)", run, n=len(paths))
    return p, photos


def bench_db_insert(repo: PhotoRepository, photos: list) -> Phase:
    def run():
        for p in photos:
            repo.insert(p)

    return _time("PhotoRepository.insert (one row at a time)", run, n=len(photos))


def bench_enrich(svc: ImportService, repo: PhotoRepository, folder: str,
                 paths: list) -> Phase:
    def run():
        for rel in paths:
            meta = svc.enrich_photo(folder, rel)
            pid = repo.get_id_by_relative_path(rel)
            if pid is not None:
                repo.update_metadata(pid, meta)

    return _time("enrich_photo + update_metadata (EXIF parse + UPDATE)",
                 run, n=len(paths))


def bench_full_import(folder: str, db_path: str, count: int) -> tuple[Phase, dict]:
    """End-to-end import: scan + minimal + insert + enrich. Mirrors what
    ImportWorker actually does on `_run_inner`, minus the Qt signal traffic."""
    svc = ImportService()
    sub_phases = {}

    t_total = time.perf_counter()

    t0 = time.perf_counter()
    paths = svc.scan_folder(folder)
    sub_phases["scan_folder_s"] = time.perf_counter() - t0

    conn = get_connection(db_path)
    init_db(conn)
    repo = PhotoRepository(conn)

    t0 = time.perf_counter()
    photos = [svc.build_photo_minimal(folder, rel) for rel in paths]
    for p in photos:
        repo.insert(p)
    sub_phases["minimal_plus_insert_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    for rel in paths:
        meta = svc.enrich_photo(folder, rel)
        pid = repo.get_id_by_relative_path(rel)
        if pid is not None:
            repo.update_metadata(pid, meta)
    sub_phases["enrich_s"] = time.perf_counter() - t0

    conn.close()

    total = time.perf_counter() - t_total
    return Phase("FULL initial import (1000-photo equiv pipeline)", total, count,
                 extra=str(sub_phases)), sub_phases


def bench_reopen_scan(folder: str, db_path: str, count: int) -> Phase:
    """Open the populated DB and run ScanService.scan() — what happens when
    a returning user opens an existing project."""
    conn = get_connection(db_path)
    init_db(conn)
    repo = PhotoRepository(conn)

    def run():
        mtime_map = repo.get_path_mtime_map()
        result = ScanService().scan(folder, mtime_map)
        # Should be a no-op (everything already imported, mtimes match).
        assert result.has_actionable_changes is False, result

    p = _time("re-open scan (DB read + disk walk + mtime compare)",
              run, n=count)
    conn.close()
    return p


def bench_thumbnails_serial(thumb_svc: ThumbnailService, folder: str,
                            paths: list, size: int = 256) -> Phase:
    def run():
        for rel in paths:
            thumb_svc.get_thumbnail(os.path.join(folder, rel), size)

    return _time(f"thumbnails serial @ {size}px", run, n=len(paths))


def bench_thumbnails_parallel(thumb_svc: ThumbnailService, folder: str,
                              paths: list, *, size: int = 256,
                              workers: int = 4) -> Phase:
    def run():
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(
                lambda rel: thumb_svc.get_thumbnail(
                    os.path.join(folder, rel), size),
                paths,
            ))

    return _time(f"thumbnails parallel x{workers} @ {size}px",
                 run, n=len(paths))


def bench_filter(filter_svc: FilterService, count: int) -> Phase:
    samples_ms = []

    def run():
        for _ in range(50):
            t0 = time.perf_counter()
            filter_svc.filter(statuses=["pick"])
            filter_svc.filter(colors=["red"])
            filter_svc.filter(statuses=["untagged"])
            samples_ms.append((time.perf_counter() - t0) * 1000)

    p = _time("filter_svc.filter (50 iters x 3 queries)", run, n=count)
    if samples_ms:
        p.extra = (f"per-iter avg={statistics.mean(samples_ms):.2f}ms"
                   f"  p95={sorted(samples_ms)[int(len(samples_ms)*0.95)-1]:.2f}ms")
    return p


# ---------------------------------------------------------------------------
# Tag a fraction of rows so filter_svc has work to do.
# ---------------------------------------------------------------------------

def _seed_tags(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    repo = PhotoRepository(conn)
    tag_repo = TagRepository(conn)
    tag_svc = TagService(tag_repo)

    rows = conn.execute("SELECT id FROM photos ORDER BY id").fetchall()
    ids = [r["id"] for r in rows]
    third = len(ids) // 3
    tag_svc.batch_set_status(ids[:third], "pick")
    tag_svc.batch_set_status(ids[third:2 * third], "reject")
    for i, pid in enumerate(ids[:third]):
        if i % 4 == 0:
            tag_svc.set_color(pid, "red")
    conn.close()


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _fmt_phase(p: Phase) -> str:
    head = f"{p.name:<55s} {p.elapsed_s:>8.3f} s"
    if p.n:
        head += f"   ({p.per_item_ms:>7.3f} ms/item, {p.n} items)"
    if p.extra:
        head += f"   [{p.extra}]"
    return head


def _verdict(label: str, value_s: float, target_s: float) -> str:
    ok = value_s <= target_s
    mark = "PASS" if ok else "FAIL"
    return f"  {mark}: {label}: {value_s:.2f}s (target <= {target_s}s)"


def main():
    parser = argparse.ArgumentParser(description="SwiftCull Phase 1 perf bench")
    parser.add_argument("--count", type=int, default=1000,
                        help="number of synthetic photos (default 1000)")
    parser.add_argument("--workers", type=int, default=4,
                        help="thread pool size for parallel thumbnails")
    parser.add_argument("--dim", type=int, default=1024,
                        help="synthetic photo dimension (square, default 1024)")
    parser.add_argument("--keep", action="store_true",
                        help="don't delete the temp working dir at exit")
    parser.add_argument("--workdir", type=Path, default=None,
                        help="explicit work directory (default: temp)")
    args = parser.parse_args()

    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="swiftcull_bench_"))
    workdir.mkdir(parents=True, exist_ok=True)
    photos_dir = workdir / "photos"
    cache_dir = workdir / "cache"
    db_path = workdir / "project.db"
    photos_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"# SwiftCull Phase 1 Benchmark")
    print(f"workdir : {workdir}")
    print(f"count   : {args.count}")
    print(f"dim     : {args.dim}px (square JPEG, q=85, EXIF embedded)")
    print(f"workers : {args.workers}")
    print()

    # Generate test data (NOT counted; warm the disk cache).
    t0 = time.perf_counter()
    _generate_photos(photos_dir, args.count, dim=args.dim)
    gen_s = time.perf_counter() - t0
    total_bytes = sum(p.stat().st_size
                      for p in photos_dir.rglob("*.jpg"))
    avg_kb = total_bytes / max(1, args.count) / 1024
    print(f"generated {args.count} photos in {gen_s:.2f}s "
          f"(avg {avg_kb:.1f} KB/photo, total {total_bytes/1024/1024:.1f} MB)")
    print()

    folder = str(photos_dir)
    phases: list[Phase] = []

    # Pure scan/build/insert/enrich measured separately so we can see which
    # part dominates.
    svc = ImportService()
    p_scan, paths = bench_scan_folder(svc, folder, args.count)
    phases.append(p_scan)

    # Use a fresh DB so insert timing isn't polluted by the prior init_db.
    conn = get_connection(str(db_path))
    init_db(conn)
    repo = PhotoRepository(conn)

    p_build, photos = bench_build_minimal(svc, folder, paths)
    phases.append(p_build)
    p_insert = bench_db_insert(repo, photos)
    phases.append(p_insert)
    conn.close()

    # Tear down + redo as full pipeline to get end-to-end number that maps
    # to the spec target.
    db_path.unlink()
    p_full, full_sub = bench_full_import(folder, str(db_path), args.count)
    phases.append(p_full)

    # ScanService over the now-populated DB (the "re-open" path).
    p_reopen = bench_reopen_scan(folder, str(db_path), args.count)
    phases.append(p_reopen)

    # Thumbnails: serial first (cold cache), then parallel (also cold cache
    # by wiping the dir between runs so we measure work, not cache hits).
    thumb_svc = ThumbnailService(str(cache_dir))
    p_thumb_serial = bench_thumbnails_serial(thumb_svc, folder, paths, size=256)
    phases.append(p_thumb_serial)

    shutil.rmtree(cache_dir)
    cache_dir.mkdir()
    thumb_svc = ThumbnailService(str(cache_dir))
    p_thumb_par = bench_thumbnails_parallel(thumb_svc, folder, paths,
                                            size=256, workers=args.workers)
    phases.append(p_thumb_par)

    # Filter: seed tags then time queries.
    _seed_tags(str(db_path))
    conn = get_connection(str(db_path))
    init_db(conn)
    photo_repo = PhotoRepository(conn)
    tag_repo = TagRepository(conn)
    filter_svc = FilterService(photo_repo, tag_repo)
    p_filter = bench_filter(filter_svc, args.count)
    phases.append(p_filter)
    conn.close()

    # ---- Report ----------------------------------------------------------
    print("=" * 88)
    print("Phase timings")
    print("=" * 88)
    for p in phases:
        print(_fmt_phase(p))
    print()

    print("Initial-import sub-phase breakdown (from FULL pipeline):")
    for k, v in full_sub.items():
        print(f"  {k:<28s} {v:>7.3f} s")
    print()

    # Spec targets — only the headlessly-verifiable ones.
    print("=" * 88)
    print("Spec verdicts (headless subset)")
    print("=" * 88)
    print(_verdict("initial-import pipeline (1000 photos < 15s)",
                  p_full.elapsed_s, 15.0))
    print(_verdict("re-open scan (< 5s)", p_reopen.elapsed_s, 5.0))
    print()
    print("Spec targets requiring the GUI (NOT measured here):")
    print("  - Grid load of 1000 visible thumbnails  : < 2 s")
    print()

    if not args.keep:
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        print(f"workdir kept at {workdir}")


if __name__ == "__main__":
    main()
