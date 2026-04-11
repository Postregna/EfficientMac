import subprocess
import time
from pynput.keyboard import Listener, Key

# the keys that trigger the window fill toggle
trigger_keys = {
    Key.alt_r,
    Key.space,
}

# stores the original window position and size before expanding
original_state = None

pressed = set()


def get_active_window():
    # get the name and position of the currently focused window
    result = subprocess.run(["osascript", "-e", '''
        tell application "System Events"
            set frontApp to name of first process whose frontmost is true
            tell process frontApp
                set w to front window
                set pos to position of w
                set sz to size of w
                return frontApp & "," & (item 1 of pos) & "," & (item 2 of pos) & "," & (item 1 of sz) & "," & (item 2 of sz)
            end tell
        end tell
    '''], capture_output=True, text=True)
    try:
        parts = result.stdout.strip().split(",")
        return {
            "app": parts[0],
            "x": int(parts[1]),
            "y": int(parts[2]),
            "width": int(parts[3]),
            "height": int(parts[4]),
        }
    except:
        return None


def get_monitor_for_window(window):
    # find which monitor the active window is on based on its position
    import Quartz
    monitors = []
    for display in Quartz.CGGetActiveDisplayList(10, None, None)[1]:
        bounds = Quartz.CGDisplayBounds(display)
        monitors.append({
            "x": int(bounds.origin.x),
            "y": int(bounds.origin.y),
            "width": int(bounds.size.width),
            "height": int(bounds.size.height),
        })

    # match window to monitor by checking which monitor it overlaps with most
    for monitor in monitors:
        if (monitor["x"] <= window["x"] < monitor["x"] + monitor["width"] and
                monitor["y"] <= window["y"] < monitor["y"] + monitor["height"]):
            return monitor

    # fallback to first monitor
    return monitors[0]


def set_window_size(app, x, y, width, height):
    # move and resize the active window of the given app
    subprocess.run(["osascript", "-e", f'''
        tell application "System Events"
            tell process "{app}"
                set position of front window to {{{x}, {y}}}
                set size of front window to {{{width}, {height}}}
            end tell
        end tell
    '''])


def toggle_fill():
    global original_state

    window = get_active_window()
    if not window:
        return

    if original_state is None:
        # save original position and expand to fill the monitor
        monitor = get_monitor_for_window(window)
        original_state = window
        set_window_size(window["app"], monitor["x"], monitor["y"], monitor["width"], monitor["height"])
    else:
        # restore the original position and size
        set_window_size(
            original_state["app"],
            original_state["x"],
            original_state["y"],
            original_state["width"],
            original_state["height"]
        )
        original_state = None


def on_press(key):
    pressed.add(key)
    if trigger_keys.issubset(pressed):
        toggle_fill()
        # clear space from pressed so holding alt and pressing space again works
        pressed.discard(Key.space)


def on_release(key):
    pressed.discard(key)


with Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()