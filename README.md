# 🎯 Project Plan: MOBA AI Bot Learning Environment

## 🧠 Objective

My goal is to develop an intelligent AI bot capable of learning how to play a real-time MOBA game (similar to *LoL: Wild Rift*) by observing gameplay and training in a controlled simulation environment.

Eventually, I plan to transfer the learned logic into a real-game setting. However, all training will initially take place in a **custom MOBA environment** that I fully control.

---

## ✅ Current Strategy & Environment Choice

### Why use a custom environment?

Training directly in Wild Rift (or any real MOBA) is not feasible because:

- ❌ I don't have access to internal game states like HP, cooldowns, or positions
- ❌ I can't control all players or enforce bot-only matches
- ❌ Anti-cheat systems block automation
- ❌ I can't define custom rewards or get low-level state data

### ✅ My Solution: **Unity + ML-Agents**

I will build a custom environment using [Unity](https://unity.com/) and integrate [ML-Agents Toolkit](https://github.com/Unity-Technologies/ml-agents) to train reinforcement learning agents.

**Why this setup:**
- Full control over the game logic, visuals, units, and balance
- Built-in support for physics, navigation, and 2D/3D graphics
- ML-Agents offers a stable API for agent training and Python integration
- Easy to scale and run parallel simulations if needed

---

## 🧩 Project Roadmap

### Phase 1: Core MOBA Environment

- [ ] Create a basic 3-lane map with bases and turrets
- [ ] Add minion spawning and pathfinding logic
- [ ] Implement a simple controllable unit with health and attack
- [ ] Add a basic scripted enemy bot for testing

### Phase 2: Agent API & Observations

- [ ] Define what the agent can observe (e.g., HP, nearby enemies, positions)
- [ ] Implement a reward system based on kills, farming, survival, etc.
- [ ] Allow both hand-crafted logic and RL-based agent control

### Phase 3: Machine Learning Training

- [ ] Integrate Unity ML-Agents
- [ ] Set up the observation and action space for agents
- [ ] Train using PPO or SAC
- [ ] Optionally, experiment with behavior cloning from rule-based bots

---

## ⚙️ Tools & Technologies I Plan to Use

| Tool / Library         | Purpose                             |
|------------------------|-------------------------------------|
| **Unity**              | Game engine for environment         |
| **ML-Agents Toolkit**  | Reinforcement learning integration  |
| **Python**             | Training pipeline and scripting     |
| **PyTorch**            | Custom model development (if needed)|
| **Gym Wrapper (opt.)** | For scaling with Gym-compatible tools|

---

## 🔮 Future Plans

- Add features like mana, cooldowns, and fog of war
- Create a progression system with curriculum learning
- Add vision-based input (for imitation learning or future multimodal training)
- Try exporting trained agents for testing in scripted game replays

---

## 📌 Next Steps

1. ✅ Set up an empty Unity project (URP or HDRP)
2. 🔧 Build a prototype map (start with one lane)
3. 👣 Script basic movement and spawning logic
4. 📤 Create observation definitions for ML input
5. 🧠 Configure ML-Agents and start first training runs

---

## 🔊 Discord Voice Assistant Bot

This repository now also contains a Discord bot capable of joining a voice channel, listening to what you say, transcribing it with OpenAI Whisper, generating a reply with GPT, and speaking the answer back using OpenAI TTS.

### ⚙️ Prerequisites

- Python 3.9+
- `ffmpeg` installed and available on your `PATH`
- Discord bot token with the necessary privileged intents enabled
- OpenAI API key with access to GPT-4o models and the speech endpoints

### 🚀 Setup

1. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file based on the provided example:

   ```bash
   cp .env.example .env
   ```

   Fill in your `DISCORD_TOKEN` and `OPENAI_API_KEY` values.

3. Run the bot:

   ```bash
   python -m bot.main
   ```

### 🕹️ Usage

- Invite the bot to your server and ensure it has permission to join and speak in voice channels.
- Type `!join` in any text channel while connected to a voice channel.
- Speak normally; after 2-3 seconds of silence the bot will transcribe your message, respond in text, and synthesize an audible reply.
- Use `!reset` to clear the conversation history without leaving the call.
- Use `!leave` to disconnect the bot from the voice channel.

