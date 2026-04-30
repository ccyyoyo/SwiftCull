"""Plain user-facing text helpers. No Qt — safe to import everywhere."""


def format_scan_message(new_count: int, modified_count: int) -> str:
    """Build the toast text for a scan result.

    Examples:
      (3, 0) -> "發現 3 個新增 檔案，是否匯入？"
      (0, 2) -> "發現 2 個修改 檔案，是否匯入？"
      (3, 2) -> "發現 3 個新增 / 2 個修改 檔案，是否匯入？"
      (0, 0) -> "發現 0 檔案，是否匯入？"  (callers usually skip this case)
    """
    parts = []
    if new_count:
        parts.append(f"{new_count} 個新增")
    if modified_count:
        parts.append(f"{modified_count} 個修改")
    summary = " / ".join(parts) if parts else "0"
    return f"發現 {summary} 檔案，是否匯入？"
