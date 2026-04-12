import os
import shutil
import time
from datetime import datetime, timedelta

# where screenshots land by default
WATCH_FOLDER = os.path.expanduser("~/Desktop")

# where to move them
SCREENSHOTS_FOLDER = os.path.expanduser("~/Desktop/Screenshots")

# how old an unnamed screenshot can be before it gets deleted (in days)
DELETE_AFTER_DAYS = 1

# how often to check for new screenshots (in seconds)
POLL_INTERVAL = 5


def is_default_screenshot_name(filename):
    # macOS default screenshot names start with "Screenshot"
    return filename.startswith("Screenshot") and filename.endswith(".png")


def get_dated_folder():
    # create a folder for today's date inside Screenshots if it doesn't exist
    today = datetime.now().strftime("%Y-%m-%d")
    folder = os.path.join(SCREENSHOTS_FOLDER, today)
    os.makedirs(folder, exist_ok=True)
    return folder


def move_new_screenshots():
    # look for any screenshot files sitting on the Desktop
    for filename in os.listdir(WATCH_FOLDER):
        if not filename.endswith(".png"):
            continue
        if not is_default_screenshot_name(filename):
            continue

        src = os.path.join(WATCH_FOLDER, filename)
        dst = os.path.join(get_dated_folder(), filename)

        # move it to today's dated folder
        shutil.move(src, dst)


def delete_old_unnamed_screenshots():
    # walk through all dated folders and delete old unnamed screenshots
    cutoff = datetime.now() - timedelta(days=DELETE_AFTER_DAYS)

    for dated_folder in os.listdir(SCREENSHOTS_FOLDER):
        folder_path = os.path.join(SCREENSHOTS_FOLDER, dated_folder)
        if not os.path.isdir(folder_path):
            continue

        for filename in os.listdir(folder_path):
            if not is_default_screenshot_name(filename):
                # file has been renamed — skip it and keep it
                continue

            filepath = os.path.join(folder_path, filename)
            modified = datetime.fromtimestamp(os.path.getmtime(filepath))

            if modified < cutoff:
                os.remove(filepath)

        # remove the dated folder if its now empty
        if not os.listdir(folder_path):
            os.rmdir(folder_path)


def main():
    while True:
        move_new_screenshots()
        delete_old_unnamed_screenshots()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()