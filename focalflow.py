#!/usr/bin/env python3


import sys, os, json, time, math, subprocess, threading, queue as _queue_mod
import numpy as np
import cv2
from pathlib import Path
import tempfile
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from license import read_activation, write_activation, TIER_FULL, TIER_TRIAL

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QFileDialog, QSplitter, QFrame,
    QStatusBar, QToolBar, QMessageBox, QProgressBar, QListWidget,
    QListWidgetItem, QSizePolicy, QDialog, QSpinBox,
    QDoubleSpinBox, QFormLayout, QDialogButtonBox, QScrollArea,
    QGroupBox, QCheckBox, QComboBox, QButtonGroup, QToolButton,
    QMenu, QScrollBar, QStyle
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QPoint, QPointF, QRect, QRectF,
    QSize, QObject, QMutex, QMutexLocker
)
from PyQt6.QtGui import (
    QImage, QPixmap, QPainter, QPen, QBrush, QColor, QFont,
    QIcon, QAction, QCursor, QTransform, QWheelEvent, QPolygonF
)

# ── Constants ─────────────────────────────────────────────────────────────────
PROGRESS_FILE = os.path.join(tempfile.gettempdir(), "focalflow_progress.txt")

BOKEH_DEFAULT_PT_R = 50  / 1920
BOKEH_DEFAULT_SR   = 117 / 1920
POINT_DEFAULT_PT_R = 20  / 1920
POINT_DEFAULT_SR   = 50  / 1920

TRACKER_BOKEH = "bokeh"
TRACKER_POINT = "point"

# ── Palette ───────────────────────────────────────────────────────────────────
BG_DARK      = "#0a0b0d"
BG_MID       = "#121315"
BG_PANEL     = "#181920"
BG_HOVER     = "#22232a"
ACCENT       = "#c8a84b"
ACCENT_DIM   = "#7a6428"
ACCENT2      = "#4b8fc8"
ACCENT3      = "#4bc87a"
TEXT_PRIMARY = "#e6e2d8"
TEXT_DIM     = "#636159"
TEXT_MUTED   = "#35342f"
GREEN        = "#4caf7d"
RED          = "#d95f5f"
YELLOW       = "#c8a84b"
BORDER       = "#252628"

POINT_COLORS = [
    QColor("#c8a84b"), QColor("#3ecfcf"), QColor("#5c9fe0"),
    QColor("#c05fdb"), QColor("#e07c5c"), QColor("#5aab6e"),
    QColor("#db5f8a"), QColor("#bf6e6e"),
]

# ── FFmpeg discovery ──────────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    _HERE = os.path.dirname(sys.executable)
else:
    _HERE = os.path.dirname(os.path.abspath(sys.argv[0]))
_PARENT = os.path.dirname(_HERE)

def _find_ffmpeg():
    import platform
    candidates = [
        os.path.join(_HERE,   "ffmpeg.exe"),
        os.path.join(_PARENT, "ffmpeg.exe"),
        os.path.join(_HERE,   "ffmpeg"),
        os.path.join(_PARENT, "ffmpeg"),
    ]
    if platform.system() == "Darwin":
        candidates += ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]
    candidates.append("ffmpeg")
    for candidate in candidates:
        if candidate == "ffmpeg" or os.path.isfile(candidate):
            return candidate
    return "ffmpeg"

FFMPEG = _find_ffmpeg()

def _find_ffprobe():
    import platform
    candidates = [
        FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"),
        FFMPEG.replace("ffmpeg", "ffprobe"),
    ]
    if platform.system() == "Darwin":
        candidates += ["/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"]
    candidates.append("ffprobe")
    for candidate in candidates:
        if candidate == "ffprobe" or os.path.isfile(candidate):
            return candidate
    return "ffprobe"

FFPROBE = _find_ffprobe()


_CFLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

PREFS_PATH = os.path.join(_HERE, "focal_prefs.json")
LOG_PATH   = os.path.join(_HERE, "focal_launch_log.txt")

FORMAT_OPTIONS = {
    "prores_4444":  {"label": "ProRes 4444",        "codec": "prores_ks", "profile": "4",         "pix_fmt": "yuv444p10le", "ext": "mov"},
    "prores_422hq": {"label": "ProRes 422 HQ",       "codec": "prores_ks", "profile": "3",         "pix_fmt": "yuv422p10le", "ext": "mov"},
    "prores_422":   {"label": "ProRes 422",         "codec": "prores_ks", "profile": "2",         "pix_fmt": "yuv422p10le", "ext": "mov"},
    "dnxhr_444":    {"label": "DNxHR 444",          "codec": "dnxhd",     "profile": "dnxhr_444", "pix_fmt": "yuv444p10le", "ext": "mov"},
    "dnxhr_hqx":    {"label": "DNxHR HQX",            "codec": "dnxhd",     "profile": "dnxhr_hqx", "pix_fmt": "yuv422p10le", "ext": "mov"},
    "h264":         {"label": "H.264",           "codec": "libx264",   "profile": None,        "pix_fmt": "yuv420p",     "ext": "mp4"},
}

def _log(msg):
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"{datetime.datetime.now().strftime('%H:%M:%S')}  {msg}\n")
    except Exception:
        pass


def _check_activation():
    tier = read_activation()
    if tier == TIER_FULL:
        return "full"
    if tier == TIER_TRIAL:
        return "trial"
    from PyQt6.QtWidgets import QApplication, QMessageBox
    app = QApplication(sys.argv)
    QMessageBox.critical(None, "FocalFlow — Not Activated",
        "FocalFlow is not activated on this machine.\n\n"
        "Please run install.exe and enter your license key.")
    sys.exit(1)

_ACTIVATION_MODE = _check_activation()
# ── Stylesheet ────────────────────────────────────────────────────────────────
STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_DARK}; color: {TEXT_PRIMARY};
    font-family: "SF Mono", "Fira Code", "Consolas", monospace; font-size: 12px;
}}
QMenuBar {{ background-color: {BG_MID}; color: {TEXT_PRIMARY};
           border-bottom: 1px solid {BORDER}; padding: 2px; }}
QMenuBar::item:selected {{ background-color: {BG_HOVER}; }}
QMenu {{ background-color: {BG_PANEL}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER}; }}
QMenu::item:selected {{ background-color: {BG_HOVER}; }}
QToolBar {{ background-color: {BG_MID}; border-bottom: 1px solid {BORDER};
           spacing: 6px; padding: 4px 10px; }}
QStatusBar {{ background-color: {BG_MID}; color: {TEXT_DIM};
             border-top: 1px solid {BORDER}; font-size: 11px; }}
QPushButton {{ background-color: {BG_PANEL}; color: {TEXT_PRIMARY};
              border: 1px solid {BORDER}; border-radius: 4px;
              padding: 6px 14px; font-size: 12px; }}
QPushButton:hover {{ background-color: {BG_HOVER}; border-color: {ACCENT_DIM}; }}
QPushButton:pressed {{ background-color: {BG_DARK}; }}
QPushButton:disabled {{ color: {TEXT_MUTED}; border-color: {TEXT_MUTED}; }}
QPushButton:checked {{ background-color: {BG_HOVER}; border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton#accent {{ background-color: {ACCENT}; color: #110e00;
                      border: none; font-weight: bold; }}
QPushButton#accent:hover {{ background-color: #dabb5a; }}
QPushButton#accent:disabled {{ background-color: {ACCENT_DIM}; color: #4a3f10; }}
QPushButton#accent2 {{ background-color: {ACCENT2}; color: #00101a;
                       border: none; font-weight: bold; }}
QPushButton#accent2:hover {{ background-color: #6aaee8; }}
QPushButton#accent3 {{ background-color: {ACCENT3}; color: #001a08;
                       border: none; font-weight: bold; }}
QPushButton#accent3:hover {{ background-color: #6ae89e; }}
QPushButton#danger {{ background-color: transparent; color: {RED};
                      border-color: {RED}; }}
QPushButton#danger:hover {{ background-color: #2a1010; }}
QPushButton#stop {{ background-color: {RED}; color: white;
                    border: none; font-weight: bold; }}
QPushButton#stop:hover {{ background-color: #e87070; }}
QToolButton {{ background-color: transparent; color: {TEXT_PRIMARY};
               border: 1px solid transparent; border-radius: 4px; padding: 4px 8px; }}
QToolButton:hover {{ background-color: {BG_HOVER}; border-color: {BORDER}; }}
QToolButton:checked {{ background-color: {BG_HOVER}; border-color: {ACCENT}; color: {ACCENT}; }}
QSlider::groove:horizontal {{ background: {BG_HOVER}; height: 3px; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ACCENT}; width: 14px; height: 14px;
                              border-radius: 7px; margin: -6px 0; }}
QSlider::sub-page:horizontal {{ background: {ACCENT_DIM}; border-radius: 2px; }}
QLabel {{ color: {TEXT_PRIMARY}; }}
QLabel#dim {{ color: {TEXT_DIM}; font-size: 11px; }}
QLabel#section {{ color: {ACCENT}; font-size: 10px; letter-spacing: 2px; font-weight: bold; }}
QLabel#section2 {{ color: {ACCENT2}; font-size: 10px; letter-spacing: 2px; font-weight: bold; }}
QLabel#hd_ready {{ color: {ACCENT3}; font-size: 10px; letter-spacing: 1px; }}
QLabel#hd_loading {{ color: {YELLOW}; font-size: 10px; letter-spacing: 1px; }}
QSplitter::handle {{ background-color: {BORDER}; }}
QProgressBar {{ background-color: {BG_HOVER}; border: 1px solid {BORDER};
               border-radius: 3px; text-align: center; color: {TEXT_PRIMARY}; height: 16px; }}
QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 2px; }}
QListWidget {{ background-color: {BG_PANEL}; border: 1px solid {BORDER};
              border-radius: 4px; color: {TEXT_PRIMARY}; outline: none; }}
QListWidget::item {{ padding: 4px 8px; border-bottom: 1px solid {BORDER}; }}
QListWidget::item:selected {{ background-color: {BG_HOVER}; color: {ACCENT}; }}
QGroupBox {{ border: 1px solid {BORDER}; border-radius: 4px; margin-top: 18px;
            padding-top: 10px; color: {TEXT_DIM}; font-size: 10px; letter-spacing: 1px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; }}
QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {BG_PANEL}; border: 1px solid {BORDER};
    border-radius: 3px; color: {TEXT_PRIMARY}; padding: 3px 6px; }}
QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {ACCENT_DIM}; }}
QCheckBox {{ color: {TEXT_PRIMARY}; spacing: 6px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {BORDER};
                        border-radius: 3px; background: {BG_PANEL}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: {BG_PANEL}; width: 6px; border-radius: 3px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; min-height: 20px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""

# ─────────────────────────────────────────────────────────────────────────────
# PREFS
# ─────────────────────────────────────────────────────────────────────────────
def load_prefs():
    try:
        if os.path.isfile(PREFS_PATH):
            with open(PREFS_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {"output_format": "prores_4444"}

def save_prefs(prefs):
    try:
        with open(PREFS_PATH, "w") as f:
            json.dump(prefs, f, indent=2)
    except Exception as e:
        print(f"Could not save prefs: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# TRACK POINT
# ─────────────────────────────────────────────────────────────────────────────
class TrackPoint:
    def __init__(self, pid, x, y,
                 point_radius=None, search_radius=None,
                 tracker_type=TRACKER_BOKEH):
        self.id               = pid
        self.positions        = {}
        self.creation_frame   = 0
        self.enabled          = True
        self.color            = POINT_COLORS[pid % len(POINT_COLORS)]
        self.confidence       = {}
        self.tracker_type     = tracker_type
        self.initial_template = None
        self.point_radius  = point_radius  if point_radius  is not None else (
            BOKEH_DEFAULT_PT_R if tracker_type == TRACKER_BOKEH else POINT_DEFAULT_PT_R)
        self.search_radius = search_radius if search_radius is not None else (
            BOKEH_DEFAULT_SR   if tracker_type == TRACKER_BOKEH else POINT_DEFAULT_SR)

    def get_pos(self, frame):        return self.positions.get(frame)
    def set_pos(self, frame, x, y): self.positions[frame] = (x, y)

    def last_tracked_frame(self):
        return max(self.positions.keys()) if self.positions else self.creation_frame

    def clear_from(self, frame):
        for k in [k for k in self.positions  if k >= frame]: del self.positions[k]
        for k in [k for k in self.confidence if k >= frame]: del self.confidence[k]

    def point_radius_px(self, frame_w):  return max(2, int(self.point_radius  * frame_w))
    def search_radius_px(self, frame_w): return max(4, int(self.search_radius * frame_w))

    @staticmethod
    def norm_to_px(norm, ref_w): return max(1, int(norm * ref_w))
    @staticmethod
    def px_to_norm(px, ref_w):   return px / ref_w


# ─────────────────────────────────────────────────────────────────────────────
# SCRUB SLIDER
# ─────────────────────────────────────────────────────────────────────────────
class ScrubSlider(QSlider):
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            val = self.style().sliderValueFromPosition(
                self.minimum(), self.maximum(),
                int(e.position().x()), self.width())
            self.setValue(val)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            val = self.style().sliderValueFromPosition(
                self.minimum(), self.maximum(),
                int(e.position().x()), self.width())
            self.setValue(val)
        super().mouseMoveEvent(e)


# ─────────────────────────────────────────────────────────────────────────────
# VIDEO CANVAS
# ─────────────────────────────────────────────────────────────────────────────
class VideoCanvas(QWidget):
    pointPlaced          = pyqtSignal(float, float)
    pointMoved           = pyqtSignal(int, float, float)
    pointClicked         = pyqtSignal(int)
    pointRadiusChanged   = pyqtSignal(int, float, bool)
    trackerTypeToggled   = pyqtSignal(int)
    pivotMoved           = pyqtSignal(float, float)

    MODE_PLACE = "place"
    MODE_EDIT  = "edit"
    RING_HIT   = 12
    MOVE_ZONE  = 0.45
    PIVOT_HIT  = 14

    def __init__(self):
        super().__init__()
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #040506;")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._pixmap_raw        = None
        self._track_points      = []
        self._current_frame     = 0
        self._mode              = self.MODE_EDIT
        self._selected_point    = None
        self._drag_action       = None
        self._drag_pid          = None
        self._drag_start_w      = QPointF()
        self._pan_at_drag_start = QPointF()
        self._zoom              = 1.0
        self._pan               = QPointF(0.0, 0.0)
        self._in_frame          = 0
        self._out_frame         = 0
        self._show_range        = False
        self._pivot_nx          = 0.5
        self._pivot_ny          = 0.5
        self._show_pivot        = False
        self._dragging_pivot    = False

    # ── public ───────────────────────────────────────────────────────────
    def set_mode(self, mode):
        self._mode = mode
        self.setCursor(Qt.CursorShape.CrossCursor if mode == self.MODE_PLACE
                       else Qt.CursorShape.ArrowCursor)
        self.update()

    def set_frame(self, pixmap, frame_idx):
        self._pixmap_raw    = pixmap
        self._current_frame = frame_idx
        self.update()

    def set_track_points(self, pts): self._track_points = pts; self.update()
    def set_selected_point(self, pid): self._selected_point = pid; self.update()

    def set_range_overlay(self, in_f, out_f, total):
        self._in_frame = in_f; self._out_frame = out_f; self._show_range = True
        self.update()

    def reset_zoom(self): self._zoom = 1.0; self._pan = QPointF(0.0, 0.0); self.update()

    def set_pivot_visible(self, visible): self._show_pivot = visible; self.update()
    def set_pivot(self, nx, ny): self._pivot_nx = nx; self._pivot_ny = ny; self.update()
    def get_pivot(self): return self._pivot_nx, self._pivot_ny
    def reset_pivot_to_center(self): self._pivot_nx = 0.5; self._pivot_ny = 0.5; self.update()

    # ── geometry ─────────────────────────────────────────────────────────
    def _zoomed_image_rect(self):
        if not self._pixmap_raw:
            return QRectF(0, 0, self.width(), self.height())
        pw, ph = self._pixmap_raw.width(), self._pixmap_raw.height()
        cw, ch = float(self.width()), float(self.height())
        fit    = min(cw / pw, ch / ph)
        iw, ih = pw * fit * self._zoom, ph * fit * self._zoom
        return QRectF((cw - iw) / 2 + self._pan.x(),
                      (ch - ih) / 2 + self._pan.y(), iw, ih)

    def _img_to_canvas(self, nx, ny):
        r = self._zoomed_image_rect()
        return QPointF(r.x() + nx * r.width(), r.y() + ny * r.height())

    def _canvas_to_img(self, wx, wy):
        r = self._zoomed_image_rect()
        if r.width() == 0 or r.height() == 0: return 0.0, 0.0
        return (max(0.0, min(1.0, (wx - r.x()) / r.width())),
                max(0.0, min(1.0, (wy - r.y()) / r.height())))

    def _norm_r_to_canvas(self, norm_r):
        return norm_r * self._zoomed_image_rect().width()

    def _canvas_r_to_norm(self, canvas_r):
        r = self._zoomed_image_rect()
        return (canvas_r / r.width()) if r.width() > 0 else 0.0

    # ── paint ─────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#040506"))
        if not self._pixmap_raw:
            p.setPen(QColor(TEXT_DIM))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Open a video file  (Ctrl+O)")
            return
        r = self._zoomed_image_rect()
        p.drawPixmap(r, self._pixmap_raw, QRectF(self._pixmap_raw.rect()))

        if self._show_range:
            fi = self._current_frame
            if fi < self._in_frame or fi > self._out_frame:
                p.fillRect(self.rect(), QColor(0, 0, 0, 140))
                p.setPen(QColor(ACCENT2))
                f = QFont("Consolas", 11); f.setBold(True); p.setFont(f)
                p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                           "◀ before IN" if fi < self._in_frame else "after OUT ▶")

        self._draw_points(p)
        if self._show_pivot:
            self._draw_pivot(p)

    def _draw_pivot(self, p):
        sp     = self._img_to_canvas(self._pivot_nx, self._pivot_ny)
        cx, cy = sp.x(), sp.y()
        s      = 10
        p.setPen(QPen(QColor(0, 0, 0, 120), 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        diamond = [QPointF(cx, cy - s), QPointF(cx + s, cy),
                   QPointF(cx, cy + s), QPointF(cx - s, cy)]
        poly = QPolygonF(diamond)
        p.drawPolygon(poly)
        fill = QColor(ACCENT2); fill.setAlpha(60)
        p.setBrush(QBrush(fill))
        p.setPen(QPen(QColor(ACCENT2), 1.5))
        p.drawPolygon(poly)
        p.setBrush(QBrush(QColor(ACCENT2)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), 3.0, 3.0)
        p.setPen(QColor(ACCENT2))
        f = QFont("Consolas", 8); p.setFont(f)
        p.drawText(QPointF(cx + s + 4, cy + 4), "PIVOT")

    def _draw_points(self, p):
        frame = self._current_frame
        for pt in self._track_points:
            if not pt.enabled: continue
            pos = pt.get_pos(frame)
            if pos is None: continue
            sp       = self._img_to_canvas(pos[0], pos[1])
            spx, spy = sp.x(), sp.y()
            color    = pt.color
            conf     = pt.confidence.get(frame, 1.0)
            sel      = (self._selected_point == pt.id)
            sr       = self._norm_r_to_canvas(pt.search_radius)
            pr       = self._norm_r_to_canvas(pt.point_radius)
            if pt.tracker_type == TRACKER_POINT:
                self._draw_point_marker(p, spx, spy, pr, sr, color, conf, sel)
            else:
                self._draw_bokeh_marker(p, spx, spy, pr, sr, color, conf, sel)
            lc = QColor(color)
            lc.setAlpha(120 if self._selected_point != pt.id else 255)
            p.setPen(QPen(lc))
            f = QFont("Consolas", 9); f.setBold(True); p.setFont(f)
            suffix = "●" if pt.tracker_type == TRACKER_POINT else "◎"
            p.drawText(QPointF(spx + pr + 5, spy - 4), f"P{pt.id + 1}{suffix}")

    def _draw_bokeh_marker(self, p, spx, spy, pr, sr, color, conf, sel):
        sc = QColor(color); sc.setAlpha(50 if not sel else 160)
        p.setPen(QPen(sc, 1.5, Qt.PenStyle.DashLine)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(spx, spy), sr, sr)
        fc = QColor(color); fc.setAlpha(100 if not sel else 255)
        p.setPen(QPen(fc, 4 if sel else 1))
        p.drawEllipse(QPointF(spx, spy), pr, pr)
        if sel:
            white = QColor(255, 255, 255, 60)
            p.setPen(QPen(white, 2))
            p.drawEllipse(QPointF(spx, spy), pr + 6, pr + 6)
        cs = 10
        p.setPen(QPen(QColor(0, 0, 0, 120), 3))
        p.drawLine(QPointF(spx - cs, spy), QPointF(spx + cs, spy))
        p.drawLine(QPointF(spx, spy - cs), QPointF(spx, spy + cs))
        p.setPen(QPen(color, 1 + int(sel)))
        p.drawLine(QPointF(spx - cs, spy), QPointF(spx + cs, spy))
        p.drawLine(QPointF(spx, spy - cs), QPointF(spx, spy + cs))
        dc = color if conf > 0.5 else QColor(RED)
        p.setBrush(QBrush(dc)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(spx, spy), 4.0, 4.0)
        if sel:
            hc = QColor(color); hc.setAlpha(35); p.setBrush(QBrush(hc))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(spx, spy), max(8.0, pr * self.MOVE_ZONE),
                          max(8.0, pr * self.MOVE_ZONE))
        if conf < 0.8:
            wc = QColor(YELLOW if conf > 0.4 else RED); wc.setAlpha(160)
            p.setPen(QPen(wc, 1)); p.setBrush(Qt.BrushStyle.NoBrush)
            wr = int(18 * (1 - conf) + 6)
            p.drawEllipse(QPointF(spx, spy), wr, wr)

    def _draw_point_marker(self, p, spx, spy, pr, sr, color, conf, sel):
        sc = QColor(color); sc.setAlpha(40 if not sel else 150)
        p.setPen(QPen(sc, 1.5, Qt.PenStyle.DashLine)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(spx - sr, spy - sr, sr * 2, sr * 2))
        fc = QColor(color); fc.setAlpha(110 if not sel else 255)
        p.setPen(QPen(fc, 4 if sel else 1.5))
        p.drawRect(QRectF(spx - pr, spy - pr, pr * 2, pr * 2))
        if sel:
            white = QColor(255, 255, 255, 60)
            p.setPen(QPen(white, 2))
            p.drawRect(QRectF(spx - pr - 6, spy - pr - 6, pr * 2 + 12, pr * 2 + 12))
        dc = color if conf > 0.5 else QColor(RED)
        p.setBrush(QBrush(dc)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(spx, spy), 4.0, 4.0)
        if sel:
            hc = QColor(color); hc.setAlpha(35); p.setBrush(QBrush(hc))
            p.setPen(Qt.PenStyle.NoPen)
            sz = max(8.0, pr * self.MOVE_ZONE)
            p.drawRect(QRectF(spx - sz, spy - sz, sz * 2, sz * 2))
        if conf < 0.8:
            wc = QColor(YELLOW if conf > 0.4 else RED); wc.setAlpha(160)
            p.setPen(QPen(wc, 1)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(spx - (10 + 8 * (1 - conf)), spy - (10 + 8 * (1 - conf)),
                              20 + 16 * (1 - conf), 20 + 16 * (1 - conf)))

    def resizeEvent(self, e): super().resizeEvent(e); self.update()

    # ── hit testing ───────────────────────────────────────────────────────
    def _hit_pivot(self, wx, wy):
        if not self._show_pivot: return False
        sp = self._img_to_canvas(self._pivot_nx, self._pivot_ny)
        return math.hypot(wx - sp.x(), wy - sp.y()) <= self.PIVOT_HIT

    def _hit_test(self, wx, wy):
        for pt in reversed(self._track_points):
            if not pt.enabled: continue
            pos = pt.get_pos(self._current_frame)
            if pos is None: continue
            sp     = self._img_to_canvas(pos[0], pos[1])
            dist   = math.hypot(wx - sp.x(), wy - sp.y())
            pr     = self._norm_r_to_canvas(pt.point_radius)
            sr     = self._norm_r_to_canvas(pt.search_radius)
            move_r = max(8.0, pr * self.MOVE_ZONE)
            if pt.tracker_type == TRACKER_POINT:
                adx = abs(wx - sp.x()); ady = abs(wy - sp.y())
                if adx <= move_r and ady <= move_r: return 'move', pt
                on_feat = ((abs(adx - pr) <= self.RING_HIT and ady <= pr + self.RING_HIT) or
                           (abs(ady - pr) <= self.RING_HIT and adx <= pr + self.RING_HIT))
                if on_feat: return 'feat', pt
                on_srch = ((abs(adx - sr) <= self.RING_HIT and ady <= sr + self.RING_HIT) or
                           (abs(ady - sr) <= self.RING_HIT and adx <= sr + self.RING_HIT))
                if on_srch: return 'srch', pt
            else:
                if dist <= move_r:                  return 'move', pt
                if abs(dist - pr) <= self.RING_HIT: return 'feat', pt
                if abs(dist - sr) <= self.RING_HIT: return 'srch', pt
        return None, None

    # ── mouse ─────────────────────────────────────────────────────────────
    def wheelEvent(self, e: QWheelEvent):
        dy = e.angleDelta().y() or e.angleDelta().x() or e.pixelDelta().y() * 8
        if dy == 0: e.ignore(); return
        factor     = 1.15 if dy > 0 else 1.0 / 1.15
        mp         = e.position()
        nx_a, ny_a = self._canvas_to_img(mp.x(), mp.y())
        new_zoom   = max(0.15, min(30.0, self._zoom * factor))
        if not self._pixmap_raw:
            self._zoom = new_zoom; self.update(); e.accept(); return
        pw, ph = self._pixmap_raw.width(), self._pixmap_raw.height()
        cw, ch = float(self.width()), float(self.height())
        fit    = min(cw / pw, ch / ph)
        iw_new = pw * fit * new_zoom
        ih_new = ph * fit * new_zoom
        self._zoom = new_zoom
        self._pan  = QPointF(mp.x() - (cw - iw_new) / 2 - nx_a * iw_new,
                             mp.y() - (ch - ih_new) / 2 - ny_a * ih_new)
        self.update(); e.accept()

    def mousePressEvent(self, e):
        if not self._pixmap_raw: return
        wx, wy = e.position().x(), e.position().y()
        if e.button() == Qt.MouseButton.MiddleButton or (
                e.button() == Qt.MouseButton.LeftButton and
                e.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self._drag_action = 'pan'; self._drag_start_w = e.position()
            self._pan_at_drag_start = QPointF(self._pan)
            self.setCursor(Qt.CursorShape.ClosedHandCursor); return
        if (self._mode == self.MODE_EDIT and
                e.button() == Qt.MouseButton.LeftButton and self._hit_pivot(wx, wy)):
            self._dragging_pivot = True
            self.setCursor(Qt.CursorShape.SizeAllCursor); return
        if self._mode == self.MODE_PLACE and e.button() == Qt.MouseButton.LeftButton:
            nx, ny = self._canvas_to_img(wx, wy)
            self.pointPlaced.emit(nx, ny); return
        if self._mode == self.MODE_EDIT:
            action, pt = self._hit_test(wx, wy)
            if action == 'move' and e.button() == Qt.MouseButton.RightButton:
                self._selected_point = pt.id
                is_tracked = len(pt.positions) > 1
                if not is_tracked:
                    self.trackerTypeToggled.emit(pt.id)
                self.update(); return
            if action == 'move' and e.button() == Qt.MouseButton.LeftButton:
                self._drag_action = 'move'; self._drag_pid = pt.id
                self._selected_point = pt.id; self.pointClicked.emit(pt.id)
                self.update(); return
            if action in ('feat', 'srch') and e.button() in (
                    Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
                self._drag_action = action; self._drag_pid = pt.id
                self._drag_start_w = e.position()
                self._selected_point = pt.id; self.update(); return
            self._selected_point = None; self.update()

    def mouseMoveEvent(self, e):
        wx, wy = e.position().x(), e.position().y()
        if self._dragging_pivot:
            nx, ny = self._canvas_to_img(wx, wy)
            self._pivot_nx = nx; self._pivot_ny = ny
            self.pivotMoved.emit(nx, ny); self.update(); return
        if self._drag_action == 'pan':
            self._pan = self._pan_at_drag_start + (e.position() - self._drag_start_w)
            self.update(); return
        if self._drag_action == 'move' and self._drag_pid is not None:
            nx, ny = self._canvas_to_img(wx, wy)
            self.pointMoved.emit(self._drag_pid, nx, ny); return
        if self._drag_action in ('feat', 'srch') and self._drag_pid is not None:
            pt = next((x for x in self._track_points if x.id == self._drag_pid), None)
            if pt is None: return
            sp = self._img_to_canvas(*pt.get_pos(self._current_frame))
            if pt.tracker_type == TRACKER_POINT:
                new_canvas_r = max(abs(wx - sp.x()), abs(wy - sp.y()))
            else:
                new_canvas_r = math.hypot(wx - sp.x(), wy - sp.y())
            new_norm = max(0.005, self._canvas_r_to_norm(new_canvas_r))
            if self._drag_action == 'feat':
                pt.point_radius = min(new_norm, pt.search_radius - 0.005)
            else:
                pt.search_radius = max(pt.point_radius + 0.005, new_norm)
            self.pointRadiusChanged.emit(pt.id, new_norm, self._drag_action == 'srch')
            self.update()
        if self._show_pivot and self._mode == self.MODE_EDIT:
            self.setCursor(Qt.CursorShape.SizeAllCursor if self._hit_pivot(wx, wy)
                           else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, e):
        if self._dragging_pivot:
            self._dragging_pivot = False
            self.setCursor(Qt.CursorShape.ArrowCursor); return
        if e.button() == Qt.MouseButton.MiddleButton or self._drag_action == 'pan':
            self.setCursor(Qt.CursorShape.CrossCursor if self._mode == self.MODE_PLACE
                           else Qt.CursorShape.ArrowCursor)
        self._drag_action = None; self._drag_pid = None


# ─────────────────────────────────────────────────────────────────────────────
# TRACKER ALGORITHMS  (unchanged from working v4)
# ─────────────────────────────────────────────────────────────────────────────
def _gradient_mag(gray):
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    mx  = mag.max()
    return (mag / mx) if mx > 1e-6 else mag

def _make_ring_template(inner_r, outer_r):
    size = outer_r * 2 + 1
    tmpl = np.full((size, size), -0.5, dtype=np.float32)
    cv2.circle(tmpl, (outer_r, outer_r), outer_r,  1.0, -1)
    cv2.circle(tmpl, (outer_r, outer_r), inner_r, -0.5, -1)
    std = tmpl.std()
    return (tmpl - tmpl.mean()) / std if std > 1e-6 else tmpl

def _ncc_search(grad_win, tmpl):
    if tmpl.shape[0] > grad_win.shape[0] or tmpl.shape[1] > grad_win.shape[1]:
        return -1.0, (0, 0)
    std = grad_win.std()
    if std < 1e-6: return -1.0, (0, 0)
    norm_win = (grad_win - grad_win.mean()) / std
    res = cv2.matchTemplate(norm_win, tmpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    return float(max_val), max_loc

def _phase_shift(prev_gray, gray, cx, cy, search_r):
    pad = int(search_r * 1.5); h, w = gray.shape
    x0, y0 = max(0, int(cx - pad)), max(0, int(cy - pad))
    x1, y1 = min(w, int(cx + pad)), min(h, int(cy + pad))
    if x1 - x0 < 8 or y1 - y0 < 8: return 0.0, 0.0
    p  = prev_gray[y0:y1, x0:x1].astype(np.float32)
    c  = gray[y0:y1, x0:x1].astype(np.float32)
    sq = (max(p.shape[1], c.shape[1]), max(p.shape[0], c.shape[0]))
    p2 = cv2.resize(p, sq); c2 = cv2.resize(c, sq)
    (dx, dy), resp = cv2.phaseCorrelate(p2, c2)
    if resp < 0.05: return 0.0, 0.0
    return dx * (x1 - x0) / sq[0], dy * (y1 - y0) / sq[1]

def _track_bokeh_circle(prev_gray, gray, cx, cy, point_r_px, search_r_px):
    h, w = gray.shape
    ps_dx, ps_dy = _phase_shift(prev_gray, gray, cx, cy, search_r_px)
    max_shift    = search_r_px * 0.75
    ps_dx = float(np.clip(ps_dx, -max_shift, max_shift))
    ps_dy = float(np.clip(ps_dy, -max_shift, max_shift))
    seed_cx, seed_cy = cx + ps_dx, cy + ps_dy
    grad  = _gradient_mag(gray)
    slack = int(search_r_px * 0.5) + 6
    sw_r  = int(abs(ps_dx) + abs(ps_dy)) + slack
    x0 = max(0, int(seed_cx - sw_r)); y0 = max(0, int(seed_cy - sw_r))
    x1 = min(w, int(seed_cx + sw_r)); y1 = min(h, int(seed_cy + sw_r))
    grad_win   = grad[y0:y1, x0:x1]
    best_score = -1.0
    best_cx, best_cy = seed_cx, seed_cy
    for scale in [0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.30]:
        outer_r = max(4, int(point_r_px * scale))
        inner_r = max(1, int(outer_r * 0.55))
        tmpl    = _make_ring_template(inner_r, outer_r)
        score, loc = _ncc_search(grad_win, tmpl)
        if score > best_score:
            best_score = score; best_cx = x0 + loc[0] + outer_r; best_cy = y0 + loc[1] + outer_r
    x0b = max(0, int(cx - sw_r)); y0b = max(0, int(cy - sw_r))
    x1b = min(w, int(cx + sw_r)); y1b = min(h, int(cy + sw_r))
    grad_win_b = grad[y0b:y1b, x0b:x1b]
    for scale in [0.90, 1.00, 1.10]:
        outer_r = max(4, int(point_r_px * scale))
        inner_r = max(1, int(outer_r * 0.55))
        tmpl    = _make_ring_template(inner_r, outer_r)
        score, loc = _ncc_search(grad_win_b, tmpl)
        if score > best_score:
            best_score = score; best_cx = x0b + loc[0] + outer_r; best_cy = y0b + loc[1] + outer_r
    pt_lk = np.array([[[float(cx), float(cy)]]], dtype=np.float32)
    ws    = max(5, int(point_r_px) * 2 + 1)
    lk_p  = dict(winSize=(ws, ws), maxLevel=4,
                 criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    npts, status, err = cv2.calcOpticalFlowPyrLK(prev_gray, gray, pt_lk, None, **lk_p)
    if status is not None and status[0][0] == 1:
        lk_cx  = float(npts[0][0][0]); lk_cy = float(npts[0][0][1])
        lk_err  = float(err[0][0]) if err is not None else 30.0
        lk_conf = max(0.0, 1.0 - lk_err / 30.0)
        pt_back = np.array([[[lk_cx, lk_cy]]], dtype=np.float32)
        back_pts, back_status, _ = cv2.calcOpticalFlowPyrLK(gray, prev_gray, pt_back, None, **lk_p)
        if back_status is not None and back_status[0][0] == 1:
            back_err = math.hypot(float(back_pts[0][0][0]) - cx, float(back_pts[0][0][1]) - cy)
            if back_err < point_r_px * 0.5: lk_conf = min(1.0, lk_conf + 0.25)
            else: lk_conf *= max(0.0, 1.0 - back_err / (point_r_px * 2))
        if lk_conf > best_score:
            best_cx, best_cy = lk_cx, lk_cy; best_score = lk_conf * 0.85
    dist_from_prev = math.hypot(best_cx - cx, best_cy - cy)
    if dist_from_prev > search_r_px:
        alpha = search_r_px / dist_from_prev
        best_cx = cx + (best_cx - cx) * alpha; best_cy = cy + (best_cy - cy) * alpha
        best_score *= 0.5
    return (float(np.clip(best_cx, 0, w - 1)),
            float(np.clip(best_cy, 0, h - 1)),
            float(np.clip(best_score, 0.0, 1.0)))

def _track_point_lk(prev_gray, gray, cx, cy, point_r_px, search_r_px,
                    initial_template=None, current_frame=0):
    h, w = gray.shape
    ps_dx, ps_dy = _phase_shift(prev_gray, gray, cx, cy, search_r_px)
    max_shift = search_r_px * 0.75
    ps_dx = float(np.clip(ps_dx, -max_shift, max_shift))
    ps_dy = float(np.clip(ps_dy, -max_shift, max_shift))
    seed_cx = cx + ps_dx; seed_cy = cy + ps_dy
    ws = max(7, int(point_r_px) * 2 + 1)
    if ws % 2 == 0: ws += 1
    ws   = min(ws, 63)
    lk_p = dict(winSize=(ws, ws), maxLevel=4,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    pt_lk  = np.array([[[float(cx), float(cy)]]], dtype=np.float32)
    npts, status, err = cv2.calcOpticalFlowPyrLK(prev_gray, gray, pt_lk, None, **lk_p)
    lk_ok  = (status is not None and status[0][0] == 1)
    lk_cx  = float(npts[0][0][0]) if lk_ok else cx
    lk_cy  = float(npts[0][0][1]) if lk_ok else cy
    pt_seed = np.array([[[float(seed_cx), float(seed_cy)]]], dtype=np.float32)
    npts_s, status_s, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, pt_seed, None, **lk_p)
    seed_ok = (status_s is not None and status_s[0][0] == 1)
    slk_cx  = float(npts_s[0][0][0]) if seed_ok else seed_cx
    slk_cy  = float(npts_s[0][0][1]) if seed_ok else seed_cy

    def _backward_err(fcx, fcy):
        pt_back = np.array([[[fcx, fcy]]], dtype=np.float32)
        back_pts, back_status, _ = cv2.calcOpticalFlowPyrLK(gray, prev_gray, pt_back, None, **lk_p)
        if back_status is not None and back_status[0][0] == 1:
            return math.hypot(float(back_pts[0][0][0]) - cx, float(back_pts[0][0][1]) - cy)
        return search_r_px

    lk_back_err  = _backward_err(lk_cx,  lk_cy)  if lk_ok  else search_r_px
    slk_back_err = _backward_err(slk_cx, slk_cy) if seed_ok else search_r_px
    if slk_back_err < lk_back_err:
        best_lk_cx, best_lk_cy, best_back_err = slk_cx, slk_cy, slk_back_err
    else:
        best_lk_cx, best_lk_cy, best_back_err = lk_cx, lk_cy, lk_back_err
    lk_conf = max(0.0, 1.0 - best_back_err / max(1.0, point_r_px))

    tm_cx, tm_cy, tm_conf = cx, cy, 0.0
    if initial_template is not None and initial_template.size > 0:
        th, tw = initial_template.shape[:2]
        sr     = int(search_r_px)
        for search_origin, seed_name in [((int(seed_cx), int(seed_cy)), 'seed'),
                                          ((int(cx),     int(cy)),      'prev')]:
            sox, soy = search_origin
            x0s = max(0, sox - sr); y0s = max(0, soy - sr)
            x1s = min(w, sox + sr); y1s = min(h, soy + sr)
            search_win = gray[y0s:y1s, x0s:x1s]
            scales = [0.75, 0.85, 1.00, 1.15, 1.25] if seed_name == 'seed' else [0.90, 1.00, 1.10]
            for scale in scales:
                sw = max(4, int(tw * scale)); sh = max(4, int(th * scale))
                if sw % 2 == 0: sw += 1
                if sh % 2 == 0: sh += 1
                scaled_tmpl = cv2.resize(initial_template, (sw, sh))
                if search_win.shape[0] < sh or search_win.shape[1] < sw: continue
                res = cv2.matchTemplate(search_win.astype(np.float32),
                                        scaled_tmpl.astype(np.float32),
                                        cv2.TM_CCOEFF_NORMED)
                _, tm_val, _, tm_loc = cv2.minMaxLoc(res)
                if tm_val > tm_conf:
                    tm_conf = tm_val
                    tm_cx   = float(x0s + tm_loc[0] + sw // 2)
                    tm_cy   = float(y0s + tm_loc[1] + sh // 2)

    lk_weight = lk_conf * (1.0 - min(1.0, best_back_err / search_r_px))
    tm_weight = tm_conf * 0.95
    if tm_weight > lk_weight and tm_conf > 0.4:
        best_cx, best_cy = tm_cx, tm_cy; conf = tm_conf * 0.95
    else:
        best_cx, best_cy = best_lk_cx, best_lk_cy; conf = lk_conf

    dist_from_prev = math.hypot(best_cx - cx, best_cy - cy)
    if dist_from_prev > search_r_px:
        alpha   = search_r_px / dist_from_prev
        best_cx = cx + (best_cx - cx) * alpha; best_cy = cy + (best_cy - cy) * alpha
        conf   *= 0.5

    if current_frame % 5 == 0 and conf > 0.7:
        r   = int(point_r_px)
        x0t = max(0, int(best_cx) - r); y0t = max(0, int(best_cy) - r)
        x1t = min(w, int(best_cx) + r); y1t = min(h, int(best_cy) + r)
        patch = gray[y0t:y1t, x0t:x1t]
        if patch.size > 0:
            initial_template = patch.copy()

    return (float(np.clip(best_cx, 0, w - 1)),
            float(np.clip(best_cy, 0, h - 1)),
            float(np.clip(conf, 0.0, 1.0)),
            initial_template)


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — PREVIEW LOADER  (background QThread)
# ─────────────────────────────────────────────────────────────────────────────
class PreviewLoader(QObject):
    """Decodes a fast 1280px BGR preview in a background thread.

    Signals
    -------
    firstFrame(np.ndarray)   – emitted after the very first frame so the canvas
                               paints immediately
    progress(n, expected)    – frame counter update
    finished(frames, w, h)   – all frames decoded
    error(str)               – fatal failure
    """
    firstFrame = pyqtSignal(object)
    progress   = pyqtSignal(int, int)
    finished   = pyqtSignal(list, int, int)
    error      = pyqtSignal(str)

    PREV_W = 1280

    def __init__(self, path, source_fps, output_fps,
                 source_frame_in, source_frame_out, expected_frames):
        super().__init__()
        self._path            = path
        self._source_fps      = source_fps
        self._output_fps      = output_fps
        self._source_frame_in  = source_frame_in
        self._source_frame_out = source_frame_out
        self._expected        = expected_frames
        self._cancel          = False

    def cancel(self): self._cancel = True

    def run(self):
        import re as _re
        import io
        path    = self._path
        src_fps = self._source_fps

        # probe dimensions
        probe  = subprocess.run([FFMPEG, "-i", path],
                                capture_output=True, creationflags=_CFLAGS)
        stderr = probe.stderr.decode(errors="replace")
        dim_m  = _re.search(r"(\d{2,5})x(\d{2,5})", stderr)
        if not dim_m:
            self.error.emit(f"Cannot probe dimensions: {path}"); return
        src_w, src_h = int(dim_m.group(1)), int(dim_m.group(2))

        scale_w = self.PREV_W
        scale_h = int(src_h * self.PREV_W / src_w)
        if scale_h % 2 != 0: scale_h += 1
        bpf = scale_w * scale_h * 3

        cmd = [FFMPEG, "-threads", "4", "-accurate_seek"]
        if self._source_frame_in is not None and src_fps > 0:
            cmd += ["-ss", f"{self._source_frame_in / src_fps:.4f}"]
        cmd += ["-i", path]
        if (self._source_frame_out is not None and
                self._source_frame_in is not None and src_fps > 0):
            duration = (self._source_frame_out - self._source_frame_in + 2) / src_fps
            cmd += ["-t", f"{duration:.4f}"]
        cmd += ["-vf", f"scale={scale_w}:-2,fps={self._output_fps}",
                "-f", "rawvideo", "-pix_fmt", "bgr24", "-v", "quiet", "pipe:1"]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, creationflags=_CFLAGS)
        except Exception as ex:
            self.error.emit(f"FFmpeg launch failed: {ex}"); return

        buffered_stdout = io.BufferedReader(proc.stdout, buffer_size=16 * 1024 * 1024)  # ADD THIS

        frames = []
        n      = 0
        while not self._cancel:
            raw = proc.stdout.read(bpf)
            if len(raw) < bpf: break
            frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                (scale_h, scale_w, 3)).copy()
            frames.append(frame)
            n += 1
            if n == 1:
                self.firstFrame.emit(frame.copy())
            if n % 5 == 0:
                self.progress.emit(n, self._expected)

        proc.stdout.close(); proc.wait()
        if self._cancel: return
        self.progress.emit(n, self._expected)
        if not frames:
            self.error.emit(f"No frames decoded from: {path}"); return

        # Discard seek-safety buffer frames -- only the exact requested range
        # should ever become real content.
        if self._expected and len(frames) > self._expected:
            frames = frames[:self._expected]

        self.finished.emit(frames, scale_w, scale_h)


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — HD FRAME LOADER  (background QThread, sequential, reliable)
# ─────────────────────────────────────────────────────────────────────────────
class HDFrameLoader(QObject):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, video_path, total_frames, source_fps,
                 output_fps=None, frame_in=0, frame_out=None, pix_fmt="yuv444p10le"):
        super().__init__()
        self._path       = video_path
        self._total      = total_frames
        self._source_fps = source_fps
        self._output_fps = output_fps if output_fps is not None else source_fps
        self._frame_in   = frame_in
        self._frame_out  = frame_out
        self._pix_fmt    = pix_fmt
        self._cancel     = False
        self.hd_frames   = []
        self._lock       = threading.Lock()

    def cancel(self): self._cancel = True

    def get_frame(self, i):
        with self._lock:
            return self.hd_frames[i] if 0 <= i < len(self.hd_frames) else None

    def count(self):
        with self._lock:
            return len(self.hd_frames)

    def run(self):
        import re as _re
        import io

        w, h = 0, 0
        try:
            import platform as _plat
            ffprobe = FFPROBE
            probe = subprocess.run(
                [ffprobe, "-v", "quiet", "-print_format", "json",
                 "-show_streams", "-select_streams", "v:0", self._path],
                capture_output=True, creationflags=_CFLAGS)
            data   = json.loads(probe.stdout.decode(errors="replace"))
            stream = data.get("streams", [{}])[0]
            w      = int(stream.get("width",  0))
            h      = int(stream.get("height", 0))
        except Exception:
            pass

        if w == 0 or h == 0:
            p = subprocess.run([FFMPEG, "-i", self._path],
                               capture_output=True, creationflags=_CFLAGS)
            m = _re.search(r"(\d{2,5})x(\d{2,5})", p.stderr.decode(errors="replace"))
            if not m:
                self.error.emit("HD probe failed — cannot read video dimensions"); return
            w, h = int(m.group(1)), int(m.group(2))

        pix_fmt  = self._pix_fmt
        is_10bit = "10le" in pix_fmt
        dtype    = np.uint16 if is_10bit else np.uint8

        if pix_fmt == "yuv444p10le":
            bpf = w * h * 2 * 3
        elif pix_fmt == "yuv422p10le":
            bpf = w * h * 2 + (w // 2) * h * 2 * 2
        elif pix_fmt == "yuv420p":
            bpf = w * h + (w // 2) * (h // 2) * 2
        else:
            self.error.emit(f"Unsupported pix_fmt: {pix_fmt}"); return

        total = self._total
        t_start = self._frame_in / self._source_fps if self._source_fps > 0 else 0.0

        _log(f"HDFrameLoader: {w}x{h} fmt={pix_fmt} bpf={bpf} total={total}")

        with self._lock:
            self.hd_frames = [None] * total

        cores = min(os.cpu_count() or 4, 6)
        cmd = [FFMPEG, "-threads", str(cores), "-accurate_seek",
               "-ss", f"{t_start:.6f}", "-i", self._path]
        if self._frame_out is not None and self._source_fps > 0:
            duration = (self._frame_out - self._frame_in + 2) / self._source_fps
            cmd += ["-t", f"{duration:.4f}"]
        cmd += ["-vf", f"format={pix_fmt},fps={self._output_fps}",
                "-frames:v", str(total + 2),
                "-f", "rawvideo", "-pix_fmt", pix_fmt,
                "-v", "error", "pipe:1"]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, creationflags=_CFLAGS)
        except Exception as ex:
            self.error.emit(f"HD FFmpeg launch failed: {ex}"); return

        buffered_stdout = io.BufferedReader(proc.stdout, buffer_size=16 * 1024 * 1024)

        parse_q      = _queue_mod.Queue(maxsize=20)
        parse_errors = []

        def _parser():
            slot = 0
            while True:
                raw = parse_q.get()
                if raw is None: break
                try:
                    raw_arr = np.frombuffer(raw, dtype=dtype)
                    if pix_fmt == "yuv444p10le":
                        y = raw_arr[:h * w].reshape((h, w)).copy()
                        u = raw_arr[h*w : h*w*2].reshape((h, w)).copy()
                        v = raw_arr[h*w*2:].reshape((h, w)).copy()
                    elif pix_fmt == "yuv422p10le":
                        y = raw_arr[:h * w].reshape((h, w)).copy()
                        u = raw_arr[h*w : h*w + h*(w//2)].reshape((h, w//2)).copy()
                        v = raw_arr[h*w + h*(w//2):].reshape((h, w//2)).copy()
                    elif pix_fmt == "yuv420p":
                        y = raw_arr[:h * w].reshape((h, w)).copy()
                        u = raw_arr[h*w : h*w + (h//2)*(w//2)].reshape((h//2, w//2)).copy()
                        v = raw_arr[h*w + (h//2)*(w//2):].reshape((h//2, w//2)).copy()
                    with self._lock:
                        self.hd_frames[slot] = {"y": y, "u": u, "v": v,
                                                 "w": w, "h": h, "fmt": pix_fmt}
                    slot += 1
                    if slot % 30 == 0:
                        self.progress.emit(slot, total)
    
                      
                except Exception as ex:
                    parse_errors.append(str(ex)); break

        parse_thread = threading.Thread(target=_parser, daemon=True)
        parse_thread.start()

        def _reader():
            idx = 0
            try:
                while not self._cancel and idx < total:
                    raw = buffered_stdout.read(bpf)
                    if len(raw) < bpf:
                        break
                    parse_q.put(raw)
                    idx += 1
            finally:
                parse_q.put(None)

        read_thread = threading.Thread(target=_reader, daemon=True)
        read_thread.start()
        read_thread.join()

        parse_thread.join()
        buffered_stdout.close(); proc.wait()

        if self._cancel:
            self.finished.emit(); return

        with self._lock:
            while self.hd_frames and self.hd_frames[-1] is None:
                self.hd_frames.pop()
            actual = len(self.hd_frames)

        _log(f"HDFrameLoader: decoded {actual}/{total} frames")
        self.progress.emit(actual, total)
        self.finished.emit()

    
# ─────────────────────────────────────────────────────────────────────────────
# TRACKING WORKER  (background QThread — unchanged algorithm)
# ─────────────────────────────────────────────────────────────────────────────
class TrackingWorker(QObject):
    progress    = pyqtSignal(int, int)
    pointUpdate = pyqtSignal(int, int, float, float, float)
    trackFailed = pyqtSignal(int, int, str)
    finished    = pyqtSignal()
    FAIL_THRESHOLD = 0.66

    def __init__(self, frames, track_points, global_start, range_end, reverse=False):
        super().__init__()
        self.frames       = frames
        self.track_points = track_points
        self.global_start = global_start
        self.range_end    = range_end
        self.reverse      = reverse
        self._cancel      = False

    def cancel(self): self._cancel = True

    def run(self):
        if not self.frames: self.finished.emit(); return

        failed      = set()
        fail_streak = {}
        WARMUP      = 5

        if self.reverse:
            warmup_start = min(len(self.frames) - 1, self.global_start + WARMUP)
            prev_gray = cv2.cvtColor(self.frames[warmup_start], cv2.COLOR_BGR2GRAY)
            for fi in range(warmup_start - 1, self.global_start, -1):
                prev_gray = cv2.cvtColor(self.frames[fi], cv2.COLOR_BGR2GRAY)
        else:
            warmup_start = max(0, self.global_start - WARMUP)
            prev_gray = cv2.cvtColor(self.frames[warmup_start], cv2.COLOR_BGR2GRAY)
            for fi in range(warmup_start + 1, self.global_start):
                prev_gray = cv2.cvtColor(self.frames[fi], cv2.COLOR_BGR2GRAY)

        h, w = self.frames[0].shape[:2]
        frame_range = (range(self.global_start, self.range_end)
                       if not self.reverse else range(self.global_start, -1, -1))

        for fi in frame_range:
            if self._cancel: break
            frame = self.frames[fi]
            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # warm LK pyramid once per frame
            for warm_pt in self.track_points:
                if warm_pt.enabled:
                    warm_pos = warm_pt.get_pos(fi - 1)
                    if warm_pos is not None:
                        h, w = gray.shape
                        _dummy = np.array([[[warm_pos[0] * w, warm_pos[1] * h]]],
                                          dtype=np.float32)
                        lk_warm = dict(winSize=(21, 21), maxLevel=4,
                                       criteria=(cv2.TERM_CRITERIA_EPS |
                                                 cv2.TERM_CRITERIA_COUNT, 30, 0.01))
                        cv2.calcOpticalFlowPyrLK(prev_gray, gray, _dummy, None, **lk_warm)
                break

            for pt in self.track_points:
                if pt.id in failed:         continue
                if fi <= pt.creation_frame: continue
                if fi in pt.positions:      continue
                ref_frame = fi + 1 if self.reverse else fi - 1
                prev_pos  = pt.get_pos(ref_frame)
                if prev_pos is None:        continue

                px   = prev_pos[0] * w
                py   = prev_pos[1] * h
                pt_r = pt.point_radius_px(w)
                sr   = pt.search_radius_px(w)

                if pt.tracker_type == TRACKER_POINT:
                    npx, npy, conf, pt.initial_template = _track_point_lk(
                        prev_gray, gray, px, py, pt_r, sr,
                        initial_template=pt.initial_template, current_frame=fi)
                else:
                    npx, npy, conf = _track_bokeh_circle(prev_gray, gray, px, py, pt_r, sr)

                nx = float(np.clip(npx / w, 0.0, 1.0))
                ny = float(np.clip(npy / h, 0.0, 1.0))

                if conf < self.FAIL_THRESHOLD:
                    fail_streak[pt.id] = fail_streak.get(pt.id, 0) + 1
                    if fail_streak[pt.id] >= 8:
                        failed.add(pt.id)
                        pt.clear_from(fi - 3)
                        self.trackFailed.emit(pt.id, fi,
                            f"Point {pt.id + 1} lost at frame {fi} "
                            f"(conf={conf:.2f}) — reposition and re-track.")
                    self.pointUpdate.emit(pt.id, fi, prev_pos[0], prev_pos[1], 0.0)
                else:
                    fail_streak[pt.id] = 0
                    self.pointUpdate.emit(pt.id, fi, nx, ny, conf)

            prev_gray = gray
            self.progress.emit(fi, self.global_start if self.reverse else self.range_end)
            time.sleep(0)

        self.finished.emit()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3/4 — STABILIZATION WORKER  (background QThread, parallel warp)
# ─────────────────────────────────────────────────────────────────────────────
class StabilizationWorker(QObject):
    """Computes smoothed trajectory then warps every frame in parallel.

    The trajectory math is sequential (must be); the warpAffine calls are
    embarrassingly parallel so we use a ThreadPoolExecutor for that part.
    """
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(list, object, object, list, list)
    error    = pyqtSignal(str)

    def __init__(self, frames, track_points, fps, smoothing, extra_scale,
                 in_frame, out_frame,
                 correct_rotation=False, rotation_smoothing=5.0,
                 pivot_nx=0.5, pivot_ny=0.5):
        super().__init__()
        self.frames             = frames
        self.track_points       = track_points
        self.fps                = fps
        self.smoothing          = smoothing
        self.extra_scale        = extra_scale
        self.in_frame           = in_frame
        self.out_frame          = out_frame
        self.correct_rotation   = correct_rotation
        self.rotation_smoothing = rotation_smoothing
        self.pivot_nx           = pivot_nx
        self.pivot_ny           = pivot_ny
        self._cancel            = False

    def cancel(self): self._cancel = True

    def _smooth(self, curve, ks):
        k = np.ones(ks) / ks
        return np.convolve(np.pad(curve, ks // 2, mode='edge'), k,
                           mode='valid')[:len(curve)]

    @staticmethod
    def _min_scale(angle, dx, dy, w, h, pivot_px, pivot_py):
        if abs(angle) < 1e-7 and abs(dx) < 0.5 and abs(dy) < 0.5:
            return max((w + 2 * abs(dx)) / w, (h + 2 * abs(dy)) / h)
        cos_a = math.cos(angle); sin_a = math.sin(angle)
        required = 1.0
        for u, v in [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]:
            ux = u - dx - pivot_px; vy = v - dy - pivot_py
            rx =  ux * cos_a + vy * sin_a
            ry = -ux * sin_a + vy * cos_a
            if rx > 0 and (w - pivot_px) > 1e-6:
                required = max(required, rx / (w - pivot_px))
            elif rx < 0 and pivot_px > 1e-6:
                required = max(required, -rx / pivot_px)
            if ry > 0 and (h - pivot_py) > 1e-6:
                required = max(required, ry / (h - pivot_py))
            elif ry < 0 and pivot_py > 1e-6:
                required = max(required, -ry / pivot_py)
        return required

    def run(self):
        try:
            clip  = self.frames[self.in_frame:self.out_frame + 1]
            total = len(clip)
            if total == 0:
                self.error.emit("Empty clip range"); return

            if isinstance(clip[0], dict):
                h, w = clip[0]["h"], clip[0]["w"]
            else:
                h, w = clip[0].shape[:2]

            # ── per-frame translation ─────────────────────────────────────
            # ── per-frame translation ─────────────────────────────────────
            transforms = []
            for fi in range(1, total):
                if self._cancel: return
                wdx = wdy = tw = 0.0
                abs_fi = self.in_frame + fi
                for pt in self.track_points:
                    p0 = pt.get_pos(abs_fi - 1); p1 = pt.get_pos(abs_fi)
                    if p0 is None or p1 is None: continue
                    conf = pt.confidence.get(abs_fi, 0.5)
                    if conf < 0.1: continue
                    wdx += (p1[0] - p0[0]) * w * conf
                    wdy += (p1[1] - p0[1]) * h * conf
                    tw  += conf
                transforms.append((wdx / tw, wdy / tw) if tw > 0 else (0.0, 0.0))

            # Full-length trajectory (length == total), with frame 0 fixed at 0.0.
            # This keeps the correction curve properly aligned to frame indices
            # instead of being anchored one frame late.
            raw_traj_x = np.concatenate(([0.0], np.cumsum([t[0] for t in transforms])))
            raw_traj_y = np.concatenate(([0.0], np.cumsum([t[1] for t in transforms])))
            ks_t     = max(3, int(self.smoothing * total / 10) | 1)
            smooth_x = self._smooth(raw_traj_x, ks_t)
            smooth_y = self._smooth(raw_traj_y, ks_t)
            diff_x   = smooth_x - raw_traj_x
            diff_y   = smooth_y - raw_traj_y
            diff_x  -= diff_x[0]
            diff_y  -= diff_y[0]

            # ── per-frame rotation ─────────────────────────────────────────
            rot_angles = np.zeros(total - 1)
            if self.correct_rotation and len(self.track_points) >= 2:
                enabled_pts = list(self.track_points)
                for fi in range(1, total):
                    if self._cancel: return
                    abs_fi  = self.in_frame + fi
                    angles, weights = [], []
                    for i in range(len(enabled_pts)):
                        for j in range(i + 1, len(enabled_pts)):
                            ptA = enabled_pts[i]; ptB = enabled_pts[j]
                            a0 = ptA.get_pos(abs_fi - 1); a1 = ptA.get_pos(abs_fi)
                            b0 = ptB.get_pos(abs_fi - 1); b1 = ptB.get_pos(abs_fi)
                            if None in (a0, a1, b0, b1): continue
                            conf_a = ptA.confidence.get(abs_fi, 0.5)
                            conf_b = ptB.confidence.get(abs_fi, 0.5)
                            if conf_a < 0.1 or conf_b < 0.1: continue
                            prev_angle = math.atan2((b0[1] - a0[1]) * h, (b0[0] - a0[0]) * w)
                            curr_angle = math.atan2((b1[1] - a1[1]) * h, (b1[0] - a1[0]) * w)
                            delta = (curr_angle - prev_angle + math.pi) % (2 * math.pi) - math.pi
                            angles.append(delta); weights.append(conf_a * conf_b)
                    if angles:
                        tw2 = sum(weights)
                        rot_angles[fi - 1] = sum(a * wt for a, wt in zip(angles, weights)) / tw2

            raw_traj_rot = np.concatenate(([0.0], np.cumsum(rot_angles)))
            ks_r       = max(3, int(self.rotation_smoothing * total / 10) | 1)
            smooth_rot = self._smooth(raw_traj_rot, ks_r)
            diff_rot   = smooth_rot - raw_traj_rot
            diff_rot  -= diff_rot[0]

            pivot_px = self.pivot_nx * w
            pivot_py = self.pivot_ny * h

            # ── auto-scale to keep all frames inside the canvas ────────────
            
            auto_scale = 1.0
            for fi in range(total):
                angle = float(diff_rot[fi]) if self.correct_rotation else 0.0
                dx    = float(diff_x[fi])
                dy    = float(diff_y[fi])
                s     = self._min_scale(angle, dx, dy, w, h, pivot_px, pivot_py)
                auto_scale = max(auto_scale, s)
            scale = auto_scale + self.extra_scale * 0.05 + 0.02

            # ── pre-compute warp matrices ──────────────────────────────────
            matrices      = []
            matrix_params = []
            for fi in range(total):
                dx      = float(diff_x[fi])
                dy      = float(diff_y[fi])
                angle_r = float(diff_rot[fi]) if self.correct_rotation else 0.0
                matrix_params.append((dx, dy, angle_r, scale,
                                      self.pivot_nx, self.pivot_ny))
                M = cv2.getRotationMatrix2D((pivot_px, pivot_py),
                                            -math.degrees(angle_r), scale)
                M[0, 2] += dx
                M[1, 2] += dy
                matrices.append(M)


            # ── parallel warp ──────────────────────────────────────────────
            # Each frame is independent so ThreadPoolExecutor is safe here.
            # We write into pre-allocated slots (thread-safe: unique indices).
            out_frames   = [None] * total
            done_count   = [0]            # use list for mutability inside closure
            done_lock    = threading.Lock()
            warp_kw      = dict(flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_REFLECT_101)
            n_workers    = min(max(1, (os.cpu_count() or 4)), total)

            def _warp(fi):
                if self._cancel: return fi
                src = clip[fi]; M = matrices[fi]
                if isinstance(src, dict):
                    yw, yh = src["w"], src["h"]
                    y_out = cv2.warpAffine(src["y"], M, (yw, yh), **warp_kw)
                    u_out = cv2.warpAffine(src["u"], M, (yw, yh), **warp_kw)
                    v_out = cv2.warpAffine(src["v"], M, (yw, yh), **warp_kw)
                    out_frames[fi] = {"y": np.ascontiguousarray(y_out),
                                      "u": np.ascontiguousarray(u_out),
                                      "v": np.ascontiguousarray(v_out),
                                      "w": yw, "h": yh, "fmt": "yuv444p10le"}
                else:
                    out_frames[fi] = cv2.warpAffine(src, M, (w, h), **warp_kw)
                return fi

            with ThreadPoolExecutor(max_workers=n_workers) as pool:
                futures = {pool.submit(_warp, fi): fi for fi in range(total)}
                for fut in as_completed(futures):
                    if self._cancel:
                        break
                    try:
                        fut.result()
                    except Exception as ex:
                        raise RuntimeError(f"Warp error: {ex}")
                    with done_lock:
                        done_count[0] += 1
                    self.progress.emit(done_count[0], total)

            if self._cancel: return

            result = [f for f in out_frames if f is not None]
            self.finished.emit(result, diff_x, diff_y, matrices, matrix_params)

        except Exception as ex:
            import traceback
            _log(f"StabilizationWorker error: {traceback.format_exc()}")
            self.error.emit(str(ex))


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 5 — EXPORT WORKER  (background QThread, producer queue → FFmpeg stdin)
# ─────────────────────────────────────────────────────────────────────────────
class ExportWorker(QObject):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    QUEUE_DEPTH = 8

    def __init__(self, hd_loader, matrices, in_frame, fps, fmt_info, video_out,
             preview_w, preview_h):
        super().__init__()
        self._hd_loader = hd_loader
        self._matrices  = matrices
        self._in_frame  = in_frame
        self._fps       = fps
        self._fmt_info  = fmt_info
        self._out       = video_out
        self._preview_w = preview_w
        self._preview_h = preview_h
        self._cancel    = False

    def cancel(self): self._cancel = True

    def run(self):
        total    = len(self._matrices)
        fmt_info = self._fmt_info
        fps      = self._fps

        if total == 0:
            self.error.emit("No stabilization data"); return

        first = self._hd_loader.get_frame(self._in_frame)
        if first is None:
            self.error.emit("HD frames not available"); return

        w, h    = first["w"], first["h"]
        pix_fmt = first.get("fmt", "yuv444p10le")
        codec   = fmt_info.get("codec", "prores_ks")
        profile = fmt_info["profile"]
        cores   = min(os.cpu_count() or 4, 6)

        cmd = [FFMPEG, "-y",
               "-f", "rawvideo", "-vcodec", "rawvideo",
               "-pix_fmt", pix_fmt,
               "-s", f"{w}x{h}", "-r", str(fps), "-i", "pipe:0",
               "-vcodec", codec, "-threads", str(cores)]
        if codec == "prores_ks":
            cmd += ["-profile:v", profile, "-vendor", "apl0"]
        elif codec == "dnxhd":
            cmd += ["-profile:v", profile]
        elif codec == "libx264":
            cmd += ["-preset", "fast", "-crf", "23"]
        cmd += [self._out]

        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                    stderr=subprocess.PIPE, creationflags=_CFLAGS)
        except Exception as ex:
            self.error.emit(f"FFmpeg export launch failed: {ex}"); return

        stderr_chunks = []
        def _drain():
            for chunk in iter(lambda: proc.stderr.read(4096), b""):
                stderr_chunks.append(chunk)
            proc.stderr.close()
        threading.Thread(target=_drain, daemon=True).start()

        warp_kw = dict(flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)

        frames_written = 0
        
        try:
            for fi, (dx, dy, angle_r, scale, pivot_nx, pivot_ny) in enumerate(self._matrices):
                if self._cancel: break

                hd_frame = self._hd_loader.get_frame(self._in_frame + fi)
                if hd_frame is None:
                    self.error.emit(f"Missing HD frame {self._in_frame + fi}"); return

                frame_fmt = hd_frame.get("fmt", "yuv444p10le")
                fh, fw    = hd_frame["h"], hd_frame["w"]
                uw, uh    = hd_frame["u"].shape[1], hd_frame["u"].shape[0]

                # scale factors: preview→HD and luma→chroma
                hd_scale_x = fw / self._preview_w
                hd_scale_y = fh / self._preview_h
                sx = uw / fw
                sy = uh / fh

                pivot_px = pivot_nx * fw
                pivot_py = pivot_ny * fh
                M = cv2.getRotationMatrix2D((pivot_px, pivot_py), -math.degrees(angle_r), scale)
                M[0, 2] += dx * hd_scale_x
                M[1, 2] += dy * hd_scale_y

                cpivot_x = pivot_nx * fw * sx
                cpivot_y = pivot_ny * fh * sy
                Mc = cv2.getRotationMatrix2D((cpivot_x, cpivot_y), -math.degrees(angle_r), scale)
                Mc[0, 2] += dx * hd_scale_x * sx
                Mc[1, 2] += dy * hd_scale_y * sy

                y_out = cv2.warpAffine(hd_frame["y"], M,  (fw, fh), **warp_kw)
                u_out = cv2.warpAffine(hd_frame["u"], Mc, (uw, uh), **warp_kw)
                v_out = cv2.warpAffine(hd_frame["v"], Mc, (uw, uh), **warp_kw)


                if _ACTIVATION_MODE == "trial":
                    from PIL import Image, ImageDraw, ImageFont

                    pil_mask = Image.new("L", (fw, fh), 0)
                    draw     = ImageDraw.Draw(pil_mask)
                    try:
                        font = ImageFont.truetype("arial.ttf", size=int(fw / 12))
                    except:
                        font = ImageFont.load_default()

                    text = "FOCALFLOW"
                    bbox = draw.textbbox((0, 0), text, font=font)
                    tw   = bbox[2] - bbox[0]
                    th   = bbox[3] - bbox[1]
                    tx   = (fw - tw) // 2
                    ty   = (fh - th) // 2
                    draw.text((tx, ty), text, fill=255, font=font)

                    mask  = np.array(pil_mask).astype(np.float32) / 255.0
                    dtype = y_out.dtype

                    # Detect actual data range from the frame itself, not dtype max
                    actual_max = float(y_out.max())
                    actual_max = max(actual_max, 1.0)  # safety

                    y_f   = y_out.astype(np.float32)
                    mid   = actual_max * 0.5
                    y_f   = y_f * (1.0 - mask * 0.5) + mid * mask * 0.5
                    y_out = np.clip(y_f, 0, actual_max).astype(dtype)

                buf = (np.ascontiguousarray(y_out).tobytes() +
                       np.ascontiguousarray(u_out).tobytes() +
                       np.ascontiguousarray(v_out).tobytes())
                proc.stdin.write(buf)
                frames_written += 1
                self.progress.emit(frames_written, total)

        except Exception as ex:
            proc.stdin.close(); proc.wait()
            self.error.emit(f"Export error: {ex}"); return

        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.wait()

        if self._cancel: return

        if proc.returncode != 0:
            err_text = b"".join(stderr_chunks).decode(errors="replace")
            self.error.emit(f"FFmpeg failed (exit {proc.returncode}):\n{err_text}"); return

        self.finished.emit(self._out)

# ─────────────────────────────────────────────────────────────────────────────
# POINT ROW WIDGET
# ─────────────────────────────────────────────────────────────────────────────
class PointRowWidget(QWidget):
    def __init__(self, color_hex, parent=None):
        super().__init__(parent)
        self._color    = QColor(color_hex)
        self._selected = False

    def set_selected(self, selected):
        self._selected = selected
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        opacity = 1.0 if selected else 0.4
        for child in self.findChildren(QLabel):
            eff = QGraphicsOpacityEffect(child)
            eff.setOpacity(opacity)
            child.setGraphicsEffect(eff)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = QColor(self._color)
        if not self._selected: col.setAlpha(100)
        p.setBrush(QBrush(QColor(BG_PANEL if self._selected else BG_HOVER)))
        p.setPen(QPen(col, 2))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)


# ─────────────────────────────────────────────────────────────────────────────
# POINT LIST PANEL
# ─────────────────────────────────────────────────────────────────────────────
class PointListPanel(QWidget):
    pointSelected      = pyqtSignal(int)
    pointToggled       = pyqtSignal(int, bool)
    pointDeleted       = pyqtSignal(int)
    clearFromFrame     = pyqtSignal(int, int)
    trackerTypeChanged = pyqtSignal(int, str)
    resetPointOrigin   = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 10, 8, 8); lay.setSpacing(6)
        hdr = QLabel("TRACK POINTS"); hdr.setObjectName("section")
        lay.addWidget(hdr)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{ background: transparent; border: none; outline: none; }}
            QListWidget::item {{ border-radius: 6px; border: none;
                                padding: 0px; margin: 2px 0px; }}
            QListWidget::item:selected {{ background: transparent; }}
            QListWidget::item:hover   {{ background: transparent; }}
        """)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._context_menu)
        self.list_widget.setSpacing(2)
        lay.addWidget(self.list_widget)

        self._items            = {}
        self._type_btns        = {}
        self._selected_pid     = None
        self._current_frame_fn = lambda: 0
        self._get_track_points = lambda: []
        self.list_widget.currentItemChanged.connect(self._on_select)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_frame_getter(self, fn): self._current_frame_fn = fn

    def update_confidence(self, pt_id, conf):
        entry = self._items.get(pt_id)
        if not entry: return
        _, w, dot, lbl = entry
        if conf < 0.4:
            dot.setStyleSheet(f"color:{RED}; font-size:11px; background:transparent;")
        elif conf < 0.7:
            dot.setStyleSheet(f"color:{YELLOW}; font-size:11px; background:transparent;")

    def add_point(self, pt):
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, pt.id)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled
                      | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        w   = PointRowWidget(pt.color.name())
        row = QHBoxLayout(w)
        row.setContentsMargins(8, 6, 8, 6); row.setSpacing(8)
        dot = QLabel("◆")
        dot.setStyleSheet(f"color:{pt.color.name()}; font-size:11px; background:transparent;")
        row.addWidget(dot)
        lbl = QLabel(f"P{pt.id + 1}")
        lbl.setStyleSheet(f"color:{pt.color.name()}; font-size:12px; font-weight:bold; background:transparent;")
        row.addWidget(lbl)
        type_lbl = QLabel("BOK" if pt.tracker_type == TRACKER_BOKEH else "PT")
        type_lbl.setStyleSheet(f"color:{pt.color.name()}; font-size:10px; background:transparent;")
        row.addWidget(type_lbl)
        row.addStretch()
        chk = QCheckBox(); chk.setChecked(True)
        chk.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        chk.stateChanged.connect(lambda s, pid=pt.id: self.pointToggled.emit(pid, s == 2))
        row.addWidget(chk)
        item.setSizeHint(w.sizeHint() + QSize(0, 8))
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, w)
        self._items[pt.id]     = (item, w, dot, lbl)
        self._type_btns[pt.id] = type_lbl

    def _set_row_selected(self, pid, selected):
        entry = self._items.get(pid)
        if not entry: return
        _, w, _, _ = entry
        w.set_selected(selected)

    def update_type_btn(self, pid, tracker_type):
        lbl = self._type_btns.get(pid)
        if lbl: lbl.setText("PT" if tracker_type == TRACKER_POINT else "BOK")

    def _toggle_type(self, pid):
        lbl = self._type_btns.get(pid)
        if not lbl: return
        new_type = TRACKER_POINT if lbl.text() == "BOK" else TRACKER_BOKEH
        self.update_type_btn(pid, new_type)
        self.trackerTypeChanged.emit(pid, new_type)

    def _on_select(self, current, previous):
        if previous: self._set_row_selected(previous.data(Qt.ItemDataRole.UserRole), False)
        if current:
            pid = current.data(Qt.ItemDataRole.UserRole)
            self._selected_pid = pid
            self._set_row_selected(pid, True)
            self.pointSelected.emit(pid)
        else:
            self._selected_pid = None

    def _delete_selected(self):
        item = self.list_widget.currentItem()
        if item:
            pid = item.data(Qt.ItemDataRole.UserRole)
            self.list_widget.takeItem(self.list_widget.row(item))
            self._items.pop(pid, None); self._type_btns.pop(pid, None)
            self.pointDeleted.emit(pid)

    def _context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item: return
        pid    = item.data(Qt.ItemDataRole.UserRole)
        menu   = QMenu(self); menu.setStyleSheet(STYLESHEET)
        a_fwd  = menu.addAction("Clear track from current frame →")
        a_reset = menu.addAction("Reset — clear track, keep at frame 0")

        # Find the point to check if it's been tracked
        pt_obj = next((p for p in self._get_track_points() if p.id == pid), None)
        is_tracked = pt_obj is not None and len(pt_obj.positions) > 1

        if not is_tracked:
            a_tog = menu.addAction("Toggle tracker type (BOKEH ↔ POINT)")
        else:
            a_tog = None

        a_del  = menu.addAction("Delete point")
        chosen = menu.exec(self.list_widget.mapToGlobal(pos))
        frame  = self._current_frame_fn()
        if   chosen == a_fwd:   self.clearFromFrame.emit(pid, frame)
        elif chosen == a_reset: self.resetPointOrigin.emit(pid)
        elif a_tog and chosen == a_tog: self._toggle_type(pid)
        elif chosen == a_del:
            self.list_widget.setCurrentItem(item); self._delete_selected()

    def select_point(self, pid):
        entry = self._items.get(pid)
        if not entry: return
        self.list_widget.setCurrentItem(entry[0])

    def clear_all(self):
        self.list_widget.clear()
        self._items.clear(); self._type_btns.clear()
        self._selected_pid = None

    def _delete_by_pid(self, pid):
        entry = self._items.get(pid)
        if not entry: return
        self.list_widget.takeItem(self.list_widget.row(entry[0]))
        self._items.pop(pid, None); self._type_btns.pop(pid, None)


# ─────────────────────────────────────────────────────────────────────────────
# STAB TUNING PANEL
# ─────────────────────────────────────────────────────────────────────────────
class StabTuningPanel(QWidget):
    restabilize         = pyqtSignal(float, float, bool, float)
    exportVideo         = pyqtSignal()
    pivotResetRequested = pyqtSignal()
    deleteSolve         = pyqtSignal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10); lay.setSpacing(8)
        hdr = QLabel("STABILIZATION"); hdr.setObjectName("section2")
        lay.addWidget(hdr)

        lay.addWidget(self._dim("Translation smoothing"))
        row1 = QHBoxLayout()
        self.smooth_slider = QSlider(Qt.Orientation.Horizontal)
        self.smooth_slider.setRange(10, 400); self.smooth_slider.setValue(50)
        self.smooth_val = QLabel("5.0")
        self.smooth_val.setFixedWidth(32)
        self.smooth_val.setStyleSheet(f"color:{ACCENT}; font-size:11px;")
        self.smooth_slider.valueChanged.connect(lambda v: self.smooth_val.setText(f"{v / 10:.1f}"))
        self.smooth_slider.sliderReleased.connect(lambda: self.window().canvas.setFocus())
        row1.addWidget(self.smooth_slider); row1.addWidget(self.smooth_val)
        lay.addLayout(row1)
        lay.addWidget(self._dim("Higher = glassier, lower = more organic"))

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{BORDER};"); lay.addWidget(sep)

        lay.addWidget(self._dim("Scale margin (edge safety)"))
        row2 = QHBoxLayout()
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(0, 100); self.scale_slider.setValue(5)
        self.scale_val = QLabel("5%")
        self.scale_val.setFixedWidth(36)
        self.scale_val.setStyleSheet(f"color:{ACCENT}; font-size:11px;")
        self.scale_slider.valueChanged.connect(lambda v: self.scale_val.setText(f"{v}%"))
        row2.addWidget(self.scale_slider); row2.addWidget(self.scale_val)
        lay.addLayout(row2)
        lay.addWidget(self._dim("0% = min zoom. 100% = +5% buffer."))

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color:{BORDER};"); lay.addWidget(sep2)

        rot_hdr = QHBoxLayout()
        self.rot_check = QCheckBox("Correct rotation")
        self.rot_check.setToolTip("Requires 2+ track points.\nDrag ◆ on canvas to set pivot.")
        self.rot_check.stateChanged.connect(self._on_rot_toggled)
        rot_hdr.addWidget(self.rot_check); rot_hdr.addStretch()
        lay.addLayout(rot_hdr)

        self.rot_sub = QWidget()
        rsl = QVBoxLayout(self.rot_sub)
        rsl.setContentsMargins(0, 0, 0, 0); rsl.setSpacing(4)
        rsl.addWidget(self._dim("Rotation smoothing"))
        row3 = QHBoxLayout()
        self.rot_smooth_slider = QSlider(Qt.Orientation.Horizontal)
        self.rot_smooth_slider.setRange(10, 400); self.rot_smooth_slider.setValue(80)
        self.rot_smooth_val = QLabel("8.0")
        self.rot_smooth_val.setFixedWidth(32)
        self.rot_smooth_val.setStyleSheet(f"color:{ACCENT2}; font-size:11px;")
        self.rot_smooth_slider.valueChanged.connect(lambda v: self.rot_smooth_val.setText(f"{v / 10:.1f}"))
        row3.addWidget(self.rot_smooth_slider); row3.addWidget(self.rot_smooth_val)
        rsl.addLayout(row3)
        rsl.addWidget(self._dim("Higher = less rotation correction"))
        self.pivot_info = QLabel("◆ pivot: drag on canvas to reposition")
        self.pivot_info.setObjectName("dim"); self.pivot_info.setWordWrap(True)
        rsl.addWidget(self.pivot_info)
        reset_pivot_btn = QPushButton("Reset pivot to center")
        reset_pivot_btn.setFixedHeight(24)
        reset_pivot_btn.setStyleSheet(
            f"font-size:10px; padding:2px 8px; color:{ACCENT2}; "
            f"border-color:{ACCENT2}; background:transparent;")
        reset_pivot_btn.clicked.connect(self.pivotResetRequested.emit)
        rsl.addWidget(reset_pivot_btn)
        self.rot_sub.setVisible(False)
        lay.addWidget(self.rot_sub)

        self.rot_needs_pts_lbl = QLabel("⚠  Need 2+ track points for rotation")
        self.rot_needs_pts_lbl.setStyleSheet(f"color:{YELLOW}; font-size:10px;")
        self.rot_needs_pts_lbl.setVisible(False)
        lay.addWidget(self.rot_needs_pts_lbl)

        sep3 = QFrame(); sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet(f"color:{BORDER};"); lay.addWidget(sep3)

        self.stab_btn = QPushButton("↺  Re-stabilize")
        self.stab_btn.setStyleSheet(
            f"background:{ACCENT2}; color:#00101a; font-weight:bold; "
            f"border:none; padding:8px; border-radius:4px;")
        self.stab_btn.clicked.connect(self._emit_restabilize)
        lay.addWidget(self.stab_btn)

        self.delete_solve_btn = QPushButton("✕  Delete Solve")
        self.delete_solve_btn.setStyleSheet(
            f"background:transparent; color:{RED}; border:1px solid {RED}; "
            f"padding:8px; border-radius:4px;")
        self.delete_solve_btn.clicked.connect(self.deleteSolve.emit)
        lay.addWidget(self.delete_solve_btn)

        self.export_btn = QPushButton("✓  Save and Close")
        self.export_btn.setStyleSheet(
            f"background:{ACCENT}; color:#110e00; font-weight:bold; "
            f"border:none; padding:8px; border-radius:4px;")
        self.export_btn.clicked.connect(self.exportVideo.emit)
        lay.addWidget(self.export_btn)
        lay.addStretch()

        for child in self.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Space:
            return False
        return super().eventFilter(obj, event)

    def _dim(self, t):
        l = QLabel(t); l.setObjectName("dim"); l.setWordWrap(True); return l

    def _on_rot_toggled(self, state): self.rot_sub.setVisible(state == 2)

    def _emit_restabilize(self):
        self.restabilize.emit(self.get_smoothing(), self.get_extra_scale(),
                              self.get_correct_rotation(), self.get_rotation_smoothing())

    def show_rotation_warning(self, show): self.rot_needs_pts_lbl.setVisible(show)
    def get_smoothing(self):          return self.smooth_slider.value() / 10.0
    def get_extra_scale(self):        return self.scale_slider.value() / 100.0
    def get_correct_rotation(self):   return self.rot_check.isChecked()
    def get_rotation_smoothing(self): return self.rot_smooth_slider.value() / 10.0

    def set_enabled_all(self, en):
        self.stab_btn.setEnabled(en)
        self.export_btn.setEnabled(en)
        self.delete_solve_btn.setEnabled(en)


# ─────────────────────────────────────────────────────────────────────────────
# SETTINGS DIALOG
# ─────────────────────────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    def __init__(self, current_prefs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(430, 160)
        self.setStyleSheet(STYLESHEET)
        self._prefs = dict(current_prefs)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20); lay.setSpacing(12)
        form = QFormLayout(); form.setSpacing(10)
        self.format_combo = QComboBox()
        for key, info in FORMAT_OPTIONS.items():
            self.format_combo.addItem(info["label"], key)
        current_fmt = current_prefs.get("output_format", "prores_4444")
        for i in range(self.format_combo.count()):
            if self.format_combo.itemData(i) == current_fmt:
                self.format_combo.setCurrentIndex(i); break
        form.addRow(QLabel("Output format:"), self.format_combo)
        lay.addLayout(form); lay.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_save); btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _on_save(self):
        self._prefs["output_format"] = self.format_combo.currentData()
        save_prefs(self._prefs); self.accept()

    def get_prefs(self): return self._prefs


# ─────────────────────────────────────────────────────────────────────────────
# MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────
class FocalMainWindow(QMainWindow):
    SPIN_REF_W = 1920

    def __init__(self):
        super().__init__()
        suffix = " (Free Trial)" if _ACTIVATION_MODE == "trial" else ""
        self.setWindowTitle(f"FocalFlow v6{suffix}")
        screen = QApplication.primaryScreen().availableGeometry()
        w = int(screen.width()  * 0.66)
        h = int(screen.height() * 0.66)
        self.resize(w, h)
        self.move(screen.x() + (screen.width()  - w) // 2,
                  screen.y() + (screen.height() - h) // 2)
        self.setStyleSheet(STYLESHEET)

        # ── state ─────────────────────────────────────────────────────────
        self._video_path          = None
        self._preview_frames      = []
        self._preview_w           = 1
        self._fps                 = 24.0
        self._source_fps          = 24.0
        self._source_meta         = {}
        self._source_frame_in     = None
        self._source_frame_out    = None
        self._current_frame       = 0
        self._total_frames        = 0
        self._track_points        = []
        self._next_point_id       = 0
        self._canvas_mode         = VideoCanvas.MODE_EDIT
        self._stab_frames         = []       # HD-quality YUV stab frames for export
        self._stab_preview_frames = []       # 8-bit BGR preview stab frames
        self._view_mode           = "original"
        self._default_pt_r_norm   = BOKEH_DEFAULT_PT_R
        self._default_sr_norm     = BOKEH_DEFAULT_SR
        self._default_tracker     = TRACKER_BOKEH
        self._is_playing          = False
        self._play_timer          = QTimer()
        self._play_timer.timeout.connect(self._advance_frame)
        self._is_tracking         = False
        self._is_stabilizing      = False
        self._in_frame            = 0
        self._out_frame           = 0
        self._undo_stack          = []
        self._max_undo            = 40
        self._last_a_press        = 0.0
        self._stab_is_first_solve = False
        self._close_after_export  = False
        self._move_drag_snapped   = False
        self._ghost_point         = None
        self._resolve_timeline_in = None
        self._resolve_track       = None
        self._prefs               = load_prefs()
        self._stab_matrices = []
        self._stab_matrix_params = []

        # Stage 1 — preview loader
        self._preview_loader      = None
        self._preview_thread      = None
        self._preview_load_params = {}

        # Stage 2 — HD loader
        self._hd_loader  = None
        self._hd_thread  = None
        self._hd_ready   = False

        # Stage 3 — preview stabilization
        self._stab_thread  = None
        self._stabilizer   = None


        # Tracking
        self._tracking_thread = None
        self._tracker         = None

        # Stage 5 — export
        self._export_worker = None
        self._export_thread = None

        self._build_ui()
        self._build_menu()
        self.canvas.installEventFilter(self)
        self._update_ui_state()

    # ── UNDO ─────────────────────────────────────────────────────────────
    def _push_undo(self):
        snapshot = []
        for pt in self._track_points:
            s = TrackPoint(pt.id, 0, 0,
                           point_radius=pt.point_radius,
                           search_radius=pt.search_radius,
                           tracker_type=pt.tracker_type)
            s.positions        = dict(pt.positions)
            s.confidence       = dict(pt.confidence)
            s.creation_frame   = pt.creation_frame
            s.enabled          = pt.enabled
            s.color            = pt.color
            s.initial_template = (pt.initial_template.copy()
                                  if pt.initial_template is not None else None)
            snapshot.append(s)
        self._undo_stack.append((snapshot, self._next_point_id))
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)

    def _undo(self):
        if not self._undo_stack:
            self.status_label.setText("Nothing to undo."); return
        snapshot, next_id   = self._undo_stack.pop()
        self._track_points  = snapshot
        self._next_point_id = next_id
        self.point_list.clear_all()
        for pt in self._track_points:
            self.point_list.add_point(pt)
        self.point_list.set_frame_getter(lambda: self._current_frame)
        self.canvas.set_track_points(self._track_points)
        self.canvas.update()
        self.status_label.setText(f"Undo — {len(self._undo_stack)} step(s) remaining.")

    # ── UI BUILD ──────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        ml = QVBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0); ml.setSpacing(0)
        self._build_toolbar()

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(1)
        self._splitter.addWidget(self._build_left_panel())
        self._splitter.addWidget(self._build_center())
        self._splitter.addWidget(self._build_right_panel())
        self._splitter.setSizes([220, 940, 230])
        self._splitter.setStretchFactor(1, 1)
        ml.addWidget(self._splitter)

        self.status = QStatusBar(); self.setStatusBar(self.status)
        self.status_label = QLabel("Open a video file to begin  (Ctrl+O)")
        self.status.addWidget(self.status_label)

        self.quality_lbl = QLabel("")
        self.quality_lbl.setObjectName("hd_loading")
        self.status.addPermanentWidget(self.quality_lbl)

        self.format_status_lbl = QLabel("")
        self.format_status_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; margin-right:8px;")
        self.status.addPermanentWidget(self.format_status_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(220); self.progress_bar.setVisible(False)
        self.status.addPermanentWidget(self.progress_bar)

        self.stop_btn = QPushButton("■ Stop  [Esc]")
        self.stop_btn.setObjectName("stop"); self.stop_btn.setFixedWidth(110)
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._stop_operation)
        self.status.addPermanentWidget(self.stop_btn)

        self.frame_label = QLabel("")
        self.frame_label.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; margin-right:8px;")
        self.status.addPermanentWidget(self.frame_label)

    def _build_toolbar(self):
        tb = QToolBar("Main"); tb.setMovable(False); tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)

        def tbtn(text):
            b = QToolButton(); b.setText(text); tb.addWidget(b); return b

        tb.addWidget(self._tb_label("  Mode: "))
        self.edit_mode_btn = QToolButton()
        self.edit_mode_btn.setText("✥  Edit  [e]")
        self.edit_mode_btn.setCheckable(True); self.edit_mode_btn.setChecked(True)
        self.edit_mode_btn.clicked.connect(lambda: self._set_canvas_mode(VideoCanvas.MODE_EDIT))
        tb.addWidget(self.edit_mode_btn)

        self.place_mode_btn = QToolButton()
        self.place_mode_btn.setText("✛  Place  [a]")
        self.place_mode_btn.setCheckable(True)
        self.place_mode_btn.clicked.connect(lambda: self._set_canvas_mode(VideoCanvas.MODE_PLACE))
        tb.addWidget(self.place_mode_btn)
        tb.addSeparator()

        tb.addWidget(self._tb_label("  New pt: "))
        self.bokeh_tb = QToolButton(); self.bokeh_tb.setText("◎ Bokeh")
        self.bokeh_tb.setCheckable(True); self.bokeh_tb.setChecked(True)
        self.bokeh_tb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bokeh_tb.clicked.connect(lambda: self._set_default_tracker(TRACKER_BOKEH))
        tb.addWidget(self.bokeh_tb)

        self.point_tb = QToolButton(); self.point_tb.setText("● Point")
        self.point_tb.setCheckable(True)
        self.point_tb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.point_tb.clicked.connect(lambda: self._set_default_tracker(TRACKER_POINT))
        tb.addWidget(self.point_tb)
        tb.addSeparator()

        self.track_btn_tb = tbtn("▶  Track  [t]")
        self.track_btn_tb.clicked.connect(self.run_tracking)
        self.stab_btn_tb  = tbtn("⟳  Stabilize  [s]")
        self.stab_btn_tb.clicked.connect(self._smart_stabilize)
        tb.addSeparator()

        self.view_btn_tb    = tbtn("⇄  Toggle View  [v]")
        self.view_btn_tb.clicked.connect(self._toggle_view)
        self.zoom_reset_btn = tbtn("⊙  Reset Zoom  [z]")
        tb.addSeparator()

        hint = QLabel("  Mid-drag=pan  ·  Scroll=zoom  ·  Ring edge=resize  ·  Right-click pt=toggle tracker  ")
        hint.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        tb.addWidget(hint)

    def _tb_label(self, t):
        l = QLabel(t); l.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;"); return l

    def _set_default_tracker(self, t):
        self._default_tracker = t
        if t == TRACKER_BOKEH:
            self._default_pt_r_norm = BOKEH_DEFAULT_PT_R
            self._default_sr_norm   = BOKEH_DEFAULT_SR
        else:
            self._default_pt_r_norm = POINT_DEFAULT_PT_R
            self._default_sr_norm   = POINT_DEFAULT_SR
        self.bokeh_tb.blockSignals(True); self.point_tb.blockSignals(True)
        self.bokeh_tb.setChecked(t == TRACKER_BOKEH)
        self.point_tb.setChecked(t == TRACKER_POINT)
        self.bokeh_tb.blockSignals(False); self.point_tb.blockSignals(False)

    def _open_settings(self):
        dlg = SettingsDialog(self._prefs, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._prefs = dlg.get_prefs()
            fmt_label = FORMAT_OPTIONS[self._prefs['output_format']]['label']
            if self._preview_frames:
                QMessageBox.warning(
                    self,
                    "Reopen Clip to Apply",
                    f"Output format changed to {fmt_label}.\n\n"
                    f"The current clip was already loaded in the previous format.\n"
                    f"Close and reopen the clip for this setting to take effect."
                )
            self.status_label.setText(f"Settings saved — output: {fmt_label}")
            if self._hd_ready:
                self.format_status_lbl.setText(f"  {fmt_label}")

    def _build_left_panel(self):
        panel = QWidget(); panel.setFixedWidth(220)
        panel.setStyleSheet(f"background-color:{BG_PANEL}; border-right:1px solid {BORDER};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        self.point_list = PointListPanel()
        self.point_list.set_frame_getter(lambda: self._current_frame)
        self.point_list._get_track_points = lambda: self._track_points
        self.point_list.pointToggled.connect(self._toggle_point)
        self.point_list.pointDeleted.connect(self._delete_point)
        self.point_list.pointSelected.connect(self._on_point_list_select)
        self.point_list.clearFromFrame.connect(self._clear_point_from_frame)
        self.point_list.trackerTypeChanged.connect(self._on_tracker_type_changed_panel)
        self.point_list.resetPointOrigin.connect(self._reset_point_to_origin)
        lay.addWidget(self.point_list)

        acts = QWidget()
        acts.setStyleSheet(f"background:{BG_PANEL}; border-top:1px solid {BORDER};")
        al = QVBoxLayout(acts)
        al.setContentsMargins(8, 8, 8, 8); al.setSpacing(6)

        self.hide_all_btn = QPushButton("Hide All")
        self.hide_all_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.hide_all_btn.clicked.connect(self._toggle_hide_all)
        al.addWidget(self.hide_all_btn)

        self.restart_btn = QPushButton("↺  Restart")
        self.restart_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.restart_btn.setObjectName("danger")
        self.restart_btn.setToolTip(
            "Clear all points, tracking data, and stabilization.\n"
            "Returns to a clean state with the same clip loaded.")
        self.restart_btn.clicked.connect(self._restart_session)
        al.addWidget(self.restart_btn)
        lay.addWidget(acts)
        return panel

    def _build_center(self):
        w   = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        tab_bar = QWidget()
        tab_bar.setStyleSheet(f"background:{BG_MID}; border-bottom:1px solid {BORDER};")
        tab_bar.setFixedHeight(34)
        tl = QHBoxLayout(tab_bar)
        tl.setContentsMargins(8, 3, 8, 3); tl.setSpacing(4)

        ts = (f"QPushButton {{ background:transparent; color:{TEXT_DIM}; "
              f"border:1px solid {BORDER}; border-radius:3px; "
              f"padding:3px 12px; font-size:10px; letter-spacing:1px; }}"
              f"QPushButton:checked {{ background:{ACCENT}; color:#110e00; "
              f"border-color:{ACCENT}; font-weight:bold; }}")
        self.orig_tab = QPushButton("ORIGINAL"); self.orig_tab.setCheckable(True)
        self.orig_tab.setChecked(True); self.orig_tab.setStyleSheet(ts)
        self.orig_tab.clicked.connect(lambda: self._set_view("original"))

        self.stab_tab = QPushButton("STABILIZED"); self.stab_tab.setCheckable(True)
        self.stab_tab.setStyleSheet(ts); self.stab_tab.setEnabled(False)
        self.stab_tab.clicked.connect(lambda: self._set_view("stabilized"))

        self.mode_lbl = QLabel("")
        self.mode_lbl.setStyleSheet(f"color:{ACCENT}; font-size:11px; margin-left:8px;")
        tl.addWidget(self.orig_tab); tl.addWidget(self.stab_tab)
        tl.addWidget(self.mode_lbl); tl.addStretch()
        lay.addWidget(tab_bar)

        self.canvas = VideoCanvas()
        self.canvas.pointPlaced.connect(self._on_point_placed)
        self.canvas.pointMoved.connect(self._on_point_moved)
        self.canvas.pointClicked.connect(self._on_point_clicked)
        self.canvas.trackerTypeToggled.connect(self._on_tracker_type_toggled_canvas)
        self.canvas.pointRadiusChanged.connect(self._on_canvas_radius_changed)
        self.canvas.pivotMoved.connect(self._on_pivot_moved)
        lay.addWidget(self.canvas)
        self.zoom_reset_btn.clicked.connect(self.canvas.reset_zoom)
        lay.addWidget(self._build_transport())
        return w

    def _build_transport(self):
        bar = QWidget()
        bar.setStyleSheet(f"background:{BG_MID}; border-top:1px solid {BORDER};")
        outer = QVBoxLayout(bar)
        outer.setContentsMargins(12, 4, 12, 4); outer.setSpacing(2)
        row1 = QHBoxLayout(); row1.setSpacing(6)
        self.prev_btn = QPushButton("◀◀"); self.prev_btn.setFixedWidth(34)
        self.prev_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.prev_btn.clicked.connect(self._prev_frame)
        self.play_btn = QPushButton("▶"); self.play_btn.setFixedWidth(34)
        self.play_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.play_btn.clicked.connect(self._toggle_play)
        self.next_btn = QPushButton("▶▶"); self.next_btn.setFixedWidth(34)
        self.next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_btn.clicked.connect(self._next_frame)
        self.scrub = ScrubSlider(Qt.Orientation.Horizontal); self.scrub.setRange(0, 0)
        self.scrub.valueChanged.connect(self._scrub_changed)
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; min-width:96px;")
        row1.addWidget(self.prev_btn); row1.addWidget(self.play_btn)
        row1.addWidget(self.next_btn); row1.addWidget(self.scrub)
        row1.addWidget(self.time_label)
        outer.addLayout(row1)
        bar.setFixedHeight(40)
        return bar

    def _build_right_panel(self):
        panel = QWidget(); panel.setFixedWidth(230)
        panel.setStyleSheet(f"background:{BG_PANEL}; border-left:1px solid {BORDER};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        divider = QFrame(); divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color:{BORDER}; margin:0;")
        lay.addWidget(divider)

        self.stab_panel = StabTuningPanel()
        self.stab_panel.restabilize.connect(self._on_restabilize_signal)
        self.stab_panel.exportVideo.connect(self.export_file)
        self.stab_panel.pivotResetRequested.connect(self._reset_pivot)
        self.stab_panel.rot_check.stateChanged.connect(self._on_rot_check_changed)
        self.stab_panel.deleteSolve.connect(self._delete_solve)
        self.stab_panel.setVisible(False)
        lay.addWidget(self.stab_panel)

        self.stab_placeholder = QWidget()
        sp = QVBoxLayout(self.stab_placeholder)
        sp.setContentsMargins(10, 10, 10, 10); sp.setSpacing(6)
        sp.addWidget(self._section("STABILIZATION"))
        self.stab_btn_r = QPushButton("⟳  Stabilize  [s]")
        self.stab_btn_r.setObjectName("accent")
        self.stab_btn_r.clicked.connect(self._smart_stabilize)
        sp.addWidget(self.stab_btn_r)
        note = QLabel("Stabilizes clip range.\nTuning controls appear after first run.")
        note.setObjectName("dim"); note.setWordWrap(True); sp.addWidget(note)
        sp.addStretch()
        lay.addWidget(self.stab_placeholder)
        return panel

    def _section(self, t):
        l = QLabel(t); l.setObjectName("section"); return l

    def _build_menu(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")
        for lbl, sc, fn in [
            ("Open…",      "Ctrl+O", self.open_file),
            (None, None, None),
            ("Export As…", "Ctrl+E", self.export_file_as),
            (None, None, None),
            ("Settings…",  None,     self._open_settings),
            (None, None, None),
            ("Quit",       "Ctrl+Q", self.close),
        ]:
            if lbl is None: fm.addSeparator(); continue
            a = QAction(lbl, self)
            if sc: a.setShortcut(sc)
            a.triggered.connect(fn); fm.addAction(a)

        tm = mb.addMenu("Track")
        for lbl, sc, fn in [
            ("Edit Mode",        "e",  lambda: self._set_canvas_mode(VideoCanvas.MODE_EDIT)),
            ("Place Mode  [a]",  None, lambda: self._set_canvas_mode(VideoCanvas.MODE_PLACE)),
            (None, None, None),
            ("Run Tracking",     "t",  self.run_tracking),
            ("Stop [Esc]",       None, self._stop_operation),
            ("Clear All Points", None, self._clear_points),
        ]:
            if lbl is None: tm.addSeparator(); continue
            a = QAction(lbl, self)
            if sc: a.setShortcut(sc)
            a.triggered.connect(fn); tm.addAction(a)

        vm = mb.addMenu("View")
        for lbl, sc, fn in [
            ("Toggle Orig/Stab", "v",     self._toggle_view),
            ("Reset Zoom",       "z",     self.canvas.reset_zoom),
            (None, None, None),
            ("Previous Frame",   "Left",  self._prev_frame),
            ("Next Frame",       "Right", self._next_frame),
        ]:
            if lbl is None: vm.addSeparator(); continue
            a = QAction(lbl, self)
            if sc: a.setShortcut(sc)
            a.triggered.connect(fn); vm.addAction(a)

    # ── event filter ──────────────────────────────────────────────────────
    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self.canvas and event.type() == QEvent.Type.KeyPress:
            self.keyPressEvent(event); return True
        return super().eventFilter(obj, event)

    # ── rotation pivot ────────────────────────────────────────────────────
    def _on_rot_check_changed(self, state):
        checked = (state == 2)
        self.canvas.set_pivot_visible(checked)
        if checked: self._validate_rotation_pts()
        else: self.canvas.reset_pivot_to_center()

    def _on_pivot_moved(self, nx, ny):
        self.status_label.setText(
            f"Rotation pivot → ({nx:.3f}, {ny:.3f})  —  re-stabilize to apply")

    def _reset_pivot(self):
        self.canvas.reset_pivot_to_center()
        self.status_label.setText("Pivot reset to center — re-stabilize to apply.")

    def _validate_rotation_pts(self):
        needs_warn = len(self._track_points) < 2
        self.stab_panel.show_rotation_warning(needs_warn)
        return not needs_warn

    # ── canvas radius ─────────────────────────────────────────────────────
    def _on_canvas_radius_changed(self, pid, new_norm, is_search):
        px   = TrackPoint.norm_to_px(new_norm, self.SPIN_REF_W)
        kind = "search" if is_search else "feature"
        self.status_label.setText(f"P{pid + 1} {kind} radius → {px}px  (norm={new_norm:.4f})")

    # ── tracker type ──────────────────────────────────────────────────────
    def _on_tracker_type_toggled_canvas(self, pid):
        for pt in self._track_points:
            if pt.id == pid:
                pt.tracker_type = (TRACKER_POINT if pt.tracker_type == TRACKER_BOKEH
                                   else TRACKER_BOKEH)
                self.point_list.update_type_btn(pid, pt.tracker_type)
                self.status_label.setText(
                    f"P{pid + 1} → {'POINT' if pt.tracker_type == TRACKER_POINT else 'BOKEH'} tracker")
                self.canvas.update(); break

    def _on_tracker_type_changed_panel(self, pid, new_type):
        for pt in self._track_points:
            if pt.id == pid:
                pt.tracker_type = new_type
                self.status_label.setText(
                    f"P{pid + 1} → {'POINT' if new_type == TRACKER_POINT else 'BOKEH'} tracker")
                self.canvas.update(); break

    # ── hide/show all ─────────────────────────────────────────────────────
    def _toggle_hide_all(self):
        if not self._track_points: return
        all_hidden = (all(not pt.enabled for pt in self._track_points)
                      and not self.canvas._show_pivot)
        new_state = all_hidden
        for pt in self._track_points:
            pt.enabled = new_state
            entry = self.point_list._items.get(pt.id)
            if entry:
                _, w, _, _ = entry
                for child in w.findChildren(QCheckBox):
                    child.blockSignals(True); child.setChecked(new_state); child.blockSignals(False)
        if self.stab_panel.get_correct_rotation():
            self.canvas.set_pivot_visible(new_state)
        self._update_hide_all_btn(); self.canvas.update()

    def _update_hide_all_btn(self):
        if not self._track_points:
            self.hide_all_btn.setText("Hide All"); return
        all_hidden = (all(not pt.enabled for pt in self._track_points)
                      and not self.canvas._show_pivot)
        self.hide_all_btn.setText("Show All" if all_hidden else "Hide All")

    # ── restart ───────────────────────────────────────────────────────────
    def _restart_session(self):
        if QMessageBox.question(
            self, "Restart",
            "Clear all points, tracking data, and stabilization?\nThe clip will stay loaded.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        self._stop_operation()
        self._track_points = []; self._next_point_id = 0
        self._stab_matrices = []; self._undo_stack = []; self._stab_preview_frames = []
        self._view_mode = "original"
        self.point_list.clear_all()
        self.canvas.set_track_points([]); self.canvas.set_selected_point(None)
        self.canvas.reset_pivot_to_center(); self.canvas.set_pivot_visible(False)
        self.stab_panel.rot_check.setChecked(False); self.stab_panel.rot_sub.setVisible(False)
        self.stab_panel.smooth_slider.setValue(50); self.stab_panel.scale_slider.setValue(5)
        self.stab_panel.rot_smooth_slider.setValue(80)
        self.canvas.update()
        self.stab_tab.setEnabled(False); self.orig_tab.setChecked(True)
        self.stab_panel.setVisible(False); self.stab_placeholder.setVisible(True)
        self._show_frame(0); self._update_ui_state()
        self.status_label.setText("Restarted — clip loaded, all tracking and stabilization cleared.")

    def _reset_point_to_origin(self, pid):
        self._push_undo()
        for pt in self._track_points:
            if pt.id != pid: continue
            anchor_pos = pt.positions[min(pt.positions.keys())] if pt.positions else (0.5, 0.5)
            pt.positions = {0: anchor_pos}; pt.confidence = {}; pt.creation_frame = 0
            if self._preview_frames:
                frame_bgr = self._preview_frames[0]
                gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
                fh, fw = gray.shape
                px = int(anchor_pos[0] * fw); py = int(anchor_pos[1] * fh)
                r  = pt.point_radius_px(fw)
                patch = gray[max(0, py - r):min(fh, py + r), max(0, px - r):min(fw, px + r)]
                pt.initial_template = patch.copy() if patch.size > 0 else None
            self.status_label.setText(
                f"P{pid + 1} reset to frame 0 at ({anchor_pos[0]:.3f}, {anchor_pos[1]:.3f}) — "
                f"reposition if needed, then re-track.")
            break
        self.canvas.set_track_points(self._track_points); self.canvas.update()
        self._show_frame(0)

    # ── FILE — Stage 1: start preview load ───────────────────────────────
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", str(Path.home()),
            "Video Files (*.mp4 *.mov *.avi *.mkv *.mts *.m4v);;All Files (*)")
        if path: self._load_video(path)

    def _load_video(self, path, frame_in=None, frame_out=None, timeline_fps=None):
        import re as _re
        self.status_label.setText(f"Probing: {Path(path).name}…")
        QApplication.processEvents()

        # Cancel any running loads
        self._cancel_all_background()

        self._source_meta = self._probe_video_meta(path)
        self._source_fps  = self._source_meta.get("source_fps") or 24.0
        self._fps         = timeline_fps if timeline_fps is not None else self._source_fps

        meta_parts = []
        for k, label in [("color_primaries", "primaries"), ("color_trc", "trc"),
                          ("colorspace", "space"), ("pix_fmt", "pix")]:
            v = self._source_meta.get(k)
            if v: meta_parts.append(f"{label}={v}")
        if meta_parts: self.status_label.setText("  ".join(meta_parts))

        # Compute source frame range
        if timeline_fps is not None and frame_in is not None:
            source_frame_in  = round(frame_in  / timeline_fps * self._source_fps)
            source_frame_out = round(frame_out / timeline_fps * self._source_fps)
        else:
            source_frame_in  = frame_in
            source_frame_out = frame_out

        self._source_frame_in  = source_frame_in
        self._source_frame_out = source_frame_out

        # Estimate total frames from duration
        probe  = subprocess.run([FFMPEG, "-i", path],
                                capture_output=True, creationflags=_CFLAGS)
        stderr = probe.stderr.decode(errors="replace")
        dur_m  = _re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", stderr)
        total_hint = 500
        if dur_m:
            hh, mm, ss = int(dur_m.group(1)), int(dur_m.group(2)), float(dur_m.group(3))
            total_hint = int((hh * 3600 + mm * 60 + ss) * self._fps)

        expected_frames = ((frame_out - frame_in + 1)
                           if frame_in is not None and frame_out is not None
                           else total_hint)

        # Reset all state
        self._video_path          = path
        self._preview_frames      = []
        self._track_points        = []
        self._next_point_id       = 0
        self._stab_matrices = []
        self._stab_matrix_params = []
        self._stab_preview_frames = []
        self._hd_ready            = False
        self._undo_stack          = []
        self._current_frame       = 0
        self._in_frame            = 0
        self._out_frame           = 0
        self._view_mode           = "original"

        self.point_list.clear_all()
        self.canvas.reset_pivot_to_center(); self.canvas.set_pivot_visible(False)
        self.stab_panel.setVisible(False); self.stab_placeholder.setVisible(True)
        self.stab_tab.setEnabled(False); self.orig_tab.setChecked(True)
        self.quality_lbl.setText("")
        suffix = " (Free Trial)" if _ACTIVATION_MODE == "trial" else ""
        self.setWindowTitle(f"FocalFlow{suffix} — {Path(path).name}")
        self.progress_bar.setRange(0, max(1, expected_frames))
        self.progress_bar.setVisible(True)
        self.status_label.setText("Loading preview…")

        self._preview_load_params = {
            "source_frame_in":  source_frame_in,
            "source_frame_out": source_frame_out,
        }

        self._preview_loader = PreviewLoader(
            path, self._source_fps, self._fps,
            source_frame_in, source_frame_out, expected_frames)
        self._preview_thread = QThread()
        self._preview_loader.moveToThread(self._preview_thread)
        self._preview_thread.started.connect(self._preview_loader.run)
        self._preview_loader.firstFrame.connect(self._on_first_preview_frame)
        self._preview_loader.progress.connect(self._on_preview_progress)
        self._preview_loader.finished.connect(self._on_preview_finished)
        self._preview_loader.error.connect(self._on_preview_error)
        self._preview_thread.start()

    def _on_first_preview_frame(self, frame_bgr):
        """Paint the canvas the instant the first frame arrives."""
        rgb  = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.canvas.set_frame(QPixmap.fromImage(qimg.copy()), 0)

    def _on_preview_progress(self, n, expected):
        self.progress_bar.setValue(n)
        try:
            with open(PROGRESS_FILE, "w") as f:
                f.write(f"{n}/{expected}")
        except Exception:
            pass

    def _on_preview_error(self, msg):
        self._preview_thread.quit()
        self.progress_bar.setVisible(False)
        self._update_ui_state()
        QMessageBox.critical(self, "Error", msg)

    def _on_preview_finished(self, frames, scale_w, scale_h):
        self._preview_thread.quit()
        self.progress_bar.setVisible(False)
        try:
            with open(PROGRESS_FILE, "w") as f:
                f.write(f"{len(frames)}/{len(frames)}")
        except Exception:
            pass
        # ... rest of the method unchanged

        self.show()
        self.raise_()
        self.activateWindow()

        if not frames:
            QMessageBox.critical(self, "Error", f"No frames decoded:\n{self._video_path}")
            self._update_ui_state(); self.show(); return

        params = self._preview_load_params

        self._preview_frames = frames
        self._preview_w      = scale_w
        self._total_frames   = len(frames)
        self._current_frame  = 0
        self._in_frame       = 0
        self._out_frame      = self._total_frames - 1

        self.scrub.setRange(0, self._total_frames - 1); self.scrub.setValue(0)
        self.canvas.set_track_points(self._track_points)
        self.canvas.set_range_overlay(0, self._total_frames - 1, self._total_frames)
        self._show_frame(0); self._update_ui_state()

        self.status_label.setText(
            f"{Path(self._video_path).name}  ·  {self._total_frames} frames  ·  "
            f"{self._fps:.2f} fps  ·  preview ready  ·  HD loading…")
        self.quality_lbl.setText("⟳ HD loading…")
        self.quality_lbl.setObjectName("hd_loading")
        self.quality_lbl.style().unpolish(self.quality_lbl)
        self.quality_lbl.style().polish(self.quality_lbl)

        self.show(); self.raise_(); self.activateWindow()

        # Stage 2: start HD load now that we know _total_frames
        self._start_hd_load(self._video_path,
                            source_in=params.get("source_frame_in") or 0,
                            source_out=params.get("source_frame_out"))

    # ── Stage 2: HD load ─────────────────────────────────────────────────
    def _start_hd_load(self, path, source_in=0, source_out=None):
        if hasattr(self, '_hd_thread_raw') and self._hd_thread_raw and self._hd_thread_raw.is_alive():
            if self._hd_loader: self._hd_loader.cancel()
            self._hd_thread_raw.join(timeout=2.0)

        fmt_key  = self._prefs.get("output_format", "prores_4444")
        fmt_info = FORMAT_OPTIONS.get(fmt_key, FORMAT_OPTIONS["prores_4444"])
        pix_fmt  = fmt_info.get("pix_fmt", "yuv444p10le")

        self._hd_loader = HDFrameLoader(
            path, self._total_frames, self._source_fps,
            output_fps=self._fps, frame_in=source_in,
            frame_out=source_out, pix_fmt=pix_fmt)

        # Keep loader on main thread so signal emissions from worker threads
        # are queued safely via Qt's AutoConnection mechanism
        self._hd_loader.progress.connect(self._on_hd_progress, Qt.ConnectionType.QueuedConnection)
        self._hd_loader.finished.connect(self._on_hd_finished, Qt.ConnectionType.QueuedConnection)
        self._hd_loader.error.connect(
            lambda e: self.status_label.setText(f"HD error: {e}"),
            Qt.ConnectionType.QueuedConnection)

        self._hd_thread_raw = threading.Thread(target=self._hd_loader.run, daemon=True)
        self._hd_thread_raw.start()
        
    def _on_hd_progress(self, count, total):
        pct = int(count / total * 100) if total else 0
        self.quality_lbl.setText(f"⟳ HD {pct}%")
        self.quality_lbl.setObjectName("hd_loading")
        self.quality_lbl.style().unpolish(self.quality_lbl)
        self.quality_lbl.style().polish(self.quality_lbl)

    def _on_hd_finished(self):
        self._hd_ready = True
        fmt_key   = self._prefs.get("output_format", "prores_4444")
        fmt_info  = FORMAT_OPTIONS.get(fmt_key, FORMAT_OPTIONS["prores_4444"])
        fmt_label = fmt_info["label"]
        self.quality_lbl.setText("✓ HD ready")
        self.quality_lbl.setObjectName("hd_ready")
        self.quality_lbl.style().unpolish(self.quality_lbl)
        self.quality_lbl.style().polish(self.quality_lbl)
        self.format_status_lbl.setText(f"  {fmt_label}")
        _log("HD decode finished")
        if self._close_after_export and self._stab_matrix_params:
            self._write_output()

    # ── probe ─────────────────────────────────────────────────────────────
    def _probe_video_meta(self, path):
        try:
            import platform as _plat
            ffprobe = FFPROBE
            probe = subprocess.run(
                [ffprobe, "-v", "quiet", "-print_format", "json",
                 "-show_streams", "-select_streams", "v:0", path],
                capture_output=True, creationflags=_CFLAGS)
            data   = json.loads(probe.stdout.decode(errors="replace"))
            stream = data.get("streams", [{}])[0]

            def parse_rational(s):
                if s and "/" in s:
                    n, d = s.split("/")
                    return float(n) / float(d) if float(d) else None
                try: return float(s)
                except: return None

            return {
                "color_primaries": stream.get("color_primaries"),
                "color_trc":       stream.get("color_transfer"),
                "colorspace":      stream.get("color_space"),
                "color_range":     stream.get("color_range"),
                "pix_fmt":         stream.get("pix_fmt"),
                "source_fps":      parse_rational(stream.get("r_frame_rate")),
            }
        except Exception as e:
            _log(f"_probe_video_meta error: {e}")
            return {"color_primaries": None, "color_trc": None,
                    "colorspace": None, "color_range": None,
                    "pix_fmt": None, "source_fps": None}

    # ── EXPORT — Stage 5 ─────────────────────────────────────────────────
    def export_file(self):
        if not self._stab_preview_frames:
            QMessageBox.information(self, "Nothing to Export",
                                    "Stabilize the video first."); return
        if not self._stab_matrices:
            QMessageBox.information(self, "Nothing to Export",
                                    "Stabilize the video first."); return
        if not self._hd_ready:
            self._close_after_export = True
            self.stab_panel.set_enabled_all(False)
            self.quality_lbl.setText("⟳ HD loading — will export when ready…")
            return
        # HD is ready — queue export and let _on_export_finished close the window
        self._close_after_export = True
        self._write_output()

    def export_file_as(self):
        if not self._stab_preview_frames:
            QMessageBox.information(self, "Nothing to Export",
                                    "Stabilize the video first."); return
        fmt_key  = self._prefs.get("output_format", "prores_4444")
        fmt_info = FORMAT_OPTIONS.get(fmt_key, FORMAT_OPTIONS["prores_4444"])
        ext      = fmt_info.get("ext", "mov")
        default_name = f"focal_{Path(self._video_path).stem}.{ext}"
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Export Stabilized Video",
            os.path.join(os.path.dirname(self._video_path), default_name),
            f"Video Files (*.{ext});;All Files (*)")
        if not out_path: return
        self._write_output(override_path=out_path)

    def _write_output(self, override_path=None):
        if not self._stab_matrices: return

        # Cancel any previous export
        if self._export_thread and self._export_thread.isRunning():
            if self._export_worker: self._export_worker.cancel()
            self._export_thread.quit(); self._export_thread.wait(3000)

        fmt_key  = self._prefs.get("output_format", "prores_4444")
        fmt_info = FORMAT_OPTIONS.get(fmt_key, FORMAT_OPTIONS["prores_4444"])
        ext      = fmt_info.get("ext", "mov")

        if override_path:
            video_out  = override_path
            output_dir = os.path.dirname(override_path)
            out_name   = Path(override_path).stem
        else:
            source_dir = os.path.dirname(os.path.abspath(self._video_path))
            output_dir = os.path.join(source_dir, "FocalFlow")
            os.makedirs(output_dir, exist_ok=True)
            base     = Path(self._video_path).stem
            tl_in    = self._resolve_timeline_in or 0
            stamp    = datetime.datetime.now().strftime("%H%M%S")
            out_name = f"focal_{base}_t{tl_in}_{stamp}"
            video_out = os.path.join(output_dir, f"{out_name}.{ext}")

        self._export_out_name  = out_name
        self._export_out_dir   = output_dir
        self._export_video_out = video_out
        self._export_ext       = ext

        total_frames = len(self._stab_matrices)
        self.progress_bar.setRange(0, total_frames); self.progress_bar.setVisible(True)
        self.status_label.setText("Encoding stabilized output…")
        self.stab_panel.set_enabled_all(False); self._update_ui_state()

        preview_h = self._preview_frames[0].shape[0] if self._preview_frames else 720

        self._export_worker = ExportWorker(
            self._hd_loader, self._stab_matrix_params,
            self._in_frame, self._fps, fmt_info, video_out,
            self._preview_w, preview_h)
        self._export_thread = QThread()
        self._export_worker.moveToThread(self._export_thread)
        self._export_thread.started.connect(self._export_worker.run)
        self._export_worker.progress.connect(self._on_export_progress)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.error.connect(self._on_export_error)
        self._export_thread.start()

    def _on_export_progress(self, n, total):
        self.progress_bar.setValue(n)
        if n == total:
            self.status_label.setText("Finalizing file…")

    def _on_export_finished(self, video_out):
        self._export_thread.quit()
        self.progress_bar.setVisible(False)
        self.stab_panel.set_enabled_all(True); self._update_ui_state()


        out_name   = self._export_out_name
        output_dir = self._export_out_dir
        ext        = self._export_ext

        json_out  = os.path.join(output_dir, "focal_result.json")
        json_meta = {
            "video_path":   video_out,
            "json_path":    json_out,
            "timeline_in":  self._resolve_timeline_in,
            "track":        self._resolve_track,
            "frame_count":  len(self._stab_preview_frames),
            "timeline_fps": self._fps,
            "source_fps":   self._source_fps,
        }
        try:
            with open(json_out, "w") as f: json.dump(json_meta, f, indent=2)
        except Exception: pass
        try:
            pointer = os.path.join(_HERE, "focal_last_result.txt")
            with open(pointer, "w") as f: f.write(f"{json_out}\n{self._video_path}")
        except Exception: pass

        self.status_label.setText(
            f"✓ Saved → {out_name}.{ext}  |  Run place_result in Resolve.")
        _log(f"Export done: {video_out}")

        if self._close_after_export:
            self._close_after_export = False
            QTimer.singleShot(200, self.close)

    def _on_export_error(self, msg):
        self._export_thread.quit()
        self.progress_bar.setVisible(False)
        self.stab_panel.set_enabled_all(True); self._update_ui_state()
        QMessageBox.critical(self, "Export Failed", msg)

    def _delete_solve(self):
        self._stab_preview_frames = []
        self._stab_matrices = []
        self._stab_matrix_params = []
        self._view_mode = "original"
        self.stab_panel.smooth_slider.setValue(50); self.stab_panel.scale_slider.setValue(5)
        self.stab_panel.rot_smooth_slider.setValue(80); self.stab_panel.rot_check.setChecked(False)
        self.canvas.set_pivot_visible(False); self.canvas.reset_pivot_to_center()
        self.stab_tab.setEnabled(False); self.orig_tab.setChecked(True)
        self.stab_panel.setVisible(False); self.stab_placeholder.setVisible(True)
        self._show_frame(self._current_frame); self._update_ui_state()
        self.status_label.setText("Solve deleted — tracks preserved. Re-stabilize when ready.")    # ── close ─────────────────────────────────────────────────────────────


    def closeEvent(self, e):
        self._cancel_all_background()
        super().closeEvent(e)

    def _cancel_all_background(self):
        if self._preview_loader:
            try: self._preview_loader.cancel()
            except: pass
        if self._tracker:
            try: self._tracker.cancel()
            except: pass
        if self._stabilizer:
            try: self._stabilizer.cancel()
            except: pass
        if self._hd_loader:
            try: self._hd_loader.cancel()
            except: pass
        if self._export_worker:
            try: self._export_worker.cancel()
            except: pass
        for thread in [self._preview_thread, self._tracking_thread,
                       self._stab_thread, self._export_thread]:
            if thread and thread.isRunning():
                thread.quit(); thread.wait(2000)
        if hasattr(self, '_hd_thread_raw') and self._hd_thread_raw:
            self._hd_thread_raw.join(timeout=2.0)

    def _save_and_close(self):
        if not self._stab_matrix_params:
            return  # nothing to do, just ignore
        self._close_after_export = True
        if not self._hd_ready:
            self.stab_panel.set_enabled_all(False)
            self.quality_lbl.setText("⟳ HD loading — will export when ready…")
            return
        self._write_output()

    # ── MODE / POINTS ─────────────────────────────────────────────────────
    def _set_canvas_mode(self, mode):
        self._canvas_mode = mode; self.canvas.set_mode(mode)
        is_place = (mode == VideoCanvas.MODE_PLACE)
        self.place_mode_btn.setChecked(is_place)
        self.edit_mode_btn.setChecked(not is_place)
        self.mode_lbl.setText("● PLACE MODE — click to add point" if is_place else "")

    def _on_point_placed(self, nx, ny):
        if not self._preview_frames: return
        self._push_undo()
        pt = TrackPoint(self._next_point_id, nx, ny,
                        point_radius=self._default_pt_r_norm,
                        search_radius=self._default_sr_norm,
                        tracker_type=self._default_tracker)
        pt.creation_frame = self._current_frame
        pt.positions      = {self._current_frame: (nx, ny)}
        frame_bgr = self._preview_frames[self._current_frame]
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        fh, fw = gray.shape
        px = int(nx * fw); py = int(ny * fh); r = pt.point_radius_px(fw)
        patch = gray[max(0, py - r):min(fh, py + r), max(0, px - r):min(fw, px + r)]
        pt.initial_template = patch.copy() if patch.size > 0 else None
        self._track_points.append(pt); self._next_point_id += 1
        self.point_list.add_point(pt); self.point_list.select_point(pt.id)
        self.canvas.set_selected_point(pt.id)
        self.canvas.set_track_points(self._track_points); self.canvas.update()
        ttype = "BOKEH" if pt.tracker_type == TRACKER_BOKEH else "POINT"
        self.status_label.setText(
            f"P{pt.id + 1} [{ttype}] placed at frame {self._current_frame}  |  "
            f"feat r={pt.point_radius_px(self._preview_w)}px  "
            f"search r={pt.search_radius_px(self._preview_w)}px")
        if self.stab_panel.isVisible() and self.stab_panel.get_correct_rotation():
            self._validate_rotation_pts()

    def _on_point_moved(self, pid, nx, ny):
        if not self._move_drag_snapped:
            self._push_undo(); self._move_drag_snapped = True
        for pt in self._track_points:
            if pt.id == pid:
                pt.positions[self._current_frame] = (nx, ny); break
        self.canvas.update()

    def _on_point_clicked(self, pid):
        self._move_drag_snapped = False; self.point_list.select_point(pid)

    def _on_point_list_select(self, pid): self.canvas.set_selected_point(pid)

    def _toggle_point(self, pid, enabled):
        for pt in self._track_points:
            if pt.id == pid: pt.enabled = enabled; break
        self.canvas.update()
        if self.stab_panel.isVisible() and self.stab_panel.get_correct_rotation():
            self._validate_rotation_pts()
        self._update_hide_all_btn()

    def _delete_point(self, pid):
        self._push_undo()
        self._track_points = [p for p in self._track_points if p.id != pid]
        self.canvas.set_track_points(self._track_points); self.canvas.update()
        if self.stab_panel.isVisible() and self.stab_panel.get_correct_rotation():
            self._validate_rotation_pts()

    def _clear_points(self):
        if self._track_points:
            if QMessageBox.question(
                self, "Clear All", "Remove all track points?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) != QMessageBox.StandardButton.Yes:
                return
        self._push_undo()
        self._track_points = []; self._next_point_id = 0
        self.point_list.clear_all()
        self.canvas.set_track_points([]); self.canvas.update()

    def _clear_point_from_frame(self, pid, frame):
        self._push_undo()
        for pt in self._track_points:
            if pt.id == pid: pt.clear_from(frame); break
        self.canvas.update()
        self.status_label.setText(f"P{pid + 1}: cleared from frame {frame} — re-track to fill.")

    # ── TRACKING ──────────────────────────────────────────────────────────
    def run_tracking(self):
        if not self._preview_frames or self._is_tracking or self._is_stabilizing: return
        if not self._track_points:
            QMessageBox.information(self, "No Points",
                                    "Place at least one tracking point first  (press a)."); return
        self._push_undo(); self._set_canvas_mode(VideoCanvas.MODE_EDIT)
        range_end    = self._out_frame + 1
        global_start = range_end
        for pt in self._track_points:
            if not pt.enabled: continue
            last = pt.last_tracked_frame()
            if last < self._out_frame:
                global_start = min(global_start, max(last - 1, self._in_frame))
        if global_start >= range_end:
            self.status_label.setText("All points already tracked in this range."); return
        self._launch_tracking(global_start, range_end, reverse=False)

    def run_tracking_reverse(self):
        if not self._preview_frames or self._is_tracking or self._is_stabilizing: return
        if not self._track_points:
            QMessageBox.information(self, "No Points",
                                    "Place at least one tracking point first."); return
        global_start = self._current_frame
        range_end    = self._in_frame
        if global_start <= range_end:
            self.status_label.setText("Already at the start of range."); return
        self._push_undo(); self._set_canvas_mode(VideoCanvas.MODE_EDIT)
        self._launch_tracking(global_start, range_end, reverse=True)

    def _launch_tracking(self, global_start, range_end, reverse):
        import copy
        self._is_tracking = True
        direction = "backward" if reverse else "forward"
        self.status_label.setText(
            f"Tracking {direction} {global_start}→{range_end}…  Esc to stop")
        self.progress_bar.setRange(
            min(global_start, range_end), max(global_start, range_end))
        self.progress_bar.setVisible(True)
        self.stop_btn.setVisible(True); self._update_ui_state()

        working_points = list(self._track_points)
        if len(working_points) == 1:
            ghost = copy.deepcopy(working_points[0]); ghost.id = -1
            working_points.append(ghost); self._ghost_point = ghost
        else:
            self._ghost_point = None

        self._tracking_thread = QThread()
        self._tracker = TrackingWorker(
            self._preview_frames, working_points, global_start, range_end, reverse)
        self._tracker.moveToThread(self._tracking_thread)
        self._tracking_thread.started.connect(self._tracker.run)
        self._tracker.progress.connect(self._on_track_progress)
        self._tracker.pointUpdate.connect(self._on_point_update)
        self._tracker.trackFailed.connect(self._on_track_failed)
        self._tracker.finished.connect(self._on_tracking_done)
        self._tracking_thread.start()

    def _stop_operation(self):
        if self._is_tracking and self._tracker:
            self._tracker.cancel(); self.status_label.setText("Stopping…")
        if self._is_stabilizing and self._stabilizer:
            self._stabilizer.cancel(); self.status_label.setText("Stopping…")

    def _on_track_progress(self, frame, total):
        self.progress_bar.setValue(frame); self._show_frame(frame)

    def _on_point_update(self, pid, frame, nx, ny, conf):
        if pid == -1:
            if self._ghost_point:
                self._ghost_point.positions[frame] = (nx, ny)
                self._ghost_point.confidence[frame] = conf
            return
        for pt in self._track_points:
            if pt.id == pid:
                pt.positions[frame] = (nx, ny); pt.confidence[frame] = conf; break
        self.point_list.update_confidence(pid, conf)

    def _on_track_failed(self, pid, frame, reason):
        self.status_label.setText(f"⚠  {reason}")

    def _on_tracking_done(self):
        self._ghost_point = None
        self._tracking_thread.quit(); self._is_tracking = False
        self.progress_bar.setVisible(False); self.stop_btn.setVisible(False)
        self._update_ui_state()
        n = sum(1 for p in self._track_points if p.enabled)
        self.status_label.setText(f"Tracking done — {n} point(s).  Press s to stabilize.")

    # ── STABILIZATION — Stage 3 ───────────────────────────────────────────
    def _run_stabilization_default(self):
        self.run_stabilization(smoothing=5.0, extra_scale=0.05,
                               correct_rotation=False, rotation_smoothing=8.0)

    def _smart_stabilize(self):
        if self._stab_preview_frames:
            self._on_restabilize_signal(
                self.stab_panel.get_smoothing(), self.stab_panel.get_extra_scale(),
                self.stab_panel.get_correct_rotation(), self.stab_panel.get_rotation_smoothing())
        else:
            self._run_stabilization_default()

    def _on_restabilize_signal(self, smoothing, extra_scale, correct_rotation, rot_smooth):
        self.run_stabilization(smoothing, extra_scale, correct_rotation, rot_smooth)

    def run_stabilization(self, smoothing=None, extra_scale=None,
                          correct_rotation=False, rotation_smoothing=8.0):
        if not self._preview_frames or self._is_tracking or self._is_stabilizing: return
        if not any(len(pt.positions) > 1 for pt in self._track_points):
            QMessageBox.information(self, "No Track Data",
                                    "Track points before stabilizing."); return
        if self._stab_preview_frames:
            if smoothing   is None: smoothing        = self.stab_panel.get_smoothing()
            if extra_scale is None: extra_scale      = self.stab_panel.get_extra_scale()
            correct_rotation   = self.stab_panel.get_correct_rotation()
            rotation_smoothing = self.stab_panel.get_rotation_smoothing()
        if smoothing   is None: smoothing   = 5.0
        if extra_scale is None: extra_scale = 0.05
        if correct_rotation and len(self._track_points) < 2:
            QMessageBox.information(self, "Rotation needs 2+ points",
                                    "Add at least 2 track points to use rotation correction.")
            return

        pivot_nx, pivot_ny        = self.canvas.get_pivot()
        self._stab_is_first_solve = not bool(self._stab_preview_frames)
        self._is_stabilizing      = True
        self.status_label.setText(
            f"Stabilizing frames {self._in_frame}–{self._out_frame}…  Esc to stop")
        self.progress_bar.setRange(0, self._out_frame - self._in_frame + 1)
        self.progress_bar.setVisible(True)
        self.stop_btn.setVisible(True)
        self.stab_panel.set_enabled_all(False); self._update_ui_state()

        self._stab_thread = QThread()
        self._stabilizer  = StabilizationWorker(
            self._preview_frames, self._track_points, self._fps,
            smoothing, extra_scale, self._in_frame, self._out_frame,
            correct_rotation=correct_rotation, rotation_smoothing=rotation_smoothing,
            pivot_nx=pivot_nx, pivot_ny=pivot_ny)
        self._stabilizer.moveToThread(self._stab_thread)
        self._stab_thread.started.connect(self._stabilizer.run)
        self._stabilizer.progress.connect(
            lambda f, t: self.progress_bar.setValue(f) if t > 0 else None)
        self._stabilizer.finished.connect(self._on_stab_done)
        self._stabilizer.error.connect(self._on_stab_error)
        self._stab_thread.start()

    def _on_stab_error(self, msg):
        self._stab_thread.quit(); self._is_stabilizing = False
        self.progress_bar.setVisible(False); self.stop_btn.setVisible(False)
        self.stab_panel.set_enabled_all(True); self._update_ui_state()
        QMessageBox.critical(self, "Stabilization Error", msg)

    def _on_stab_done(self, out_frames, diff_x, diff_y, matrices, matrix_params):
        self._stab_matrices = matrices
        self._stab_matrix_params = matrix_params
        self._stab_thread.quit(); self._is_stabilizing = False
        self._stab_preview_frames = out_frames
        self.progress_bar.setVisible(False); self.stop_btn.setVisible(False)
        self.stab_panel.set_enabled_all(True); self.stab_tab.setEnabled(True)
        self.stab_panel.setVisible(True); self.stab_placeholder.setVisible(False)
        self._set_view("stabilized"); self._update_ui_state()
        self.canvas.setFocus()
        self.quality_lbl.setText("✓ HD ready" if self._hd_ready else "⟳ HD loading…")
        self.status_label.setText(
            "Stabilization done.  Adjust sliders → Re-stabilize, then Export.")
        _log(f"Preview stab done: {len(out_frames)} frames")   

    # ── PLAYBACK ──────────────────────────────────────────────────────────
    def _show_frame(self, idx):
        if not self._preview_frames: return
        idx = max(0, min(idx, self._total_frames - 1))
        self._current_frame = idx

        if self._view_mode == "stabilized" and self._stab_preview_frames:
            ci  = idx - self._in_frame
            bgr = (self._stab_preview_frames[ci]
                   if 0 <= ci < len(self._stab_preview_frames)
                   else self._preview_frames[idx])
        else:
            bgr = self._preview_frames[idx]

        if isinstance(bgr, dict) or (hasattr(bgr, 'dtype') and bgr.dtype == np.uint16):
            bgr = (bgr >> 8).astype(np.uint8) if not isinstance(bgr, dict) else bgr

        if not isinstance(bgr, np.ndarray):
            return

        rgb  = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.canvas.set_frame(QPixmap.fromImage(qimg.copy()), idx)
        self.canvas.set_range_overlay(self._in_frame, self._out_frame, self._total_frames)

        self.scrub.blockSignals(True); self.scrub.setValue(idx); self.scrub.blockSignals(False)
        secs = idx / self._fps; tot = self._total_frames / self._fps
        self.time_label.setText(
            f"{int(secs // 60)}:{int(secs % 60):02d} / {int(tot // 60)}:{int(tot % 60):02d}")
        self.frame_label.setText(f"  {idx + 1} / {self._total_frames}")

    def _scrub_changed(self, val): self._show_frame(val)
    def _prev_frame(self):         self._show_frame(self._current_frame - 1)
    def _next_frame(self):         self._show_frame(self._current_frame + 1)

    def _toggle_play(self):
        self._is_playing = not self._is_playing
        if self._is_playing:
            self.play_btn.setText("⏸")
            self._play_timer.start(max(1, int(1000 / self._fps)))
        else:
            self.play_btn.setText("▶"); self._play_timer.stop()

    def _advance_frame(self):
        nxt = self._current_frame + 1
        if nxt > self._out_frame: nxt = self._in_frame
        self._show_frame(nxt)

    def _set_view(self, mode):
        self._view_mode = mode
        self.orig_tab.setChecked(mode == "original")
        self.stab_tab.setChecked(mode == "stabilized")
        self._show_frame(self._current_frame)

    def _toggle_view(self):
        if self._stab_preview_frames:
            self._set_view("stabilized" if self._view_mode == "original" else "original")

    def _update_ui_state(self):
        hv   = bool(self._preview_frames)
        hs   = bool(self._stab_preview_frames)
        busy = self._is_tracking or self._is_stabilizing
        for w in [self.track_btn_tb, self.stab_btn_tb, self.edit_mode_btn, self.place_mode_btn]:
            w.setEnabled(hv and not busy)
        self.stab_tab.setEnabled(hs)
        self.view_btn_tb.setEnabled(hs)
        for w in [self.prev_btn, self.play_btn, self.next_btn]:
            w.setEnabled(hv)
        self.stab_panel.set_enabled_all(hs and not busy)

    # ── KEY EVENTS ────────────────────────────────────────────────────────
    def keyPressEvent(self, e):
        raw = e.key()

        if raw == Qt.Key.Key_Escape:
            self._stop_operation(); return

        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if raw == Qt.Key.Key_O: self.open_file(); return
            if raw == Qt.Key.Key_T: self.run_tracking_reverse(); return
            if raw == Qt.Key.Key_S: self._save_and_close(); return
            if raw == Qt.Key.Key_Z:
                if self._stab_is_first_solve and self._stab_preview_frames:
                    self._stab_is_first_solve = False; self._delete_solve()
                elif not self._stab_preview_frames:
                    self._undo()
                return

        if raw in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace, Qt.Key.Key_X):
            pid = self.canvas._selected_point
            if pid is not None:
                self._delete_point(pid); self.point_list._delete_by_pid(pid)
                self.canvas._selected_point = None; self.canvas.update()
            return

        if raw == Qt.Key.Key_Left:  self._prev_frame(); return
        if raw == Qt.Key.Key_Right: self._next_frame(); return
        if raw == Qt.Key.Key_Space: self._toggle_play(); return
        if raw == Qt.Key.Key_H:     self._toggle_hide_all(); return

        if raw == Qt.Key.Key_A:
            now        = time.time()
            double_tap = (now - self._last_a_press) < 0.5
            self._last_a_press = now
            if double_tap:
                new_type = (TRACKER_POINT if self._default_tracker == TRACKER_BOKEH
                            else TRACKER_BOKEH)
                self._set_default_tracker(new_type)
                self._set_canvas_mode(VideoCanvas.MODE_PLACE)
                type_name = "POINT" if new_type == TRACKER_POINT else "BOKEH"
                self.status_label.setText(f"Switched to {type_name} — place mode ready")
            else:
                self._set_canvas_mode(VideoCanvas.MODE_PLACE)
                self.canvas.setFocus()
            return

        if raw == Qt.Key.Key_S:
            self._smart_stabilize(); return

        k = raw | 0x20
        if   k == Qt.Key.Key_E: self._set_canvas_mode(VideoCanvas.MODE_EDIT)
        elif k == Qt.Key.Key_T: self.run_tracking()
        elif k == Qt.Key.Key_V: self._toggle_view()
        elif k == Qt.Key.Key_Z: self.canvas.reset_zoom()
        elif raw == Qt.Key.Key_Q:
            self._show_frame(self._in_frame); self.scrub.setValue(self._in_frame)
        else:
            super().keyPressEvent(e)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def main():
    import argparse, traceback
    _check_activation()
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--file",        default=None)
        parser.add_argument("--in",          default=None, dest="in_frame",    type=int)
        parser.add_argument("--out",         default=None, dest="out_frame",   type=int)
        parser.add_argument("--timeline-in", default=None, dest="timeline_in", type=int)
        parser.add_argument("--track",       default=None, dest="track",       type=int)
        parser.add_argument("--fps",         default=None, dest="fps",         type=float)
        parser.add_argument("--hidden", action="store_true", default=False)
        args, _ = parser.parse_known_args()

        app = QApplication(sys.argv)
        app.setApplicationName("FOCAL")
        win = FocalMainWindow()
        if not args.hidden:
            win.show()

        if args.file:
            win._resolve_timeline_in = args.timeline_in
            win._resolve_track       = args.track
            in_f  = args.in_frame  if args.in_frame  is not None else None
            out_f = args.out_frame if args.out_frame is not None else None
            win._load_video(args.file, frame_in=in_f, frame_out=out_f,
                            timeline_fps=args.fps)

        sys.exit(app.exec())

    except Exception:
        _log(f"\n--- FOCAL v6 crash ---\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    main()
