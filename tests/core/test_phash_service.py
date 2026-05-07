import numpy as np
import cv2


def _write_jpeg(tmp_path, name: str, pattern: str) -> str:
    if pattern == "checkerboard":
        arr = np.zeros((64, 64, 3), dtype=np.uint8)
        for i in range(64):
            for j in range(64):
                arr[i, j] = 255 if (i // 8 + j // 8) % 2 == 0 else 0
    elif pattern == "solid_white":
        arr = np.full((64, 64, 3), 255, dtype=np.uint8)
    elif pattern == "solid_gray":
        arr = np.full((64, 64, 3), 128, dtype=np.uint8)
    else:
        raise ValueError(f"unknown pattern: {pattern}")
    path = tmp_path / name
    cv2.imwrite(str(path), arr)
    return str(path)


def test_compute_hash_returns_16_char_hex(tmp_path):
    from app.core.phash_service import PHashService
    _write_jpeg(tmp_path, "a.jpg", "checkerboard")
    svc = PHashService()
    h = svc.compute_hash(str(tmp_path), "a.jpg")
    assert h is not None
    assert len(h) == 16
    int(h, 16)  # must be valid hex


def test_compute_hash_same_image_deterministic(tmp_path):
    from app.core.phash_service import PHashService
    _write_jpeg(tmp_path, "img.jpg", "solid_gray")
    svc = PHashService()
    h1 = svc.compute_hash(str(tmp_path), "img.jpg")
    h2 = svc.compute_hash(str(tmp_path), "img.jpg")
    assert h1 == h2


def test_compute_hash_different_images_differ(tmp_path):
    from app.core.phash_service import PHashService
    _write_jpeg(tmp_path, "checker.jpg", "checkerboard")
    _write_jpeg(tmp_path, "white.jpg", "solid_white")
    svc = PHashService()
    h_checker = svc.compute_hash(str(tmp_path), "checker.jpg")
    h_white = svc.compute_hash(str(tmp_path), "white.jpg")
    assert h_checker != h_white


def test_compute_hash_returns_none_for_missing_file(tmp_path):
    from app.core.phash_service import PHashService
    svc = PHashService()
    assert svc.compute_hash(str(tmp_path), "no_such_file.jpg") is None


def test_hamming_distance_identical():
    from app.core.phash_service import PHashService
    h = "0123456789abcdef"
    assert PHashService.hamming_distance(h, h) == 0


def test_hamming_distance_one_bit():
    from app.core.phash_service import PHashService
    # flip lowest bit of last nibble
    assert PHashService.hamming_distance("0000000000000000", "0000000000000001") == 1


def test_hamming_distance_all_bits():
    from app.core.phash_service import PHashService
    assert PHashService.hamming_distance("0000000000000000", "ffffffffffffffff") == 64


def test_group_by_similarity_identical_hashes():
    from app.core.phash_service import PHashService
    h = "0000000000000000"
    hashes = {1: h, 2: h, 3: h}
    groups = PHashService.group_by_similarity(hashes, threshold=0)
    assert len(groups) == 1
    assert sorted(groups[0]) == [1, 2, 3]


def test_group_by_similarity_no_match():
    from app.core.phash_service import PHashService
    # max Hamming distance between these two is 64
    hashes = {1: "0000000000000000", 2: "ffffffffffffffff"}
    groups = PHashService.group_by_similarity(hashes, threshold=10)
    assert groups == []


def test_group_by_similarity_transitive():
    from app.core.phash_service import PHashService
    # 1↔2 close, 2↔3 close, 1↔3 should merge via transitivity
    h1 = "0000000000000000"
    h2 = "0000000000000001"  # 1 bit from h1
    h3 = "0000000000000003"  # 2 bits from h1, 1 bit from h2
    hashes = {1: h1, 2: h2, 3: h3}
    groups = PHashService.group_by_similarity(hashes, threshold=2)
    assert len(groups) == 1
    assert sorted(groups[0]) == [1, 2, 3]


def test_group_by_similarity_single_photo_excluded():
    from app.core.phash_service import PHashService
    # Only one photo → no group
    hashes = {1: "0000000000000000"}
    groups = PHashService.group_by_similarity(hashes, threshold=10)
    assert groups == []
