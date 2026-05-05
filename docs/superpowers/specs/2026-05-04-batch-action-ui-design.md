# Batch Action UI Design

Date: 2026-05-04

## Problem

Multi-selection already works (rubber-band, Shift+Click, Ctrl+Click) and keyboard shortcuts P/R/M/U already trigger batch tagging. However there is no visual affordance — users cannot discover these actions, and mouse-only users cannot trigger them at all.

## Goals

- Mouse users can trigger batch status and color tagging
- Keyboard users retain existing P/R/M/U shortcuts
- Selection count is visible with Select All / Deselect All controls
- UI stays clean when nothing is selected

## Out of Scope

- "Open in Loupe", "Open in Explorer" context menu items
- Mixed-state indicators in context menu
- Any other batch operations (delete, export)

---

## Design

### 1. Right-Click Context Menu (Submenu Structure)

**Trigger:** Right-click any thumbnail.

**Selection rules:**
- Right-click an **unselected** thumbnail → clear existing selection, select that thumbnail, show menu
- Right-click an **already-selected** thumbnail → keep existing multi-selection, show menu

**Menu structure:**
```
標記 N 張照片          ← disabled header, N = selection count
────────────────────
  標記狀態    ▶        → Pick (P)
                        Reject (R)
                        Maybe (M)
                        ─────────
                        清除狀態 (U)
  顏色標籤    ▶        → 🔴 紅
                        🟠 橙
                        🟡 黃
                        🟢 綠
                        🔵 藍
                        🟣 紫
                        ─────────
                        清除顏色
```

Keyboard shortcuts shown as right-aligned hints on submenu items.

**Implementation:** Add `contextMenuEvent()` to `ThumbnailGrid` in `app/ui/thumbnail_grid.py`. Use `QMenu` with `addMenu()` for submenus. Reuse existing `batch_status_requested` and a new `batch_color_requested` signal for the actual operations. Wire color signal in `GridView` similar to `_on_batch_status`.

---

### 2. Status Bar Enhancements

**Location:** Bottom status bar in `GridView` (`app/ui/grid_view.py`), left side.

**Behaviour:**
- No selection → show `[全選]` button only
- Has selection → show `已選 N 張　[取消全選]` (全選button hidden)

**Signal flow:**
`ThumbnailGrid.selection_changed` → `GridView._on_selection_changed()` → update status bar label + toggle buttons

**New methods needed in `ThumbnailGrid`:**
- `select_all()` — adds all visible photo IDs to `_selected`, emits `selection_changed`
- `clear_selection()` — clears `_selected`, emits `selection_changed`

---

### 3. Keyboard Shortcuts (Unchanged)

Existing P/R/M/U shortcuts in `thumbnail_grid.py` remain untouched. Context menu surface them as discoverable hints only.

---

## Files Changed

| File | Change |
|------|--------|
| `app/ui/thumbnail_grid.py` | Add `contextMenuEvent()`, `select_all()`, `clear_selection()`, new `batch_color_requested` signal |
| `app/ui/grid_view.py` | Update `_on_selection_changed()` to update status bar; add `_on_batch_color()` handler; add Select All / Deselect All buttons to status bar |

---

## Non-Goals / Explicitly Excluded

- No mixed-state indicators (showing current tag state in menu)
- No floating toolbar above grid
- No permanent bottom toolbar with tag buttons
- No color label batch operation confirmation dialog (status already has one; color changes are low-risk)
