FOCALFLOW
Stabilizer for DaVinci Resolve
================================

Hey, thanks for trying FocalFlow. It's a stabilizer
that actually understands what you were pointing at
when you shot the thing. Whether that's a bokeh ball,
an edge, a smudge, or a vague hope — it'll track it.

Works great on long lens, but honestly throw anything
at it. Handheld run-and-gun, gimbal drift, shoulder
rig wobble, "I thought I was stable" — all fair game.


WHAT YOU NEED
-------------
- Windows 10 or newer (64-bit)
- DaVinci Resolve 17 or newer (free version is fine)
- Python 3.6 or newer installed system-wide (see below)
- Your footage somewhere Resolve can actually find it


INSTALLING
----------
1. Unzip this folder somewhere (Downloads is fine)
2. Double-click install_FocalFlow.exe
3. Enter your license key from your Gumroad receipt,
   or enter FreeTrial to try it out first
4. The installer checks for Python first. If it finds
   it, you're off to the races. If not, read below.
5. It cleans up the zip and installer files. You can
   delete the remaining folder when you're done.

Updates are free.
Buyers get notified directly when a new version is available.

UPGRADING FROM FREE TRIAL
--------------------------
Already using the free trial and just bought a
license? You don't need to reinstall anything.

1. Go to the folder where FocalFlow was installed
   (C:\Users\[YourName]\FocalFlow)
2. Double-click upgrade_FocalFlow.exe
3. Enter your real license key from your Gumroad
   receipt
4. That's it — restart FocalFlow if it's currently
   open, and the watermark will be gone on your
   next export.

No reinstall, no re-downloading, nothing else moves.

FREE TRIAL
----------
The free trial is fully functional with one difference
— exported footage has a FocalFlow watermark burned in.
This makes the output unusable for real work, but lets
you try the full workflow before committing.

To try it: when the installer asks for your license
key, type FreeTrial and press Enter. That's it.
Everything else is identical to the paid version.

When you're ready to buy, grab it on Gumroad and
run upgrade_FocalFlow.exe from your FocalFlow
folder with your real key — see UPGRADING FROM
FREE TRIAL above.


ABOUT PYTHON
------------
FocalFlow needs Python installed system-wide so that
DaVinci Resolve can find it when running scripts.
This is a Resolve requirement, not ours.

If the installer doesn't find Python, it will walk
you through the whole thing. A Python installer is
included in the zip. Here's what matters:

  !! TWO THINGS YOU CANNOT SKIP !!

  1. Run the Python installer AS ADMINISTRATOR
     (right-click it, "Run as administrator")

  2. On the FIRST screen, tick this box:
     ☑  "Add Python to PATH"

     That checkbox is easy to miss and it's the whole
     thing. If you skip it, Resolve will never see
     Python no matter what else you do.

The installer will close itself while you do this.
Once Python is installed, double-click
install_FocalFlow.exe again to continue. Your license
key won't be wasted — it only gets counted when the
install actually completes.


HOW TO USE IT
-------------
1. In Resolve, park your playhead on the clip you want
   to fix and make sure that track is selected
2. Workspace > Scripts > launch_FocalFlow
3. Wait for it to load — it's pulling in HD frames in
   the background while you work, so don't wait for it
4. Drop some tracking points on things that aren't
   moving — bokeh circles, edges, signs, whatever
   has contrast and isn't your subject
5. Press T to track
6. Press S to stabilize
7. The view switches to stabilized automatically.
   Mess with the smoothing slider and hit Re-stabilize
   until it feels right
8. Hit Save and Close when you're happy
9. Back in Resolve: Workspace > Scripts > place_result_FocalFlow
   Your stabilized clip lands on the track above the
   original with all your transforms already copied over.
   You're welcome.


IMPORTANT — DON'T MOVE THE CLIP FIRST
--------------------------------------
FocalFlow remembers exactly where your clip sits on
the timeline when you launch it. That's how it knows
where to place the stabilized version when you run
place_result.

If you move, trim, or shuffle the original clip on
the timeline between launching FocalFlow and running
place_result, the stabilized clip will land in the
wrong place. It has no way of knowing you moved it.

The workflow is:
  Launch > Track > Stabilize > Save and Close > Place.


TRACKER TYPES
-------------
You get two:

BOKEH  — looks for circular out-of-focus blobs.
         Perfect for long lens stuff with those big
         dreamy highlight circles floating around.

POINT  — tracks any high contrast feature or edge.
         Use this when there's no bokeh or you just
         want to track something specific.

Right-click any point on the canvas to switch types.
Double-tap A to change the default for new points.


WHERE YOUR OUTPUT GOES
----------------------
Right next to your footage, in its own folder:

  YourFootageFolder\
      YourClip.mov
      FocalFlow\
          focal_YourClip_t1234_143022.mov

No hunting around for it. No mystery output folder.
It's just sitting there next to the original like
it was always meant to be there.


SOMETHING WENT WRONG
--------------------
First stop: the log file.

  C:\Users\[YourName]\FocalFlow\FocalFlow\focal_launch_log.txt

It writes down everything it did and exactly where
it fell over. Nine times out of ten the answer is
in there. Check it before you email anyone.

Common culprits:
- Python not found or not on the system PATH
  (did you tick "Add Python to PATH" during install?)
- Footage got moved or renamed since you added it
  to Resolve (classic)
- Resolve couldn't find the clip's source file
- You ran place_result on the wrong project
  (it'll tell you if you did)
- You moved the clip on the timeline before placing
  (see the section above)
- Licensing seems stuck or an upgrade didn't take
  (check C:\Users\[YourName]\AppData\Local\FocalFlow
  — deleting this folder resets activation and lets
  you start clean; you'll need to re-enter your key
  via upgrade_FocalFlow.exe afterward)


KEYBOARD SHORTCUTS
------------------
A               Place mode
                (double-tap to switch tracker type)
E               Edit mode
T               Track
S               Stabilize / Re-stabilize
V               Toggle original / stabilized
Z               Reset zoom
Left / Right    Step through frames
Space           Play / pause
Delete / X      Delete selected point
Ctrl+Z          Undo
                (after first stabilize: deletes the solve)
Ctrl+S          Save and Close
Esc             Stop whatever it's doing


UNINSTALLING
------------
  C:\Users\[YourName]\FocalFlow\uninstall_FocalFlow.bat

Removes everything. Your rendered clips are safe,
it only touches the stuff it installed.


Good luck out there. Shoot something beautiful.



SOFTWARE LICENSE AGREEMENT

This software is licensed, not sold.

By purchasing, downloading, or using this software,
you agree to the following terms:

1. Grant of License
You are granted a non-exclusive, non-transferable
license to use this software for personal or
commercial use.

2. Restrictions
You may NOT:
- Resell, redistribute, share, sublicense, or
  otherwise transfer this software, in whole or in part
- Upload or distribute this software on any website,
  marketplace, or file-sharing service
- Claim this software as your own or modify it for resale
- Provide access to the software to others who have
  not purchased it

3. Ownership
The software, including all code and associated
materials, remains the intellectual property of
the original creator.

4. Unauthorized Use
Any unauthorized distribution or resale of this
software is a violation of this agreement and
applicable copyright law, and may result in
legal action.

5. Termination
This license is automatically terminated if you
violate any of these terms. Upon termination, you
must delete all copies of the software.

6. No Warranty
This software is provided "as is" without warranty
of any kind.

FocalFlow uses PyQt6 by Riverbank Computing
https://www.riverbankcomputing.com/software/pyqt/

Support Email: twinsuns320@gmail.com

© 2026 Palmer LeVake. All rights reserved.