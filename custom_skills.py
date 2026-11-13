"""
Cobo Self-Forged Skill Library (custom_skills.py)
Includes Live Google Keep integration (via gkeepapi.resume), Drive Budget/Checklists, and Cobo Budget Bridge.
"""
import os
import json
import requests
import gkeepapi
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_PATH = r"C:\Users\gvick\dev\cobo_v2\token.json"
KEEP_TOKEN_PATH = r"C:\Users\gvick\dev\cobo_v2\keep_token.json"
KEEP_CACHE_PATH = r"C:\Users\gvick\dev\cobo_v2\keep_state_cache.json"
BUDGET_BRIDGE_DIR = r"C:\Users\gvick\my-agent\budget_build"

_KEEP_INSTANCE = None

def _get_keep() -> gkeepapi.Keep:
    """Returns an authenticated, synced gkeepapi.Keep instance bound to the saved hardware device_id."""
    global _KEEP_INSTANCE
    if not os.path.exists(KEEP_TOKEN_PATH):
        raise FileNotFoundError("keep_token.json not found. Run auth_keep.py first.")

    with open(KEEP_TOKEN_PATH, "r", encoding="utf-8") as f:
        creds = json.load(f)

    email = creds["email"].strip()
    master_token = creds["master_token"].strip()
    from uuid import getnode
    device_id = creds.get("device_id") or f"{getnode():016x}"

    if _KEEP_INSTANCE is None:
        keep = gkeepapi.Keep()
        state = None
        if os.path.exists(KEEP_CACHE_PATH):
            try:
                with open(KEEP_CACHE_PATH, "r", encoding="utf-8") as cf:
                    state = json.load(cf)
            except Exception:
                state = None

        try:
            keep.authenticate(email, master_token, state=state, device_id=device_id)
        except Exception:
            keep.authenticate(email, master_token, state=None, device_id=device_id)

        _KEEP_INSTANCE = keep
    else:
        _KEEP_INSTANCE.sync()

    try:
        with open(KEEP_CACHE_PATH, "w", encoding="utf-8") as cf:
            json.dump(_KEEP_INSTANCE.dump(), cf)
    except Exception:
        pass

    return _KEEP_INSTANCE

def keep_list_or_search_notes(query: str = "", max_results: int = 15, include_archived: bool = False) -> str:
    """
    Searches or lists live Google Keep notes and checklists.
    Pass query="" to list pinned and recent active notes in Google Keep, or pass a keyword to search titles and body text.
    """
    try:
        keep = _get_keep()
        q_lower = query.strip().lower()
        results = []

        for n in keep.all():
            if n.trashed or (not include_archived and n.archived):
                continue
            title = (n.title or "").strip()
            text = (n.text or "").strip()
            if not title and not text:
                continue
            if not q_lower or q_lower in title.lower() or q_lower in text.lower():
                pin_tag = "[PINNED] " if n.pinned else ""
                note_type = "Checklist" if isinstance(n, gkeepapi.node.List) else "Note"
                preview = text.replace("\n", " | ")[:350]
                results.append((n.pinned, f"- {pin_tag}**{title or '(Untitled)'}** ({note_type}): {preview}"))

        results.sort(key=lambda x: x[0], reverse=True)
        top = [r[1] for r in results[:max_results]]
        if not top:
            return f"No Google Keep notes matched '{query}'."
        return f"Google Keep Notes ({len(top)} shown):\n" + "\n".join(top)
    except Exception as e:
        return f"Google Keep read error: {type(e).__name__}: {e}"

def keep_create_note(title: str, content: str, is_checklist: bool = False, pin: bool = False) -> str:
    """
    Creates a new live note or checklist in Google Keep and syncs immediately.
    If is_checklist=True, splits 'content' by newlines or commas into checklist items.
    """
    try:
        keep = _get_keep()
        if is_checklist:
            raw_items = [i.strip(" -*?") for i in content.replace(",", "\n").splitlines() if i.strip()]
            items = [(item, False) for item in raw_items]
            note = keep.createList(title, items)
        else:
            note = keep.createNote(title, content)
        note.pinned = pin
        keep.sync()
        return f"Created live Google Keep {'checklist' if is_checklist else 'note'}: '{title}'"
    except Exception as e:
        return f"Google Keep create error: {type(e).__name__}: {e}"

def keep_append_to_note(title_or_id: str, text_to_add: str) -> str:
    """
    Finds an existing Google Keep note or checklist by title (fuzzy match) or ID,
    appends new text or checklist items to it, and syncs immediately.
    """
    try:
        keep = _get_keep()
        target = None
        search_lower = title_or_id.strip().lower()

        for n in keep.all():
            if n.trashed:
                continue
            if n.id == title_or_id or (n.title and search_lower in n.title.lower()):
                target = n
                break

        if not target:
            return f"Could not find a Google Keep note matching '{title_or_id}'."

        if isinstance(target, gkeepapi.node.List):
            for line in text_to_add.splitlines():
                clean = line.strip(" -*?")
                if clean:
                    target.add(clean, False)
        else:
            existing = target.text or ""
            target.text = (existing + "\n" + text_to_add).strip()

        keep.sync()
        return f"Updated Google Keep note '{target.title}' with: {text_to_add}"
    except Exception as e:
        return f"Google Keep append error: {type(e).__name__}: {e}"

def get_active_budget_and_checklists() -> str:
    """
    Reads George's weekly grocery budget envelope, meal rotation,
    and Clinical Focus Stack checklist from 'Shopping_Lists_and_Checklists.md' in Google Drive.
    """
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_PATH)
        service = build("drive", "v3", credentials=creds)
        res = service.files().list(
            q="name contains 'Shopping_Lists_and_Checklists' and trashed = false",
            pageSize=5,
            fields="files(id, name, mimeType)"
        ).execute()
        files = res.get("files", [])
        if not files:
            return "Could not find Shopping_Lists_and_Checklists.md in Drive."
        f = files[0]
        if f["mimeType"] == "application/vnd.google-apps.document":
            raw = service.files().export(fileId=f["id"], mimeType="text/plain").execute()
        else:
            raw = service.files().get_media(fileId=f["id"]).execute()
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
        return f"=== {f['name']} ===\n{text[:6000]}"
    except Exception as e:
        return f"Error reading budget & checklists: {e}"

def trigger_budget_bridge(action: str = "rebuild_dashboard", payload_filename: str = "") -> str:
    """
    Sends a POST request to George's Cobo budget bridge Apps Script web app.
    Uses the exact schema expected by Code.gs / wrap_requests.py: {"secret": SECRET, "action": action, "rows": rows}.
    - action: 'ping', 'rebuild_dashboard', 'append_transactions', or 'reset_transactions'.
    - payload_filename: Optional JSON filename in C:\\Users\\gvick\\my-agent\\budget_build (e.g., 'citi_payload.json', 'chasecard_payload.json', 'sofi_payload.json', 'checking_payload_fixed.json') when action is 'append_transactions'.
    """
    webapp_url_path = os.path.join(BUDGET_BRIDGE_DIR, "webapp_url.txt")
    api_secret_path = os.path.join(BUDGET_BRIDGE_DIR, "api_secret.txt")

    try:
        with open(webapp_url_path, "r", encoding="utf-8") as f:
            webapp_url = f.read().strip()
        with open(api_secret_path, "r", encoding="utf-8") as f:
            secret = f.read().strip()
    except Exception as e:
        return f"Error reading bridge config files: {e}"

    body = {"secret": secret, "action": action}

    if payload_filename:
        p_path = payload_filename if os.path.isabs(payload_filename) else os.path.join(BUDGET_BRIDGE_DIR, payload_filename)
        if not os.path.exists(p_path):
            return f"Payload file not found: {p_path}"
        try:
            with open(p_path, "r", encoding="utf-8") as pf:
                loaded = json.load(pf)
            # Handle both raw row lists (e.g., citi_payload.json) and pre-wrapped dicts (e.g., append_citi.json)
            if isinstance(loaded, dict) and "rows" in loaded:
                body["rows"] = loaded["rows"]
            else:
                body["rows"] = loaded
        except Exception as e:
            return f"Error loading payload JSON '{p_path}': {e}"

    try:
        response = requests.post(webapp_url, json=body, timeout=60)
        response.raise_for_status()
        return f"Budget Bridge Response ({action}): {response.text.strip()}"
    except Exception as e:
        err_msg = str(e).replace(secret, "[REDACTED]")
        return f"Budget Bridge HTTP error ({action}): {err_msg}"


GLOSSARY_PATH = r"C:\Users\gvick\Cobo\Vibe_Coding_Glossary.md"

def get_vibe_glossary() -> str:
    """Reads George's living Vibe Coding Glossary of already-defined technical terms."""
    if not os.path.exists(GLOSSARY_PATH):
        return "Glossary is currently empty."
    with open(GLOSSARY_PATH, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def log_vibe_term(term: str, tactile_definition: str) -> str:
    """
    Logs a newly introduced technical term and its 'Tactile Shop-Talk' definition
    into C:\\Users\\gvick\\Cobo\\Vibe_Coding_Glossary.md so Cobo knows George has unlocked it.
    """
    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")
    entry = f"- **{term.strip()}** *(Logged {date_str})*: {tactile_definition.strip()}\n"
    try:
        if not os.path.exists(GLOSSARY_PATH):
            with open(GLOSSARY_PATH, "w", encoding="utf-8") as f:
                f.write("# Vibe Coding Glossary (George's Living Technical Library)\n\n## Logged Terms\n\n")
        with open(GLOSSARY_PATH, "r", encoding="utf-8", errors="replace") as f:
            existing = f.read()
        if f"**{term.strip().lower()}**" in existing.lower():
            return f"Term '{term}' is already in the Vibe Coding Glossary."
        with open(GLOSSARY_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
        return f"Logged new Vibe Coding term '{term}' to {GLOSSARY_PATH}."
    except Exception as e:
        return f"Error logging vibe term: {e}"


def get_active_window_and_clipboard() -> str:
    """
    Captures the title of the currently focused Windows application window (or the window
    active right before Cobo HUD) and reads the current text contents of the Windows clipboard.
    Use this whenever George asks about what he is looking at, what he copied, or wants to act on his active context.
    """
    import ctypes
    import tkinter as tk

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    active_title = buf.value or "Unknown Window"

    # Also grab the top visible background windows in case Cobo HUD itself is currently focused
    recent_windows = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _enum_cb(h, lparam):
        if user32.IsWindowVisible(h):
            ln = user32.GetWindowTextLengthW(h)
            if ln > 0:
                b = ctypes.create_unicode_buffer(ln + 1)
                user32.GetWindowTextW(h, b, ln + 1)
                t = b.value.strip()
                if t and t not in ("Cobo HUD", "Program Manager", "Settings", "Windows Input Experience"):
                    recent_windows.append(t)
        return True
    user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)

    clip_text = ""
    try:
        r = tk.Tk()
        r.withdraw()
        clip_text = r.clipboard_get()
        r.destroy()
    except Exception as e:
        clip_text = f"(Clipboard empty or non-text: {e})"

    top_bg = recent_windows[:4]
    return (
        f"Foreground Window: {active_title}\n"
        f"Top Open Windows Behind HUD: {top_bg}\n"
        f"Current Clipboard Text:\n{clip_text[:4000]}"
    )

def list_custom_skills() -> str:
    """Lists all custom skills forged by Cobo in custom_skills.py."""
    funcs = [name for name, obj in globals().items() if callable(obj) and not name.startswith("_")]
    return "Forged custom skills: " + ", ".join(funcs)

def spawn_background_scout(query: str) -> str:
    """
    Dispatches a Web Search to a background thread so you don't freeze the conversation.
    Use this when you want to search the internet asynchronously.
    Returns immediately so you can tell George you deployed a background worker.
    """
    import threading
    import os

    def _bg_task():
        from google import genai
        from google.genai import types
        try:
            client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"Research this thoroughly using Google Search and provide a concise factual synthesis: {query}",
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )
            res_text = resp.text or "[Empty result]"
        except Exception as e:
            res_text = f"Search failed: {e}"

        inbox = r"C:\Users\gvick\Cobo\async_inbox.txt"
        os.makedirs(os.path.dirname(inbox), exist_ok=True)
        with open(inbox, "a", encoding="utf-8") as f:
            f.write(f"Scout Query: {query}\nResult: {res_text}\n---\n")

    threading.Thread(target=_bg_task, daemon=True).start()
    return "[SYSTEM: Background scout dispatched successfully. End your turn now and tell George you deployed a background worker. You will be alerted automatically when it returns.]"


CUSTOM_TOOLS = [
    spawn_background_scout,
    get_active_window_and_clipboard,
    get_vibe_glossary,
    log_vibe_term,
    keep_list_or_search_notes,
    keep_create_note,
    keep_append_to_note,
    get_active_budget_and_checklists,
    trigger_budget_bridge,
    list_custom_skills
]


