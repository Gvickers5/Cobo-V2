import os
import re
import webbrowser
import tkinter as tk
from tkinter import scrolledtext
import threading
import ctypes

GLOSSARY_PATH = r"C:\Users\gvick\Cobo\Vibe_Coding_Glossary.md"

class CoboHUD(tk.Tk):
    def __init__(self, on_submit=None):
        super().__init__()
        self.on_submit = on_submit
        self.title("Cobo HUD")
        self.geometry("460x620+100+100")

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.94)
        self.config(bg="#1e1e1e")

        self.is_collapsed = False
        self._drag_data = {"x": 0, "y": 0}
        self._popup_win = None
        self._tag_counter = 0
        self.vibe_mode = "PASSIVE"  # Cycles: PASSIVE -> TEACH -> OFF
        self.after(2000, self.check_async_inbox)

        main_frame = tk.Frame(self, bg="#1e1e1e", padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        self.main_frame = main_frame

        # Title Bar / Header
        header_frame = tk.Frame(main_frame, bg="#252526", height=30)
        header_frame.pack(fill=tk.X, pady=(0, 8))
        header_frame.bind("<Button-1>", self._on_drag_start)
        header_frame.bind("<B1-Motion>", self._on_drag_motion)

        title_label = tk.Label(header_frame, text="\u26a1 Cobo HUD", fg="#ffffff", bg="#252526", font=("Segoe UI", 10, "bold"))
        title_label.pack(side=tk.LEFT, padx=5)
        title_label.bind("<Button-1>", self._on_drag_start)
        title_label.bind("<B1-Motion>", self._on_drag_motion)

        # Window Controls (Hard Close, Collapse, Copy Log, Glossary Button)
        close_btn = tk.Button(header_frame, text="\u00d7", fg="#ffffff", bg="#252526", activebackground="#e81123", activeforeground="#ffffff", bd=0, font=("Segoe UI", 12, "bold"), command=self.hard_close)
        close_btn.pack(side=tk.RIGHT, padx=5)

        self.min_btn = tk.Button(header_frame, text="\u2014", fg="#ffffff", bg="#252526", activebackground="#3f3f46", activeforeground="#ffffff", bd=0, font=("Segoe UI", 10), command=self.toggle_collapse)
        self.min_btn.pack(side=tk.RIGHT, padx=2)

        self.copy_btn = tk.Button(header_frame, text="Copy", fg="#4ec9b0", bg="#252526", activebackground="#3f3f46", activeforeground="#ffffff", bd=0, font=("Segoe UI", 9), command=self.copy_all_text)
        self.copy_btn.pack(side=tk.RIGHT, padx=6)

        self.glossary_btn = tk.Button(header_frame, text="Glossary", fg="#dcdcaa", bg="#252526", activebackground="#3f3f46", activeforeground="#ffffff", bd=0, font=("Segoe UI", 9, "underline"), command=self.open_glossary_in_obsidian)
        self.glossary_btn.pack(side=tk.RIGHT, padx=4)

        self.vibe_btn = tk.Button(
            header_frame,
            text="Vibe: PASSIVE",
            fg="#4ec9b0",
            bg="#252526",
            activebackground="#3f3f46",
            activeforeground="#ffffff",
            bd=0,
            font=("Segoe UI", 8, "bold"),
            command=self.cycle_vibe_mode
        )
        self.vibe_btn.pack(side=tk.RIGHT, padx=4)

        self.content_widgets = []

        # Interactive Text Input Section
        input_label = tk.Label(main_frame, text="Command / Message Cobo (Enter to send, Shift+Enter for newline):", fg="#858585", bg="#1e1e1e", font=("Segoe UI", 8))
        input_label.pack(anchor="w")
        self.content_widgets.append(input_label)

        input_row = tk.Frame(main_frame, bg="#1e1e1e")
        input_row.pack(fill=tk.X, pady=(2, 8))
        self.content_widgets.append(input_row)

        self.input_box = tk.Text(
            input_row,
            height=2,
            wrap=tk.WORD,
            bg="#2d2d2d",
            fg="#ffffff",
            insertbackground="#4ec9b0",
            bd=1,
            relief=tk.FLAT,
            font=("Segoe UI", 10),
            padx=6,
            pady=4
        )
        self.input_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_box.bind("<Return>", self._handle_return)
        self.input_box.bind("<Shift-Return>", self._handle_shift_return)

        self.send_btn = tk.Button(
            input_row,
            text="Send",
            fg="#1e1e1e",
            bg="#4ec9b0",
            activebackground="#3ba892",
            activeforeground="#1e1e1e",
            bd=0,
            font=("Segoe UI", 9, "bold"),
            padx=10,
            command=self.submit_input
        )
        self.send_btn.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))

        # Compact Live Status Strip
        self.status_label = tk.Label(main_frame, text="Status: Ready. Hold [HOME] to speak or type above.", fg="#4ec9b0", bg="#1e1e1e", font=("Segoe UI", 8, "italic"), anchor="w")
        self.status_label.pack(fill=tk.X, pady=(0, 6))
        self.content_widgets.append(self.status_label)

        # Main Conversation & Vault Output Section
        conv_label_title = tk.Label(main_frame, text="Conversation & Live Output (Click cyan underlined terms for definitions):", fg="#4ec9b0", bg="#1e1e1e", font=("Segoe UI", 8, "bold"))
        conv_label_title.pack(anchor="w")
        self.content_widgets.append(conv_label_title)

        self.conversation_box = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, bg="#252526", fg="#d4d4d4", bd=0, font=("Segoe UI", 10), padx=6, pady=6)
        self.conversation_box.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        self.conversation_box.bind("<Key>", self._allow_copy_only)
        self.content_widgets.append(self.conversation_box)

        self.protocol("WM_DELETE_WINDOW", self.hard_close)
        self.after(100, self._enable_taskbar_icon)
        self.after(150, lambda: self.input_box.focus_set())

    def check_async_inbox(self):
        import os
        inbox = r"C:\Users\gvick\Cobo\async_inbox.txt"
        if os.path.exists(inbox):
            try:
                with open(inbox, "r", encoding="utf-8") as f:
                    data = f.read().strip()
                if data:
                    open(inbox, "w", encoding="utf-8").close()
                    if hasattr(self, 'manager') and self.manager and hasattr(self.manager, 'handle_async_event'):
                        self.manager.handle_async_event(data)
            except Exception:
                pass
        self.after(2000, self.check_async_inbox)

    def cycle_vibe_mode(self):
        modes = ["PASSIVE", "TEACH", "OFF"]
        colors = {"PASSIVE": "#4ec9b0", "TEACH": "#dcdcaa", "OFF": "#858585"}
        idx = (modes.index(self.vibe_mode) + 1) % len(modes)
        self.vibe_mode = modes[idx]
        self.vibe_btn.config(text=f"Vibe: {self.vibe_mode}", fg=colors[self.vibe_mode])
        self.update_subtitle(f"Vibe Coding Plugin set to {self.vibe_mode}")

    def open_glossary_in_obsidian(self):
        try:
            webbrowser.open("obsidian://open?vault=Cobo&file=Vibe_Coding_Glossary")
        except Exception:
            pass

    def _load_glossary_entries(self):
        """Parses Vibe_Coding_Glossary.md and auto-generates morphological stems for every logged term."""
        if not os.path.exists(GLOSSARY_PATH):
            return []
        entries = []

        def _expand_stems(word):
            w = word.strip()
            if len(w) < 4:
                return {w}
            forms = {w, w + "s", w + "es", w + "ed", w + "ing"}
            wl = w.lower()
            if wl.endswith("e"):
                base = w[:-1]
                forms.update([base + "ing", base + "ed", base + "tion"])
            if wl.endswith("tion"):
                base = w[:-4]
                forms.update([base + "te", base + "ted", base + "ting", base + "tive"])
            if wl.endswith("cy"):
                base = w[:-2]
                forms.update([base + "t", base + "ts"])
            if wl.endswith("ing") and len(w) > 6:
                base = w[:-3]
                forms.update([base, base + "s", base + "ed", base + "es"])
            if wl.endswith("y") and len(w) > 4:
                base = w[:-1]
                forms.update([base + "ies", base + "ied"])
            return forms

        try:
            with open(GLOSSARY_PATH, "r", encoding="utf-8-sig", errors="replace") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line.startswith("-") or "**" not in line or ":" not in line:
                        continue
                    m = re.search(r"\*\*(.+?)\*\*[^:]*:\s*(.+)$", line)
                    if m:
                        canonical = m.group(1).strip()
                        definition = m.group(2).strip()
                        clean_no_ticks = canonical.replace("`", "").strip()
                        base_phrases = {clean_no_ticks}

                        for part in re.split(r"[/()]", clean_no_ticks):
                            p = part.strip()
                            if len(p) >= 3:
                                base_phrases.add(p)

                        all_variants = set()
                        for bp in base_phrases:
                            all_variants.add(bp)
                            if " " not in bp:
                                all_variants.update(_expand_stems(bp))

                        for v in all_variants:
                            entries.append((v, canonical, definition))
        except Exception:
            pass
        entries.sort(key=lambda x: len(x[0]), reverse=True)
        return entries

    def _close_popup(self):
        if self._popup_win is not None:
            try:
                self._popup_win.destroy()
            except Exception:
                pass
            self._popup_win = None

    def _show_term_popup(self, event, canonical_term, definition):
        self._close_popup()
        popup = tk.Toplevel(self)
        popup.wm_overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.config(bg="#4ec9b0", padx=1, pady=1)

        inner = tk.Frame(popup, bg="#1e1e1e", padx=12, pady=10)
        inner.pack(fill=tk.BOTH, expand=True)

        top_bar = tk.Frame(inner, bg="#1e1e1e")
        top_bar.pack(fill=tk.X, pady=(0, 6))

        hdr = tk.Label(top_bar, text=f"\ud83d\udcd6 {canonical_term}", fg="#4ec9b0", bg="#1e1e1e", font=("Segoe UI", 10, "bold"), anchor="w")
        hdr.pack(side=tk.LEFT)

        close_lbl = tk.Button(top_bar, text="\u00d7", fg="#ffffff", bg="#2d2d2d", activebackground="#e81123", activeforeground="#ffffff", bd=0, padx=6, font=("Segoe UI", 9, "bold"), command=self._close_popup)
        close_lbl.pack(side=tk.RIGHT)

        body = tk.Label(inner, text=definition, fg="#e0e0e0", bg="#1e1e1e", font=("Segoe UI", 9), wraplength=340, justify=tk.LEFT, anchor="w")
        body.pack(fill=tk.X, pady=(0, 8))

        btn_row = tk.Frame(inner, bg="#1e1e1e")
        btn_row.pack(fill=tk.X)

        obs_btn = tk.Button(
            btn_row,
            text="Open Full Glossary in Obsidian \u2197",
            fg="#1e1e1e",
            bg="#dcdcaa",
            activebackground="#c8c696",
            activeforeground="#1e1e1e",
            bd=0,
            padx=8,
            pady=3,
            font=("Segoe UI", 8, "bold"),
            command=lambda: (self.open_glossary_in_obsidian(), self._close_popup())
        )
        obs_btn.pack(side=tk.LEFT)

        x = min(event.x_root + 10, self.winfo_screenwidth() - 380)
        y = max(event.y_root - 100, 20)
        popup.geometry(f"+{x}+{y}")
        self._popup_win = popup

    def _highlight_glossary_terms(self):
        """Uses Tkinter's native Text.search() to highlight all glossary terms across the conversation box."""
        entries = self._load_glossary_entries()
        if not entries:
            return

        # Clear existing vibe_term tags so we can cleanly re-index the whole conversation
        for tag in list(self.conversation_box.tag_names()):
            if tag.startswith("vibe_term_"):
                self.conversation_box.tag_delete(tag)

        word_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")

        for phrase, canonical, definition in entries:
            if not phrase:
                continue
            start_pos = "1.0"
            while True:
                pos = self.conversation_box.search(phrase, start_pos, stopindex=tk.END, nocase=True)
                if not pos:
                    break
                end_pos = f"{pos}+{len(phrase)}c"

                # Verify whole-word boundary so short terms don't match inside longer words
                prev_char = self.conversation_box.get(f"{pos}-1c", pos) if pos != "1.0" else " "
                next_char = self.conversation_box.get(end_pos, f"{end_pos}+1c")

                if prev_char not in word_chars and next_char not in word_chars:
                    # Skip if already tagged by a longer phrase
                    existing_tags = [t for t in self.conversation_box.tag_names(pos) if t.startswith("vibe_term_")]
                    if not existing_tags:
                        self._tag_counter += 1
                        tag_name = f"vibe_term_{self._tag_counter}"
                        self.conversation_box.tag_add(tag_name, pos, end_pos)
                        self.conversation_box.tag_config(tag_name, foreground="#4ec9b0", underline=True, font=("Segoe UI", 10, "bold"))
                        self.conversation_box.tag_bind(tag_name, "<Enter>", lambda e: self.conversation_box.config(cursor="hand2"))
                        self.conversation_box.tag_bind(tag_name, "<Leave>", lambda e: self.conversation_box.config(cursor=""))
                        self.conversation_box.tag_bind(
                            tag_name,
                            "<Button-1>",
                            lambda e, c=canonical, d=definition: self._show_term_popup(e, c, d)
                        )
                start_pos = end_pos

    def _handle_return(self, event):
        self.submit_input()
        return "break"

    def _handle_shift_return(self, event):
        return None

    def submit_input(self):
        text = self.input_box.get("1.0", tk.END).strip()
        if not text:
            return
        self.input_box.delete("1.0", tk.END)
        if self.on_submit:
            threading.Thread(target=self.on_submit, args=(text,), daemon=True).start()

    def _allow_copy_only(self, event):
        if (event.state & 0x4) and event.keysym.lower() in ("c", "a"):
            return None
        if event.keysym in ("Up", "Down", "Left", "Right", "Prior", "Next", "Home", "End"):
            return None
        return "break"

    def copy_all_text(self):
        try:
            if self.conversation_box.tag_ranges(tk.SEL):
                text = self.conversation_box.get(tk.SEL_FIRST, tk.SEL_LAST)
            else:
                text = self.conversation_box.get("1.0", tk.END).strip()
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            self.copy_btn.config(text="Copied!")
            self.after(1500, lambda: self.copy_btn.config(text="Copy"))
        except Exception:
            pass

    def hard_close(self):
        try:
            self.destroy()
        except Exception:
            pass
        os._exit(0)

    def _enable_taskbar_icon(self):
        try:
            HWND = ctypes.windll.user32.GetParent(self.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(HWND, -20)
            style = style & ~0x00000080
            style = style | 0x00040000
            ctypes.windll.user32.SetWindowLongW(HWND, -20, style)
            self.withdraw()
            self.deiconify()
        except Exception:
            pass

    def toggle_collapse(self):
        current_x = self.winfo_x()
        current_y = self.winfo_y()

        if not self.is_collapsed:
            self._close_popup()
            for widget in self.content_widgets:
                widget.pack_forget()
            self.geometry(f"460x50+{current_x}+{current_y}")
            self.min_btn.config(text="+")
            self.is_collapsed = True
        else:
            self.content_widgets[0].pack(anchor="w")
            self.content_widgets[1].pack(fill=tk.X, pady=(2, 8))
            self.content_widgets[2].pack(fill=tk.X, pady=(0, 6))
            self.content_widgets[3].pack(anchor="w")
            self.content_widgets[4].pack(fill=tk.BOTH, expand=True, pady=(2, 0))
            self.geometry(f"460x620+{current_x}+{current_y}")
            self.min_btn.config(text="\u2014")
            self.is_collapsed = False

    def _on_drag_start(self, event):
        self._drag_data["x"] = event.x_root
        self._drag_data["y"] = event.y_root

    def _on_drag_motion(self, event):
        delta_x = event.x_root - self._drag_data["x"]
        delta_y = event.y_root - self._drag_data["y"]
        x = self.winfo_x() + delta_x
        y = self.winfo_y() + delta_y
        self.geometry(f"+{x}+{y}")
        self._drag_data["x"] = event.x_root
        self._drag_data["y"] = event.y_root

    def update_subtitle(self, text):
        def _update():
            short_status = text.replace("\n", " ").strip()
            if len(short_status) > 75:
                short_status = short_status[:72] + "..."
            self.status_label.config(text=f"Status: {short_status}")
        self.after(0, _update)

    def append_conversation(self, sender, text):
        def _update():
            self.conversation_box.insert(tk.END, f"\n[{sender}]:\n{text}\n")
            self._highlight_glossary_terms()
            self.conversation_box.see(tk.END)
        self.after(0, _update)

def run_hud(hud_ref_container, on_submit=None):
    hud = CoboHUD(on_submit=on_submit)
    hud_ref_container['hud'] = hud
    hud.mainloop()