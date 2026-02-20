# 🎉 **✨ TWITCHCHAT SIM – Twitch Chat Simulator (Beta 0.5) ✨** 🎉  
> *Let’s bring your stream to life… even when it’s just you and your code!*  
> _(repository/file name: **TWITCHCHAT SIM**)_

[![GitHub stars](https://img.shields.io/github/stars/yourusername/EcomineAI?style=social)](https://github.com/yourusername/EcomineAI/stargazers)
[![Issues](https://img.shields.io/github/issues/yourusername/EcomineAI)](https://github.com/yourusername/EcomineAI/issues)
[![License](https://img.shields.io/github/license/yourusername/EcomineAI)](https://github.com/yourusername/EcomineAI/blob/main/LICENSE)
[![Repo size](https://img.shields.io/github/repo-size/yourusername/EcomineAI)](https://github.com/yourusername/EcomineAI)
[![Version](https://img.shields.io/badge/version-Beta%200.5-orange)](https://github.com/yourusername/EcomineAI/releases)

---

## 💡 Credits

Created and maintained by **EcomineAI** – the mastermind behind TWITCHCHAT SIM and the chaos of chat!

---

## 📘 About EcomineAI

EcomineAI is a **Twitch chat simulator** currently in **Beta 0.5**.  
It’s designed to recreate the energy and madness of a live Twitch chat using artificial intelligence.  
⚠️ *Features are experimental and the experience may change as we iterate!*

The idea? When you want to test a stream, bot, or script but don’t have hundreds of real viewers, EcomineAI fills the void with:

- **Realistic chat behavior**  
- **Emote spam**  
- **Hyper, salty, or chill reactions**  
- **AI-driven personalities**

Whether you're debugging a chatbot, practising streaming, or just goofing around, EcomineAI pumps in the life you crave.

---

## 🚀 Features

- 🗨️ **Simulated Twitch Chat** – feeling real with random delays, caps lock, and all  
- 😄 **Custom Emotes & Reactions** – `Kappa`, `PogChamp`, or your own!  
- 🖥️ **Interactive CLI or GUI** – chat back and forth in real-time  
- 🤖 **AI Responses powered by Gemma 3 3B** – local model shipped via **LM Studio** (default, no external API required)  
- 🧪 **Fun Experimentation** – spawn spam, raid scenarios, bot armies…

---

## 🛠️ Installation & Setup

1. **Prerequisites**  
   - Python 3.10+  
   - LM Studio installed & the **Gemma 3 3B** model downloaded (the default); other GGUF models work too but this project defaults to Gemma  
   - Optional: GUI dependencies if using the graphical mode (`tkinter`, `PySimpleGUI`, etc.)

2. **Clone the repo**

   ```bash
   git clone https://github.com/yourusername/EcomineAI.git
   cd EcomineAI
   ```

3. **Install Python dependencies**

   ```bash
   python -m venv venv
   source venv/bin/activate      # or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   ```

4. **Configure**  
   - Edit `config.py` with your LLM path, chat speed, emote list, etc.  
   - Ensure LM Studio is running and listening.

5. **Run**

   ```bash
   python main.py          # start the simulator
   # or for GUI
   python ui_components.py
   ```

---

## 📝 Usage Example

**Input prompt** (your “stream” description):

```text
Stream Title: Coding with Ecomine
Goal: test chat spam
Mood: hype
```

**Simulated output**:

```
[00:00] <Viewer123> PogChamp POGGERS this is insane LOL
[00:01] <gamer_girl> anyone got the code?
[00:02] <ChatBot> !followage 
[00:03] <twitchy> Kappa keep going!
[00:05] <anon> HeyEugene 👍👍👍
```

> Looks and feels like the real thing, emotes and all. 🔥

---

## 🎉 Fun & Engaging Style

This README is designed like a streamer’s hype page: light, playful, and decorated with emojis.  
Expect the simulator itself to throw in fun surprises, like “raid” events and mock subs.

---

> **⚠️ Beta 0.5** – features may change.  
> **👍 Feedback welcome!** Open an issue or drop a message.

---

Thanks for trying **EcomineAI** – the chat simulator that doesn’t sleep!  
Get ready to hear the fake viewcount rise. 📈💬
