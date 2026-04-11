import subprocess
import time
import threading
from pynput.keyboard import Listener, Key

# how long to hold the trigger keys before locking (in seconds)
HOLD_SECONDS = 3

# apps that should not be quit when locking — add names here to protect them
EXCEPTIONS = [
    "Claude",
    ## "Spotify",
    ## "Music",
]

# the two keys that must be held simultaneously to trigger the lock
trigger_keys = {
    Key.shift_r,
    Key.ctrl_r,
}

# tracks which trigger keys are currently being held
pressed = set()

# holds the countdown timer object
lock_timer = None


def play_sound():
    # save the current system volume
    result = subprocess.run(
        ["osascript", "-e", "output volume of (get volume settings)"],
        capture_output=True, text=True
    )
    original_volume = result.stdout.strip()

    # bump volume to 50 so the alert is always audible
    subprocess.run(["osascript", "-e", "set volume output volume 50"])

    # play the alert sound
    subprocess.run(["afplay", "/System/Library/Sounds/Funk.aiff", "-v", "3"])

    # restore the original volume after the sound finishes
    subprocess.run(["osascript", "-e", f"set volume output volume {original_volume}"])


def empty_trash():
    # permanently delete everything in the trash
    subprocess.run(["osascript", "-e", 'tell application "Finder" to empty trash'])


def close_exception_windows():
    # click the close button on every open window for apps in the exceptions list
    # this hides them cleanly without quitting the app
    subprocess.run(["osascript", "-e", '''
        tell application "System Events"
            repeat with p in (every process whose background only is false)
                repeat with w in (every window of p)
                    click button 1 of w
                end repeat
            end repeat
        end tell
    '''])


def quit_app(app):
    # send a quit command to a single app by name
    subprocess.run(["osascript", "-e", f'tell application "{app}" to quit'])


def kill_app_mode_loader():
    # force kill any browser web apps running as standalone processes
    subprocess.run(["pkill", "-f", "app_mode_loader"])


def quit_all_apps():
    # get the names of all visible running apps
    result = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to get name of every process whose background only is false'],
        capture_output=True, text=True
    )
    apps = [a.strip() for a in result.stdout.split(",")]

    threads = []
    for app in apps:
        # skip exceptions and Finder (Finder cant be quit on macOS)
        if app and app not in EXCEPTIONS and app != "Finder":
            # quit each app in its own thread so they all close simultaneously
            t = threading.Thread(target=quit_app, args=(app,))
            t.start()
            threads.append(t)

    # also kill any web app processes running in the background
    threading.Thread(target=kill_app_mode_loader).start()

    # wait up to 2 seconds for all apps to finish quitting
    for t in threads:
        t.join(timeout=2)


def lock():
    play_sound()          # alert the user the lock is about to trigger
    empty_trash()         # clean up the trash before locking
    close_exception_windows()  # close windows for apps we are keeping alive
    quit_all_apps()       # quit everything else
    time.sleep(1.5)       # brief pause to let everything finish closing
    subprocess.run([
        "osascript", "-e",
        # send ctrl + cmd + q to lock the screen
        'tell application "System Events" to keystroke "q" using {control down, command down}'
    ])


def start_timer():
    global lock_timer
    cancel_timer()
    # start a countdown — if keys are still held when it fires, lock triggers
    lock_timer = threading.Timer(HOLD_SECONDS, lock)
    lock_timer.start()


def cancel_timer():
    global lock_timer
    # cancel the countdown if keys are released before time is up
    if lock_timer is not None:
        lock_timer.cancel()
        lock_timer = None


def on_press(key):
    if key not in trigger_keys:
        return
    pressed.add(key)
    # start the timer only once both keys are held and no timer is running
    if len(pressed) >= len(trigger_keys) and lock_timer is None:
        start_timer()


def on_release(key):
    pressed.discard(key)
    # if either key is released before time is up, cancel the lock
    if len(pressed) < len(trigger_keys):
        cancel_timer()


# start listening for keypresses in the background
with Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()