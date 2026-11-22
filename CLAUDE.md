# Mira: notes for Claude

Owner: Mark. Keep his decisions; change only what he asks. Explain changes simply: what changed, which files, how to check.

## What this is
- `mira` (bash): runs Claude Code with ANTHROPIC_BASE_URL pointed at Mira's brain. All model slots (opus/sonnet/haiku/subagent) = the same model.
  Modes: code (huihui_ai/qwen3-coder-abliterated:30b), think (huihui_ai/qwen3-abliterated:30b), cloud (OpenRouter, MIRA_CLOUD_MODEL,
  default nousresearch/hermes-4-405b; key saved in ~/.mira/openrouter.key 0600). `mira connect <trycloudflare link> <password>` writes ~/.mira/brain.env.
- `kaggle/brain.py`: Kaggle script kernel `reviewboost/mira-brain` (GPU T4 x2, internet). Installs Ollama (Anthropic Messages API
  compatible), pulls the two models into /tmp, puts the `Gate` password proxy (127.0.0.1:8000, /v1/ only, x-api-key or Bearer,
  random token per run) in front, opens a cloudflared quick tunnel, prints the `mira connect` line, exits after MIRA_IDLE_MINUTES (30) idle.
- Push a new version: POST https://www.kaggle.com/api/v1/kernels/push with the script text (see kernel-metadata.json). Pushing starts a run.
- Tests: `python3 -m unittest tests/test_gate.py`.

## Rules
- Never commit keys or tokens. Never weaken the Gate (password + /v1/ only).
- Don't use Mark's Claude subscription tokens with other models; Mira only uses Claude Code with ANTHROPIC_BASE_URL.
