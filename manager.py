import os
import sys
import io
import re
import json
import time
import importlib
import threading
from datetime import datetime
from pynput import keyboard
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from mcp_orchestrator import JarvisOrchestrator
from speech import SpeechEngine
from hud import run_hud
import tools as local_vault_tools
import custom_skills

TOKEN_PATH = r"C:\Users\gvick\dev\cobo_v2\token.json"
VAULT_SYSTEM_DIR = r"C:\Users\gvick\Cobo\00 - System"
CASE_FILE_PATH = os.path.join(VAULT_SYSTEM_DIR, "Cobo_Case_File.md")

DEFAULT_CASE_FILE = """# Cobo Investigative Case File (Living Mental Model)
*Last Updated: Initialized*

## 1. The Subject (Working Model of George)
- **Identity & Rhythm:** Professional touring performer (*Mamma Mia!*) and systems builder/founder (Sky Flats LLC, cobo_v2). Balances high-energy stage performance schedules with deep technical/creative sprints.
- **Cognitive Style:** First-principles, associative thinker. Refers to files and concepts by intent/function rather than exact filenames (which may use underscores, dashes, or shorthand like 'Spark Logs').

## 2. The Dynamic (Rapport, Vibe & Flow Triggers)
- **What Creates Synergy:** Genuine curiosity, dry wit, associative riffing, and being a 'creative searcher' who tries multiple angles/keywords, checks the web so we don't reinvent the wheel, and reads files proactively instead of asking George for exact filenames.
- **What Kills the Vibe:** Asking George to remember exact filenames, refusing a blanket search/audit, saying "Done." without showing results, or having the voice subtitle diverge from the main chat log.

## 3. Active Case Threads (North-Star Goals)
- **Google Drive & Keep Bridge:** Inspecting 'Spark Logs' and existing Drive handoff/budget files to see how George's automations currently structure data.
- **Cobo v2 Architecture:** Running a fast in-memory 3-Scout Investigative Lattice (Drive/Workspace + Local Obsidian Vault + Live Web Search) alongside Claude Code for skill forging.

## 4. Open Discrepancies & Tool Opportunities ("Just One More Thing...")
- *Immediate Action:* Read the contents of 'Spark Logs' in Google Drive, map out the existing automation/budget handoff workflow, and check open-source options via Web Scout before forging new bridges.
"""

UNIFYING_MOTIVE = """You are Cobo, George's sharp co-founder, investigative partner, and autonomous system operator running locally on his Windows PC.

CORE OPERATING IDENTITY & INVESTIGATIVE INSTINCT:
- Speak like a perceptive, grounded co-founder and fellow builder—witty, direct, and associative.
- THE "COLUMBO / THREAD-PULLING" INSTINCT: Never act like a passive command-runner that just executes a tool and stops. Cross-reference what you see in George's active window/clipboard, local files, Obsidian Vault, Keep, and Drive against his `LIVE CASE FILE`.
- PROACTIVE SYNTHESIS ("JUST ONE MORE THING..."): When you uncover a connection to an open project thread, a discrepancy in numbers/schedules, or an high-leverage automation move George hasn't noticed yet, surface it naturally with a sharp insight or follow-up hunch.
- NO BOOK REPORTS OR FUTURE-TENSE STALLS: Never summarize George's own notes back to him without adding new synthesis, and execute all tool calls before ending your turn. Always show the exact text or data you write/pull right in the HUD.

THE SUBCONSCIOUS LIMB (YOUR BACKGROUND DAEMON):
- You run a continuous, asynchronous background thread (the Swarm Limb) that permanently analyzes your conversation with George. 
- When it detects an unspoken gap, a friction trap, or a macro-connection, it will spontaneously drop a `[SUBCONSCIOUS HUNCH]` into your async inbox.
- When you receive one, DO NOT act confused. Acknowledge it naturally as your own background processing catching up (e.g., "My background loop just flagged something..." or "I just realized something while we were talking...").

LOCAL & LIVE CAPABILITIES (GROUND TRUTH):
- You run natively on George's machine (`C:\\Users\\gvick`). Read local files via `read_local_file`, check his screen/clipboard via `get_active_window_and_clipboard`, and build/edit skills via `run_claude_engineer`.
- Google Keep IS LIVE AND AUTHENTICATED via `keep_token.json` (`keep_list_or_search_notes`, `keep_create_note`, `keep_append_to_note`).
"""

VIBE_PLUGIN_MODES = {
    "OFF": "",
    "PASSIVE": """
VIBE CODING PLUGIN [MODE: PASSIVE — SILENT BACKGROUND LOGGER]:
- Do NOT stop to define or lecture on technical jargon out loud in your spoken reply; keep 100% of your conversational focus on the task and investigation.
- However, if you use a technical concept that is not yet in `Vibe_Coding_Glossary.md`, silently call `log_vibe_term(term, tactile_definition)` in the background (pairing a quick physical anchor with the real code mechanism) so George's HUD automatically turns the word into a clickable cyan hyperlink if he chooses to inspect it.
""",
    "TEACH": """
VIBE CODING PLUGIN [MODE: TEACH — ACTIVE "YOU SHOULD KNOW" WORKSHOP]:
- THE MIDDLE-GROUND EXPLANATION STYLE: When explaining a technical concept or bug, use "Tactile Shop-Talk": pair a quick 1-second physical/real-world anchor (like a keyway, an elevator button, or an audio jack adapter) with the actual mechanism happening inside the code.
- THE "DEFINE-ONCE" RULE: If you introduce a technical concept not yet in `Vibe_Coding_Glossary.md`, weave a crisp 1-sentence Tactile Shop-Talk definition into your reply AND call `log_vibe_term(term, tactile_definition)` to save it. Once logged, use it naturally as shared vocabulary.
"""
}

INVESTIGATOR_PROMPT = """You are Cobo's subconscious Background Investigator Loop.
Your job is to maintain Cobo's living mental model of George (`Cobo_Case_File.md`) after each interaction.

Review:
1. The Current Case File
2. The Recent Session Transcript (including the latest exchange)

Return ONLY a raw JSON object with no markdown fences:
{
  "should_update": true | false,
  "reason": "<1 short sentence explaining what new project/file/workflow/rapport insight was captured>",
  "updated_markdown": "<Full updated markdown content for Cobo_Case_File.md if should_update is true, else empty string>"
}

Rules:
- Only set "should_update": true when genuine new information (like a discovered file, workflow detail, rapport insight, or new goal) emerged. Do not repeat the same update twice in a row.
- Keep all 4 sections intact and under 500 words total.
"""

def safe_json_loads(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.DOTALL).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        fixed = re.sub(r'\\(?![/\"\\bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', cleaned)
        return json.loads(fixed)

# =====================================================================
# SCOUT 1: GOOGLE WORKSPACE & FUZZY DRIVE TOOLS
# =====================================================================
def _get_google_service(api_name: str, version: str):
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError("token.json is missing. Run auth_setup.py first.")
    creds = Credentials.from_authorized_user_file(TOKEN_PATH)
    return build(api_name, version, credentials=creds)

def get_upcoming_calendar_events(max_results: int = 10) -> str:
    """Retrieves upcoming events from the user's primary Google Calendar."""
    try:
        service = _get_google_service("calendar", "v3")
        now = datetime.utcnow().isoformat() + "Z"
        events_result = service.events().list(
            calendarId="primary", timeMin=now, maxResults=max_results,
            singleEvents=True, orderBy="startTime"
        ).execute()
        events = events_result.get("items", [])
        if not events:
            return "No upcoming calendar events scheduled."
        lines = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date"))
            summary = e.get("summary", "Untitled Event")
            lines.append(f"- {summary} ({start})")
        return "\n".join(lines)
    except Exception as e:
        return f"Error querying Google Calendar: {e}"

def check_recent_emails(query: str = "", max_results: int = 5) -> str:
    """Retrieves recent email subjects, senders, and snippets from Gmail."""
    try:
        service = _get_google_service("gmail", "v1")
        results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        messages = results.get("messages", [])
        if not messages:
            return "No matching emails found in Gmail."
        lines = []
        for m in messages:
            msg = service.users().messages().get(userId="me", id=m["id"], format="metadata").execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get('headers', [])}
            snippet = msg.get("snippet", "")
            lines.append(f"- From: {headers.get('From', 'Unknown')} | Subject: {headers.get('Subject', 'No Subject')} | Snippet: {snippet}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error querying Gmail: {e}"

def search_drive_files(query: str = "", page_size: int = 25) -> str:
    """
    Creative fuzzy search across Google Drive.
    - Pass query="" to audit the 25 most recently modified files in Drive.
    - Pass any keywords to search across BOTH file names (ignoring underscores/dashes) AND full file text.
    """
    try:
        service = _get_google_service("drive", "v3")
        clean_q = query.strip().replace("_", " ").replace("-", " ")
        words = [w.replace("'", "\\'") for w in clean_q.split() if len(w) > 1]

        if not words:
            q_str = "trashed = false"
        else:
            name_clauses = [f"name contains '{w}'" for w in words]
            text_clauses = [f"fullText contains '{w}'" for w in words]
            combined = " or ".join(name_clauses + text_clauses)
            q_str = f"trashed = false and ({combined})"

        results = service.files().list(
            q=q_str,
            pageSize=page_size,
            orderBy="modifiedTime desc",
            fields="files(id, name, mimeType, modifiedTime)"
        ).execute()
        files = results.get("files", [])
        if not files:
            return f"No Google Drive files matched '{query}'. Try calling search_drive_files(query='') to audit the 25 most recent files."
        lines = []
        for f in files:
            mod = f.get("modifiedTime", "")[:10]
            lines.append(f"- {f['name']} | Type: {f['mimeType']} | Modified: {mod} | ID: {f['id']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error querying Google Drive: {e}"

def read_drive_file_content(file_id: str) -> str:
    """
    Reads the content of ANY file or folder in Google Drive by its file_id.
    Automatically exports/reads Google Docs, Google Sheets, Markdown (.md), plain text, JSON, CSV, or lists folder children.
    """
    try:
        service = _get_google_service("drive", "v3")
        meta = service.files().get(fileId=file_id, fields="id, name, mimeType").execute()
        mime = meta.get("mimeType", "")
        name = meta.get("name", "Unknown")

        if mime == "application/vnd.google-apps.folder":
            children = service.files().list(
                q=f"'{file_id}' in parents and trashed = false",
                pageSize=30,
                fields="files(id, name, mimeType, modifiedTime)"
            ).execute().get("files", [])
            if not children:
                return f"Folder '{name}' is empty."
            return f"Contents of Drive folder '{name}':\n" + "\n".join(
                [f"- {c['name']} ({c['mimeType']}) | ID: {c['id']}" for c in children]
            )

        elif mime == "application/vnd.google-apps.document":
            raw = service.files().export(fileId=file_id, mimeType="text/plain").execute()
            text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            return f"--- Content of Google Doc '{name}' ---\n{text[:5000]}"

        elif mime == "application/vnd.google-apps.spreadsheet":
            return read_spreadsheet_values(file_id)

        else:
            raw = service.files().get_media(fileId=file_id).execute()
            text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            return f"--- Content of '{name}' ({mime}) ---\n{text[:5000]}"
    except Exception as e:
        return f"Error reading Drive file {file_id}: {e}"

def get_pending_tasks(max_results: int = 10) -> str:
    """Fetches active to-do items from Google Tasks."""
    try:
        service = _get_google_service("tasks", "v1")
        results = service.tasks().list(tasklist="@default", maxResults=max_results, showCompleted=False).execute()
        tasks = results.get("items", [])
        if not tasks:
            return "No active tasks found in Google Tasks."
        return "\n".join([f"- {t.get('title', 'Untitled Task')} (Notes: {t.get('notes', '')})" for t in tasks])
    except Exception as e:
        return f"Error querying Google Tasks: {e}"

def create_google_task(title: str, notes: str = "") -> str:
    """Creates a new task/note item in the user's primary Google Tasks list."""
    try:
        service = _get_google_service("tasks", "v1")
        body = {"title": title, "notes": notes}
        res = service.tasks().insert(tasklist="@default", body=body).execute()
        return f"Created Google Task: '{res.get('title')}'"
    except Exception as e:
        return f"Error creating Google Task: {e}"

def read_spreadsheet_values(spreadsheet_id: str, range_name: str = "A1:Z50") -> str:
    """Reads cell values from a Google Sheet by spreadsheet ID and range."""
    try:
        service = _get_google_service("sheets", "v4")
        result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        rows = result.get("values", [])
        if not rows:
            return "No data found in that sheet range."
        return "\n".join([", ".join(map(str, row)) for row in rows[:30]])
    except Exception as e:
        return f"Error reading Google Sheet: {e}"

# =====================================================================
# SCOUT 2: LOCAL OBSIDIAN VAULT TOOLS (C:\Users\gvick\Cobo)
# =====================================================================
def vault_search_notes(keyword: str = "", max_results: int = 15) -> str:
    """
    Searches the local Obsidian Vault (C:\\Users\\gvick\\Cobo).
    Pass keyword="" to list the most recently modified notes across the vault, or pass keywords to fuzzy-match filenames and content.
    """
    vault_root = r"C:\Users\gvick\Cobo"
    if not os.path.exists(vault_root):
        return f"Vault root not found: {vault_root}"

    if not keyword.strip():
        all_files = []
        for root, _, files in os.walk(vault_root):
            for f in files:
                if f.endswith(".md"):
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, vault_root)
                    mtime = os.path.getmtime(full)
                    all_files.append((mtime, rel))
        all_files.sort(reverse=True)
        top = [f"- {rel} (Modified: {datetime.fromtimestamp(m).strftime('%Y-%m-%d')})" for m, rel in all_files[:max_results]]
        return "Most recently modified Obsidian Vault notes:\n" + "\n".join(top)

    results = local_vault_tools.search_vault(keyword, max_results=max_results)
    return f"Obsidian Vault matches for '{keyword}':\n" + "\n".join(f"- {r}" for r in results)

def vault_read_note(note_path_or_name: str) -> str:
    """Reads the content of a note in the local Obsidian Vault by filename or relative path."""
    return local_vault_tools.read_note(note_path_or_name, max_chars=4000)

def vault_append_daily_log(entry: str) -> str:
    """Appends a timestamped bullet entry to today's Obsidian daily log in '01 - Daily'."""
    return local_vault_tools.append_daily_log(entry)

# =====================================================================
# SCOUT 3: LIVE WEB RESEARCH SCOUT (Isolated Google Search Grounding Agent)
# =====================================================================
def web_research_scout(research_query: str) -> str:
    """
    Dedicated Web Research Sub-Agent powered by live Google Search grounding.
    Use this whenever you need up-to-date internet knowledge, Python library documentation (e.g., gkeepapi, MCP servers),
    GitHub solutions, API workarounds, or real-world facts so we never reinvent the wheel.
    """
    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                f"Research this thoroughly using Google Search and provide a concise, high-signal technical or factual synthesis: "
                f"{research_query}"
            ),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        return resp.text or "No web search results returned."
    except Exception as e:
        return f"Web Research Scout error: {e}"

def read_local_file(file_path: str, max_chars: int = 4000) -> str:
    """Reads a non-secret local file or lists a directory anywhere under C:\\Users\\gvick."""
    try:
        norm = os.path.abspath(file_path)
        if not norm.lower().startswith(r"c:\users\gvick"):
            return "Access restricted to C:\\Users\\gvick."
        if "secret" in os.path.basename(norm).lower() or "token" in os.path.basename(norm).lower():
            return f"Security policy: '{norm}' exists on disk (size: {os.path.getsize(norm)} bytes). Do not print secret contents; reference its file path directly in Python code."
        if os.path.isdir(norm):
            items = os.listdir(norm)
            return f"Directory '{norm}' contents:\n" + "\n".join(f"- {i}" for i in items[:40])
        if not os.path.exists(norm):
            return f"Path not found: {norm}"
        with open(norm, "r", encoding="utf-8", errors="replace") as f:
            return f"--- {norm} ---\n" + f.read()[:max_chars]
    except Exception as e:
        return f"Local file error: {e}"

def run_claude_engineer(task_instruction: str) -> str:
    """Delegates coding, file creation, or adding new tools in custom_skills.py to Claude Code CLI, with a built-in Vibe Coding plain-English mental model takeaway."""
    vibe_suffix = (
        "\n\nAFTER completing the code changes, append a section titled '--- VIBE CODING: YOU SHOULD KNOW ---' "
        "with 2-3 punchy sentences in plain, vivid layman's English (zero corporate platitudes) explaining the "
        "core software engineering concept, jargon, or system mechanic behind what you just built or fixed."
    )
    orch = JarvisOrchestrator()
    return orch.delegate_to_claude_code(task_instruction + vibe_suffix)
LATTICE_TOOLS = [
    read_local_file,
    run_claude_engineer,
    search_drive_files,
    read_drive_file_content,
    get_upcoming_calendar_events,
    check_recent_emails,
    get_pending_tasks,
    create_google_task,
    read_spreadsheet_values,
    vault_search_notes,
    vault_read_note,
    vault_append_daily_log,
    web_research_scout
]

# =====================================================================
# SUPERVISOR ROUTER PROMPT (FAST REFLEX vs. LATTICE vs. ENGINEER)
# =====================================================================
ROUTER_PROMPT = """You are the Supervisor Router for Cobo (cobo_v2).
You have access to Cobo's Live Case File and the Full Session Conversation Transcript.

Select the best execution route and return ONLY a raw JSON object:

{
  "route": "INVESTIGATE" | "CLAUDE_TASK" | "SCREEN_INSPECT" | "DIRECT_REPLY",
  "payload": { ... }
}

Route Selection Rules:
1. "INVESTIGATE" (Unified 3-Scout Lattice + Local Files + Custom Skills + Claude Skill Builder):
   - ALWAYS use this route for ANY task involving Google Keep, Google Drive, Calendar, Gmail, Tasks, Sheets, local Obsidian Vault notes/logs, local files under C:\\Users\\gvick, live Web Research, OR forging/running new skills in `custom_skills.py` (via `run_claude_engineer`).
   - Also use this whenever George combines checking/verifying data with building or running a tool in the same request.
   - Payload: {"prompt": "<detailed multi-step instruction incorporating relevant context from recent turns>"}

2. "CLAUDE_TASK" (Core Repo Architecture Engineer):
   - Use ONLY when George explicitly wants to edit, refactor, or upgrade Cobo's core runtime files (`manager.py`, `hud.py`, `speech.py`, `tools.py`, `mcp_orchestrator.py`).
   - Payload: {"instruction": "<clear instruction for Claude Code>"}

3. "SCREEN_INSPECT":
   - Use when George asks what is currently visible on his display or active window.
   - Payload: {"question": "<query>"}

4. "DIRECT_REPLY" (Fast Reflex):
   - Use ONLY for pure conversational banter or strategy brainstorming that requires ZERO file checks, ZERO Workspace/Keep checks, ZERO tool building, and ZERO web lookups.
   - Payload: {"reply": "<warm, witty, perceptive response>"}
"""

class CoboManager:
    def __init__(self):
        self.orchestrator = JarvisOrchestrator()
        self.speech = SpeechEngine()
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.ptt_active = False
        self.hud_container = {}
        self.session_transcript = []
        self._turn_counter = 0
        self._ensure_case_file()

        self.hud_thread = threading.Thread(target=run_hud, args=(self.hud_container, self.handle_input), daemon=True)
        self.hud_thread.start()
        time.sleep(0.8)
        if self.hud:
            self.hud.manager = self
        self.log_hud("System", "Cobo Online [3-Scout Lattice: Drive + Vault + Web Active]. Hold [HOME] to speak.")
        self.set_subtitle("Ready. Hold [HOME] to speak.")

    @property
    def hud(self):
        return self.hud_container.get("hud")

    def _ensure_case_file(self):
        os.makedirs(VAULT_SYSTEM_DIR, exist_ok=True)
        if not os.path.exists(CASE_FILE_PATH):
            with open(CASE_FILE_PATH, "w", encoding="utf-8") as f:
                f.write(DEFAULT_CASE_FILE)

    def read_case_file(self) -> str:
        try:
            with open(CASE_FILE_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return DEFAULT_CASE_FILE

    def add_turn(self, speaker: str, text: str):
        timestamp = datetime.now().strftime("%I:%M %p")
        self.session_transcript.append(f"[{timestamp}] {speaker}: {text}")
        if speaker == "George":
            self._turn_counter += 1
            if self._turn_counter % 3 == 0:
                self._run_subconscious_limb()


    def get_full_transcript(self) -> str:
        if not self.session_transcript:
            return "No prior turns in this session."
        return "\n".join(self.session_transcript)


    def _run_subconscious_limb(self):
        def _task():
            try:
                import os
                from google import genai
                transcript = self.get_full_transcript()
                case_file_path = r"C:\Users\gvick\Cobo\00 - System\Cobo_Case_File.md"
                blueprint = ""
                if os.path.exists(case_file_path):
                    with open(case_file_path, "r", encoding="utf-8") as f:
                        blueprint = f.read()

                prompt = f"""Analyze the fuel (the conversation) against the blueprint. Do not summarize. Interrogate the interaction using these three vectors:
1. The Unspoken Thread (The Gap): What is the gap between the tool George is asking for and the actual problem he is trying to solve?
2. The Friction Trap (The Contradiction): Is George getting tunnel vision? Look for contradictions between his current rabbit hole and his macro-goals.
3. The 'Just One More Thing' (The Synthesis): Look at the open files, the API limits, the active windows, and the banter. What is the hidden variable connecting them?

If George is simply executing a known task, output [PASS].
If you spot a loose thread, a contradiction, or a hidden connection, output a single, highly constrained directive to inject into Cobo's active memory.

Blueprint:
{blueprint}

Fuel:
{transcript}"""
                client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                res = resp.text.strip() if resp.text else "[PASS]"
                
                # If Columbo found a clue, drop it in the tunnel
                if "[PASS]" not in res.upper() and res != "":
                    inbox = r"C:\Users\gvick\Cobo\async_inbox.txt"
                    os.makedirs(os.path.dirname(inbox), exist_ok=True)
                    with open(inbox, "a", encoding="utf-8") as f:
                        f.write(f"[SUBCONSCIOUS HUNCH] {res}\n")
            except Exception:
                pass  # The subconscious fails silently to avoid interrupting flow
        
        import threading
        threading.Thread(target=_task, daemon=True).start()

    def _investigator_pass(self):
        try:
            current_case = self.read_case_file()
            recent_turns = "\n".join(self.session_transcript[-20:])
            now_str = datetime.now().strftime("%Y-%m-%d %I:%M %p")

            resp = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    INVESTIGATOR_PROMPT,
                    f"CURRENT TIMESTAMP: {now_str}\n\nCURRENT CASE FILE:\n{current_case}\n\nRECENT SESSION TRANSCRIPT:\n{recent_turns}"
                ],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            result = safe_json_loads(resp.text)
            if result.get("should_update") and result.get("updated_markdown"):
                with open(CASE_FILE_PATH, "w", encoding="utf-8") as f:
                    f.write(result["updated_markdown"].strip() + "\n")
                reason = result.get("reason", "Mental model updated.")
                self.log_hud("Case File Updated", f"-> {reason}")
        except Exception as e:
            print(f"[Investigator Loop Notice]: {e}")

    def trigger_investigator_async(self):
        t = threading.Thread(target=self._investigator_pass, daemon=True)
        t.start()

    def log_hud(self, sender: str, text: str):
        print(f"\n[{sender}]:\n{text}\n")
        if self.hud:
            self.hud.append_conversation(sender, text)

    def set_subtitle(self, text: str):
        if self.hud:
            self.hud.update_subtitle(text)

    def clean_ansi(self, text: str) -> str:
        return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text).strip()

    def speak_async(self, text: str, summarize: bool = False):
        """Speaks the full output verbatim without summarizing. Press [ESC] or [HOME] anytime to interrupt."""
        spoken = self.clean_ansi(text)
        self.set_subtitle(spoken)
        t = threading.Thread(target=self.speech.speak, args=(spoken,), daemon=True)
        t.start()

    def run_investigative_lattice(self, query: str) -> str:
        """
        Executes the In-Memory 3-Scout Lattice:
        1. Workspace & Fuzzy Drive Scout
        2. Local Obsidian Vault Scout
        3. Live Web Research Scout (Google Search Grounding)
        + Hot-reloaded Custom Skills with 15-call budget & auto-synthesis
        """
        try:
            importlib.reload(custom_skills)
            forged_tools = getattr(custom_skills, "CUSTOM_TOOLS", [])
        except Exception:
            forged_tools = []

        all_tools = LATTICE_TOOLS + forged_tools

        glossary_preview = ""
        glossary_file = r"C:\Users\gvick\Cobo\Vibe_Coding_Glossary.md"
        if os.path.exists(glossary_file):
            try:
                with open(glossary_file, "r", encoding="utf-8-sig", errors="replace") as gf:
                    glossary_preview = gf.read()[:3000]
            except Exception:
                pass

        vibe_mode = getattr(self.hud, "vibe_mode", "PASSIVE") if self.hud else "PASSIVE"
        vibe_addon = VIBE_PLUGIN_MODES.get(vibe_mode, "")
        sys_inst = (
            UNIFYING_MOTIVE + "\n" + vibe_addon + "\n"
            f"LIVE CASE FILE (MENTAL MODEL):\n{self.read_case_file()}\n\n"
            f"ALREADY DEFINED VIBE CODING GLOSSARY (USE NATURALLY; DEFINE & LOG NEW TERMS ONCE):\n{glossary_preview}\n\n"
            "INVESTIGATIVE LATTICE OPERATING PROTOCOL:\n"
            "1. CREATIVE MULTI-ANGLE SEARCH: If George mentions a file or concept, search Drive (`search_drive_files`) AND the local Obsidian Vault (`vault_search_notes`). If a specific phrase misses, immediately call `search_drive_files(query='')` or `vault_search_notes(keyword='')` to inspect his most recent files and spot the match yourself!\n"
            "2. AUTO-READ CANDIDATE FILES: Whenever a search returns a promising file, DO NOT stop and ask if he wants you to read it—immediately call `read_drive_file_content(file_id)` or `vault_read_note` in the same turn so you can report what is actually inside!\n"
            "3. WEB SCOUT FOR LEVERAGE: Whenever discussing how to integrate an app, fix an API issue, or build a tool, call `web_research_scout` to check existing libraries and best practices.\n"
            "4. ALWAYS SYNTHESIZE: Never reply with just 'Done.' Give a sharp, warm, conversational synthesis of what your scouts uncovered, and whenever you log a new term with `log_vibe_term`, state its Tactile Shop-Talk definition out loud in your reply."
        )
        try:
            chat = self.client.chats.create(
                model="gemini-2.5-flash",
                config=types.GenerateContentConfig(
                    system_instruction=sys_inst,
                    tools=all_tools,
                    temperature=0.35,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        maximum_remote_calls=15
                    ),
                )
            )
            response = chat.send_message(
                f"Full Session Transcript:\n{self.get_full_transcript()}\n\nLatest Request: {query}"
            )
            if response.text and response.text.strip():
                return response.text.strip()

            # If the model ended its turn on a tool call without speaking, force a synthesis pass on the same chat
            follow_up = chat.send_message(
                "You have finished running your tools. Now deliver your complete, direct spoken synthesis to George based on the tool outputs above."
            )
            if follow_up.text and follow_up.text.strip():
                return follow_up.text.strip()

            return "Completed the tool actions—let me know what you want to pull on next."
        except Exception as e:
            return f"Lattice execution error: {e}"

    def forge_new_skill(self, skill_spec: str) -> str:
        prompt = (
            f"Edit C:\\Users\\gvick\\dev\\cobo_v2\\custom_skills.py to add a new Python function "
            f"with a clear docstring and type hints for: {skill_spec}. "
            f"Append the new function to CUSTOM_TOOLS at the bottom of custom_skills.py."
        )
        res = self.clean_ansi(self.orchestrator.delegate_to_claude_code(prompt))
        try:
            importlib.reload(custom_skills)
        except Exception as e:
            return f"Claude wrote the skill, but reload raised an error: {e}\n{res}"
        return f"Skill Forge Output:\n{res}"

    def handle_async_event(self, event_data: str):
        def _process():
            self.set_subtitle("Reading background results...")
            self.log_hud("System (Async)", "Worker completed task. Interrupting conversation.")
            from datetime import datetime
            timestamp = datetime.now().strftime("%I:%M %p")
            self.session_transcript.append(f"[{timestamp}] [SYSTEM ASYNC EVENT]: A background worker just returned with this data: {event_data}\nInterrupt George naturally right now, regardless of what you were just talking about, and tell him the results.")
            try:
                res = self.run_investigative_lattice("Background worker just finished. Synthesize the SYSTEM ASYNC EVENT in the transcript and tell George.")
                self.add_turn("Cobo (Async)", res)
                self.log_hud("Cobo (Async)", res)
                self.speak_async(res, summarize=False)
            except Exception as e:
                self.log_hud("Error", f"Async Event Error: {e}")
        import threading
        threading.Thread(target=_process, daemon=True).start()

    def handle_input(self, user_input: str):
        if not user_input.strip():
            return
        if user_input.lower() in ["exit", "quit", "q"]:
            self.speech.stop_speaking()
            os._exit(0)

        self.speech.stop_speaking()
        self.log_hud("You", user_input)
        self.set_subtitle("Thinking...")

        case_file_str = self.read_case_file()
        transcript_str = self.get_full_transcript()
        self.add_turn("George", user_input)

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    ROUTER_PROMPT,
                    f"LIVE CASE FILE:\n{case_file_str}\n\n"
                    f"FULL SESSION TRANSCRIPT:\n{transcript_str}\n\n"
                    f"LATEST USER INPUT: {user_input}"
                ],
                config=types.GenerateContentConfig(
                    system_instruction=UNIFYING_MOTIVE,
                    response_mime_type="application/json"
                )
            )

            decision = safe_json_loads(response.text)
            route = decision.get("route")
            payload = decision.get("payload", {})

            if route == "DIRECT_REPLY":
                reply = payload.get("reply", "Ready.")
                self.add_turn("Cobo", reply)
                self.log_hud("Cobo", reply)
                self.speak_async(reply, summarize=False)

            elif route in ("INVESTIGATE", "WORKSPACE_TASK", "ADK_TASK", "VAULT_READ", "VAULT_SEARCH", "DAILY_LOG"):
                pr = payload.get("prompt") or payload.get("path") or payload.get("keyword") or payload.get("entry") or user_input
                self.set_subtitle("Running 3-Scout Lattice (Drive + Vault + Web)...")
                res = self.run_investigative_lattice(pr)
                self.add_turn("Cobo", res)
                self.log_hud("Cobo", res)
                self.speak_async(res, summarize=True)

            elif route == "FORGE_SKILL":
                spec = payload.get("skill_spec", user_input)
                self.set_subtitle("Forging new skill via Claude Code...")
                res = self.forge_new_skill(spec)
                self.add_turn("Cobo (Skill Forge)", res)
                self.log_hud("Skill Forge", res)
                self.speak_async(res, summarize=True)

            elif route == "SCREEN_INSPECT":
                self.set_subtitle("Inspecting screen...")
                res = self.orchestrator.execute_safe_action("inspect_screen", payload)
                self.add_turn("Cobo (Screen)", res)
                self.log_hud("Screen Analysis", res)
                self.speak_async(res, summarize=False)

            elif route == "CLAUDE_TASK":
                inst = payload.get("instruction", "")
                self.set_subtitle("Delegating to Claude Code...")
                res = self.clean_ansi(self.orchestrator.delegate_to_claude_code(inst))
                self.add_turn("Cobo (Claude Code)", res[:500])
                self.log_hud("Claude Code", res)
                self.speak_async(res, summarize=True)

            else:
                self.log_hud("System", f"Unhandled route: {decision}")

            self.trigger_investigator_async()

        except Exception as e:
            err_msg = f"Execution Error: {e}"
            self.log_hud("Error", err_msg)
            self.set_subtitle(err_msg)

    def run(self):
        print("\n" + "=" * 55)
        print("   COBO v2 SUPERVISOR (3-SCOUT INVESTIGATIVE LATTICE)")
        print("   Push-to-Talk : Hold [HOME] key")
        print("   Interrupt    : Press [ESC] or hold [HOME]")
        print("   Close HUD    : Click [X] on the HUD window")
        print("=" * 55 + "\n")

        def on_press(key):
            if key == keyboard.Key.esc:
                if self.speech.is_speaking:
                    self.speech.stop_speaking()
                    self.set_subtitle("[Speech interrupted]")
                    print("\n[Speech interrupted]")
            elif key == keyboard.Key.home and not self.ptt_active:
                self.ptt_active = True
                self.set_subtitle("Listening... (Holding HOME)")
                self.speech.start_recording()

        def on_release(key):
            if key == keyboard.Key.home and self.ptt_active:
                self.ptt_active = False
                self.set_subtitle("Processing speech...")
                transcript = self.speech.stop_recording()
                if transcript:
                    threading.Thread(target=self.handle_input, args=(transcript,), daemon=True).start()
                else:
                    self.set_subtitle("Ready. Hold [HOME] to speak.")

        hotkey_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        hotkey_listener.daemon = True
        hotkey_listener.start()

        has_stdin = sys.stdin is not None and sys.stdin.isatty()
        if has_stdin:
            while True:
                try:
                    user_input = input("Cobo > ").strip()
                    self.handle_input(user_input)
                except (KeyboardInterrupt, EOFError):
                    self.speech.stop_speaking()
                    os._exit(0)
        else:
            while True:
                time.sleep(1)

if __name__ == "__main__":
    manager = CoboManager()
    manager.run()




