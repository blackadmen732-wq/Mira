#!/usr/bin/env bash
# Puts the `mira` command on this computer (Linux / Chromebook Linux / Mac). Run once: bash install.sh
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p "$HOME/.local/bin"; cp mira "$HOME/.local/bin/mira"; chmod +x "$HOME/.local/bin/mira"
mkdir -p "$HOME/.mira"; chmod 700 "$HOME/.mira"; cp computer/computer_mcp.py "$HOME/.mira/computer_mcp.py"
echo "Installing Mira's eyes and hands (screen + mouse + keyboard; asks for your password once)..."
if command -v apt-get >/dev/null; then sudo apt-get install -y -q xdotool scrot imagemagick tesseract-ocr wmctrl python3 >/dev/null
elif command -v brew >/dev/null; then echo "(Mac: screen control isn't supported yet; the terminal and coding still work.)"
else echo "Install xdotool, scrot, imagemagick, tesseract and wmctrl with your package manager for screen control."; fi
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"; echo "(open a new terminal so 'mira' is found)";; esac
command -v claude >/dev/null || { echo "Installing Claude Code (Mira's body)..."; curl -fsSL https://claude.ai/install.sh | bash; }
echo "Done. Start the brain on Kaggle (see README), then run the 'mira connect ...' line it prints."
