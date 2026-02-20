import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import threading
import time
import random
import queue
import re
import os
import sys
from collections import deque
from datetime import datetime
from PIL import Image, ImageTk

from config import config
from data_structures import (
    twitch_data, INVISIBLE_CHARS, DONATION_MESSAGES, EVENT_MESSAGES, 
    EMOTE_LIST, EMOTE_COLORS, HYPE_WORDS, CHILL_WORDS, USERNAME_POOL, 
    USERNAME_COLORS, CHAT_PERSONALITIES, USER_BADGES
)
from ui_components import (
    ModernCheckbox, DonationPopup, EmotePanel, EnhancedText, StreamStatsPanel, 
    SettingsWindow, LLMConnectionPool, clean_chat_line, get_screen_data_url, llm_pool
)

# ===========================
# MAIN TWITCH CHAT UI CLASS
# ===========================

class TwitchChatUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Twitch Chat Abello - AI-Powered")
        self.root.attributes("-topmost", config.get("WINDOW_ON_TOP"))
        
        if config.get("HIDE_TITLE_BAR"):
            self.root.overrideredirect(True)
        
        self.root.geometry(f"{config.get('WINDOW_WIDTH')}x{config.get('WINDOW_HEIGHT')}")
        self.root.configure(bg="#0E0E10")
        
        # Center the window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (config.get("WINDOW_WIDTH") // 2)
        y = (self.root.winfo_screenheight() // 2) - (config.get("WINDOW_HEIGHT") // 2)
        self.root.geometry(f"+{x}+{y}")
        
        # Enhanced functionality
        self.running = False
        self.msg_queue = queue.Queue()
        self.recent_chat = deque(maxlen=config.get("HISTORY_LEN"))
        self.message_cache = deque(maxlen=config.get("MESSAGE_CACHE_SIZE"))
        self.last_screenshot_data = None
        self.last_screenshot_time = 0
        self.photo = None
        self.chatter_map = {}
        self.banned_users = {}
        self.modjv_override_requested = False
        self.is_paused = False
        self.search_results = []
        self.current_search_index = -1
        self.last_streamer_message = None
        self.last_streamer_message_time = 0
        
        # Queue monitoring
        self.queue_monitor_active = False
        self.last_queue_size = 0
        
        # Create helper objects FIRST
        self.settings_window = SettingsWindow(root, self)
        self.emote_panel = EmotePanel(root, self)
        self.stream_stats = StreamStatsPanel(root, self)
        self.hover_timer = None
        
        # Dynamic emote loading from Emojis directory
        self.emojis_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'Emojis_The_Camp____Social__Karaoke__Events__VC__Valorant__Pinoy__Filipino__Call__Anime__Voice', 'Emojis'))
        try:
            files = [f for f in os.listdir(self.emojis_dir) if f.lower().endswith(('.png', '.gif', '.jpg', '.jpeg'))]
            self.emote_list = {os.path.splitext(f)[0].upper() for f in files}
        except (OSError, FileNotFoundError):
            self.emote_list = set(EMOTE_LIST)
        self.emote_colors = {emote: EMOTE_COLORS.get(emote, random.choice(USERNAME_COLORS)) for emote in self.emote_list}
        
        # THEN create UI elements
        self._configure_styles()
        self._create_stream_stats()
        self._create_toolbar()
        self._create_chat_area()
        self._create_input_area()
        
        self._configure_tags()
        self._setup_bindings()
        self.root.after(100, self._drain_queue)
        self.root.after(5000, self._monitor_queue)  # Start queue monitoring
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Debug frame if enabled
        if config.get("DEBUG_SCREENSHOT"):
            self.debug_frame = ttk.Frame(root)
            self.debug_label = tk.Label(self.debug_frame, bg="#1A1A1D", 
                                       text=f"Screenshot Preview ({config.get('IMAGE_SIZE')}px)", 
                                       fg="#777", font=("Segoe UI", 9))
            self.debug_label.pack(fill="both", expand=True, padx=5, pady=5)
            self.debug_frame.pack(side="top", fill="x", expand=False)
        
    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use('default')
        
        style.configure("TScrollbar", 
            troughcolor="#18181B", background="#2F2F32", 
            arrowcolor="#EFEFF1")
        style.map("TScrollbar", background=[('active', '#3D3D42')])
        
        style.configure("Toolbar.TButton", 
            background="#1F1F23", foreground="#EFEFF1",
            borderwidth=0, focuscolor="none")
        style.map("Toolbar.TButton", 
            background=[('active', '#9147FF')])
        
    def _create_stream_stats(self):
        """Create stream statistics panel"""
        if config.get("SHOW_STREAM_STATS"):
            self.stats_frame = self.stream_stats.create_panel()
        
    def _create_toolbar(self):
        toolbar = tk.Frame(self.root, bg="#1F1F23", height=35)
        toolbar.pack(side="top", fill="x", padx=5, pady=2)
        toolbar.pack_propagate(False)
        
        buttons = [
            ("☰", self._toggle_density, "Chat Density"),
            ("🕒", self._toggle_timestamps, "Toggle Timestamps"),
            ("🔍", self._show_search, "Search Chat"),
            ("💾", self._export_chat, "Export Chat"),
            ("😀", self.emote_panel.show, "Emote Panel"),
            ("⚙", self.settings_window.show, "Settings"),
            ("👥", self._show_follower_stats, "Follower Stats"),
            ("⭐", self._simulate_event, "Simulate Event"),
        ]
        
        for text, command, tooltip in buttons:
            btn = ttk.Button(toolbar, text=text, style="Toolbar.TButton",
                           command=command, width=3)
            btn.pack(side="left", padx=2)
        
        tk.Frame(toolbar, bg="#1F1F23").pack(side="left", expand=True)
        
        ttk.Button(toolbar, text="↑", style="Toolbar.TButton",
                 command=lambda: self._smooth_scroll_to("1.0"), width=3).pack(side="right", padx=1)
        ttk.Button(toolbar, text="↓", style="Toolbar.TButton",
                 command=lambda: self._smooth_scroll_to("end"), width=3).pack(side="right", padx=1)
        
    def _create_chat_area(self):
        chat_frame = tk.Frame(self.root, bg="#0E0E10")
        chat_frame.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        
        self.chat_box = EnhancedText(chat_frame, wrap="word", state="disabled", 
                                   bg="#0E0E10", fg="#EDEEEE", 
                                   font=(config.get("FONT_FAMILY"), config.get("TEXT_SIZE")), 
                                   relief="flat", padx=8, pady=4,
                                   borderwidth=0, highlightthickness=0)
        
        self.scrollbar = ttk.Scrollbar(chat_frame, command=self.chat_box.yview)
        self.chat_box.configure(yscrollcommand=self.scrollbar.set)
        
        self.chat_box.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        self._update_chat_density()
        
    def _create_input_area(self):
        self.input_frame = tk.Frame(self.root, bg="#0E0E10", height=45)
        self.input_frame.pack(side="bottom", fill="x", padx=5, pady=5)
        self.input_frame.pack_propagate(False)
        
        self.input_entry = tk.Entry(
            self.input_frame, bg="#1F1F23", fg="#EFEFF1", font=(config.get("FONT_FAMILY"), 10), 
            relief="flat", borderwidth=0, highlightthickness=1,
            highlightcolor="#9147FF", highlightbackground="#2F2F32"
        )
        self.input_entry.pack(side="left", fill="both", expand=True, padx=(5, 5), pady=5)
        self.input_entry.bind("<Return>", self._send_streamer_message)
        
        self.input_entry.insert(0, f"Type your message as {config.get('STREAMER_NAME')}...")
        self.input_entry.bind("<FocusIn>", lambda e: self.input_entry.delete(0, tk.END) 
                             if self.input_entry.get() == f"Type your message as {config.get('STREAMER_NAME')}..." else None)
        
        button_frame = tk.Frame(self.input_frame, bg="#0E0E10")
        button_frame.pack(side="right", padx=(0, 5))
        
        self.modjv_button = tk.Button(
            button_frame, text="ModJV", bg="#5C2D91", fg="#FFFFFF",
            font=(config.get("FONT_FAMILY"), 9, "bold"), relief="flat", cursor="hand2",
            activebackground="#772CE8", command=self._trigger_modjv_intervention,
            width=8
        )
        self.modjv_button.pack(side="left", padx=2)
        
        self.send_button = tk.Button(
            button_frame, text="Chat", bg="#9147FF", fg="#FFFFFF",
            font=(config.get("FONT_FAMILY"), 9, "bold"), relief="flat", cursor="hand2",
            activebackground="#772CE8", command=self._send_streamer_message,
            width=8
        )
        self.send_button.pack(side="left", padx=2)
        
    def _setup_bindings(self):
        self.context_menu = tk.Menu(self.root, tearoff=0, bg="#1F1F23", fg="#EFEFF1")
        self.context_menu.add_command(label="Copy Message", command=self._copy_message)
        self.context_menu.add_command(label="Highlight User", command=self._highlight_user)
        self.context_menu.add_command(label="Mock Reply", command=self._mock_reply)
        
        self.chat_box.bind("<Button-3>", self._show_context_menu)
        
        if config.get("AUTO_PAUSE_ON_HOVER"):
            self.chat_box.bind("<Enter>", self._on_chat_enter)
            self.chat_box.bind("<Leave>", self._on_chat_leave)
            
        self.root.bind("<Control-f>", lambda e: self._show_search())
        self.root.bind("<Control-e>", lambda e: self._export_chat())
        self.root.bind("<Control-p>", lambda e: self.settings_window.show())
        
        if config.get("HIDE_TITLE_BAR"):
            self.root.bind("<Button-1>", self._start_drag)
            self.root.bind("<B1-Motion>", self._on_drag)
        
    def _start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        
    def _on_drag(self, event):
        x = self.root.winfo_x() + (event.x - self._drag_start_x)
        y = self.root.winfo_y() + (event.y - self._drag_start_y)
        self.root.geometry(f"+{x}+{y}")
        
    def _update_chat_density(self):
        density = config.get("CHAT_DENSITY")
        if density == "compact":
            self.chat_box.configure(spacing1=0, spacing2=0, spacing3=0, 
                                  font=(config.get("FONT_FAMILY"), config.get("TEXT_SIZE")-1))
        elif density == "normal":
            self.chat_box.configure(spacing1=1, spacing2=1, spacing3=1, 
                                  font=(config.get("FONT_FAMILY"), config.get("TEXT_SIZE")))
        else:
            self.chat_box.configure(spacing1=3, spacing2=2, spacing3=2, 
                                  font=(config.get("FONT_FAMILY"), config.get("TEXT_SIZE")+1))
            
    def _update_font_size(self, size):
        config.set("TEXT_SIZE", int(size))
        self.chat_box.configure(font=(config.get("FONT_FAMILY"), config.get("TEXT_SIZE")))
        self._configure_tags()
        
    def _smooth_scroll_to(self, position):
        if config.get("SMOOTH_SCROLLING"):
            current_pos = self.chat_box.yview()[0]
            target_pos = 0.0 if position == "1.0" else 1.0
            
            steps = 10
            for i in range(steps + 1):
                progress = i / steps
                new_pos = current_pos + (target_pos - current_pos) * progress
                self.chat_box.yview_moveto(new_pos)
                self.root.update()
                time.sleep(0.01)
        else:
            self.chat_box.see(position)
            
    def _configure_tags(self):
        self.chat_box.tag_config("message_text", foreground="#EDEEEE", 
                                font=(config.get("FONT_FAMILY"), config.get("TEXT_SIZE")))
        self.chat_box.tag_config(config.get("STREAMER_NAME"), foreground="#00FF00", 
                                font=(config.get("FONT_FAMILY") + " Bold", config.get("TEXT_SIZE")))
        self.chat_box.tag_config(config.get("MODJV_USERNAME"), foreground="#FFD700", 
                                font=(config.get("FONT_FAMILY") + " Bold", config.get("TEXT_SIZE")))
        self.chat_box.tag_config("BAN_NOTIFICATION", foreground="#FF3333", 
                                background="#330000")
        self.chat_box.tag_config("timestamp", foreground="#777777", 
                                font=(config.get("FONT_FAMILY"), config.get("TEXT_SIZE")-1))
        self.chat_box.tag_config("username", font=(config.get("FONT_FAMILY") + " Semibold", config.get("TEXT_SIZE")))
        self.chat_box.tag_config("separator", foreground="#777777")
        self.chat_box.tag_config("mention_highlight", background="#2A2A40")
        self.chat_box.tag_config("search_highlight", background="#9147FF", 
                                foreground="white")
        self.chat_box.tag_config("badge", font=(config.get("FONT_FAMILY"), config.get("TEXT_SIZE")-1))
        
        for emote in self.emote_list:
            self.chat_box.tag_config(f"emote_{emote}", 
                                   foreground=self.emote_colors.get(emote, "#FFFFFF"), 
                                   font=(config.get("FONT_FAMILY") + " Bold", config.get("TEXT_SIZE") + 2))

    def _drain_queue(self):
        try:
            while True:
                data = self.msg_queue.get_nowait()
                if isinstance(data, dict) and data.get('type') == 'ban':
                    self._append_ban_notification(data['username'], data['reason'])
                else:
                    username, color, text, badges = data
                    self._append_line(username, color, text, badges)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_queue)

    def _monitor_queue(self):
        """Monitor queue size and auto-clear if needed"""
        if self.running:
            current_size = self.msg_queue.qsize()
            
            # Auto-clear queue if enabled and queue is too large
            if (config.get("AUTO_CLEAR_QUEUE") and 
                current_size > config.get("MAX_QUEUE_SIZE") and 
                current_size > self.last_queue_size):
                self.clear_queue()
                print(f"Auto-cleared queue (size: {current_size})")
            
            self.last_queue_size = current_size
            
            # Continue monitoring
            self.root.after(5000, self._monitor_queue)

    def clear_queue(self):
        """Clear all messages from the queue"""
        try:
            while True:
                self.msg_queue.get_nowait()
        except queue.Empty:
            pass
        print("Message queue cleared")

    def show_queue_status(self):
        """Show current queue status"""
        queue_size = self.msg_queue.qsize()
        cache_size = len(self.message_cache)
        recent_size = len(self.recent_chat)
        
        status = f"Queue Status:\n"
        status += f"Message Queue: {queue_size} items\n"
        status += f"Message Cache: {cache_size}/{config.get('MESSAGE_CACHE_SIZE')} messages\n"
        status += f"Recent Chat: {recent_size}/{config.get('HISTORY_LEN')} messages\n"
        status += f"Chatter Map: {len(self.chatter_map)} users\n"
        status += f"Banned Users: {len(self.banned_users)} users"
        
        messagebox.showinfo("Queue Status", status)

    def _append_ban_notification(self, banned_user_id, reason):
        self.chat_box.configure(state="normal")
        
        base_name = re.sub(r'\d+$', '', banned_user_id)
        self.banned_users[base_name] = time.time() + 120
        
        if base_name in self.chatter_map:
            del self.chatter_map[base_name]
        
        ban_message = f"\n{banned_user_id} has been timed out by {config.get('MODJV_USERNAME')} for {reason} (120s).\n"
        self.chat_box.insert("end", ban_message, "BAN_NOTIFICATION")
        
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def _append_line(self, username, color, text, badges=None):
        if self.is_paused and not username == config.get("STREAMER_NAME"):
            return
            
        self.chat_box.configure(state="normal")
        
        scroll_at_bottom = self._is_scroll_at_bottom()
        
        if config.get("SHOW_TIMESTAMPS"):
            timestamp = datetime.now().strftime("[%H:%M:%S] ")
            self.chat_box.insert("end", timestamp, "timestamp")
        
        if badges:
            for badge in badges:
                badge_info = USER_BADGES.get(badge)
                if badge_info:
                    self.chat_box.insert("end", badge_info["text"] + " ", 
                                       ("badge", f"badge_{badge}"))
                    if not self.chat_box.tag_cget(f"badge_{badge}", "foreground"):
                        self.chat_box.tag_config(f"badge_{badge}", 
                                              foreground=badge_info["color"])
        
        tags = []
        if username in twitch_data.highlighted_users:
            tags.append("user_highlight")
            color = twitch_data.highlighted_users[username]
            
        self.chat_box.insert("end", username, (username, *tags))
        self.chat_box.insert("end", ": ", "separator")
        
        words = text.split()
        message_tags = ["message_text"]
        if config.get("HIGHLIGHT_USERNAME") and config.get("STREAMER_NAME").upper() in text.upper():
            message_tags.append("mention_highlight")
            
        for word in words:
            if word.upper() in self.emote_list:
                emote_name = word.upper()
                emote_tag = f"emote_{emote_name}"
                self.chat_box.insert("end", f"{word} ", (emote_tag, *message_tags))
            else:
                self.chat_box.insert("end", f"{word} ", message_tags)
                
        self.chat_box.insert("end", "\n")
        
        if not self.chat_box.tag_cget(username, "foreground"):
            self.chat_box.tag_config(username, foreground=color, 
                                   font=(config.get("FONT_FAMILY") + " Semibold", config.get("TEXT_SIZE")))
            
        if config.get("ANIMATIONS_ENABLED"):
            self._animate_message_insertion()
            
        if scroll_at_bottom:
            self.chat_box.see("end")
            
        self.chat_box.configure(state="disabled")
        
        self.message_cache.append({
            "timestamp": datetime.now().isoformat(),
            "username": username,
            "text": text,
            "color": color,
            "badges": badges or []
        })
        
    def _animate_message_insertion(self):
        last_line = self.chat_box.index("end-2c")
        self.chat_box.tag_add("fade_in", last_line)
        self.chat_box.tag_config("fade_in", foreground="#808080")
        self.root.after(50, lambda: self.chat_box.tag_config("fade_in", foreground="#EDEEEE"))
        
    def _is_scroll_at_bottom(self):
        first_visible, last_visible = self.chat_box.yview()
        return last_visible >= 0.99
        
    def _toggle_density(self):
        densities = ["compact", "normal", "comfortable"]
        current_index = densities.index(config.get("CHAT_DENSITY"))
        config.set("CHAT_DENSITY", densities[(current_index + 1) % len(densities)])
        self._update_chat_density()
        
    def _toggle_timestamps(self):
        config.set("SHOW_TIMESTAMPS", not config.get("SHOW_TIMESTAMPS"))
        
    def _show_search(self):
        search_term = simpledialog.askstring("Chat Search", "Enter search term:")
        if search_term:
            self._search_chat(search_term)
            
    def _search_chat(self, term):
        self.search_results = []
        content = self.chat_box.get("1.0", "end")
        lines = content.split("\n")
        
        for i, line in enumerate(lines):
            if term.lower() in line.lower():
                self.search_results.append(i + 1)
                
        if self.search_results:
            self.current_search_index = 0
            self._highlight_search_result()
        else:
            messagebox.showinfo("Search", "No matches found.")
            
    def _highlight_search_result(self):
        if not self.search_results:
            return
            
        line = self.search_results[self.current_search_index]
        self.chat_box.see(f"{line}.0")
        self.chat_box.tag_remove("search_highlight", "1.0", "end")
        self.chat_box.tag_add("search_highlight", f"{line}.0", f"{line}.end")
        
    def _export_chat(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                for msg in self.message_cache:
                    timestamp = msg["timestamp"][11:19]
                    badges = " ".join([USER_BADGES.get(b, {}).get("text", "") for b in msg["badges"]])
                    f.write(f"{timestamp} {badges} {msg['username']}: {msg['text']}\n")
            messagebox.showinfo("Export", "Chat history exported successfully!")
            
    def _show_context_menu(self, event):
        try:
            index = self.chat_box.index(f"@{event.x},{event.y}")
            line_start = index.split(".")[0] + ".0"
            line_end = index.split(".")[0] + ".end"
            line_text = self.chat_box.get(line_start, line_end)
            
            match = re.match(r'^(\[?[\w]+\]?):', line_text)
            if match:
                self.context_username = match.group(1).strip("[]")
                self.context_message = line_text.split(":", 1)[1].strip()
                
            self.context_menu.post(event.x_root, event.y_root)
        except Exception:
            pass
            
    def _copy_message(self):
        if hasattr(self, 'context_message'):
            self.root.clipboard_clear()
            self.root.clipboard_append(self.context_message)
            
    def _highlight_user(self):
        if hasattr(self, 'context_username'):
            color = simpledialog.askstring("Highlight User", 
                                         f"Enter color for {self.context_username}:\n(Hex code or color name)")
            if color:
                twitch_data.highlighted_users[self.context_username] = color
                
    def _mock_reply(self):
        if hasattr(self, 'context_message'):
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, f"> {self.context_message} ")
            
    def _on_chat_enter(self, event):
        if self.hover_timer:
            self.root.after_cancel(self.hover_timer)
        self.hover_timer = self.root.after(500, self._pause_chat)
        
    def _on_chat_leave(self, event):
        if self.hover_timer:
            self.root.after_cancel(self.hover_timer)
        self._resume_chat()
        
    def _pause_chat(self):
        self.is_paused = True
        
    def _resume_chat(self):
        self.is_paused = False

    def _send_streamer_message(self, event=None):
        """Send message as streamer"""
        text = self.input_entry.get().strip()
        if not text or text == f"Type your message as {config.get('STREAMER_NAME')}...":
            return
            
        self.input_entry.delete(0, tk.END)
        badges = ["moderator"]
        self.msg_queue.put((config.get("STREAMER_NAME"), "#00FF00", text, badges))
        self.recent_chat.append(f"[{config.get('STREAMER_NAME')}]: {text}")
        
        # Store streamer message for immediate response
        self.last_streamer_message = text
        self.last_streamer_message_time = time.time()
        
        # Trigger immediate response based on probability
        if random.random() < config.get("RESPOND_TO_STREAMER_CHANCE"):
            self._trigger_immediate_response(text)

    def _trigger_immediate_response(self, streamer_message):
        """Trigger immediate response to streamer message"""
        threading.Thread(target=self._generate_immediate_response, 
                        args=(streamer_message,), daemon=True).start()

    def _generate_immediate_response(self, streamer_message):
        """Generate immediate response to streamer message"""
        try:
            # Get a random chatter
            username, color, base_name, badges = self._get_chatter_id()
            
            system_instructions = (
                f"You are a Twitch chatter responding immediately to the streamer {config.get('STREAMER_NAME')}. "
                f"Generate exactly ONE short, quick response to: '{streamer_message}'\n"
                "Keep it brief (1-2 sentences max) and relevant to what the streamer just said."
            )
            
            user_text = f"Streamer {config.get('STREAMER_NAME')} just said: '{streamer_message}'. Give a quick response:"
            
            content = llm_pool._call_llm(system_instructions, user_text, self.last_screenshot_data or "")
            
            if content and len(content.strip()) > 5:
                text = clean_chat_line(content.strip())
                self.msg_queue.put((username, color, text, badges))
                self.recent_chat.append(f"[{username}]: {text}")
                
        except Exception as e:
            print(f"Immediate response error: {e}")

    def _trigger_modjv_intervention(self):
        """Trigger manual moderator intervention"""
        self.modjv_override_requested = True
        self.modjv_button.config(text="FORCING...", state=tk.DISABLED)
        self.root.after(5000, lambda: self.modjv_button.config(text="ModJV", state=tk.NORMAL))

    def _show_follower_stats(self):
        """Show current follower statistics"""
        stats = f"Followers: {twitch_data.follower_count}/{twitch_data.follower_goal}\n"
        stats += f"Subscribers: {len(twitch_data.subscribers)}\n"
        stats += f"Hype Train: Level {twitch_data.hype_train_level}\n"
        stats += f"Viewers: {twitch_data.viewer_count}\n"
        stats += f"Peak Viewers: {twitch_data.peak_viewers}\n"
        stats += f"Total Views: {twitch_data.total_views}"
        messagebox.showinfo("Stream Stats", stats)

    def _simulate_event(self):
        """Manually trigger a Twitch event with 10 options"""
        event_options = [
            "1: New Follower", "2: New Subscriber", "3: Hype Train", 
            "4: Donation", "5: Raid", "6: Host", "7: Bits", 
            "8: Sub Streak", "9: Follower Goal", "10: Giveaway", "11: Milestone"
        ]
        
        choice_text = "Choose event:\n" + "\n".join(event_options)
        choice = simpledialog.askstring("Simulate Event", choice_text)
        
        if choice == "1":
            self._trigger_follower_event()
        elif choice == "2":
            self._trigger_subscriber_event()
        elif choice == "3":
            self._trigger_hype_train_event()
        elif choice == "4":
            self._trigger_donation_event()
        elif choice == "5":
            self._trigger_raid_event()
        elif choice == "6":
            self._trigger_host_event()
        elif choice == "7":
            self._trigger_bits_event()
        elif choice == "8":
            self._trigger_sub_streak_event()
        elif choice == "9":
            self._trigger_follower_goal_event()
        elif choice == "10":
            self._trigger_giveaway_event()
        elif choice == "11":
            self._trigger_milestone_event()

    def _trigger_follower_event(self):
        """Trigger new follower event"""
        twitch_data.follower_count += 1
        username = random.choice(USERNAME_POOL)
        message = random.choice(EVENT_MESSAGES["follower"]).format(username=username)
        self.msg_queue.put(("System", "#9147FF", message, []))

    def _trigger_subscriber_event(self):
        """Trigger new subscriber event"""
        username = random.choice(USERNAME_POOL)
        months = random.randint(1, 24)
        twitch_data.subscribers[username] = months
        message = random.choice(EVENT_MESSAGES["subscriber"]).format(username=username, months=months)
        self.msg_queue.put(("System", "#FFD700", message, []))
        # Assign subscriber badge
        twitch_data.user_badges[username].append("subscriber")

    def _trigger_hype_train_event(self):
        """Trigger hype train event"""
        twitch_data.hype_train_level = min(5, twitch_data.hype_train_level + 1)
        message = random.choice(EVENT_MESSAGES["hype_train"]).format(level=twitch_data.hype_train_level)
        self.msg_queue.put(("System", "#FF6B35", message, []))

    def _trigger_donation_event(self):
        """Trigger donation event"""
        donor, amount, message, theme = random.choice(DONATION_MESSAGES)
        self.root.after(0, lambda: DonationPopup(self.root, donor, amount, message, theme))
        self._make_chat_react_to_donation(donor, amount, message)

    def _trigger_raid_event(self):
        """Trigger raid event"""
        streamer = random.choice(USERNAME_POOL)
        viewers = random.randint(10, 100)
        message = random.choice(EVENT_MESSAGES["raid"]).format(streamer=streamer, viewers=viewers)
        self.msg_queue.put(("System", "#FF69B4", message, []))
        # Add raid viewers to current count
        twitch_data.viewer_count += viewers

    def _trigger_host_event(self):
        """Trigger host event"""
        streamer = random.choice(USERNAME_POOL)
        viewers = random.randint(5, 50)
        message = random.choice(EVENT_MESSAGES["host"]).format(streamer=streamer, viewers=viewers)
        self.msg_queue.put(("System", "#00CED1", message, []))
        # Add host viewers to current count
        twitch_data.viewer_count += viewers

    def _trigger_bits_event(self):
        """Trigger bits event"""
        username = random.choice(USERNAME_POOL)
        amount = random.randint(100, 5000)
        message = random.choice(EVENT_MESSAGES["bits"]).format(username=username, amount=amount)
        self.msg_queue.put(("System", "#9147FF", message, []))

    def _trigger_sub_streak_event(self):
        """Trigger sub streak event"""
        if twitch_data.subscribers:
            subscriber = random.choice(list(twitch_data.subscribers.keys()))
            streak = twitch_data.subscribers[subscriber]
            if streak > 1:
                message = random.choice(EVENT_MESSAGES["sub_streak"]).format(username=subscriber, streak=streak)
                self.msg_queue.put(("System", "#FFD700", message, []))

    def _trigger_follower_goal_event(self):
        """Trigger follower goal event"""
        remaining = twitch_data.follower_goal - twitch_data.follower_count
        if remaining > 0:
            message = random.choice(EVENT_MESSAGES["follower_goal"]).format(
                count=remaining, goal=twitch_data.follower_goal, current=twitch_data.follower_count
            )
            self.msg_queue.put(("System", "#9147FF", message, []))

    def _trigger_giveaway_event(self):
        """Trigger giveaway event"""
        message = random.choice(EVENT_MESSAGES["giveaway"])
        self.msg_queue.put(("System", "#FFD700", message, []))

    def _trigger_milestone_event(self):
        """Trigger milestone event"""
        milestones = [
            "Reached 1000 total views!",
            "500 followers achieved!",
            "24 hour stream completed!",
            "100 subscribers milestone!",
            "Top 100 in category!",
        ]
        description = random.choice(milestones)
        message = random.choice(EVENT_MESSAGES["milestone"]).format(description=description)
        self.msg_queue.put(("System", "#32CD32", message, []))

    def _make_chat_react_to_donation(self, donor, amount, message):
        """Make chat react to donation"""
        reactions = [
            f"POG {amount}!",
            f"LETS GO {donor}!",
            f"WOW {amount}!",
            f"POGCHAMP {donor}!",
            f"THANK YOU {donor}!",
            f"{amount} POGGERS",
            f"BIG DONO {donor}!",
            f"HOLY {amount}!",
        ]
        
        # Add multiple reactions from different users
        for _ in range(random.randint(2, 5)):
            username, color, base_name, badges = self._get_chatter_id()
            reaction = random.choice(reactions)
            self.msg_queue.put((username, color, reaction, badges))
            self.recent_chat.append(f"[{username}]: {reaction}")
            time.sleep(0.2)

    def _update_debug_display(self, img):
        """Update screenshot preview in debug mode"""
        if img and hasattr(self, 'debug_label'):
            try:
                display_img = img.copy()
                display_img.thumbnail((400, 300), Image.Resampling.LANCZOS)
                self.photo = ImageTk.PhotoImage(display_img)
                self.debug_label.config(image=self.photo, text="")
            except Exception as e:
                print(f"Debug display error: {e}")
    
    def _simulate_twitch_events(self):
        """Simulate Twitch events with configurable probabilities"""
        # New Follower
        if random.random() < config.get("EVENT_FOLLOWER_CHANCE"):
            self._trigger_follower_event()
                
        # New Subscriber
        if random.random() < config.get("EVENT_SUBSCRIBER_CHANCE"):
            self._trigger_subscriber_event()
                
        # Hype Train
        if config.get("HYPE_TRAIN_ENABLED") and random.random() < config.get("EVENT_HYPE_TRAIN_CHANCE"):
            self._trigger_hype_train_event()
                    
        # Follower Goal
        if config.get("FOLLOWER_GOAL_ENABLED") and twitch_data.follower_count < twitch_data.follower_goal:
            if random.random() < config.get("EVENT_FOLLOWER_GOAL_CHANCE"):
                self._trigger_follower_goal_event()
                    
        # Raid Event
        if random.random() < config.get("EVENT_RAID_CHANCE"):
            self._trigger_raid_event()
            
        # Host Event
        if random.random() < config.get("EVENT_HOST_CHANCE"):
            self._trigger_host_event()
            
        # Bits Event
        if random.random() < config.get("EVENT_BITS_CHANCE"):
            self._trigger_bits_event()
            
        # Sub Streak
        if config.get("SUB_STREAKS_ENABLED") and random.random() < config.get("EVENT_SUB_STREAK_CHANCE"):
            self._trigger_sub_streak_event()
            
        # Giveaway
        if random.random() < config.get("EVENT_GIVEAWAY_CHANCE"):
            self._trigger_giveaway_event()
            
        # Milestone
        if random.random() < config.get("EVENT_MILESTONE_CHANCE"):
            self._trigger_milestone_event()

    def _get_chatter_id(self):
        """Get or create a consistent chatter ID with badges"""
        now = time.time()
        self.banned_users = {name: expiry for name, expiry in self.banned_users.items() if expiry > now}

        available_pool = [name for name in USERNAME_POOL if name not in self.banned_users]
        if not available_pool:
            return "Viewer", random.choice(USERNAME_COLORS), "Viewer", []

        # Check if we should reuse an existing user
        if self.chatter_map and random.random() < 0.6:  # 60% chance to reuse existing user
            available_users = [name for name in self.chatter_map.keys() if name in available_pool]
            if available_users:
                base_name = random.choice(available_users)
                full_id, color = self.chatter_map[base_name]
                # Get badges from stored user data
                badges = twitch_data.user_badges.get(full_id, [])
                return full_id, color, base_name, badges

        # Create new user
        base_name = random.choice(available_pool)
        unique_num = random.randint(100, 999)
        full_id = base_name + str(unique_num)
        color = random.choice(USERNAME_COLORS)
        
        # Store user data
        self.chatter_map[base_name] = (full_id, color)
        
        # Assign badges based on probability (consistent for this user)
        badges = []
        if random.random() < 0.3:  # 30% chance of being a sub
            badges.append("subscriber")
            if base_name not in twitch_data.subscribers:
                twitch_data.subscribers[base_name] = 1
                
        if random.random() < 0.1:  # 10% chance of VIP
            badges.append("vip")
            
        if random.random() < 0.05:  # 5% chance of founder
            badges.append("founder")
            
        # Store badges for this user
        twitch_data.user_badges[full_id] = badges
        
        # Update reputation
        twitch_data.user_reputation[base_name]["messages"] += 1
        
        return full_id, color, base_name, badges

    def _get_personality_weights(self):
        """Get current personality weights from settings"""
        return {
            "hype": config.get("PERSONALITY_HYPE"),
            "troll": config.get("PERSONALITY_TROLL"),
            "gamer": config.get("PERSONALITY_GAMER"),
            "question": config.get("PERSONALITY_QUESTION"),
            "lol": config.get("PERSONALITY_LOL"),
            "advice": config.get("PERSONALITY_ADVICE"),
            "wholesome": config.get("PERSONALITY_WHOLESOME"),
            "toxic": config.get("PERSONALITY_TOXIC"),
            "speedrunner": config.get("PERSONALITY_SPEEDRUNNER"),
            "lore_scholar": config.get("PERSONALITY_LORE_SCHOLAR"),
            "clip_goblin": config.get("PERSONALITY_CLIP_GOBLIN"),
            "backseat_gamer": config.get("PERSONALITY_BACKSEAT_GAMER"),
            "copium_addict": config.get("PERSONALITY_COPIUM_ADDICT"),
            "emote_spammer": config.get("PERSONALITY_EMOTE_SPAMMER"),
        }

    def _get_language_distribution(self):
        """Get normalized language distribution based on enabled languages and weights"""
        languages = config.get("LANGUAGES", {})
        enabled_languages = {lang: data for lang, data in languages.items() if data.get("enabled", False)}
        
        if not enabled_languages:
            # Default to English if no languages are enabled
            return {"english": 1.0}
        
        # Calculate total weight
        total_weight = sum(data.get("weight", 0.0) for data in enabled_languages.values())
        
        if total_weight == 0:
            # If all weights are zero, distribute equally
            weight_per_lang = 1.0 / len(enabled_languages)
            return {lang: weight_per_lang for lang in enabled_languages.keys()}
        
        # Normalize weights
        return {lang: data.get("weight", 0.0) / total_weight for lang, data in enabled_languages.items()}

    def _get_language_instructions(self):
        """Generate language instructions for the LLM based on current distribution"""
        distribution = self._get_language_distribution()
        
        if len(distribution) == 1:
            lang = list(distribution.keys())[0]
            if lang == "english":
                return "Generate all messages in English only."
            elif lang == "tagalog":
                return "Generate all messages in Tagalog (Filipino) only."
            elif lang == "bisaya":
                return "Generate all messages in Bisaya (Cebuano/Visayan) only."
            elif lang == "Zambal":
                return "Generate all messages in Zambal only."
            elif lang == "japanese":
                return "Generate all messages in Japanese only."
        
        # Multiple languages - create distribution instructions
        instructions = ["Generate messages in the following language distribution:"]
        for lang, weight in distribution.items():
            percentage = weight * 100
            if lang == "english":
                instructions.append(f"- English: {percentage:.1f}%")
            elif lang == "tagalog":
                instructions.append(f"- Tagalog: {percentage:.1f}%")
            elif lang == "bisaya":
                instructions.append(f"- Bisaya: {percentage:.1f}%")
            elif lang == "Zambal":
                instructions.append(f"- Zambal: {percentage:.1f}%")
            elif lang == "japanese":
                instructions.append(f"- Japanese: {percentage:.1f}%")
        
        instructions.append("Mix languages naturally within the chat. Code-switching (mixing languages in one message) is allowed and encouraged for authentic chat experience.")
        
        return " ".join(instructions)

    def _get_slang_instructions(self):
        """Generate slang and style instructions based on current settings"""
        instructions = []
        
        # Slang settings
        if config.get("SLANG_ENABLED"):
            intensity = config.get("SLANG_INTENSITY", 1)
        if intensity > 0.7:
            instructions.append(
            "Use heavy slang, chaotic casual language, and loose phrasing like Twitch chat. "
            "Sometimes drop proper punctuation entirely — no commas, no periods, more natural chat marks — just raw flow."
        )
        elif intensity > 0.4:
            instructions.append(
            "Use moderate slang and casual expressions. Occasionally skip punctuation or end sentences abruptly for a natural chat vibe."
        )
        elif intensity > 0.1:
            instructions.append(
            "Use light slang occasionally. Maybe drop punctuation once in a while but keep most sentences readable."
        )

        
        # Formality level
        formality = config.get("FORMALITY_LEVEL", 0.3)

        if formality > 0.7:
            instructions.append(
            "Use highly formal language — rich, elaborate words, old-timey or Shakespearean-style English, "
            "like 1500s British speech. Make it sound grand, theatrical, or humorously archaic."
        )
        elif formality > 0.4:
                instructions.append(
            "Use neutral, standard language — clear, readable, and appropriate for general chat."
        )
        else:
            instructions.append(
            "Use very casual and informal language — slang, shortcuts, chat-style expressions, and relaxed grammar."
        )

        
        # Internet speak
        internet_speak = config.get("INTERNET_SPEAK", 0.6)

        if internet_speak > 0.7:
            instructions.append(
            "Heavily pepper messages with internet slang and abbreviations like 'lol', 'omg', 'brb', 'wtf', "
            "and other common chat shortcuts. Messages should feel very casual and fast-moving, like real online chatter."
        )
        elif internet_speak > 0.4:
            instructions.append(
            "Use internet slang moderately — sprinkle abbreviations and casual chat expressions naturally, "
            "but keep messages mostly readable."
        )
        else:
            instructions.append(
            "Use minimal or no internet slang — messages should be mostly standard text, though small casual words or emojis are fine occasionally."
        )

        
        # Emote frequency
        emote_freq = config.get("EMOTE_FREQUENCY", 0.7)

        if emote_freq > 0.8:
            instructions.append(
            "Use emotes very frequently — almost every message should include at least one emote, just like a hype Twitch chat."
        )
        elif emote_freq > 0.5:
            instructions.append(
            "Use emotes regularly — include them naturally throughout the messages, giving the chat energy without overdoing it."
        )
        elif emote_freq > 0.2:
            instructions.append(
            "Use emotes occasionally — sprinkle them sparingly to add flavor, not overwhelm the text."
        )
        else:
            instructions.append(
            "Rarely or never use emotes — messages should be mostly text-based, with very few or no emotes."
        )

        
        # Regional dialects
        if config.get("REGIONAL_DIALECTS"):
            instructions.append("Use regional variations and local expressions where appropriate.")
        
        return " ".join(instructions) if instructions else "Use standard internet chat language."

    def _analyze_hype(self, lines):
        """Analyze hype level in messages to adjust chat speed"""
        hype_score = 0
        chill_score = 0
        
        full_text = " ".join(lines).upper()
        
        # All caps messages are hype
        if full_text == full_text.upper() and len(full_text) > 10:
            hype_score += 2
            
        # Count hype words and emotes
        for word in HYPE_WORDS + list(self.emote_list):
            hype_score += full_text.count(word)
        
        # Count chill words
        for word in CHILL_WORDS:
            chill_score += full_text.count(word)

        # Return normalized score
        return (hype_score - chill_score) / (len(lines) * 2 or 1)

    def start_simulation(self):
        """Start the chat simulation"""
        if not self.running:
            self.running = True
            self.stream_stats.set_live_status(True)
            threading.Thread(target=self._loop, daemon=True).start()
            threading.Thread(target=self._event_loop, daemon=True).start()
            print("Chat simulation STARTED")

    def stop_simulation(self):
        """Stop the chat simulation"""
        self.running = False
        self.stream_stats.set_live_status(False)
        print("Chat simulation STOPPED")

    def restart_simulation(self):
        """Restart the chat simulation"""
        self.stop_simulation()
        time.sleep(1)
        self.start_simulation()
        print("Chat simulation RESTARTED")

    def _event_loop(self):
        """Event simulation loop"""
        while self.running:
            self._simulate_twitch_events()
            time.sleep(10)  # Check for events every 10 seconds

    def _loop(self):
        """Main chat generation loop"""
        last_line_time = time.time() - config.get("LLM_REQUEST_INTERVAL")
        
        while self.running:
            try:
                # Enforce cooldown between batches
                time_since_last_line = time.time() - last_line_time
                pause_needed = config.get("LLM_REQUEST_INTERVAL") - time_since_last_line
                if pause_needed > 0:
                    time.sleep(pause_needed)

                now = time.time()
                
                # Update screenshot if needed
                if (now - self.last_screenshot_time > config.get("SCREENSHOT_COOLDOWN")) or self.last_screenshot_data is None:
                    data_url, img_obj = get_screen_data_url()
                    self.last_screenshot_data = data_url
                    self.last_screenshot_time = now
                    if config.get("DEBUG_SCREENSHOT") and hasattr(self, 'debug_label'):
                        self.root.after(0, lambda i=img_obj: self._update_debug_display(i))
                
                # Check for mod intervention
                trigger_modjv = self.modjv_override_requested or random.random() < config.get("MODJV_CHAT_CHANCE")
                
                if trigger_modjv:
                    self.modjv_override_requested = False
                    
                    lines, request_time = self._llm_generate_mod_intervention(self.last_screenshot_data, list(self.recent_chat))
                    username = config.get("MODJV_USERNAME")
                    color = "#FFD700"
                    badges = ["moderator"]
                    
                    if lines:
                        raw_line = lines[0]
                        ban_match = re.search(r'\[ACTION:BAN\s+(\w+)\]\s*(.*)', raw_line, re.IGNORECASE)
                        
                        if ban_match:
                            base_name_to_ban = ban_match.group(1).strip()
                            mod_comment = ban_match.group(2).strip()
                            full_user_id_to_ban = self.chatter_map.get(base_name_to_ban, (base_name_to_ban, None))[0]
                            
                            self.msg_queue.put({
                                'type': 'ban', 
                                'username': full_user_id_to_ban, 
                                'reason': 'toxicity'
                            })
                            
                            text = mod_comment or f"Keep the chat clean, {full_user_id_to_ban} is out for a bit."
                        else:
                            text = clean_chat_line(raw_line)
                            
                        if len(text) > 2:
                            self.recent_chat.append(f"[{username}]: {text}")
                            self.msg_queue.put((username, color, text, badges))
                    
                    time.sleep(config.get("MIN_DRIP_SPEED"))
                    last_line_time = time.time()
                    
                else:
                    # Check for donation popup
                    if random.random() < config.get("DONATION_CHANCE"):
                        donor, amount, message, theme = random.choice(DONATION_MESSAGES)
                        self.root.after(0, lambda d=donor, a=amount, m=message, t=theme: DonationPopup(self.root, d, a, m, t))
                        # Make chat react to donation
                        self._make_chat_react_to_donation(donor, amount, message)

                    # Generate normal chat batch
                    lines, request_time = self._llm_generate_batch(self.last_screenshot_data, list(self.recent_chat), count=config.get("BATCH_SIZE"))
                    
                    # Calculate dynamic drip speed based on hype
                    hype_score = self._analyze_hype(lines)
                    normalized_score = (hype_score + 1) / 2
                    drip_range = config.get("MAX_DRIP_SPEED") - config.get("MIN_DRIP_SPEED")
                    drip_speed = config.get("MIN_DRIP_SPEED") + drip_range * (1 - normalized_score)
                    drip_speed = max(config.get("MIN_DRIP_SPEED"), min(drip_speed, config.get("MAX_DRIP_SPEED")))
                    
                    # Default speed for single messages
                    if len(lines) <= 1:
                        drip_speed = (config.get("MIN_DRIP_SPEED") + config.get("MAX_DRIP_SPEED")) / 2

                    # Drip feed messages with calculated speed
                    for i, line in enumerate(lines):
                        if not self.running: 
                            break
                        
                        raw_text = line.replace('"', '').strip()
                        text = clean_chat_line(raw_text)

                        if len(text) < 2: 
                            continue
                        
                        # Get chatter ID with badges
                        username, color, base_name, badges = self._get_chatter_id()
                        
                        # Add to context and queue
                        self.recent_chat.append(f"[{username}]: {text}")
                        self.msg_queue.put((username, color, text, badges))
                        
                        # Pause between messages except the last one
                        if i < len(lines) - 1:
                            time.sleep(drip_speed)
                        else:
                            # Update timing after last message
                            last_line_time = time.time()
                    
            except Exception as e:
                print(f"Error in LLM loop: {e}")
                time.sleep(1)  # Brief pause on error

    def _llm_generate_batch(self, screen_data_url, recent_chat, count=None):
        """Generate a batch of chat messages using LLM"""
        if count is None:
            count = config.get("BATCH_SIZE")
            
        start_time = time.time()
        
        # Select personalities based on current weights
        personality_weights = self._get_personality_weights()
        personalities = []
        for personality, weight in personality_weights.items():
            if random.random() < weight / 2.0:  # Normalize probability
                personalities.append(personality)
        
        # Ensure we have at least 2 personalities
        if len(personalities) < 2:
            personalities = list(personality_weights.keys())[:2]
        else:
            personalities = random.sample(personalities, min(3, len(personalities)))
        
        # Get language instructions
        language_instructions = self._get_language_instructions()
        
        reply_target_instruction = ""
        if recent_chat and random.random() < config.get("CHATTER_REPLY_CHANCE"):
            target_message = random.choice(list(recent_chat))
            reply_target_instruction = (
                f"IMPORTANT: At least one of the {count} messages must reply to this message: "
                f"'{target_message}'. Make it sound like a real viewer actually responding — quick, casual, and acknowledging what they said."
)


        system_instructions = (
    f"You are a fast-paced Twitch Chat simulator watching {config.get('STREAMER_NAME')}'s livestream. You MUST analyze and react to the visual state of the SCREENSHOT.\n"
    f"Generate exactly {count} unique chat messages with no repeats.\n"
    f"{language_instructions}\n"
    "RULES:\n"
    "1. Output raw text only — no quotes, no markdown, no numbering.\n"
    "2. CRITICAL: Chat reactions MUST acknowledge what's happening on-screen and respond naturally to the RECENT_CHAT_CONTEXT.\n"
    "3. Make the messages feel like they're from different viewers — varied, spontaneous, and not similar.\n"
    "4. Keep the pace fast and chaotic. Short, punchy, realistic Twitch-style messages.\n"
    f"5. Blend these personalities in the chat: " + " AND ".join([CHAT_PERSONALITIES[p] for p in personalities]) +
    "\n6. Emotes: ONLY use text-based emotes like LUL KEKW PogChamp Kappa FeelsBadMan PepeHands MonkaS 4Head WutFace POG OMEGALUL PogU Sadge Okayge HYPERCLAP and other keyword emotes from the available list. Do NOT use Unicode emojis (😆 😂 🔥 💀 👀 ✨ etc.) or any graphical/symbolic characters. The chat client recognizes and styles matching text keywords automatically."
)


        user_text = (
    f"RECENT_CHAT_CONTEXT (what viewers are currently saying and reacting to in real time):\n"
    f"{recent_chat[-8:] if recent_chat else 'None'}\n\n"
    f"{reply_target_instruction}\n"
    "Your job is to generate new chat messages that feel naturally woven into an active Twitch stream. "
    "These messages should pick up the momentum, jokes, reactions, and tone seen in the ongoing chat above. "
    "Chatters should feel like they're responding not only to the streamer but also to each other, "
    "continuing threads, jumping on small moments, and building hype or confusion depending on what the screenshot shows.\n\n"
    f"Generate {count} new messages. Each message MUST:\n"
    "• React directly to the visual SCREENSHOT (gameplay, streamer face, event, UI, etc.)\n"
    "• Connect to the energy and tone of the RECENT_CHAT_CONTEXT\n"
    "• Feel spontaneous, varied, and authentic to Twitch culture\n"
    "• Be fast-paced, punchy, and chaotic — like real chat scrolling rapidly\n"
    "• Sound like different viewers with different personalities jumping in\n\n"
    "Do NOT repeat messages or structure. Keep it dynamic, and natural for a live chat environment."
            )

        
        content = llm_pool._call_llm(system_instructions, user_text, screen_data_url)
        
        end_time = time.time()
        request_time = end_time - start_time
        
        lines = [x.strip() for x in content.split('\n') if x.strip()]
        return lines[:count], request_time

    def _llm_generate_mod_intervention(self, screen_data_url, recent_chat):
        """Generate moderator intervention using LLM"""
        start_time = time.time()
        target_username = random.choice(USERNAME_POOL)
        
        system_instructions = (
    f"You are the chat moderator '{config.get('MODJV_USERNAME')}'. You are responsible for keeping the chat under control, reacting to viewer messages, and stepping in with warnings or conversation when needed.\n"
    "You MUST generate exactly ONE line of output.\n"
    "RULES:\n"
    "1. Output raw text only — no quotes, no markdown, no numbering.\n"
    "2. CRITICAL: You must reference a specific user or a specific topic mentioned in the RECENT_CHAT_CONTEXT. "
    "Your message must feel like a real-time response to something someone in chat said.\n"
    f"3. If you decide to ban or warn a user, start your message *immediately* with the action command: "
    f"`[ACTION:BAN TARGET_USER_NAME]`. For example: `[ACTION:BAN {target_username}] That comment was unnecessary, calm down.`\n"
    f"4. If you choose to ban someone, always use this base username: {target_username}.\n"
    "5. If no ban is needed, reply with a natural moderator-style comment — either a gentle warning, a judgemental observation, or a stabilizing message that addresses the situation in chat.\n"
    "6. Emotes: ONLY use text-based emotes like LUL KEKW PogChamp Kappa FeelsBadMan PepeHands MonkaS 4Head WutFace POG OMEGALUL PogU Sadge Okayge HYPERCLAP and other keyword emotes from the available list. Do NOT use Unicode emojis (😆 😂 🔥 💀 👀 ✨ etc.) or any graphical/symbolic characters.\n"
    "Your tone should match a realistic Twitch moderator: firm when needed, casual when appropriate, but always reacting to the chat context."
)


        user_text = (
    f"RECENT_CHAT_CONTEXT (latest messages from viewers):\n"
    f"{recent_chat[-8:] if recent_chat else 'None'}\n\n"
    "NOTE: Completely ignore the screenshot. Your response must be based ONLY on what users in the chat have been saying.\n"
    "As the moderator, you must react directly to something specific in the chat history — either a user’s message, a topic being discussed, "
    "or any ongoing tension, joke, or chaos happening in the context above.\n\n"
    f"Generate {config.get('MODJV_USERNAME')}'s intervention now. Your output should be a single realistic moderator action or comment in one line."
)

        
        content = llm_pool._call_llm(system_instructions, user_text, screen_data_url)
        
        end_time = time.time()
        request_time = end_time - start_time
        
        lines = [x.strip() for x in content.split('\n') if x.strip()]
        return lines[:1], request_time

    def _on_close(self):
        """Handle application close"""
        self.stop_simulation()
        config.save_settings()  # Save settings when closing
        self.root.after(100, self.root.destroy)

# ===========================
# MAIN APPLICATION
# ===========================

if __name__ == "__main__":
    # Check for required packages
    try:
        import mss
        import requests
        from PIL import Image
    except ImportError as e:
        print(f"Missing required package: {e}")
        print("Please install required packages:")
        print("pip install mss pillow requests")
        exit(1)
    
    # Create and start application
    main = tk.Tk()
    app = TwitchChatUI(main)
    
    print("Twitch Chat Abello ready")
    print("Features loaded:")
    print("Stream stats panel with live indicator")
    print("Start/Stop/Restart controls in Settings")
    print("Dynamic viewer count affecting chat")
    print(f"Streamer name: {config.get('STREAMER_NAME')} (configurable)")
    print("Consistent usernames with persistent badges")
    print("Immediate response to streamer messages")
    print("Personality sliders in settings")
    print("Donation reactions from chat")
    print("Language settings with 5 languages and distribution control")
    print("60+ settings across 5 tabs")
    print(f"Settings file location: {config.get_settings_file()}")
    print("\nQuick Controls:")
    print("Ctrl+P - Settings (with Start/Stop/Restart) | Ctrl+F - Search | Ctrl+E - Export")
    print("Follower Stats | Simulate Events")
    
    main.mainloop()
