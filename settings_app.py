import sys, os, json

import focal_paths

INSTALL_DIR = focal_paths.get_install_dir()
APP_DIR     = os.path.join(INSTALL_DIR, "FocalFlow")
PREFS_PATH  = os.path.join(APP_DIR, "focal_prefs.json")

FORMAT_OPTIONS = {
    "prores_4444":  {"label": "ProRes 4444 (10-bit, lossless)",   "pix_fmt": "yuv444p10le"},
    "prores_422hq": {"label": "ProRes 422 HQ (10-bit, high quality)", "pix_fmt": "yuv422p10le"},
    "prores_422":   {"label": "ProRes 422 (10-bit, smaller files)",   "pix_fmt": "yuv422p10le"},
    "dnxhr_444":    {"label": "DNxHR 444 (10-bit, faster export)",    "pix_fmt": "yuv444p10le"},
    "dnxhr_hqx":    {"label": "DNxHR HQX (422, fastest export)",      "pix_fmt": "yuv422p10le"},
    "h264":         {"label": "H.264 (fast, small files, 8-bit)",     "pix_fmt": "yuv420p"},
}

def load_prefs():
    try:
        if os.path.isfile(PREFS_PATH):
            with open(PREFS_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {"output_format": "prores_4444"}

def save_prefs(prefs):
    os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
    with open(PREFS_PATH, "w") as f:
        json.dump(prefs, f, indent=2)

BG_DARK  = "#0a0b0d"
BG_MID   = "#121315"
BG_PANEL = "#181920"
BG_HOVER = "#22232a"
ACCENT   = "#c8a84b"
ACCENT_DIM = "#7a6428"
TEXT_PRIMARY = "#e6e2d8"
TEXT_DIM     = "#636159"
BORDER       = "#252628"
TEXT_MUTED   = "#35342f"

STYLESHEET = f"""
QDialog, QWidget {{
    background-color: {BG_DARK}; color: {TEXT_PRIMARY};
    font-family: "SF Mono", "Fira Code", "Consolas", monospace; font-size: 12px;
}}
QLabel {{ color: {TEXT_PRIMARY}; }}
QLabel#dim {{ color: {TEXT_DIM}; font-size: 11px; }}
QLabel#section {{ color: {ACCENT}; font-size: 10px; letter-spacing: 2px; font-weight: bold; }}
QComboBox {{
    background-color: {BG_PANEL}; border: 1px solid {BORDER};
    border-radius: 3px; color: {TEXT_PRIMARY}; padding: 4px 8px;
    min-height: 24px;
}}
QComboBox:focus {{ border-color: {ACCENT_DIM}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {BG_PANEL}; color: {TEXT_PRIMARY};
    border: 1px solid {BORDER}; selection-background-color: {BG_HOVER};
    selection-color: {ACCENT};
}}
QPushButton {{
    background-color: {BG_PANEL}; color: {TEXT_PRIMARY};
    border: 1px solid {BORDER}; border-radius: 4px;
    padding: 6px 14px; font-size: 12px;
}}
QPushButton:hover {{ background-color: {BG_HOVER}; border-color: {ACCENT_DIM}; }}
QPushButton:pressed {{ background-color: {BG_DARK}; }}
QPushButton#accent {{
    background-color: {ACCENT}; color: #110e00;
    border: none; font-weight: bold;
}}
QPushButton#accent:hover {{ background-color: #dabb5a; }}
"""

def main():
    from PyQt6.QtWidgets import (
        QApplication, QDialog, QVBoxLayout, QHBoxLayout,
        QFormLayout, QComboBox, QLabel, QPushButton, QFrame
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont

    app = QApplication(sys.argv)
    app.setApplicationName("FOCAL Settings")

    prefs = load_prefs()

    dlg = QDialog()
    dlg.setWindowTitle("FOCALFLOW— Output Settings")
    dlg.setFixedSize(460, 200)
    dlg.setStyleSheet(STYLESHEET)

    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(20, 20, 20, 20)
    lay.setSpacing(14)

    hdr = QLabel("OUTPUT FORMAT")
    hdr.setObjectName("section")
    lay.addWidget(hdr)

    info = QLabel(
        "This setting is read when a clip is loaded.\n"
        "Change it here before launching FocalFlow for the next clip."
    )
    info.setObjectName("dim")
    info.setWordWrap(True)
    lay.addWidget(info)

    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"color: {BORDER};")
    lay.addWidget(sep)

    form = QFormLayout()
    form.setSpacing(10)
    combo = QComboBox()
    for key, info_d in FORMAT_OPTIONS.items():
        combo.addItem(info_d["label"], key)

    current = prefs.get("output_format", "prores_4444")
    for i in range(combo.count()):
        if combo.itemData(i) == current:
            combo.setCurrentIndex(i)
            break

    fmt_lbl = QLabel("Format:")
    fmt_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
    form.addRow(fmt_lbl, combo)
    lay.addLayout(form)

    btn_row = QHBoxLayout()
    btn_row.setSpacing(8)
    btn_row.addStretch()

    cancel_btn = QPushButton("Cancel")
    cancel_btn.clicked.connect(dlg.reject)
    btn_row.addWidget(cancel_btn)

    save_btn = QPushButton("Save")
    save_btn.setObjectName("accent")
    save_btn.setDefault(True)
    save_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(save_btn)

    lay.addLayout(btn_row)

    if dlg.exec() == QDialog.DialogCode.Accepted:
        prefs["output_format"] = combo.currentData()
        save_prefs(prefs)

    sys.exit(0)

if __name__ == "__main__":
    main()
