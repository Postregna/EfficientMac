import subprocess
import time
import Quartz

# the app you want to move to the second monitor
# change this to any app name as it appears in Activity Monitor
TARGET_APP = "Code"

# which monitor to move it to — "left" or "right"
TARGET_MONITOR = "left"

# how often to check for new windows in seconds
POLL_INTERVAL = 1


def get_monitors():
    # get a list of all connected monitors and their positions
    monitors = []
    for display in Quartz.CGGetActiveDisplayList(10, None, None)[1]:
        bounds = Quartz.CGDisplayBounds(display)
        monitors.append({
            "x": int(bounds.origin.x),
            "y": int(bounds.origin.y),
            "width": int(bounds.size.width),
            "height": int(bounds.size.height),
        })
    return monitors


def get_target_monitor(monitors):
    # pick the leftmost or rightmost monitor based on TARGET_MONITOR setting
    if TARGET_MONITOR == "left":
        return min(monitors, key=lambda m: m["x"])
    else:
        return max(monitors, key=lambda m: m["x"])


def move_app(monitor):
    # move and maximize all windows of the target app to the chosen monitor
    x = monitor["x"]
    y = monitor["y"]
    w = monitor["width"]
    h = monitor["height"]

    script = f'''
        tell application "System Events"
            tell process "{TARGET_APP}"
                repeat with w in every window
                    set position of w to {{{x}, {y}}}
                    set size of w to {{{w}, {h}}}
                end repeat
            end tell
        end tell
    '''
    subprocess.run(["osascript", "-e", script])


def get_window_count():
    # count how many windows the target app currently has open
    result = subprocess.run(
        ["osascript", "-e", f'''
            tell application "System Events"
                if exists process "{TARGET_APP}" then
                    return count of windows of process "{TARGET_APP}"
                else
                    return 0
                end if
            end tell
        '''],
        capture_output=True, text=True
    )
    try:
        return int(result.stdout.strip())
    except:
        return 0


def main():
    last_window_count = 0

    while True:
        monitors = get_monitors()

        # only move if a second monitor is actually connected
        if len(monitors) > 1:
            target = get_target_monitor(monitors)
            current_count = get_window_count()

            # if window count increased a new window just opened — move everything
            if current_count > last_window_count:
                time.sleep(1)  # wait for the window to fully load before moving
                move_app(target)

            last_window_count = current_count
        else:
            # no second monitor connected — track count but dont move anything
            last_window_count = get_window_count()

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()