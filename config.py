import json
import os

# ===========================
# CONFIGURATION MANAGER
# ===========================

class Config:
    """Configuration manager that handles all settings"""
    
    # Default settings
    DEFAULTS = {
        # Settings Directory
        "SETTINGS_DIR": "C:\\Users\\ecomi\\Documents",
        
        # LLM API Configuration
        "API_URL": "http://127.0.0.1:1234/v1/chat/completions",
        "MODEL": "gemma-3-4b-it-Q6_K.gguf",
        
        # Core Chat Simulation Settings
        "STREAMER_NAME": "JUNE",
        "MODJV_USERNAME": "modJV",
        "MODJV_CHAT_CHANCE": 0.20,
        "MODJV_BAN_CHANCE": 0.5,
        "BATCH_SIZE": 4,
        "SCREENSHOT_COOLDOWN": 2.0,
        "LLM_REQUEST_INTERVAL": 2.0,
        "MIN_DRIP_SPEED": 0.15,
        "MAX_DRIP_SPEED": 2.0,
        "CHATTER_REPLY_CHANCE": 0.35,
        "DONATION_CHANCE": 0.05,
        "RESPOND_TO_STREAMER_CHANCE": 0.8,
        
        # Technical Settings
        "IMAGE_SIZE": 672,
        "HISTORY_LEN": 5,
        "TEMPERATURE": 0.8,
        "MAX_TOKENS": 100,
        "WINDOW_WIDTH": 420,
        "WINDOW_HEIGHT": 700,
        "DEBUG_SCREENSHOT": True,
        "TEXT_SIZE": 10,
        
        # UI/UX Settings
        "CHAT_DENSITY": "normal",
        "SHOW_TIMESTAMPS": False,
        "AUTO_PAUSE_ON_HOVER": False,
        "HIGHLIGHT_USERNAME": True,
        "ANIMATIONS_ENABLED": True,
        "FONT_FAMILY": "Segoe UI",
        "SMOOTH_SCROLLING": True,
        "WINDOW_ON_TOP": True,
        "HIDE_TITLE_BAR": False,
        "SHOW_STREAM_STATS": True,
        "VIEWER_COUNT_AFFECTS_CHAT": True,
        "DYNAMIC_VIEWER_COUNT": True,
        
        # Performance Settings
        "ADAPTIVE_QUALITY": True,
        "BATCH_RENDER": True,
        "MEMORY_OPTIMIZATION": True,
        "KEEP_ALIVE_CONNECTION": True,
        "MESSAGE_CACHE_SIZE": 100,
        "DEBOUNCED_LLM_CALLS": True,
        "LAZY_LOAD_EMOTES": True,
        "COMPRESSION_ENABLED": True,
        "QUEUE_PRIORITIZATION": True,
        "AUTO_CLEAR_QUEUE": True,
        "MAX_QUEUE_SIZE": 50,
        "LLM_TIMEOUT": 60,
        "RETRY_FAILED_REQUESTS": True,
        "MAX_RETRIES": 3,
        "CONCURRENT_REQUESTS": 2,
        "REQUEST_BUFFER_SIZE": 10,
        
        # Twitch Feature Toggles
        "SUB_STREAKS_ENABLED": True,
        "BIT_EFFECTS_ENABLED": True,
        "FOLLOWER_GOAL_ENABLED": True,
        "HYPE_TRAIN_ENABLED": True,
        "CHANNEL_POINTS_ENABLED": False,
        "COPYPASTA_RECOGNITION": True,
        "EMOTE_COMBOS_ENABLED": True,
        
        # Personality Weights (0.0-2.0 scale)
        "PERSONALITY_HYPE": 1.0,
        "PERSONALITY_TROLL": 0.8,
        "PERSONALITY_GAMER": 1.2,
        "PERSONALITY_QUESTION": 0.9,
        "PERSONALITY_LOL": 1.1,
        "PERSONALITY_ADVICE": 0.7,
        "PERSONALITY_WHOLESOME": 1.0,
        "PERSONALITY_TOXIC": 0.3,
        "PERSONALITY_SPEEDRUNNER": 1.1,
        "PERSONALITY_LORE_SCHOLAR": 0.9,
        "PERSONALITY_CLIP_GOBLIN": 1.2,
        "PERSONALITY_BACKSEAT_GAMER": 1.3,
        "PERSONALITY_COPIUM_ADDICT": 0.8,
        "PERSONALITY_EMOTE_SPAMMER": 1.4,
        
        # Language Settings
        "LANGUAGES": {
            "english": {"enabled": True, "weight": 1.0},
            "tagalog": {"enabled": False, "weight": 0.0},
            "bisaya": {"enabled": False, "weight": 0.0},
            "Zambal": {"enabled": False, "weight": 0.0},
            "japanese": {"enabled": False, "weight": 0.0}
        },
        "SLANG_ENABLED": True,
        "SLANG_INTENSITY": 1.0,
        "FORMALITY_LEVEL": 0.0,
        "REGIONAL_DIALECTS": False,
        "CODE_SWITCHING": True,
        "EMOTE_FREQUENCY": 0.7,
        "INTERNET_SPEAK": 0.6,
        "AUTO_TRANSLATE": False,
        
        # Intelligence Settings
        "CONVERSATION_THREADING": True,
        "EVENT_REACTIONS_ENABLED": True,
        "USER_ARCHETYPES_ENABLED": True,
        "MOOD_BASED_RESPONSES": False,
        "CULTURAL_CALENDAR_ENABLED": False,
        "AUTO_MODERATION_ENABLED": True,
        "USER_REPUTATION_ENABLED": True,
        "PATTERN_DETECTION": True,
        "CONTEXT_AWARENESS": True,
        
        # Event Settings
        "EVENT_FOLLOWER_CHANCE": 0.02,
        "EVENT_SUBSCRIBER_CHANCE": 0.01,
        "EVENT_HYPE_TRAIN_CHANCE": 0.005,
        "EVENT_RAID_CHANCE": 0.003,
        "EVENT_HOST_CHANCE": 0.002,
        "EVENT_BITS_CHANCE": 0.008,
        "EVENT_SUB_STREAK_CHANCE": 0.01,
        "EVENT_FOLLOWER_GOAL_CHANCE": 0.02,
        "EVENT_GIVEAWAY_CHANCE": 0.001,
        "EVENT_MILESTONE_CHANCE": 0.001,
        
        # Viewer Dynamics
        "VIEWER_BASE_COUNT": 50,
        "VIEWER_FLUCTUATION_MIN": -10,
        "VIEWER_FLUCTUATION_MAX": 15,
        "VIEWER_GROWTH_RATE": 0.1,
        "VIEWER_PEAK_HOUR_MULTIPLIER": 1.5,
    }
    
    def __init__(self):
        self._settings = self.DEFAULTS.copy()
        self.load_settings()
    
    def get_settings_file(self):
        """Get the settings file path based on current SETTINGS_DIR"""
        settings_dir = self.get("SETTINGS_DIR")
        return os.path.join(settings_dir, "twitch_sim_settings.json")
    
    def load_settings(self):
        """Load settings from JSON file or use defaults"""
        settings_file = self.get_settings_file()
        
        # Create directory if it doesn't exist
        settings_dir = os.path.dirname(settings_file)
        if settings_dir:
            os.makedirs(settings_dir, exist_ok=True)
        
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    # Update defaults with saved settings
                    self._settings.update(saved_settings)
                    print("[OK] Settings loaded from", settings_file)
            except Exception as e:
                print("[ERROR] Error loading settings:", e)
                print("[INFO] Using default settings")
        else:
            print("[INFO] No settings file found, using defaults")
    
    def save_settings(self):
        """Save current settings to JSON file"""
        try:
            settings_file = self.get_settings_file()
            
            # Create directory if it doesn't exist
            settings_dir = os.path.dirname(settings_file)
            if settings_dir:
                os.makedirs(settings_dir, exist_ok=True)
            
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2)
            print("[OK] Settings saved to", settings_file)
        except Exception as e:
            print("[ERROR] Error saving settings:", e)
    
    def get(self, key, default=None):
        """Get a setting value"""
        return self._settings.get(key, default)
    
    def set(self, key, value):
        """Set a setting value"""
        self._settings[key] = value
    
    def update(self, updates):
        """Update multiple settings at once"""
        self._settings.update(updates)

# Create global config instance
config = Config()
