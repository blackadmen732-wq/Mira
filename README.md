# Mira

Your own coding assistant with **no filter**. Mira is Claude Code's body (it reads and writes files, runs your
terminal, builds and fixes code) with a different brain: an uncensored ("abliterated") open model.

- **Brain:** runs on a **free Kaggle GPU** only when you start it, and switches itself off after 30 minutes of
  no use, so it doesn't eat your free hours (about 30 GPU hours a week).
  - `mira`: **Qwen3 Coder abliterated 30B** for coding
  - `mira think`: **Qwen3 abliterated 30B** for everything else
- **No Kaggle?** `mira cloud` uses Hermes 4 405B on OpenRouter (pay per use, cents per session).
- It doesn't use your Claude subscription. It only borrows Claude Code's tools.
- **Full control of your computer:** your terminal (Claude Code's own), plus **eyes and hands**: it takes screenshots and
  reads the words on screen, moves and clicks the mouse, types, presses keys (ctrl+c, alt+Tab…), scrolls, drags,
  switches windows and opens web pages.
  - On a **Chromebook** it controls the **Linux side**: the terminal and any Linux app (Linux Chrome/Firefox, VS Code…).
    ChromeOS itself (the shelf, the normal Chrome browser, Android apps) is walled off by Google, so nothing can control it from Linux.
  - **Emergency stop:** move the mouse into the **top-left corner** of the screen; every action is refused while it's there.
    Or press **Ctrl+C** / Esc in Mira.

## Set up (once)

On your computer (Chromebook: in the Linux terminal):
```bash
git clone https://github.com/blackadmen732-wq/mira ~/mira && bash ~/mira/install.sh
```

## Use it

1. **Start the brain:** open https://www.kaggle.com/code/reviewboost/mira-brain → **Edit** → on the right, check
   **Accelerator = GPU T4 x2** and **Internet = on** → **Run All** (or **Save Version → Save & Run All**).
2. Wait about 5–10 minutes (the first part downloads the models). The output shows:
   ```
   MIRA'S BRAIN IS ON. On your computer, run this once:
       mira connect https://something.trycloudflare.com <password>
   ```
3. Paste that line into your terminal (Chromebook: **Ctrl+Shift+V**).
4. Go to the folder you want to work in and type `mira`. Talk to it like Claude Code, e.g. *"open firefox and find the Kalshi weather page"*.
   Mira asks before running terminal commands; press **Shift+Tab** to switch on auto mode so it just does them.

The link and password are new every time you start the brain, so repeat steps 1–3 each session.
`mira status` tells you if the brain is on.

## Good to know

- Open models are weaker than Claude at long multi-step work. Give Mira one clear task at a time.
- The brain is private: only someone with the password can use it, and it only answers Claude Code's API.
- Uncensored means it won't refuse; you're responsible for what you ask it to do.
