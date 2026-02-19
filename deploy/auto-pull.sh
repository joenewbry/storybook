#!/usr/bin/env bash
#
# Auto-pull deployment — polls origin/main for new commits,
# pulls them, installs deps if needed, and restarts the service.
#
# Designed to run every minute via systemd timer.
#
set -euo pipefail

REPO_DIR="/ssd/storybook"
BRANCH="main"
LOG_TAG="storybook-auto-pull"

cd "$REPO_DIR"

# Use prometheus user's SSH key for GitHub access
export GIT_SSH_COMMAND="ssh -i /home/prometheus/.ssh/id_ed25519 -o StrictHostKeyChecking=no"

# Fetch latest from origin
if ! git fetch origin "$BRANCH" --quiet 2>&1; then
    logger -t "$LOG_TAG" "git fetch failed"
    exit 1
fi

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

# Nothing to do if already up to date
if [ "$LOCAL" = "$REMOTE" ]; then
    exit 0
fi

logger -t "$LOG_TAG" "New commits detected: $LOCAL -> $REMOTE"

# Pull changes
git reset --hard "origin/$BRANCH" 2>&1 | logger -t "$LOG_TAG"

# Install any new Python dependencies
if git diff "$LOCAL" "$REMOTE" --name-only | grep -q 'requirements.txt'; then
    logger -t "$LOG_TAG" "requirements.txt changed, installing deps..."
    .venv/bin/pip install -r requirements.txt --quiet 2>&1 | logger -t "$LOG_TAG"
fi

# Restart the web service (uses passwordless sudo from /etc/sudoers.d/auto-pull)
sudo systemctl restart storybook 2>&1 | logger -t "$LOG_TAG"

logger -t "$LOG_TAG" "Deployed $(git rev-parse --short HEAD): $(git log -1 --format='%s')"
