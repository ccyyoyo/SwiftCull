from app.utils.messages import format_scan_message


def test_only_new_files():
    assert format_scan_message(3, 0) == "發現 3 個新增 檔案，是否匯入？"


def test_only_modified_files():
    assert format_scan_message(0, 4) == "發現 4 個修改 檔案，是否匯入？"


def test_both_new_and_modified():
    assert format_scan_message(2, 5) == "發現 2 個新增 / 5 個修改 檔案，是否匯入？"


def test_zero_falls_back_gracefully():
    # Callers should normally not show a toast for 0/0, but the helper
    # must not crash if it ever happens.
    assert format_scan_message(0, 0) == "發現 0 檔案，是否匯入？"


def test_singular_one_uses_same_format():
    # We deliberately avoid English-style pluralization for Chinese.
    assert format_scan_message(1, 0) == "發現 1 個新增 檔案，是否匯入？"
    assert format_scan_message(0, 1) == "發現 1 個修改 檔案，是否匯入？"
