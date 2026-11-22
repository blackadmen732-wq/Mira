# Mira: notes for Claude

Owner: Mark. Keep his decisions; change only what he asks. Explain changes simply: what changed, which files, how to check.

## What this is
- `mira` (bash): runs Claude Code with ANTHROPIC_BASE_URL pointed at Mira's brain. All model slots (opus/sonnet/haiku/subagent) = the same model.
  Modes: code (huihui_ai/qwen3-coder-abliterated:30b), think (huihui_ai/qwen3-abliterated:30b), cloud (OpenRouter, MIRA_CLOUD_MODEL,
  default nousresearch/hermes-4-405b; key saved in ~/.mira/openrouter.key 0600). `mira connect <trycloudflare link> <password>` writes ~/.mira/brain.env.
- Voice: brain.py also serves /v1/audio/speech (Kokoro via kokoro-onnx, voice af_heart, MIRA_VOICE), loaded in a background thread;
  ui/server.py /api/tts proxies it with the brain password; the page falls back to Chrome speechSynthesis. Page has chimes (mic on/off,
  done, error), a big mic-state chip, a level meter, MIC_ERR messages, and "Test mic + voice".
- `kaggle/brain.py`: Kaggle script kernel `reviewboost/mira-brain` (GPU T4 x2, internet). Installs Ollama (Anthropic Messages API
  compatible), pulls the two models into /tmp, puts the `Gate` password proxy (127.0.0.1:8000, /v1/ only, x-api-key or Bearer,
  random token per run) in front, opens a cloudflared quick tunnel, prints the `mira connect` line, exits after MIRA_IDLE_MINUTES (30) idle.
- `computer/computer_mcp.py`: stdlib MCP server (stdio) = Mira's eyes and hands: screen_look (scrot/import screenshot shrunk to
  MIRA_SCREEN_WIDTH 1280 + tesseract words with center x,y; coords scaled back to real pixels), mouse_click/move/drag, scroll,
  type_text, press_key (xdotool), open_url (http/https only), list_windows, focus_window. Emergency stop: mouse within 5 px of the
  top-left corner refuses every action. install.sh copies it to ~/.mira and apt-installs xdotool scrot imagemagick tesseract-ocr wmctrl;
  `mira` passes it with --mcp-config and pre-approves mcp__computer. X11/Xwayland only: on a Chromebook = Linux apps only.
- `ui/`: voice window. `server.py` (stdlib, 127.0.0.1:3005, Jarvis-style guard: Host/Origin/JSON) runs `mira <code|think> -p <text>
  --output-format stream-json --verbose --allowedTools "<TOOLS>"` (+ `--continue` after the first turn; /api/new resets) in
  MIRA_WORKDIR (home), streams simplified steps (step/result/say/done) as SSE; /api/stop kills the process group. `index.html` =
  orb UI, Web Speech in/out, conversation mode, wake word "Mira". `mira ui` starts it; install.sh copies ui/ to ~/.mira/ui and adds
  ~/.local/share/applications/mira.desktop.
- Kaggle kernel reviewboost/mira-brain runs `kaggle/start.py` (downloads kernel brain.py from GitHub main and runs it), so a fix here
  only needs a git push. Pushing the kernel (POST /api/v1/kernels/push) starts a run. Cancelling needs a session id the public API
  doesn't expose: stop runs from Kaggle's "View Active Events". Ollama is fetched with aria2c (one stream crawled on Kaggle).
- Tests: `python3 -m unittest tests/test_gate.py tests/test_computer.py tests/test_ui.py` (fake xdotool/scrot/tesseract).

## Rules
- Never commit keys or tokens. Never weaken the Gate (password + /v1/ only). Keep the top-left-corner emergency stop.
- Don't use Mark's Claude subscription tokens with other models; Mira only uses Claude Code with ANTHROPIC_BASE_URL.
