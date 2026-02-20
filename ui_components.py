import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import threading
import time
import random
import queue
import json
import re
import os
import base64
import io
import requests
import mss
from datetime import datetime
from PIL import Image, ImageOps, ImageTk

from config import config
from data_structures import (
    twitch_data, INVISIBLE_CHARS, DONATION_MESSAGES, EVENT_MESSAGES, 
    EMOTE_LIST, EMOTE_COLORS, HYPE_WORDS, CHILL_WORDS, USERNAME_POOL, 
    USERNAME_COLORS, CHAT_PERSONALITIES, USER_BADGES
)

# ===========================
# HELPER FUNCTIONS
# ===========================

def clean_chat_line(text):
    for invisible, replacement in INVISIBLE_CHARS.items():
        text = text.replace(invisible, replacement)
    return ' '.join(text.split()).strip()

def get_screen_data_url(max_w=None, max_h=None):
    """Get screenshot as data URL"""
    if max_w is None:
        max_w = config.get("IMAGE_SIZE")
    if max_h is None:
        max_h = config.get("IMAGE_SIZE")
        
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            
            if config.get("ADAPTIVE_QUALITY") and threading.active_count() > 10:
                max_w = max_w // 2
                max_h = max_h // 2
                
            img = ImageOps.contain(img, (max_w, max_h))
            
            buf = io.BytesIO()
            quality = 70 if threading.active_count() <= 10 else 30
            img.save(buf, format="JPEG", quality=quality)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            buf.close()
            
            return f"data:image/jpeg;base64,{b64}", img
    except Exception as e:
        print(f"[ERROR] Screenshot error: {e}")
        return "data:image/jpeg;base64,", None

class LLMConnectionPool:
    def __init__(self):
        self.session = requests.Session() if config.get("KEEP_ALIVE_CONNECTION") else None
        self.request_queue = queue.Queue()
        self.active_requests = 0
        self.max_concurrent = config.get("CONCURRENT_REQUESTS", 2)
        
    def _call_llm(self, system_instructions, user_text, screen_data_url):
        payload = {
            "model": config.get("MODEL"),
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": system_instructions}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": screen_data_url}}
                    ]
                }
            ],
            "temperature": config.get("TEMPERATURE"),
            "max_tokens": config.get("MAX_TOKENS"),
            "stream": False
        }

        try:
            timeout = config.get("LLM_TIMEOUT", 30)
            if self.session:
                resp = self.session.post(config.get("API_URL"), json=payload, timeout=timeout)
            else:
                resp = requests.post(config.get("API_URL"), json=payload, timeout=timeout)
                
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return content
        except Exception as e:
            print(f"[ERROR] LLM Error: {e}")
            return ""

llm_pool = LLMConnectionPool()

# ===========================
# UI COMPONENTS
# ===========================

class ModernCheckbox:
    """Modern checkbox with colored indicator"""
    def __init__(self, parent, text, variable, command=None, description=""):
        self.frame = tk.Frame(parent, bg="#0E0E10")
        self.var = variable
        self.command = command
        
        self.canvas = tk.Canvas(self.frame, width=20, height=20, bg="#0E0E10", 
                               highlightthickness=0, borderwidth=0)
        self.canvas.pack(side="left", padx=(0, 8))
        self._draw_checkbox()
        self.canvas.bind("<Button-1>", self._toggle)
        
        self.label = tk.Label(self.frame, text=text, bg="#0E0E10", fg="#EFEFF1",
                            font=("Segoe UI", 10), cursor="hand2")
        self.label.pack(side="left", fill="x", expand=True)
        self.label.bind("<Button-1>", self._toggle)
        
        if description:
            desc_label = tk.Label(self.frame, text=description, bg="#0E0E10", fg="#888888",
                                font=("Segoe UI", 8), wraplength=300, justify="left")
            desc_label.pack(side="left", fill="x", expand=True, padx=(10, 0))
        
        self.var.trace("w", self._on_variable_change)
    
    def _draw_checkbox(self):
        self.canvas.delete("all")
        if self.var.get():
            self.canvas.create_rectangle(2, 2, 18, 18, fill="#44FF44", outline="#44FF44", width=2)
            self.canvas.create_text(10, 10, text="✓", fill="#0E0E10", font=("Segoe UI", 10, "bold"))
        else:
            self.canvas.create_rectangle(2, 2, 18, 18, fill="#FF4444", outline="#FF4444", width=2)
            self.canvas.create_text(10, 10, text="✗", fill="#0E0E10", font=("Segoe UI", 10, "bold"))
    
    def _toggle(self, event=None):
        self.var.set(not self.var.get())
        if self.command:
            self.command()
    
    def _on_variable_change(self, *args):
        self._draw_checkbox()
    
    def pack(self, **kwargs):
        return self.frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        return self.frame.grid(**kwargs)

class DonationPopup:
    def __init__(self, root, donor, amount, message, theme):
        self.popup = tk.Toplevel(root)
        self.popup.overrideredirect(True)
        self.popup.attributes("-topmost", True)
        self.popup.configure(bg="#1A1A1D", borderwidth=3, relief="raised")
        
        root.update_idletasks()
        main_x = root.winfo_x()
        main_y = root.winfo_y()
        main_width = root.winfo_width()
        popup_width = 320
        popup_height = 140
        
        x = main_x + (main_width // 2) - (popup_width // 2)
        y = main_y + 50
        
        self.popup.geometry(f'{popup_width}x{popup_height}+{x}+{y}')

        accent_color = "#9147FF"
        if theme == "hype" or theme == "high_value": accent_color = "#FFD700"
        elif theme == "troll": accent_color = "#DC143C"

        main_frame = tk.Frame(self.popup, bg="#1A1A1D")
        main_frame.pack(fill="both", expand=True, padx=15, pady=10)

        title_label = tk.Label(main_frame, text="NEW DONATION", bg="#1A1A1D", 
                              fg=accent_color, font=("Segoe UI", 13, "bold"))
        title_label.pack(fill="x")

        donor_text = f"{amount} from {donor}"
        donor_label = tk.Label(main_frame, text=donor_text, bg="#1A1A1D", 
                              fg="#EDEEEE", font=("Segoe UI", 12, "bold"))
        donor_label.pack(fill="x", pady=(2, 0))

        message_label = tk.Label(main_frame, text=message, bg="#1A1A1D", 
                                fg="#B0B0B0", font=("Segoe UI", 10), 
                                wraplength=popup_width - 30, justify="center")
        message_label.pack(fill="x", pady=(5, 0))

        if config.get("BIT_EFFECTS_ENABLED") and theme == "hype":
            self._add_bit_effects()
            
        self.popup.after(5000, self.popup.destroy)
        
    def _add_bit_effects(self):
        canvas = tk.Canvas(self.popup, bg="#1A1A1D", highlightthickness=0)
        canvas.place(x=0, y=0, relwidth=1, relheight=1)
        
        for _ in range(10):
            x = random.randint(10, 300)
            y = random.randint(10, 120)
            canvas.create_oval(x, y, x+4, y+4, fill="#FFD700", outline="")
            
        self.popup.after(1000, lambda: canvas.destroy())

class EmotePanel:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.panel = None
        
    def show(self):
        if self.panel and self.panel.winfo_exists():
            self.panel.lift()
            return
            
        self.panel = tk.Toplevel(self.parent)
        self.panel.title("Emote Panel")
        self.panel.geometry("300x400")
        self.panel.configure(bg="#1F1F23")
        self.panel.attributes("-topmost", True)
        
        self._create_emote_grid()
        
    def _create_emote_grid(self):
        frame = tk.Frame(self.panel, bg="#1F1F23")
        frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        for i, emote in enumerate(EMOTE_LIST[:20]):
            btn = tk.Button(frame, text=emote, bg="#9147FF", fg="white",
                          font=("Segoe UI", 10), relief="flat",
                          command=lambda e=emote: self._insert_emote(e))
            btn.grid(row=i//5, column=i%5, sticky="nsew", padx=2, pady=2)
            
        for i in range(5):
            frame.grid_columnconfigure(i, weight=1)
        for i in range(4):
            frame.grid_rowconfigure(i, weight=1)
            
    def _insert_emote(self, emote):
        current_text = self.app.input_entry.get()
        self.app.input_entry.delete(0, tk.END)
        self.app.input_entry.insert(0, current_text + " " + emote)

class EnhancedText(tk.Text):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def clear_highlights(self):
        self.tag_remove("search_highlight", "1.0", "end")

class StreamStatsPanel:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.frame = None
        self.live_indicator = None
        self.viewer_count_label = None
        self.follower_count_label = None
        self.is_live = False
        
    def create_panel(self):
        if not config.get("SHOW_STREAM_STATS"):
            return None
            
        self.frame = tk.Frame(self.parent, bg="#0E0E10", height=60)
        self.frame.pack(side="top", fill="x", padx=5, pady=5)
        self.frame.pack_propagate(False)
        
        # Live indicator
        live_frame = tk.Frame(self.frame, bg="#0E0E10")
        live_frame.pack(side="left", padx=10)
        
        self.live_indicator = tk.Label(live_frame, text="●", font=("Segoe UI", 12), 
                                      fg="#FF0000", bg="#0E0E10")
        self.live_indicator.pack(side="left")
        
        live_text = tk.Label(live_frame, text="LIVE", font=("Segoe UI", 10, "bold"), 
                           fg="#FFFFFF", bg="#0E0E10")
        live_text.pack(side="left", padx=(5, 0))
        
        # Viewer count
        viewer_frame = tk.Frame(self.frame, bg="#0E0E10")
        viewer_frame.pack(side="left", padx=20)
        
        viewer_icon = tk.Label(viewer_frame, text="👥", font=("Segoe UI", 10), 
                              bg="#0E0E10", fg="#FFFFFF")
        viewer_icon.pack(side="left")
        
        self.viewer_count_label = tk.Label(viewer_frame, text="0", font=("Segoe UI", 10), 
                                         bg="#0E0E10", fg="#FFFFFF")
        self.viewer_count_label.pack(side="left", padx=(5, 0))
        
        # Follower count
        follower_frame = tk.Frame(self.frame, bg="#0E0E10")
        follower_frame.pack(side="left", padx=20)
        
        follower_icon = tk.Label(follower_frame, text="❤️", font=("Segoe UI", 10), 
                                bg="#0E0E10", fg="#FFFFFF")
        follower_icon.pack(side="left")
        
        self.follower_count_label = tk.Label(follower_frame, 
                                           text=f"{twitch_data.follower_count}/{twitch_data.follower_goal}", 
                                           font=("Segoe UI", 10), bg="#0E0E10", fg="#FFFFFF")
        self.follower_count_label.pack(side="left", padx=(5, 0))
        
        return self.frame
    
    def update_stats(self):
        if not self.frame:
            return
            
        # Update viewer count with dynamic fluctuation
        if self.is_live:
            if config.get("DYNAMIC_VIEWER_COUNT"):
                self._update_dynamic_viewers()
            else:
                # Simple random fluctuation
                base_viewers = config.get("VIEWER_BASE_COUNT")
                fluctuation = random.randint(
                    config.get("VIEWER_FLUCTUATION_MIN"), 
                    config.get("VIEWER_FLUCTUATION_MAX")
                )
                twitch_data.viewer_count = max(10, base_viewers + fluctuation)
            
            if config.get("VIEWER_COUNT_AFFECTS_CHAT"):
                # Adjust batch size based on viewer count
                viewer_ratio = twitch_data.viewer_count / 100
                config.set("BATCH_SIZE", max(1, min(10, int(5 * viewer_ratio))))
            
            self.viewer_count_label.config(text=str(twitch_data.viewer_count))
            self.follower_count_label.config(
                text=f"{twitch_data.follower_count}/{twitch_data.follower_goal}"
            )
            
        # Animate live indicator
        if self.is_live and self.live_indicator:
            current_color = self.live_indicator.cget("fg")
            new_color = "#723333" if current_color == "#FF0000" else "#FF0000"
            self.live_indicator.config(fg=new_color)
            
        # Schedule next update
        if self.is_live:
            self.parent.after(2000, self.update_stats)
    
    def _update_dynamic_viewers(self):
        """Update viewer count with realistic dynamics"""
        current_hour = datetime.now().hour
        is_peak_hour = 18 <= current_hour <= 22  # 6 PM - 10 PM
        
        # Base growth with time
        time_factor = 1.0
        if is_peak_hour:
            time_factor = config.get("VIEWER_PEAK_HOUR_MULTIPLIER")
        
        # Calculate base viewers with growth
        base_viewers = config.get("VIEWER_BASE_COUNT") * time_factor
        growth_factor = 1.0 + (config.get("VIEWER_GROWTH_RATE") * len(twitch_data.viewer_history) / 60)
        
        # Add realistic fluctuation
        fluctuation = random.randint(
            config.get("VIEWER_FLUCTUATION_MIN"), 
            config.get("VIEWER_FLUCTUATION_MAX")
        )
        
        # Event-based spikes
        event_spike = 0
        if random.random() < 0.05:  # 5% chance of viewer spike
            event_spike = random.randint(5, 25)
        
        # Calculate new viewer count
        new_viewers = max(10, int(base_viewers * growth_factor + fluctuation + event_spike))
        
        # Smooth transition (avoid jumps)
        if twitch_data.viewer_count > 0:
            change = new_viewers - twitch_data.viewer_count
            if abs(change) > 20:  # Limit rapid changes
                new_viewers = twitch_data.viewer_count + (20 if change > 0 else -20)
        
        twitch_data.viewer_count = new_viewers
        twitch_data.viewer_history.append(new_viewers)
        twitch_data.peak_viewers = max(twitch_data.peak_viewers, new_viewers)
        twitch_data.total_views += new_viewers
    
    def set_live_status(self, is_live):
        self.is_live = is_live
        if is_live:
            self.update_stats()

class SettingsWindow:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.window = None
        self.restart_required_settings = [
            "WINDOW_WIDTH", "WINDOW_HEIGHT", "FONT_FAMILY", "HIDE_TITLE_BAR", "SETTINGS_DIR"
        ]
        
    def show(self):
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return
            
        self.window = tk.Toplevel(self.parent)
        self.window.title("Twitch Abello Settings")
        self.window.geometry("800x700")
        self.window.configure(bg="#0E0E10")
        self.window.attributes("-topmost", True)
        
        button_frame = tk.Frame(self.window, bg="#0E0E10")
        button_frame.pack(side="bottom", fill="x", pady=10)
        
        ttk.Button(button_frame, text="💾 Save Settings", 
                  command=config.save_settings).pack(side="left", padx=10)
        ttk.Button(button_frame, text="🔄 Load Defaults", 
                  command=self._load_defaults).pack(side="left", padx=10)
        ttk.Button(button_frame, text="❌ Close", 
                  command=self.window.destroy).pack(side="right", padx=10)
        
        self._create_notebook()
        
    def _create_notebook(self):
        style = ttk.Style()
        style.configure("TNotebook", background="#0E0E10")
        style.configure("TNotebook.Tab", background="#1F1F23", foreground="#EFEFF1",
                       padding=[15, 5], font=("Segoe UI", 10))
        style.map("TNotebook.Tab", background=[("selected", "#9147FF")])
        
        notebook = ttk.Notebook(self.window)
        
        tabs = [
            ("🎨 Display", self._create_display_settings, 16),
            ("🧠 Behavior", self._create_behavior_settings, 15),
            ("🌐 Language", self._create_language_settings, 10),
            ("⚡ Performance", self._create_performance_settings, 15),
            ("🎪 Events", self._create_event_settings, 10),
            ("🚀 Presets", self._create_preset_settings, 8),
        ]
        
        for tab_name, tab_creator, num_settings in tabs:
            frame = ttk.Frame(notebook)
            tab_creator(frame, num_settings)
            notebook.add(frame, text=tab_name)
        
        notebook.pack(expand=True, fill="both", padx=10, pady=10)
        
    def _create_display_settings(self, parent, num_settings):
        main_frame = tk.Frame(parent)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(main_frame, bg="#0E0E10", highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#0E0E10")
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        settings = [
            ("Settings Directory", "SETTINGS_DIR", "entry", {"description": "Directory where settings are saved (requires restart)"}),
            ("Streamer Name", "STREAMER_NAME", "entry", {"description": "Your streamer name (requires restart)"}),
            ("Chat Density", "CHAT_DENSITY", "combobox", {"values": ["compact", "normal", "comfortable"]}),
            ("Show Timestamps", "SHOW_TIMESTAMPS", "checkbox", {"description": "Show time next to messages"}),
            ("Auto-pause on Hover", "AUTO_PAUSE_ON_HOVER", "checkbox", {"description": "Pause chat when mouse is over it"}),
            ("Highlight Streamer Name", "HIGHLIGHT_USERNAME", "checkbox", {"description": "Highlight messages mentioning streamer"}),
            ("Animations Enabled", "ANIMATIONS_ENABLED", "checkbox", {"description": "Enable message fade-in animations"}),
            ("Smooth Scrolling", "SMOOTH_SCROLLING", "checkbox", {"description": "Smooth scroll instead of instant jumps"}),
            ("Window Always on Top", "WINDOW_ON_TOP", "checkbox", {"description": "Keep window above other applications"}),
            ("Hide Title Bar", "HIDE_TITLE_BAR", "checkbox", {"description": "Hide window title bar (requires restart)"}),
            ("Show Stream Stats", "SHOW_STREAM_STATS", "checkbox", {"description": "Show viewer count and controls"}),
            ("Debug Screenshot", "DEBUG_SCREENSHOT", "checkbox", {"description": "Show screenshot preview at top"}),
            ("Font Size", "TEXT_SIZE", "scale", {"from_": 8, "to": 16, "resolution": 1}),
            ("Window Width", "WINDOW_WIDTH", "scale", {"from_": 300, "to": 800, "resolution": 10, "description": "Window width (requires restart)"}),
            ("Window Height", "WINDOW_HEIGHT", "scale", {"from_": 400, "to": 1200, "resolution": 10, "description": "Window height (requires restart)"}),
        ]
        
        for i, (label, setting, type_, kwargs) in enumerate(settings[:num_settings]):
            self._create_setting_widget(scrollable_frame, label, setting, type_, kwargs, i)
        
        # Add control buttons frame
        control_frame = tk.Frame(scrollable_frame, bg="#0E0E10")
        control_frame.grid(row=len(settings), column=0, sticky="ew", pady=20)
        
        label_widget = tk.Label(control_frame, text="Chat Controls:", bg="#0E0E10", fg="#EFEFF1",
                              font=("Segoe UI", 12, "bold"), width=20, anchor="w")
        label_widget.grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        button_frame = tk.Frame(control_frame, bg="#0E0E10")
        button_frame.grid(row=0, column=1, sticky="w")
        
        self.start_button = tk.Button(button_frame, text="▶ Start", bg="#00AA00", fg="white",
                                    font=("Segoe UI", 10, "bold"), width=8,
                                    command=self.app.start_simulation)
        self.start_button.pack(side="left", padx=5)
        
        self.stop_button = tk.Button(button_frame, text="⏹ Stop", bg="#AA0000", fg="white",
                                   font=("Segoe UI", 10, "bold"), width=8,
                                   command=self.app.stop_simulation)
        self.stop_button.pack(side="left", padx=5)
        
        self.restart_button = tk.Button(button_frame, text="🔄 Restart", bg="#FFAA00", fg="white",
                                      font=("Segoe UI", 10, "bold"), width=8,
                                      command=self.app.restart_simulation)
        self.restart_button.pack(side="left", padx=5)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
    def _create_behavior_settings(self, parent, num_settings):
        main_frame = tk.Frame(parent)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(main_frame, bg="#0E0E10", highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#0E0E10")
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Personality sliders
        personality_settings = [
            ("Hype Personality", "PERSONALITY_HYPE"),
            ("Troll Personality", "PERSONALITY_TROLL"),
            ("Gamer Personality", "PERSONALITY_GAMER"),
            ("Question Personality", "PERSONALITY_QUESTION"),
            ("LOL Personality", "PERSONALITY_LOL"),
            ("Advice Personality", "PERSONALITY_ADVICE"),
            ("Wholesome Personality", "PERSONALITY_WHOLESOME"),
            ("Toxic Personality", "PERSONALITY_TOXIC"),
            ("Speedrunner Personality", "PERSONALITY_SPEEDRUNNER"),
            ("Lore Scholar Personality", "PERSONALITY_LORE_SCHOLAR"),
            ("Clip Goblin Personality", "PERSONALITY_CLIP_GOBLIN"),
            ("Backseat Gamer Personality", "PERSONALITY_BACKSEAT_GAMER"),
            ("Copium Addict Personality", "PERSONALITY_COPIUM_ADDICT"),
            ("Emote Spammer Personality", "PERSONALITY_EMOTE_SPAMMER"),
        ]
        
        # Add personality sliders
        for i, (label, setting) in enumerate(personality_settings[:7]):  # First 7
            self._create_personality_slider(scrollable_frame, label, setting, i)
        
        # Other behavior settings
        other_settings = [
            ("Donation Chance", "DONATION_CHANCE", "scale", {"from_": 0.0, "to": 0.2, "resolution": 0.01}),
            ("Respond to Streamer", "RESPOND_TO_STREAMER_CHANCE", "scale", {"from_": 0.0, "to": 1.0, "resolution": 0.05, "description": "Probability of responding when streamer chats"}),
            ("Mod Intervention Chance", "MODJV_CHAT_CHANCE", "scale", {"from_": 0.0, "to": 0.2, "resolution": 0.01}),
            ("Ban Chance", "MODJV_BAN_CHANCE", "scale", {"from_": 0.0, "to": 1.0, "resolution": 0.05}),
            ("Reply Chance", "CHATTER_REPLY_CHANCE", "scale", {"from_": 0.0, "to": 1.0, "resolution": 0.05}),
            ("Batch Size", "BATCH_SIZE", "scale", {"from_": 1, "to": 10, "resolution": 1}),
            ("Viewer Count Affects Chat", "VIEWER_COUNT_AFFECTS_CHAT", "checkbox", {"description": "More viewers = more chat activity"}),
            ("Dynamic Viewer Count", "DYNAMIC_VIEWER_COUNT", "checkbox", {"description": "Realistic viewer count fluctuations"}),
            ("Sub Streaks", "SUB_STREAKS_ENABLED", "checkbox", {"description": "Show subscriber streak notifications"}),
            ("Follower Goal", "FOLLOWER_GOAL_ENABLED", "checkbox", {"description": "Show follower goal progress"}),
            ("Hype Train", "HYPE_TRAIN_ENABLED", "checkbox", {"description": "Simulate hype train events"}),
            ("Bit Effects", "BIT_EFFECTS_ENABLED", "checkbox", {"description": "Visual effects for donations"}),
        ]
        
        start_row = len(personality_settings[:7])
        for i, (label, setting, type_, kwargs) in enumerate(other_settings):
            self._create_setting_widget(scrollable_frame, label, setting, type_, kwargs, start_row + i)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
    def _create_language_settings(self, parent, num_settings):
        """Create the new Language tab with enhanced language controls"""
        main_frame = tk.Frame(parent)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(main_frame, bg="#0E0E10", highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#0E0E10")
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Language settings
        languages = [
            ("English", "english", "The primary language for chat messages"),
            ("Tagalog", "tagalog", "Filipino language for authentic local chat"),
            ("Bisaya", "bisaya", "Cebuano/Visayan language from the Philippines"),
            ("Zambal", "Zambal", "Zambal language for international diversity"),
            ("Japanese", "japanese", "Japanese language for anime/gaming culture"),
        ]
        
        # Add language controls
        for i, (label, lang_code, description) in enumerate(languages[:num_settings]):
            self._create_language_control(scrollable_frame, label, lang_code, description, i)
        
        # Add advanced language settings
        advanced_label = tk.Label(scrollable_frame, text="Advanced Language Settings", 
                                 bg="#0E0E10", fg="#9147FF", font=("Segoe UI", 12, "bold"))
        advanced_label.grid(row=len(languages), column=0, sticky="w", pady=(20, 10))
        
        advanced_settings = [
            ("Enable Slang", "SLANG_ENABLED", "checkbox", {"description": "Use slang and colloquial expressions"}),
            ("Slang Intensity", "SLANG_INTENSITY", "scale", {"from_": 0.0, "to": 1.0, "resolution": 0.1, "description": "How much slang to use in chat"}),
            ("Formality Level", "FORMALITY_LEVEL", "scale", {"from_": 0.0, "to": 1.0, "resolution": 0.1, "description": "0 = Very casual, 1 = Very formal"}),
            ("Regional Dialects", "REGIONAL_DIALECTS", "checkbox", {"description": "Use regional variations and accents"}),
            ("Code Switching", "CODE_SWITCHING", "checkbox", {"description": "Allow mixing languages in single messages"}),
            ("Emote Frequency", "EMOTE_FREQUENCY", "scale", {"from_": 0.0, "to": 1.0, "resolution": 0.1, "description": "How often to use emotes in messages"}),
            ("Internet Speak", "INTERNET_SPEAK", "scale", {"from_": 0.0, "to": 1.0, "resolution": 0.1, "description": "Use internet slang like 'lol', 'brb', 'omg'"}),
            ("Auto Translate", "AUTO_TRANSLATE", "checkbox", {"description": "Automatically translate between enabled languages"}),
        ]
        
        start_row = len(languages) + 1
        for i, (label, setting, type_, kwargs) in enumerate(advanced_settings):
            self._create_setting_widget(scrollable_frame, label, setting, type_, kwargs, start_row + i)
        
        # Add language preset buttons
        preset_frame = tk.Frame(scrollable_frame, bg="#0E0E10")
        preset_frame.grid(row=start_row + len(advanced_settings), column=0, sticky="ew", pady=20)
        
        preset_label = tk.Label(preset_frame, text="Language Presets:", bg="#0E0E10", fg="#EFEFF1",
                              font=("Segoe UI", 12, "bold"))
        preset_label.grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        preset_buttons_frame = tk.Frame(preset_frame, bg="#0E0E10")
        preset_buttons_frame.grid(row=0, column=1, sticky="w")
        
        presets = [
            ("🌍 All Languages", self._apply_all_languages_preset),
            ("🇺🇸 English Only", self._apply_english_only_preset),
            ("🇵🇭 Filipino Mix", self._apply_filipino_mix_preset),
            ("🌐 International", self._apply_international_preset),
            ("🔥 Maximum Slang", self._apply_max_slang_preset),
        ]
        
        for i, (name, command) in enumerate(presets):
            btn = ttk.Button(preset_buttons_frame, text=name, command=command, width=15)
            btn.grid(row=0, column=i, padx=5)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
    def _create_language_control(self, parent, label, lang_code, description, row):
        """Create a language control with checkbox and weight slider"""
        frame = tk.Frame(parent, bg="#0E0E10")
        frame.grid(row=row, column=0, sticky="ew", pady=8)
        frame.columnconfigure(1, weight=1)
        
        # Get current language settings
        languages = config.get("LANGUAGES", {})
        lang_settings = languages.get(lang_code, {"enabled": False, "weight": 0.0})
        
        # Checkbox for enabling the language
        var_enabled = tk.BooleanVar(value=lang_settings["enabled"])
        checkbox = ModernCheckbox(frame, label, var_enabled,
                                command=lambda: self._update_language_setting(lang_code, "enabled", var_enabled.get()),
                                description=description)
        checkbox.grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        # Slider for weight
        var_weight = tk.DoubleVar(value=lang_settings["weight"])
        
        weight_frame = tk.Frame(frame, bg="#0E0E10")
        weight_frame.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        weight_frame.columnconfigure(0, weight=1)
        
        weight_label = tk.Label(weight_frame, text="Weight:", bg="#0E0E10", fg="#EFEFF1",
                              font=("Segoe UI", 9))
        weight_label.grid(row=0, column=0, sticky="w", padx=(0, 5))
        
        scale = ttk.Scale(weight_frame, from_=0.0, to=1.0, variable=var_weight,
                         orient="horizontal")
        scale.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        
        value_label = tk.Label(weight_frame, text=f"{var_weight.get():.2f}", bg="#0E0E10",
                             fg="#EFEFF1", font=("Segoe UI", 9), width=4)
        value_label.grid(row=0, column=2, padx=(0, 10))
        
        scale.bind("<Motion>", lambda e, v=var_weight, l=value_label: l.config(text=f"{v.get():.2f}"))
        scale.bind("<ButtonRelease-1>", 
                  lambda e, l=lang_code, v=var_weight: self._update_language_setting(l, "weight", v.get()))
        
        # Only enable slider if language is enabled
        def update_slider_state(*args):
            if var_enabled.get():
                scale.config(state="normal")
                value_label.config(fg="#EFEFF1")
            else:
                scale.config(state="disabled")
                value_label.config(fg="#888888")
        
        var_enabled.trace("w", update_slider_state)
        update_slider_state()
        
    def _update_language_setting(self, lang_code, setting, value):
        """Update a specific language setting"""
        languages = config.get("LANGUAGES", {}).copy()
        if lang_code not in languages:
            languages[lang_code] = {"enabled": False, "weight": 0.0}
        
        languages[lang_code][setting] = value
        config.set("LANGUAGES", languages)
        print(f"[INFO] Updated {lang_code}.{setting} = {value}")
        
    def _apply_all_languages_preset(self):
        """Enable all languages with equal weights"""
        languages = {
            "english": {"enabled": True, "weight": 0.2},
            "tagalog": {"enabled": True, "weight": 0.2},
            "bisaya": {"enabled": True, "weight": 0.2},
            "Zambal": {"enabled": True, "weight": 0.2},
            "japanese": {"enabled": True, "weight": 0.2},
        }
        config.set("LANGUAGES", languages)
        config.set("SLANG_ENABLED", True)
        config.set("SLANG_INTENSITY", 0.5)
        config.set("CODE_SWITCHING", True)
        messagebox.showinfo("Preset Applied", "All languages enabled with equal weights! 🌍")
        
    def _apply_english_only_preset(self):
        """Enable only English"""
        languages = {
            "english": {"enabled": True, "weight": 1.0},
            "tagalog": {"enabled": False, "weight": 0.0},
            "bisaya": {"enabled": False, "weight": 0.0},
            "Zambal": {"enabled": False, "weight": 0.0},
            "japanese": {"enabled": False, "weight": 0.0},
        }
        config.set("LANGUAGES", languages)
        config.set("SLANG_ENABLED", True)
        config.set("SLANG_INTENSITY", 0.7)
        messagebox.showinfo("Preset Applied", "English only mode activated! 🇺🇸")
        
    def _apply_filipino_mix_preset(self):
        """Enable English and Filipino languages"""
        languages = {
            "english": {"enabled": True, "weight": 0.6},
            "tagalog": {"enabled": True, "weight": 0.3},
            "bisaya": {"enabled": True, "weight": 0.1},
            "Zambal": {"enabled": False, "weight": 0.0},
            "japanese": {"enabled": False, "weight": 0.0},
        }
        config.set("LANGUAGES", languages)
        config.set("SLANG_ENABLED", True)
        config.set("SLANG_INTENSITY", 0.8)
        config.set("CODE_SWITCHING", True)
        messagebox.showinfo("Preset Applied", "Filipino language mix activated! 🇵🇭")
        
    def _apply_international_preset(self):
        """Enable international language mix"""
        languages = {
            "english": {"enabled": True, "weight": 0.5},
            "tagalog": {"enabled": True, "weight": 0.2},
            "bisaya": {"enabled": False, "weight": 0.0},
            "Zambal": {"enabled": True, "weight": 0.2},
            "japanese": {"enabled": True, "weight": 0.1},
        }
        config.set("LANGUAGES", languages)
        config.set("SLANG_ENABLED", True)
        config.set("SLANG_INTENSITY", 0.4)
        config.set("CODE_SWITCHING", True)
        messagebox.showinfo("Preset Applied", "International language mix activated! 🌐")
        
    def _apply_max_slang_preset(self):
        """Enable maximum slang and casual speech"""
        languages = {
            "english": {"enabled": True, "weight": 1.0},
            "tagalog": {"enabled": False, "weight": 0.0},
            "bisaya": {"enabled": False, "weight": 0.0},
            "Zambal": {"enabled": False, "weight": 0.0},
            "japanese": {"enabled": False, "weight": 0.0},
        }
        config.set("LANGUAGES", languages)
        config.set("SLANG_ENABLED", True)
        config.set("SLANG_INTENSITY", 1.0)
        config.set("FORMALITY_LEVEL", 0.0)
        config.set("EMOTE_FREQUENCY", 0.9)
        config.set("INTERNET_SPEAK", 0.9)
        messagebox.showinfo("Preset Applied", "Maximum slang mode activated! Very casual chat! 🔥")
        
    def _create_event_settings(self, parent, num_settings):
        """Create the Events tab with 10 customizable events"""
        main_frame = tk.Frame(parent)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(main_frame, bg="#0E0E10", highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#0E0E10")
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Event settings with descriptions
        event_settings = [
            ("New Follower Chance", "EVENT_FOLLOWER_CHANCE", "scale", 
             {"from_": 0.0, "to": 0.1, "resolution": 0.001, 
              "description": "Probability of new follower event per check"}),
            
            ("New Subscriber Chance", "EVENT_SUBSCRIBER_CHANCE", "scale", 
             {"from_": 0.0, "to": 0.05, "resolution": 0.001,
              "description": "Probability of new subscriber event per check"}),
            
            ("Hype Train Chance", "EVENT_HYPE_TRAIN_CHANCE", "scale", 
             {"from_": 0.0, "to": 0.02, "resolution": 0.001,
              "description": "Probability of hype train level increase"}),
            
            ("Raid Chance", "EVENT_RAID_CHANCE", "scale", 
             {"from_": 0.0, "to": 0.01, "resolution": 0.001,
              "description": "Probability of incoming raid event"}),
            
            ("Host Chance", "EVENT_HOST_CHANCE", "scale", 
             {"from_": 0.0, "to": 0.008, "resolution": 0.001,
              "description": "Probability of host event"}),
            
            ("Bits Chance", "EVENT_BITS_CHANCE", "scale", 
             {"from_": 0.0, "to": 0.03, "resolution": 0.001,
              "description": "Probability of bits donation event"}),
            
            ("Sub Streak Chance", "EVENT_SUB_STREAK_CHANCE", "scale", 
             {"from_": 0.0, "to": 0.04, "resolution": 0.001,
              "description": "Probability of sub streak announcement"}),
            
            ("Follower Goal Chance", "EVENT_FOLLOWER_GOAL_CHANCE", "scale", 
             {"from_": 0.0, "to": 0.08, "resolution": 0.001,
              "description": "Probability of follower goal update"}),
            
            ("Giveaway Chance", "EVENT_GIVEAWAY_CHANCE", "scale", 
             {"from_": 0.0, "to": 0.005, "resolution": 0.001,
              "description": "Probability of giveaway start"}),
            
            ("Milestone Chance", "EVENT_MILESTONE_CHANCE", "scale", 
             {"from_": 0.0, "to": 0.005, "resolution": 0.001,
              "description": "Probability of milestone achievement"}),
        ]
        
        # Viewer dynamics settings
        viewer_settings = [
            ("Base Viewer Count", "VIEWER_BASE_COUNT", "scale", 
             {"from_": 10, "to": 200, "resolution": 5,
              "description": "Average number of viewers when stream is live"}),
            
            ("Viewer Fluctuation Min", "VIEWER_FLUCTUATION_MIN", "scale", 
             {"from_": -50, "to": 0, "resolution": 5,
              "description": "Minimum viewer count change per update"}),
            
            ("Viewer Fluctuation Max", "VIEWER_FLUCTUATION_MAX", "scale", 
             {"from_": 0, "to": 50, "resolution": 5,
              "description": "Maximum viewer count change per update"}),
            
            ("Viewer Growth Rate", "VIEWER_GROWTH_RATE", "scale", 
             {"from_": 0.0, "to": 0.5, "resolution": 0.01,
              "description": "Rate at which viewer count grows over time"}),
            
            ("Peak Hour Multiplier", "VIEWER_PEAK_HOUR_MULTIPLIER", "scale", 
             {"from_": 1.0, "to": 3.0, "resolution": 0.1,
              "description": "Viewer multiplier during peak hours (6PM-10PM)"}),
        ]
        
        # Add section label for events
        event_label = tk.Label(scrollable_frame, text="Event Probabilities", 
                              bg="#0E0E10", fg="#9147FF", font=("Segoe UI", 12, "bold"))
        event_label.grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        # Add event settings
        for i, (label, setting, type_, kwargs) in enumerate(event_settings[:num_settings]):
            self._create_setting_widget(scrollable_frame, label, setting, type_, kwargs, i + 1)
        
        # Add section label for viewer dynamics
        viewer_label = tk.Label(scrollable_frame, text="Viewer Dynamics", 
                               bg="#0E0E10", fg="#9147FF", font=("Segoe UI", 12, "bold"))
        viewer_label.grid(row=len(event_settings) + 1, column=0, sticky="w", pady=(20, 10))
        
        # Add viewer settings
        start_row = len(event_settings) + 2
        for i, (label, setting, type_, kwargs) in enumerate(viewer_settings):
            self._create_setting_widget(scrollable_frame, label, setting, type_, kwargs, start_row + i)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
    def _create_personality_slider(self, parent, label, setting, row):
        frame = tk.Frame(parent, bg="#0E0E10")
        frame.grid(row=row, column=0, sticky="ew", pady=8)
        frame.columnconfigure(1, weight=1)
        
        label_widget = tk.Label(frame, text=label + ":", bg="#0E0E10", fg="#EFEFF1",
                              font=("Segoe UI", 10, "bold"), width=25, anchor="w")
        label_widget.grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        current_value = config.get(setting, 1.0)
        var = tk.DoubleVar(value=current_value)
        
        scale = ttk.Scale(frame, from_=0.0, to=2.0, variable=var, 
                         orient="horizontal")
        scale.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        
        value_label = tk.Label(frame, text=f"{current_value:.1f}", bg="#0E0E10", 
                             fg="#EFEFF1", font=("Segoe UI", 9), width=4)
        value_label.grid(row=0, column=2, padx=(0, 10))
        
        scale.bind("<Motion>", lambda e, v=var, l=value_label: l.config(text=f"{v.get():.1f}"))
        scale.bind("<ButtonRelease-1>", 
                  lambda e, s=setting, v=var: self._update_setting(s, v.get()))
    
    def _create_performance_settings(self, parent, num_settings):
        main_frame = tk.Frame(parent)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(main_frame, bg="#0E0E10", highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#0E0E10")
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Performance settings
        settings = [
            ("Adaptive Quality", "ADAPTIVE_QUALITY", "checkbox", {"description": "Reduce quality under high system load"}),
            ("Batch Rendering", "BATCH_RENDER", "checkbox", {"description": "Group messages for single UI update"}),
            ("Memory Optimization", "MEMORY_OPTIMIZATION", "checkbox", {"description": "Optimize memory usage"}),
            ("Keep-Alive Connection", "KEEP_ALIVE_CONNECTION", "checkbox", {"description": "Maintain persistent LLM connection"}),
            ("Debounced LLM Calls", "DEBOUNCED_LLM_CALLS", "checkbox", {"description": "Wait for pauses before new LLM calls"}),
            ("Lazy Load Emotes", "LAZY_LOAD_EMOTES", "checkbox", {"description": "Load emote images only when first used"}),
            ("Compression Enabled", "COMPRESSION_ENABLED", "checkbox", {"description": "Compress images to reduce memory usage"}),
            ("Queue Prioritization", "QUEUE_PRIORITIZATION", "checkbox", {"description": "User messages get priority over AI generation"}),
            ("Auto Clear Queue", "AUTO_CLEAR_QUEUE", "checkbox", {"description": "Automatically clear queue when it gets too full"}),
            ("Retry Failed Requests", "RETRY_FAILED_REQUESTS", "checkbox", {"description": "Automatically retry failed LLM requests"}),
        ]
        
        for i, (label, setting, type_, kwargs) in enumerate(settings[:10]):
            self._create_setting_widget(scrollable_frame, label, setting, type_, kwargs, i)
        
        # Queue management section
        queue_label = tk.Label(scrollable_frame, text="Queue Management", 
                              bg="#0E0E10", fg="#9147FF", font=("Segoe UI", 12, "bold"))
        queue_label.grid(row=10, column=0, sticky="w", pady=(20, 10))
        
        queue_settings = [
            ("Max Queue Size", "MAX_QUEUE_SIZE", "scale", {"from_": 1, "to": 10, "resolution": 10, "description": "Maximum messages in queue before auto-clear"}),
            ("Message Cache Size", "MESSAGE_CACHE_SIZE", "scale", {"from_": 50, "to": 500, "resolution": 10, "description": "Number of messages to keep in history"}),
            ("LLM Timeout", "LLM_TIMEOUT", "scale", {"from_": 5, "to": 60, "resolution": 5, "description": "Timeout for LLM requests in seconds"}),
            ("Max Retries", "MAX_RETRIES", "scale", {"from_": 0, "to": 10, "resolution": 1, "description": "Maximum retry attempts for failed requests"}),
            ("Concurrent Requests", "CONCURRENT_REQUESTS", "scale", {"from_": 0, "to": 3, "resolution": 1, "description": "Maximum simultaneous LLM requests"}),
            ("Request Buffer Size", "REQUEST_BUFFER_SIZE", "scale", {"from_": 5, "to": 50, "resolution": 5, "description": "Buffer size for pending LLM requests"}),
        ]
        
        start_row = 11
        for i, (label, setting, type_, kwargs) in enumerate(queue_settings):
            self._create_setting_widget(scrollable_frame, label, setting, type_, kwargs, start_row + i)
        
        # Add queue control buttons
        button_frame = tk.Frame(scrollable_frame, bg="#0E0E10")
        button_frame.grid(row=start_row + len(queue_settings), column=0, sticky="ew", pady=20)
        
        clear_queue_btn = ttk.Button(button_frame, text="🗑️ Clear Queue Now", 
                                   command=self.app.clear_queue)
        clear_queue_btn.pack(side="left", padx=5)
        
        status_btn = ttk.Button(button_frame, text="📊 Queue Status", 
                              command=self.app.show_queue_status)
        status_btn.pack(side="left", padx=5)
        
        optimize_btn = ttk.Button(button_frame, text="⚡ Optimize Performance", 
                                command=self._apply_performance_preset)
        optimize_btn.pack(side="left", padx=5)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
    def _apply_performance_preset(self):
        """Apply optimized performance settings"""
        updates = {
            "ADAPTIVE_QUALITY": True,
            "BATCH_RENDER": True,
            "MEMORY_OPTIMIZATION": True,
            "KEEP_ALIVE_CONNECTION": True,
            "DEBOUNCED_LLM_CALLS": True,
            "LAZY_LOAD_EMOTES": True,
            "COMPRESSION_ENABLED": True,
            "QUEUE_PRIORITIZATION": True,
            "AUTO_CLEAR_QUEUE": True,
            "MAX_QUEUE_SIZE": 30,
            "LLM_TIMEOUT": 60,
            "RETRY_FAILED_REQUESTS": True,
            "MAX_RETRIES": 2,
            "CONCURRENT_REQUESTS": 2,
            "REQUEST_BUFFER_SIZE": 15,
        }
        for key, value in updates.items():
            self._update_setting(key, value)
        messagebox.showinfo("Performance Optimized", "Performance settings optimized for smooth operation! ⚡")
        
    def _create_preset_settings(self, parent, num_settings):
        main_frame = tk.Frame(parent)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(main_frame, bg="#0E0E10", highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#0E0E10")
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        presets = [
            ("🎮 Tournament Mode", "High-speed competitive chat", self._apply_tournament_preset),
            ("🌿 Chill Stream", "Relaxed casual pace", self._apply_chill_preset),
            ("🔥 Hype Chat", "High-energy excitement", self._apply_hype_preset),
            ("📚 Creative Mode", "Thoughtful commentary", self._apply_creative_preset),
            ("🎉 Party Mode", "Celebratory atmosphere", self._apply_party_preset),
            ("⚡ Speedrun Mode", "Fast-paced technical chat", self._apply_speedrun_preset),
            ("🎵 Music Stream", "Focus on music and vibes", self._apply_music_preset),
            ("📖 Story Mode", "Lore-heavy and narrative", self._apply_story_preset),
        ]
        
        for i, (name, description, command) in enumerate(presets[:num_settings]):
            frame = tk.Frame(scrollable_frame, bg="#1F1F23", relief="raised", bd=1)
            frame.grid(row=i, column=0, sticky="ew", pady=5, padx=10)
            frame.columnconfigure(0, weight=1)
            
            btn = ttk.Button(frame, text=name, command=command, width=25)
            btn.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
            
            desc = tk.Label(frame, text=description, foreground="#B0B0B0", 
                          background="#1F1F23", font=("Segoe UI", 8), wraplength=300)
            desc.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
    def _create_setting_widget(self, parent, label, setting, type_, kwargs, row):
        frame = tk.Frame(parent, bg="#0E0E10")
        frame.grid(row=row, column=0, sticky="ew", pady=8)
        frame.columnconfigure(1, weight=1)
        
        label_widget = tk.Label(frame, text=label + ":", bg="#0E0E10", fg="#EFEFF1",
                              font=("Segoe UI", 10, "bold"), width=20, anchor="w")
        label_widget.grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        current_value = config.get(setting)
        
        if type_ == "checkbox":
            var = tk.BooleanVar(value=current_value)
            description = kwargs.get("description", "")
            checkbox = ModernCheckbox(frame, "", var, 
                                    command=lambda: self._update_setting(setting, var.get()),
                                    description=description)
            checkbox.grid(row=0, column=1, sticky="w")
            
        elif type_ == "combobox":
            var = tk.StringVar(value=current_value)
            combobox = ttk.Combobox(frame, textvariable=var, 
                                  values=kwargs.get("values", []), state="readonly")
            combobox.grid(row=0, column=1, sticky="ew", padx=(0, 10))
            combobox.bind("<<ComboboxSelected>>", 
                         lambda e: self._update_setting(setting, var.get()))
            
        elif type_ == "entry":
            var = tk.StringVar(value=current_value)
            entry = tk.Entry(frame, textvariable=var, bg="#1F1F23", fg="#EFEFF1",
                           relief="flat", borderwidth=1, highlightthickness=1,
                           highlightcolor="#9147FF", highlightbackground="#2F2F32")
            entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
            entry.bind("<FocusOut>", lambda e: self._update_setting(setting, var.get()))
            
            description = kwargs.get("description", "")
            if description:
                desc_label = tk.Label(frame, text=description, bg="#0E0E10", fg="#888888",
                                    font=("Segoe UI", 8), wraplength=200)
                desc_label.grid(row=0, column=3, sticky="w")
                
        elif type_ == "scale":
            var = tk.DoubleVar(value=current_value)
            scale = ttk.Scale(frame, from_=kwargs.get("from_", 0), 
                            to=kwargs.get("to", 100), variable=var, 
                            orient="horizontal")
            scale.grid(row=0, column=1, sticky="ew", padx=(0, 10))
            
            value_label = tk.Label(frame, text=str(current_value), bg="#0E0E10", 
                                 fg="#EFEFF1", font=("Segoe UI", 9), width=6)
            value_label.grid(row=0, column=2, padx=(0, 10))
            
            description = kwargs.get("description", "")
            if description:
                desc_label = tk.Label(frame, text=description, bg="#0E0E10", fg="#888888",
                                    font=("Segoe UI", 8), wraplength=200)
                desc_label.grid(row=0, column=3, sticky="w")
            
            scale.bind("<Motion>", lambda e, v=var, l=value_label: l.config(text=f"{v.get():.3f}"))
            scale.bind("<ButtonRelease-1>", 
                      lambda e: self._update_setting(setting, var.get()))
        
        if setting in self.restart_required_settings:
            restart_label = tk.Label(frame, text="🔄 Requires restart", bg="#0E0E10", 
                                   fg="#FFAA00", font=("Segoe UI", 8))
            restart_label.grid(row=0, column=4, padx=(10, 0))
    
    def _update_setting(self, name, value):
        config.set(name, value)
        
        if name == "CHAT_DENSITY" and hasattr(self.app, '_update_chat_density'):
            self.app._update_chat_density()
        elif name == "TEXT_SIZE" and hasattr(self.app, '_update_font_size'):
            self.app._update_font_size(value)
        elif name == "WINDOW_ON_TOP" and hasattr(self.app, 'root'):
            self.app.root.attributes("-topmost", value)
        
        print(f"[INFO] Updated {name} = {value}")
    
    def _load_defaults(self):
        config.update(config.DEFAULTS)
        messagebox.showinfo("Defaults Loaded", "All settings reset to default values!")
    
    def _apply_tournament_preset(self):
        updates = {
            "BATCH_SIZE": 10, "MIN_DRIP_SPEED": 0.1, "MAX_DRIP_SPEED": 0.5, 
            "MODJV_CHAT_CHANCE": 0.1, "CHATTER_REPLY_CHANCE": 0.4,
            "RESPOND_TO_STREAMER_CHANCE": 0.9,
            "ANIMATIONS_ENABLED": False, "SMOOTH_SCROLLING": False,
            "PERSONALITY_HYPE": 1.8, "PERSONALITY_GAMER": 1.5, "PERSONALITY_CLIP_GOBLIN": 1.6,
            "EVENT_FOLLOWER_CHANCE": 0.05, "EVENT_SUBSCRIBER_CHANCE": 0.03,
            "VIEWER_BASE_COUNT": 80, "VIEWER_PEAK_HOUR_MULTIPLIER": 2.0
        }
        self._apply_preset(updates, "Tournament Mode activated! 🎮")
        
    def _apply_chill_preset(self):
        updates = {
            "BATCH_SIZE": 3, "MIN_DRIP_SPEED": 0.5, "MAX_DRIP_SPEED": 3.0, 
            "MODJV_CHAT_CHANCE": 0.02, "CHATTER_REPLY_CHANCE": 0.2,
            "RESPOND_TO_STREAMER_CHANCE": 0.6,
            "ANIMATIONS_ENABLED": True, "SMOOTH_SCROLLING": True,
            "PERSONALITY_WHOLESOME": 1.7, "PERSONALITY_LOL": 1.3, "PERSONALITY_TOXIC": 0.1,
            "EVENT_FOLLOWER_CHANCE": 0.01, "EVENT_SUBSCRIBER_CHANCE": 0.005,
            "VIEWER_BASE_COUNT": 25, "VIEWER_PEAK_HOUR_MULTIPLIER": 1.2
        }
        self._apply_preset(updates, "Chill Stream mode activated! 🌿")
        
    def _apply_hype_preset(self):
        updates = {
            "BATCH_SIZE": 8, "MIN_DRIP_SPEED": 0.1, "MAX_DRIP_SPEED": 1.0, 
            "MODJV_CHAT_CHANCE": 0.15, "CHATTER_REPLY_CHANCE": 0.6,
            "RESPOND_TO_STREAMER_CHANCE": 0.95,
            "ANIMATIONS_ENABLED": True, "SMOOTH_SCROLLING": True,
            "PERSONALITY_HYPE": 1.9, "PERSONALITY_EMOTE_SPAMMER": 1.5, "PERSONALITY_LOL": 1.4,
            "EVENT_FOLLOWER_CHANCE": 0.08, "EVENT_HYPE_TRAIN_CHANCE": 0.015,
            "VIEWER_BASE_COUNT": 120, "VIEWER_PEAK_HOUR_MULTIPLIER": 2.5
        }
        self._apply_preset(updates, "Hype Chat mode activated! 🔥")
        
    def _apply_creative_preset(self):
        updates = {
            "BATCH_SIZE": 4, "MIN_DRIP_SPEED": 1.0, "MAX_DRIP_SPEED": 4.0, 
            "MODJV_CHAT_CHANCE": 0.05, "CHATTER_REPLY_CHANCE": 0.8,
            "RESPOND_TO_STREAMER_CHANCE": 0.7,
            "ANIMATIONS_ENABLED": True, "SMOOTH_SCROLLING": True,
            "PERSONALITY_LORE_SCHOLAR": 1.6, "PERSONALITY_ADVICE": 1.3, "PERSONALITY_QUESTION": 1.4,
            "EVENT_FOLLOWER_CHANCE": 0.03, "EVENT_SUBSCRIBER_CHANCE": 0.02,
            "VIEWER_BASE_COUNT": 40, "VIEWER_PEAK_HOUR_MULTIPLIER": 1.3
        }
        self._apply_preset(updates, "Creative Mode activated! 📚")
        
    def _apply_party_preset(self):
        updates = {
            "BATCH_SIZE": 12, "MIN_DRIP_SPEED": 0.05, "MAX_DRIP_SPEED": 0.8, 
            "MODJV_CHAT_CHANCE": 0.2, "CHATTER_REPLY_CHANCE": 0.7,
            "RESPOND_TO_STREAMER_CHANCE": 0.85,
            "ANIMATIONS_ENABLED": True, "SMOOTH_SCROLLING": True,
            "PERSONALITY_HYPE": 1.7, "PERSONALITY_EMOTE_SPAMMER": 1.8, "PERSONALITY_LOL": 1.6,
            "EVENT_FOLLOWER_CHANCE": 0.1, "EVENT_RAID_CHANCE": 0.01,
            "VIEWER_BASE_COUNT": 150, "VIEWER_PEAK_HOUR_MULTIPLIER": 2.8
        }
        self._apply_preset(updates, "Party Mode activated! 🎉")
    
    def _apply_speedrun_preset(self):
        updates = {
            "BATCH_SIZE": 6, "MIN_DRIP_SPEED": 0.2, "MAX_DRIP_SPEED": 1.5,
            "MODJV_CHAT_CHANCE": 0.08, "CHATTER_REPLY_CHANCE": 0.5,
            "RESPOND_TO_STREAMER_CHANCE": 0.8,
            "PERSONALITY_SPEEDRUNNER": 1.8, "PERSONALITY_BACKSEAT_GAMER": 1.5, "PERSONALITY_ADVICE": 1.4,
            "EVENT_FOLLOWER_CHANCE": 0.04, "EVENT_BITS_CHANCE": 0.02,
            "VIEWER_BASE_COUNT": 60, "VIEWER_PEAK_HOUR_MULTIPLIER": 1.8
        }
        self._apply_preset(updates, "Speedrun Mode activated! ⚡")
    
    def _apply_music_preset(self):
        updates = {
            "BATCH_SIZE": 4, "MIN_DRIP_SPEED": 1.2, "MAX_DRIP_SPEED": 3.5,
            "MODJV_CHAT_CHANCE": 0.03, "CHATTER_REPLY_CHANCE": 0.3,
            "RESPOND_TO_STREAMER_CHANCE": 0.6,
            "PERSONALITY_WHOLESOME": 1.5, "PERSONALITY_LOL": 1.2, "PERSONALITY_QUESTION": 1.1,
            "EVENT_FOLLOWER_CHANCE": 0.015, "EVENT_SUBSCRIBER_CHANCE": 0.008,
            "VIEWER_BASE_COUNT": 35, "VIEWER_PEAK_HOUR_MULTIPLIER": 1.4
        }
        self._apply_preset(updates, "Music Stream mode activated! 🎵")
    
    def _apply_story_preset(self):
        updates = {
            "BATCH_SIZE": 3, "MIN_DRIP_SPEED": 1.5, "MAX_DRIP_SPEED": 4.0,
            "MODJV_CHAT_CHANCE": 0.04, "CHATTER_REPLY_CHANCE": 0.9,
            "RESPOND_TO_STREAMER_CHANCE": 0.5,
            "PERSONALITY_LORE_SCHOLAR": 1.8, "PERSONALITY_QUESTION": 1.5, "PERSONALITY_ADVICE": 1.2,
            "EVENT_FOLLOWER_CHANCE": 0.025, "EVENT_MILESTONE_CHANCE": 0.003,
            "VIEWER_BASE_COUNT": 30, "VIEWER_PEAK_HOUR_MULTIPLIER": 1.2
        }
        self._apply_preset(updates, "Story Mode activated! 📖")
    
    def _apply_preset(self, updates, message):
        for key, value in updates.items():
            self._update_setting(key, value)
        messagebox.showinfo("Preset Applied", message)
