"""Plain user-facing text helpers. No Qt — safe to import everywhere."""


def format_scan_message(
    new_count: int,
    modified_count: int,
    missing_count: int = 0,
) -> str:
    """Build the toast text for a scan result.

    The "?" suffix only appears when we have actionable changes (new or
    modified files). Pure-missing scans are informational so we end with "。".

    Examples:
      (3, 0, 0) -> "發現 3 個新增 檔案，是否匯入？"
      (0, 2, 0) -> "發現 2 個修改 檔案，是否匯入？"
      (3, 2, 0) -> "發現 3 個新增 / 2 個修改 檔案，是否匯入？"
      (0, 0, 4) -> "有 4 個檔案找不到。"
      (2, 0, 1) -> "發現 2 個新增 檔案；另有 1 個檔案找不到。是否匯入？"
      (0, 0, 0) -> "發現 0 檔案，是否匯入？"  (callers usually skip this case)
    """
    parts = []
    if new_count:
        parts.append(f"{new_count} 個新增")
    if modified_count:
        parts.append(f"{modified_count} 個修改")

    if not parts and not missing_count:
        return "發現 0 檔案，是否匯入？"
    if not parts:
        return f"有 {missing_count} 個檔案找不到。"

    summary = " / ".join(parts)
    if missing_count:
        return (f"發現 {summary} 檔案；另有 {missing_count} 個檔案找不到。"
                f"是否匯入？")
    return f"發現 {summary} 檔案，是否匯入？"
