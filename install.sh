#!/usr/bin/env bash
# Puts the `mira` command on this computer (Linux / Chromebook Linux / Mac). Run once: bash install.sh
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p "$HOME/.local/bin"; cp mira "$HOME/.local/bin/mira"; chmod +x "$HOME/.local/bin/mira"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"; echo "(open a new terminal so 'mira' is found)";; esac
command -v claude >/dev/null || { echo "Installing Claude Code (Mira's body)..."; curl -fsSL https://claude.ai/install.sh | bash; }
echo "Done. Start the brain on Kaggle (see README), then run the 'mira connect ...' line it prints."
