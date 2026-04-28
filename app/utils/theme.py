"""Centralized dark theme for SwiftCull."""

BG_DEEP    = "#111111"
BG_MAIN    = "#1a1a1a"
BG_PANEL   = "#212121"
BG_ITEM    = "#1e1e1e"
BG_HOVER   = "#2a2a2a"
BG_SELECT  = "#2d3a4a"

BORDER     = "#333333"
BORDER_SEL = "#E87722"   # orange selection

TEXT_PRIMARY   = "#e8e8e8"
TEXT_SECONDARY = "#888888"
TEXT_MUTED     = "#555555"

ACCENT     = "#E87722"   # orange
PICK_CLR   = "#3ddc84"   # green
REJECT_CLR = "#ff4d4d"   # red
MAYBE_CLR  = "#ffc233"   # amber

STATUS_ICON = {"pick": "✓", "reject": "✗", "maybe": "?"}
STATUS_COLOR = {"pick": PICK_CLR, "reject": REJECT_CLR, "maybe": MAYBE_CLR}

COLOR_DOT = {
    "red":    "#FF4444",
    "orange": "#FF8800",
    "yellow": "#FFD700",
    "green":  "#44BB44",
    "blue":   "#4488FF",
    "purple": "#AA44FF",
}

APP_STYLESHEET = f"""
QWidget {{
    background-color: {BG_MAIN};
    color: {TEXT_PRIMARY};
    font-family: 'Segoe UI', sans-serif;
    font-size: 12px;
}}
QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: {BG_MAIN};
    border: none;
}}
QScrollBar:vertical {{
    background: {BG_PANEL};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: #444;
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {BG_PANEL};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: #444;
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QPushButton {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 10px;
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: #555;
}}
QPushButton:pressed {{
    background-color: #333;
}}
QPushButton:checked {{
    background-color: {ACCENT};
    color: white;
    border-color: {ACCENT};
}}
QCheckBox {{
    color: {TEXT_PRIMARY};
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid {BORDER};
    background: {BG_PANEL};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QLabel {{
    color: {TEXT_PRIMARY};
    background: transparent;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDER};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    background: {ACCENT};
    border-radius: 7px;
    margin: -5px 0;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
QMainWindow {{
    background-color: {BG_DEEP};
}}
"""
