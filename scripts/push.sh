#!/usr/bin/env bash
# Safe push helper: the Arena sandbox periodically resets .git/config and
# SSH key permissions, so plain `git push` can fail confusingly.
# This guarantees the remote + key state, then pushes.
set -euo pipefail
cd "$(dirname "$0")/.."

# 1. SSH key permissions (sandbox restores reset them to 0644)
if [ -f "$HOME/.ssh/id_ed25519" ]; then
  chmod 600 "$HOME/.ssh/id_ed25519"
fi

# 2. Remote must exist (sandbox restores can wipe .git/config)
if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin git@github.com:Cyan-JadeGirl19/careerforge-pro-Arena-.git
fi

git fetch origin
git push origin HEAD

echo "Pushed. GitHub main is now at: $(git rev-parse --short HEAD)"
