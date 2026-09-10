import sys, os, subprocess, traceback
import focal_paths

FOCAL_DIR   = focal_paths.get_install_dir()
PYTHON_PATH = focal_paths.get_python_path()
FOCAL_PATH  = focal_paths.get_focal_app_path()

if not FOCAL_DIR or not PYTHON_PATH:
    raise RuntimeError("FocalFlow is not installed. Run the installer first.")

LOG = os.path.join(FOCAL_DIR, "FocalFlow", "focal_launch_log.txt")
SPLASH_PATH = os.path.join(FOCAL_DIR, "splash_FocalFlow.py")

try:
    if "resolve" not in dir():
        fallback = focal_paths.resolve_scripting_modules_path()
        if fallback not in sys.path:
            sys.path.append(fallback)
        import DaVinciResolveScript as dvr
        resolve = dvr.scriptapp("Resolve")

    if resolve is None:
        raise RuntimeError("Could not connect to DaVinci Resolve.")

    selected = timeline.GetCurrentVideoItem()
    if selected is None:
        raise RuntimeError(
            "Could not get current clip. Make sure the playhead is over a clip "
            "and that clip's track is selected."
        )

    selected_track = 1
    track_count = timeline.GetTrackCount("video")
    for track_idx in range(1, track_count + 1):
        items = timeline.GetItemListInTrack("video", track_idx)
        if not items:
            continue
        for item in items:
            if item == selected:
                selected_track = track_idx
                break

    media = selected.GetMediaPoolItem()
    if media is None:
        raise RuntimeError("Selected clip has no media pool item.")

    props     = media.GetClipProperty()
    file_path = props.get("File Path", "")

    if not file_path or not os.path.isfile(file_path):
        raise RuntimeError(f"Source file not found:\n{file_path}")

    record_in  = selected.GetStart()
    record_out = selected.GetEnd()
    source_in  = selected.GetLeftOffset()
    clip_dur   = record_out - record_in
    source_out = source_in + clip_dur

    fps_raw = timeline.GetSetting("timelineFrameRate")
    fps_int = int(fps_raw)
    NTSC_MAP = {23: 24000/1001, 24: 24000/1001, 30: 30000/1001, 60: 60000/1001, 120: 120000/1001}
    fps = NTSC_MAP.get(fps_int, float(fps_int))

    timeline_in = record_in

    if not os.path.isfile(FOCAL_PATH):
        raise RuntimeError(f"FocalFlow not found at:\n{FOCAL_PATH}")
    if not os.path.isfile(PYTHON_PATH):
        raise RuntimeError(f"Python not found at:\n{PYTHON_PATH}")

    with open(LOG, "w") as f:
        f.write(f"Clip      : {os.path.basename(file_path)}\n")
        f.write(f"Source    : {file_path}\n")
        f.write(f"In frame  : {source_in}\n")
        f.write(f"Out frame : {source_out}\n")
        f.write(f"Clip dur  : {clip_dur}\n")
        f.write(f"Record in : {record_in}\n")
        f.write(f"Record out: {record_out}\n")
        f.write(f"FPS       : {fps}\n")
        f.write(f"Track     : {selected_track}\n")

    splash_cmd = [
        PYTHON_PATH, SPLASH_PATH,
        "--file",        file_path,
        "--in",          str(source_in),
        "--out",         str(source_out),
        "--timeline-in", str(timeline_in),
        "--track",       str(selected_track),
        "--fps",         str(fps),
        "--focal",       FOCAL_PATH,
    ]
    subprocess.Popen(splash_cmd)

    with open(LOG, "a") as f:
        f.write("FocalFlow launched.\n")

except Exception:
    with open(LOG, "a") as f:
        f.write(traceback.format_exc())
    raise
