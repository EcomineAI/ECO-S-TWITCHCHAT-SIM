from collections import deque, defaultdict

# ===========================
# DATA STRUCTURES
# ===========================

INVISIBLE_CHARS = {'\u200b': ' ', '\u00a0': ' ', '\u200c': ' ', '\ufeff': ' '}

# Enhanced Donation Messages
DONATION_MESSAGES = [
    ("GenerousGamer", "$50.00", "POG CHAMPION! That last play was insane! Keep up the grind! 🚀", "hype"),
    ("TrollDonator", "$1.00", "You almost choked that! Next time try to look at the minimap. Kappa 😏", "troll"),
    ("WholesomeWitch", "$5.00", "Just sending some positive energy! You've got this, friend. 💖", "wholesome"),
    ("MemeLord", "$6.90", "Dread it. Run from it. Destiny still arrives. Clip that! 👀", "meme"),
    ("TheQuietOne", "$100.00", "I'm always here watching. Don't let the others distract you. Enjoy the pizza. 🍕", "high_value"),
    ("ClutchKing", "$25.00", "HOLY SMOKES! That 1v3 was unbelievable! You're carrying this tournament! 🏆", "hype"),
    ("Backseat_Bobby", "$2.00", "bro why didn't you push when he was low? my grandma plays better than that 💀", "troll"),
    ("Comfort_Corner", "$10.00", "Your positivity is so infectious! This community is lucky to have you 🌈", "wholesome"),
    ("NoodleNick", "$4.20", "When the impostor is sus! 📮 Anyway here's my lunch money for the week", "meme"),
    ("SteadySupporter", "$200.00", "Consistently impressed by your growth. Investing in your success. Keep going.", "high_value"),
]

# Event Messages
EVENT_MESSAGES = {
    "follower": [
        "🎉 {username} just followed! Welcome to the community!",
        "👋 Hey everyone, welcome {username} to the stream!",
        "💫 {username} is now following! Thanks for the support!",
        "🌟 New follower alert! Welcome {username}!",
        "🔥 {username} just followed! The community grows stronger!",
    ],
    "subscriber": [
        "⭐ {username} just subscribed for {months} months! Thank you!",
        "🎊 {username} is now a subscriber! Welcome to the club!",
        "💖 {username} subscribed for {months} months! You're amazing!",
        "🏆 {username} joined the subscriber squad! {months} months strong!",
        "✨ {username} just subscribed! Thanks for the support!",
    ],
    "hype_train": [
        "🚂 Hype Train Level {level}! Choo choo! All aboard!",
        "🎯 Hype Train reached level {level}! The energy is unreal!",
        "⚡ Level {level} Hype Train! This is getting crazy!",
        "🔥 Hype Train level {level}! The chat is on fire!",
        "🌟 Hype Train at level {level}! Incredible momentum!",
    ],
    "raid": [
        "🏃‍♂️ Incoming raid from {streamer} with {viewers} viewers!",
        "🎉 RAID! {streamer} sent {viewers} viewers our way!",
        "🚀 We're being raided by {streamer} with {viewers} viewers!",
        "💫 Massive raid from {streamer}! Welcome {viewers} new viewers!",
        "🔥 RAID ALERT! {streamer} brought {viewers} viewers!",
    ],
    "host": [
        "📺 {streamer} is now hosting us with {viewers} viewers!",
        "🎪 Hosted by {streamer}! Welcome their {viewers} viewers!",
        "🌟 {streamer} is hosting us! Thanks for the support!",
        "💫 We're being hosted by {streamer} with {viewers} viewers!",
        "👋 Shoutout to {streamer} for hosting us! Welcome everyone!",
    ],
    "bits": [
        "💎 {username} cheered {amount} bits! Let's go!",
        "🎊 {username} dropped {amount} bits! Amazing!",
        "✨ {username} just cheered {amount} bits! So generous!",
        "💖 {amount} bits from {username}! You're incredible!",
        "🔥 {username} with {amount} bits! The hype is real!",
    ],
    "sub_streak": [
        "📅 {username} is on a {streak}-month sub streak! Legend!",
        "🎯 {username} has been subscribed for {streak} months straight!",
        "💫 {streak} month sub streak for {username}! Incredible loyalty!",
        "🌟 {username} rocking a {streak}-month streak! Thank you!",
        "🏆 {streak} months and counting for {username}! Amazing!",
    ],
    "follower_goal": [
        "🎯 We're {count} away from {goal} followers! So close!",
        "💫 Only {count} more followers until we hit {goal}!",
        "🚀 {count} followers needed to reach {goal}! Almost there!",
        "🌟 We're at {current}/{goal} followers! Keep it up!",
        "🔥 {count} to go for {goal} followers! Let's do this!",
    ],
    "giveaway": [
        "🎁 GIVEAWAY STARTED! Type !enter to win!",
        "🎊 GIVEAWAY TIME! Use !join to enter!",
        "💫 GIVEAWAY ACTIVE! Comment to participate!",
        "🎯 QUICK GIVEAWAY! Drop a message to enter!",
        "🌟 GIVEAWAY! Type anything to enter!",
    ],
    "milestone": [
        "🏆 MILESTONE ACHIEVED! {description}",
        "🎉 WE DID IT! {description}",
        "🌟 HUGE MILESTONE! {description}",
        "💫 COMMUNITY ACHIEVEMENT! {description}",
        "🔥 MILESTONE UNLOCKED! {description}",
    ]
}

# Expanded Emote List with Windows Emojis
EMOTE_LIST = ["LUL", "KEKW", "PogChamp", "Kappa", "FeelsBadMan", "PepeHands", 
              "MonkaS", "4Head", "WutFace", "POG", "OMEGALUL", "PogU", "Sadge", 
              "Okayge", "HYPERCLAP", "😆", "😂", "🔥", "💀", "👀", "✨", "🎮", 
              "🙏", "💖", "🚀", "📈", "🍕", "⭐", "💯", "👑",
              "Clap", "EZ", "GG", "WP", "RIP", "F", "Sheesh", "Poggers", "Bedge",
              "Copium", "Hmm", "Sus", "YEP", "NOP", "ICANT", "W", "L", "Rare",
              "Common", "GigaChad", "Pepega", "Weirdge", "Stare", "Hopium",
              "🤡", "👺", "🥶", "😱", "🤯", "🥺", "😤", "💅", "🤝", "📉",
              "🏆", "🎯", "⚡", "🌪️", "🍿", "🥤", "🎪", "🤖", "👾", "🦍"]

EMOTE_COLORS = {
    "LUL": "#FFCC00", "KEKW": "#99FF99", "PogChamp": "#FF99FF", "Kappa": "#CC00FF", 
    "POG": "#FF99FF", "OMEGALUL": "#FF4500", "PogU": "#00FF00", "Sadge": "#ADD8E6", 
    "Okayge": "#FFFF00", "HYPERCLAP": "#FF69B4", "😆": "#FFD700", "😂": "#FFA500",
    "🔥": "#FF4500", "💀": "#808080", "👀": "#00BFFF", "✨": "#FFD700", "🎮": "#00FF00",
    "🙏": "#FFD700", "💖": "#FF69B4", "🚀": "#1E90FF", "📈": "#32CD32", "🍕": "#FF6347",
    "⭐": "#FFD700", "💯": "#FF0000", "👑": "#FFD700",
}

# Chat Analysis Keywords
HYPE_WORDS = ["POG", "CLUTCH", "INSANE", "WTF", "BRO", "HOLY", "GOAT", "FIRE", "SHEESH", "NO WAY",
              "LETS GO", "WHAT", "NUTTY", "CRACKED", "BUSSIN", "DEMON", "GOD", "BROKEN", "OP", "BUFF",
              "POGGERS", "HYPERS", "RAMPAGE", "DOMINANT", "UNREAL", "DISGUSTING", "FILTHY", "NASTY",
              "BEAST", "MONSTER", "ANIMAL", "PREDATOR", "VICIOUS", "SAVAGE", "BRUTAL", "MERCILESS"]

CHILL_WORDS = ["calm", "chill", "relax", "slow", "easy", "vibes", "nvm", "wait", "ok", "oof",
               "casual", "peaceful", "quiet", "gentle", "mellow", "laidback", "cool", "steady",
               "patient", "breathe", "pause", "stop", "hold", "delay", "patience", "silence",
               "peace", "tranquil", "serene", "still", "composed", "collected", "unbothered"]

# Expanded Username Pool
USERNAME_POOL = [
    "SneakyPanda", "LagLord", "GGWP_123", "NoScopeNana", "EmoteMachine", 
    "BackseatBaron", "CopiumDealer", "ClutchGoblin", "PixelPirate", "FrameFighter",
    "ResidentSleeper", "ChatEnjoyer", "PogO", "KappaLord", "MonaLUL", "PepoG",
    "WeirdChamp", "5Head", "SimpLord", "VibeCheck", "GlitchMaster", "RNGesus",
    "TiltProof", "SaltMiner", "PingAbuser", "HitboxHarry", "PepegaClap", "KEKWarlord",
    "PogChampion", "OMEGALULer", "SadgeSpammer", "MonkaGiga", "4HeadAndy", "WutFaceUser",
    "OkaygeBusiness", "HYPERCLAPper", "JebaitMaster", "TriHard7", "EZClapper", "GG_EZ",
    "ClipChaser", "VODReviewer", "ToxicTimmy", "WholesomeWendy", "HypeHenry", "QuietQuinn",
    "LoudLarry", "RageRicky", "ChillCharles", "TryhardTina", "CasualCarl", "SweatySteve"
]

USERNAME_COLORS = [
    "#1E90FF", "#32CD32", "#FF4500", "#8A2BE2", "#DAA520", "#FF69B4", 
    "#00CED1", "#DC143C", "#FF8C00", "#00FF7F", "#9370DB", "#FF1493",
    "#7CFC00", "#FFD700", "#FF00FF", "#00FFFF", "#FF6347", "#40E0D0",
    "#EE82EE", "#F0E68C", "#9ACD32", "#FF7F50", "#6495ED", "#D2691E",
    "#008080", "#B8860B", "#FFB6C1", "#00FA9A", "#483D8B", "#2E8B57",
]

# Enhanced Personality System
CHAT_PERSONALITIES = {
    "hype": "Hype everything up! Use lots of exclamation marks and caps lock!",
    "troll": "Be slightly mean and tease the streamer or other chat users.",
    "gamer": "Comment on the gameplay mechanics, build, or strategy.",
    "question": "Ask a confused question about what is currently happening on screen.",
    "lol": "Just laugh like 'LUL', 'LOL', 'KEKW'. Use emotes often.",
    "advice": "Give unsolicited advice or tell the streamer what they should do next.",
    "wholesome": "Be positive and supportive. Spread good vibes!",
    "toxic": "Be negative and critical, but keep it PG-13.",
    "speedrunner": "Comment like a world-record chaser. Talk about skips and optimization.",
    "lore_scholar": "Reference deep lore, story elements, and hidden details.",
    "clip_goblin": "Constantly point out clip-worthy moments. Always ready with 'CLIP IT!'",
    "backseat_gamer": "Constantly tell the streamer what to do, often obvious things.",
    "copium_addict": "Make excuses for bad plays or blame everything except the streamer.",
    "emote_spammer": "Fill the chat with emotes, rarely using actual words.",
}

# Badge System
USER_BADGES = {
    "subscriber": {"text": "★", "color": "#9147FF", "tooltip": "Subscriber"},
    "moderator": {"text": "⚡", "color": "#00FF00", "tooltip": "Moderator"},
    "vip": {"text": "⭐", "color": "#FFD700", "tooltip": "VIP"},
    "founder": {"text": "👑", "color": "#FF6B35", "tooltip": "Founder"},
    "prime": {"text": "🔹", "color": "#00FF7F", "tooltip": "Prime Gaming"},
    "turbo": {"text": "🌀", "color": "#9B59B6", "tooltip": "Turbo User"},
    "bot": {"text": "🤖", "color": "#95A5A6", "tooltip": "Bot Account"},
}

# Twitch Data Storage Class
class TwitchData:
    subscribers = {}
    follower_count = 0
    follower_goal = 100
    hype_train_level = 0
    highlighted_users = {}
    user_reputation = defaultdict(lambda: {"score": 0, "messages": 0, "warnings": 0})
    user_badges = defaultdict(list)
    viewer_count = 0
    chat_users = {}  # Store user data for consistency
    viewer_history = deque(maxlen=60)  # Track viewer count over time
    peak_viewers = 0
    total_views = 0

twitch_data = TwitchData()
