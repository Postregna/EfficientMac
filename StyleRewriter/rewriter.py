import subprocess
import os
import re
import time
import urllib.request
import json
from pynput import keyboard

CONFIG_FILE = os.path.dirname(os.path.abspath(__file__)) + "/config.txt"

pressed = set()

def ensure_ollama():
    try:
        urllib.request.urlopen("http://localhost:11434", timeout=2)
    except:
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)

def get_clipboard():
    result = subprocess.run(["pbpaste"], capture_output=True, text=True)
    return result.stdout

def set_clipboard(text):
    subprocess.run(["pbcopy"], input=text, text=True)

def rewrite():
    try:
        ensure_ollama()
        draft = get_clipboard().strip()

        if not draft:
            return

        with open(CONFIG_FILE, "r") as f:
            style = f.read().strip()

        prompt = f"{style}\n\nRules: never use exclamation points, semicolons, or colons. Never use words like proceed, regarding, following, as per, necessitates, anticipate, coordinate, transition, facilitate.\n\nRewrite the following message in a professional but human tone that sounds like me. Use contractions. Keep it short. Reply with only the rewritten message, no preamble, no explanation:\n\n{draft}"

        data = json.dumps({
            "model": "mistral",
            "prompt": prompt,
            "stream": False
        }).encode()

        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=data,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            raw = result["response"].strip()
            raw = re.sub(r'\b(\w+)\s+\1\b', r'\1', raw, flags=re.IGNORECASE)
            raw = re.sub(r'\b(\w{2,})\w*\s+(\1\w*)\b', r'\2', raw, flags=re.IGNORECASE)
            rewritten = ' '.join(raw.split())
            rewritten = rewritten.replace(';', '.')
            rewritten = rewritten.replace('!', '.')
            rewritten = re.sub(r':(?!\d{2})', ',', rewritten)
            rewritten = rewritten.strip('"')

        set_clipboard(rewritten)

    except Exception as e:
        pass

def on_press(key):
    pressed.add(key)
    if keyboard.Key.ctrl_r in pressed and keyboard.KeyCode.from_char('r') in pressed:
        rewrite()

def on_release(key):
    pressed.discard(key)

with keyboard.Listener(on_press=on_press, on_release=on_release) as l:
    l.join()