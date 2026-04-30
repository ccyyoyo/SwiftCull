from app.utils.messages import format_scan_message


def test_only_new_files():
    assert format_scan_message(3, 0) == "發現 3 個新增 檔案，是否匯入？"


def test_only_modified_files():
    assert format_scan_message(0, 4) == "發現 4 個修改 檔案，是否匯入？"


def test_both_new_and_modified():
    assert format_scan_message(2, 5) == "發現 2 個新增 / 5 個修改 檔案，是否匯入？"


def test_zero_falls_back_gracefully():
    assert format_scan_message(0, 0) == "發現 0 檔案，是否匯入？"


def test_singular_one_uses_same_format():
    assert format_scan_message(1, 0) == "發現 1 個新增 檔案，是否匯入？"
    assert format_scan_message(0, 1) == "發現 1 個修改 檔案，是否匯入？"


def test_only_missing_is_informational_not_a_question():
    msg = format_scan_message(0, 0, 4)
    assert msg == "有 4 個檔案找不到。"
    assert "？" not in msg


def test_new_plus_missing_combines_into_one_line():
    msg = format_scan_message(2, 0, 1)
    assert "2 個新增" in msg
    assert "1 個檔案找不到" in msg
    assert msg.endswith("是否匯入？")


def test_modified_plus_missing():
    msg = format_scan_message(0, 3, 2)
    assert "3 個修改" in msg
    assert "2 個檔案找不到" in msg


def test_all_three_buckets():
    msg = format_scan_message(2, 3, 1)
    assert "2 個新增" in msg
    assert "3 個修改" in msg
    assert "1 個檔案找不到" in msg
    assert msg.endswith("是否匯入？")
