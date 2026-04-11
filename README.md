# EfficientMac

A collection of tools I'll continue to add to. Built on macOS.

## Tools

### AutoLock
Hold Right Shift + Right Ctrl for 3 seconds to lock your screen. Quits all open apps, empties the trash, and plays a sound so you know when to let go.

Runs automatically at login.

**Setup**
1. Install the dependency: `pip3 install pynput`
2. Grant Accessibility and Input Monitoring permissions to Python in System Settings → Privacy & Security
3. Load the launch agent: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.efficientmac.autolock.plist`

You can add app names to the `EXCEPTIONS` list in the script to prevent them from being quit on lock.

---

### AppMover
Watches for a target app to open and automatically moves and resizes it to your second monitor. Windows fill the screen but stay out of full screen mode so the menu bar stays visible.

Defaults to VS Code on the left monitor but you can change `TARGET_APP` and `TARGET_MONITOR` at the top of the script to use it with any app.

Runs automatically at login.

**Setup**
1. Set `TARGET_APP` to your app's process name as it appears in Activity Monitor
2. Set `TARGET_MONITOR` to `"left"` or `"right"`
3. Load the launch agent: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.efficientmac.appmover.plist`

---

## Requirements

```bash
pip3 install pynput
```

macOS only.

---

C. Post  
[github.com/Postregna](https://github.com/Postregna)