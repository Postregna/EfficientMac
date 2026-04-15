import subprocess
import os
import re
import time
import urllib.request
import json
import logging
import threading
from pynput import keyboard

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
OLLAMA_URL  = "http://localhost:11434"
MODEL       = "llama3"
HOTKEY      = {keyboard.Key.ctrl_r, keyboard.KeyCode.from_char('r')}

BANNED_WORDS = [
    "proceed", "regarding", "following", "as per", "necessitates",
    "anticipate", "coordinate", "transition", "facilitate",
    "endeavor", "leverage", "utilize", "oversight",
]

# casual words to preserve exactly — order matters, longer phrases first
CASUAL_WORDS = [
    "get together",
    "hang out",
    "catch up",
    "grab",
]

# words the model might swap casual words with — used to find and replace them back
CASUAL_SYNONYMS = {
    "get together": ["meet up", "catch up", "hang out", "link up", "hangout", "grab", "meet"],
    "hang out":     ["get together", "meet up", "link up", "hangout", "grab", "meet"],
    "catch up":     ["get together", "meet up", "hang out", "link up", "grab", "meet"],
    "grab":         ["meet", "get together", "catch up", "hang out", "hangout"],
}

# strips common preamble the model leaks despite being told not to
PREAMBLE_RE = re.compile(
    r"^(sure[,!.]?\s*|here(?:'s| is) the rewrite[:\s]*|"
    r"rewritten[:\s]*|of course[,!.]?\s*|absolutely[,!.]?\s*)",
    re.IGNORECASE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

# written to disk the first time the script runs, edit it to change styles
DEFAULT_CONFIG = {
    "active_style": "default",
    "styles": {
        "default": (
            "Never add anything that was not in the original message. "
            "Never add greetings, sign-offs, openers, closings, or emoticons. "
            "Never use exclamation points, semicolons, or colons. "
            "Never start with I. Use contractions always. Short sentences. "
            "Sound like a real person texting, not a corporate email. "
            "No filler phrases: Hope alls well, Hope this finds you well, on your end, "
            "I wanted to reach out, Looking forward to, See you there. "
            "No corporate words: proceed, regarding, following, as per, facilitate, "
            "coordinate, transition, necessitate, anticipate, endeavor, leverage, "
            "utilize, oversight, apologies for, please be advised, as mentioned. "
            "Be direct. Vary sentence structure. "
            "No passive voice — rewrite every passive sentence as active. "
            "Never repeat the same word twice in one message. "
            "If a rewrite sounds awkward, simplify it further. "
            "Cut any word that does not add meaning."
        ),
        "terse": (
            "Same rules as default but cut every sentence in half. "
            "One idea per sentence. If it can be implied, drop it."
        ),
        "formal": (
            "Rewrite for a senior stakeholder or legal context. "
            "No contractions. No slang. Still no corporate filler or banned words. "
            "Clear, precise, and short."
        ),
    },
}


def load_config() -> dict:
    # if no config exists yet, write the defaults and use them
    if not os.path.exists(CONFIG_FILE):
        logging.info("Config not found — writing defaults.")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(cfg: dict) -> None:
    # write the config back to disk as formatted JSON
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def active_style(cfg: dict) -> str:
    # return the style text for whatever is set as the active style
    key = cfg.get("active_style", "default")
    return cfg["styles"].get(key, cfg["styles"]["default"])


# ---------------------------------------------------------------------------
# Clipboard (macOS)
# ---------------------------------------------------------------------------

def get_clipboard() -> str:
    # read whatever text is currently on the clipboard
    return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout


def set_clipboard(text: str) -> None:
    # replace the clipboard contents with the rewritten text
    subprocess.run(["pbcopy"], input=text, text=True)


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

def notify(message: str) -> None:
    # show a macOS notification so you know what is happening
    script = f'display notification "{message}" with title "Rewriter"'
    subprocess.Popen(
        ["osascript", "-e", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

def ensure_ollama(retries: int = 5, delay: float = 1.5) -> bool:
    # check if Ollama is running, and start it if not
    for attempt in range(retries):
        try:
            urllib.request.urlopen(OLLAMA_URL, timeout=2)
            return True
        except Exception:
            if attempt == 0:
                logging.info("Starting Ollama...")
                subprocess.Popen(
                    ["/opt/homebrew/bin/ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            time.sleep(delay)
    logging.error("Ollama did not start in time.")
    return False


def call_ollama(prompt: str) -> str:
    # send the prompt to Ollama and return the raw response text
    data = json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode()
    req  = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read())["response"].strip()


# ---------------------------------------------------------------------------
# Context detector
# ---------------------------------------------------------------------------

def detect_context(text: str) -> str:
    # look for clues about what kind of message this is so the prompt can adapt
    t = text.lower()
    if any(w in t for w in ("subject:", "dear ", "regards,")):
        return "This appears to be an email."
    if len(text.split()) < 15:
        return "This is a short Slack-style message — keep it brief."
    if "?" in text:
        return "This is a question or request."
    return ""


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(style: str, draft: str) -> str:
    banned_words = ", ".join(BANNED_WORDS)
    casual_words = ", ".join(CASUAL_WORDS)
    context_hint = detect_context(draft)
    # only include the context line if we actually detected something
    context_line = f"\nContext: {context_hint}" if context_hint else ""
    return (
        f"{style}{context_line}\n\n"
        f"Rules:\n"
        f"- Never use exclamation points, semicolons, or standalone colons.\n"
        f"- Never use these words: {banned_words}.\n"
        f"- Use contractions. Sound human, not corporate.\n"
        f"- Never change the meaning or structure of the original. Only clean up the language.\n"
        f"- If any of these words appear in the original, keep them exactly as written: {casual_words}.\n"
        f"- Reply with ONLY the rewritten message — no preamble, no explanation.\n\n"
        f"Rewrite this:\n\n{draft}"
    )


# ---------------------------------------------------------------------------
# Response cleaner
# ---------------------------------------------------------------------------

# fallback replacements in case the model ignores the banned words rule
REPLACEMENTS = {
    "proceed":    "move forward",
    "facilitate": "help",
    "transition": "shift",
    "coordinate": "work with",
}


def restore_casual_words(text: str, draft: str) -> str:
    draft_lower = draft.lower()
    text_lower  = text.lower()

    # build a list of swaps to make without applying them yet
    swaps = []
    already_used = set()

    for word in CASUAL_WORDS:
        if word not in draft_lower:
            continue
        if word in text_lower:
            continue
        synonyms = CASUAL_SYNONYMS.get(word, [])
        for synonym in synonyms:
            if synonym in text_lower and synonym not in already_used:
                swaps.append((synonym, word))
                already_used.add(synonym)
                logging.info(f"Restoring '{word}' from '{synonym}'")
                break
        else:
            logging.info(f"Could not restore casual word: {word}")

    # apply all swaps at once so they don't interfere with each other
    for synonym, word in swaps:
        text = re.sub(re.escape(synonym), word, text, count=1, flags=re.IGNORECASE)

    # if the model added "grab" but it wasn't in the original, replace it
    if "grab" not in draft_lower and "grab" in text.lower():
        text = re.sub(r'\bgrab\b', 'meet up', text, flags=re.IGNORECASE)

    return text


def fix_apostrophes(text: str) -> str:
    # fix common missing apostrophes the model drops
    text = re.sub(r"\bIm\b",       "I'm",      text)
    text = re.sub(r"\bWhats\b",    "What's",   text)
    text = re.sub(r"\bIts\b",      "It's",     text)
    text = re.sub(r"\bdont\b",     "don't",    text, flags=re.IGNORECASE)
    text = re.sub(r"\bcant\b",     "can't",    text, flags=re.IGNORECASE)
    text = re.sub(r"\bwont\b",     "won't",    text, flags=re.IGNORECASE)
    text = re.sub(r"\bdidnt\b",    "didn't",   text, flags=re.IGNORECASE)
    text = re.sub(r"\bwouldnt\b",  "wouldn't", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcouldnt\b",  "couldn't", text, flags=re.IGNORECASE)
    text = re.sub(r"\bshouldnt\b", "shouldn't",text, flags=re.IGNORECASE)
    text = re.sub(r"\bwasnt\b",    "wasn't",   text, flags=re.IGNORECASE)
    text = re.sub(r"\bisnt\b",     "isn't",    text, flags=re.IGNORECASE)
    text = re.sub(r"\barent\b",    "aren't",   text, flags=re.IGNORECASE)
    text = re.sub(r"\bhasnt\b",    "hasn't",   text, flags=re.IGNORECASE)
    text = re.sub(r"\bhavent\b",   "haven't",  text, flags=re.IGNORECASE)
    text = re.sub(r"\bhadnt\b",    "hadn't",   text, flags=re.IGNORECASE)
    return text

def fix_capitalization(text: str) -> str:
    # capitalize days of the week
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        text = re.sub(rf"\b{day}\b", day.capitalize(), text, flags=re.IGNORECASE)

    # capitalize months
    for month in ["january", "february", "march", "april", "may", "june",
                  "july", "august", "september", "october", "november", "december"]:
        text = re.sub(rf"\b{month}\b", month.capitalize(), text, flags=re.IGNORECASE)

    return text

def clean_response(text: str, draft: str) -> str:
    # strip any preamble the model leaked before the actual rewrite
    text = PREAMBLE_RE.sub("", text).strip()

    # remove surrounding quotes the model sometimes wraps the reply in
    if text.startswith(('"', "'")) and text.endswith(('"', "'")):
        text = text[1:-1].strip()

    # fix banned punctuation
    text = text.replace(";", ".").replace("!", ".")

    # replace colons unless they are part of a time like 3:00
    text = re.sub(r":(?!\d{2})", ",", text)

    # collapse multiple dots into a normal ellipsis
    text = re.sub(r"\.{3,}", "...", text)

    # collapse any extra whitespace
    text = " ".join(text.split())

    # swap out banned words the model ignored
    for bad, good in REPLACEMENTS.items():
        text = re.sub(rf"\b{bad}\b", good, text, flags=re.IGNORECASE)

    # fix missing apostrophes
    text = fix_apostrophes(text)

    # capitalize days and months
    text = fix_capitalization(text)

    # put back any casual words the model replaced
    text = restore_casual_words(text, draft)

    # capitalize after sentence endings
    text = re.sub(r'(?<=[.?!])\s+([a-z])', lambda m: m.group(0).upper(), text)

    # capitalize the first character of the whole message
    text = text[0].upper() + text[1:] if text else text

    # add a period if the message has no ending punctuation
    if text and text[-1] not in ".?!":
        text = text + "."

    return text


# ---------------------------------------------------------------------------
# Rewrite
# ---------------------------------------------------------------------------

# prevents two rewrites from running at the same time
_rewrite_lock = threading.Lock()


def rewrite() -> None:
    # if a rewrite is already running, do nothing
    if not _rewrite_lock.acquire(blocking=False):
        logging.info("Rewrite already in progress — skipping.")
        return
    try:
        _do_rewrite()
    finally:
        # always release the lock so the next hotkey press works
        _rewrite_lock.release()


def _do_rewrite() -> None:
    if not ensure_ollama():
        notify("Ollama unavailable.")
        return

    draft = get_clipboard().strip()
    if not draft:
        logging.info("Clipboard empty — skipping.")
        return

    cfg   = load_config()
    style = active_style(cfg)

    notify("Rewriting.")

    try:
        prompt    = build_prompt(style, draft)
        raw       = call_ollama(prompt)
        rewritten = clean_response(raw, draft)
        set_clipboard(rewritten)
        notify("Done. Paste.")
        logging.info("Clipboard updated.")
    except Exception:
        logging.exception("Rewrite failed")
        notify("Rewrite failed. Check logs.")


# ---------------------------------------------------------------------------
# Hotkey listener
# ---------------------------------------------------------------------------

# tracks which keys are currently held down
pressed: set = set()


def on_press(key) -> None:
    # ignore the keypress if the key is already being held
    if key in pressed:
        return
    pressed.add(key)
    # fire the rewrite on a background thread when the full hotkey is held
    if HOTKEY.issubset(pressed):
        threading.Thread(target=rewrite, daemon=True).start()


def on_release(key) -> None:
    pressed.discard(key)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.info("Rewriter active — Ctrl+R to rewrite clipboard")
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()