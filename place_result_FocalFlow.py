import sys, os, json, traceback

try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _SCRIPT_DIR = os.path.expanduser("~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Comp")
if _SCRIPT_DIR not in sys.path:
    sys.path.append(_SCRIPT_DIR)

import focal_paths

_APP_DIR = os.path.join(focal_paths.get_install_dir(), "FocalFlow")
os.makedirs(_APP_DIR, exist_ok=True)
LOG          = os.path.join(_APP_DIR, "focal_launch_log.txt")
POINTER_FILE = os.path.join(_APP_DIR, "focal_last_result.txt")

TRANSFORM_PROPS = [
    "ZoomX", "ZoomY", "ZoomGang",
    "Pan", "Tilt",
    "RotationAngle",
    "AnchorPointX", "AnchorPointY",
    "Pitch", "Yaw",
    "FlipX", "FlipY",
    "CropLeft", "CropRight", "CropTop", "CropBottom",
    "CompositeMode", "Opacity",
    "RetimeProcess", "MotionEstimation",
    "ResizingPreset", "ResizeFilter",
]


def find_original_clip(timeline, record_in, track_idx):
    items = timeline.GetItemListInTrack("video", track_idx)
    if not items:
        return None
    for item in items:
        if item.GetStart() == record_in:
            return item
    for item in items:
        if item.GetStart() <= record_in < item.GetEnd():
            return item
    return None


def is_track_clear(timeline, track_idx, start_frame, end_frame):
    items = timeline.GetItemListInTrack("video", track_idx)
    if not items:
        return True
    for item in items:
        if item.GetStart() < end_frame and item.GetEnd() > start_frame:
            return False
    return True


def find_clear_track(timeline, above_track, start_frame, end_frame, log_f):
    target_track = above_track
    while True:
        current_track_count = timeline.GetTrackCount("video")
        if target_track > current_track_count:
            timeline.AddTrack("video")
            log_f.write(f"Created new video track V{target_track}\n")
        if is_track_clear(timeline, target_track, start_frame, end_frame):
            log_f.write(f"Found clear track: V{target_track}\n")
            return target_track
        log_f.write(f"V{target_track} occupied, trying V{target_track + 1}\n")
        target_track += 1


def copy_transforms(src_clip, dst_clip, log_f):
    copied  = []
    skipped = []
    for prop in TRANSFORM_PROPS:
        try:
            val = src_clip.GetProperty(prop)
            if val is not None:
                dst_clip.SetProperty(prop, val)
                copied.append(f"  {prop} = {val}")
        except Exception as ex:
            skipped.append(f"  {prop}: {ex}")
    log_f.write("Transforms copied:\n")
    for c in copied:
        log_f.write(c + "\n")
    if skipped:
        log_f.write("Skipped:\n")
        for s in skipped:
            log_f.write(s + "\n")


def copy_keyframes(src_clip, dst_clip, log_f):
    dur = src_clip.GetDuration()
    if not dur or dur < 2:
        log_f.write("No keyframes to copy.\n")
        return
    keyframeable = [
        "ZoomX", "ZoomY", "Pan", "Tilt",
        "RotationAngle", "AnchorPointX", "AnchorPointY",
        "Pitch", "Yaw", "Opacity",
        "CropLeft", "CropRight", "CropTop", "CropBottom",
    ]
    kf_count = 0
    for prop in keyframeable:
        try:
            prev_val = None
            for frame in range(int(dur)):
                val = src_clip.GetPropertyAtFrame(prop, frame)
                if val is None:
                    continue
                if val != prev_val:
                    dst_clip.SetPropertyAtFrame(prop, frame, val)
                    kf_count += 1
                prev_val = val
        except Exception:
            pass
    log_f.write(f"Keyframes written: {kf_count}\n")


try:
    if not os.path.isfile(POINTER_FILE):
        raise RuntimeError("No FocalFlow result found. Stabilize a clip first.")

    with open(POINTER_FILE, "r") as f:
        lines        = f.read().strip().splitlines()
        FOCAL_RESULT = lines[0]
        source_path  = lines[1] if len(lines) > 1 else None

    if not os.path.isfile(FOCAL_RESULT):
        raise RuntimeError(f"Result file not found:\n{FOCAL_RESULT}")

    with open(FOCAL_RESULT, "r") as f:
        meta = json.load(f)

    video_path  = meta.get("video_path")
    timeline_in = meta.get("timeline_in")
    track       = meta.get("track")
    frame_count = meta.get("frame_count")

    if not video_path or not os.path.isfile(video_path):
        raise RuntimeError(f"Stabilized video not found:\n{video_path}")
    if timeline_in is None or track is None:
        raise RuntimeError("JSON missing timeline_in or track.")

    with open(LOG, "w") as log_f:
        log_f.write(f"Placing    : {video_path}\n")
        log_f.write(f"Timeline in: {timeline_in}  track: {track}\n")
        log_f.write(f"Frame count: {frame_count}\n\n")

    if "resolve" not in dir():
        fallback = focal_paths.resolve_scripting_modules_path()
        if fallback not in sys.path:
            sys.path.append(fallback)
        import DaVinciResolveScript as dvr
        resolve = dvr.scriptapp("Resolve")

    if resolve is None:
        raise RuntimeError("Could not connect to DaVinci Resolve.")

    project  = resolve.GetProjectManager().GetCurrentProject()
    mp       = project.GetMediaPool()
    timeline = project.GetCurrentTimeline()

    if timeline is None:
        raise RuntimeError("No timeline is currently open.")

    if source_path:
        selected = timeline.GetCurrentVideoItem()
        if selected:
            media     = selected.GetMediaPoolItem()
            props     = media.GetClipProperty() if media else {}
            clip_path = props.get("File Path", "")
            if clip_path and os.path.abspath(clip_path) != os.path.abspath(source_path):
                raise RuntimeError(
                    f"Last export was for a different clip.\n\n"
                    f"Expected : {os.path.basename(source_path)}\n"
                    f"Selected : {os.path.basename(clip_path)}\n\n"
                    f"Select the original clip and try again."
                )

    original_clip = find_original_clip(timeline, timeline_in, track)

    with open(LOG, "a") as log_f:
        if original_clip:
            log_f.write(f"Original clip: {original_clip.GetName()}\n")
        else:
            log_f.write("WARNING: original clip not found.\n")

    imported = mp.ImportMedia([video_path])
    if not imported:
        raise RuntimeError(f"Media pool import failed:\n{video_path}")
    media_item = imported[0]

    clip_end    = timeline_in + frame_count
    start_above = track + 1

    with open(LOG, "a") as log_f:
        log_f.write(f"\nLooking for clear track above V{track}...\n")
        target_track = find_clear_track(
            timeline, start_above, timeline_in, clip_end, log_f
        )

    clip_info = {
        "mediaPoolItem": media_item,
        "startFrame":    0,
        "endFrame":      original_clip.GetDuration() if original_clip else frame_count - 1,
        "recordFrame":   timeline_in,
        "trackIndex":    target_track,
    }
    result = mp.AppendToTimeline([clip_info])
    if not result:
        raise RuntimeError(f"AppendToTimeline failed on V{target_track}.")

    new_clip = result[0]

    with open(LOG, "a") as log_f:
        if original_clip and new_clip:
            log_f.write("\n--- Copying transforms ---\n")
            copy_transforms(original_clip, new_clip, log_f)
            log_f.write("\n--- Copying keyframes ---\n")
            copy_keyframes(original_clip, new_clip, log_f)
        else:
            log_f.write("Skipping transform copy.\n")

    timeline.DeleteRenderCache()

    os.remove(FOCAL_RESULT)
    os.remove(POINTER_FILE)

    with open(LOG, "a") as log_f:
        log_f.write(f"\n✓ Placed on V{target_track} @ frame {timeline_in}\n")

    print(f"✓ Stabilized clip placed on V{target_track} @ frame {timeline_in}")

except Exception:
    with open(LOG, "a") as f:
        f.write("\n" + traceback.format_exc())
    raise
