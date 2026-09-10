import sys, subprocess, os, argparse, tempfile
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, QTimer

PROGRESS_FILE = os.path.join(tempfile.gettempdir(), "focalflow_progress.txt")

STYLESHEET = """
QWidget {
    background-color: #0a0b0d;
    font-family: "Consolas", monospace;
}
QLabel#title {
    color: #c8a84b;
    font-size: 22px;
    font-weight: bold;
    letter-spacing: 3px;
}
QLabel#sub {
    color: #636159;
    font-size: 11px;
    letter-spacing: 1px;
}
QProgressBar {
    background-color: #22232a;
    border: 1px solid #252628;
    border-radius: 3px;
    height: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #c8a84b;
    border-radius: 2px;
}
"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file")
    parser.add_argument("--in",          dest="in_frame")
    parser.add_argument("--out",         dest="out_frame")
    parser.add_argument("--timeline-in", dest="timeline_in")
    parser.add_argument("--track")
    parser.add_argument("--fps")
    parser.add_argument("--focal")
    args, _ = parser.parse_known_args()

    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)

    app = QApplication(sys.argv)

    win = QWidget()
    win.setWindowFlags(
        Qt.WindowType.FramelessWindowHint |
        Qt.WindowType.WindowStaysOnTopHint
    )
    win.setFixedSize(340, 120)
    win.setStyleSheet(STYLESHEET)

    lay = QVBoxLayout(win)
    lay.setContentsMargins(28, 24, 28, 24)
    lay.setSpacing(10)

    title = QLabel("FOCALFLOW")
    title.setObjectName("title")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(title)

    sub = QLabel("Loading clip…")
    sub.setObjectName("sub")
    sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(sub)

    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(0)
    bar.setFixedHeight(4)
    bar.setTextVisible(False)
    lay.addWidget(bar)

    screen = app.primaryScreen().geometry()
    win.move((screen.width() - win.width()) // 2,
             (screen.height() - win.height()) // 2)
    win.show()

    _closing = [False]

    def poll_progress():
        if _closing[0]:
            return
        try:
            with open(PROGRESS_FILE, "r") as f:
                parts = f.read().strip().split("/")
                if len(parts) == 2:
                    current, total = int(parts[0]), int(parts[1])
                    bar.setValue(int(current / max(1, total) * 100))
                    sub.setText(f"Loading frames…  {current} / {total}")
                    if current >= total:
                        _closing[0] = True
                        QTimer.singleShot(400, win.close)
                        QTimer.singleShot(400, app.quit)
        except:
            pass

    poll_timer = QTimer()
    poll_timer.timeout.connect(poll_progress)

    def launch():
        cmd = [
            args.focal,
            "--file",        args.file,
            "--in",          args.in_frame,
            "--out",         args.out_frame,
            "--timeline-in", args.timeline_in,
            "--track",       args.track,
            "--fps",         args.fps,
            "--hidden",
        ]
        subprocess.Popen(cmd)
        poll_timer.start(100)

        
    QTimer.singleShot(1, launch)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
