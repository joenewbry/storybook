#!/usr/bin/env bash
#
# Initial Jetson setup for Storybook.
# Run once as prometheus user on the Jetson.
#
set -euo pipefail

REPO_DIR="/ssd/storybook"
DEPLOY_DIR="$REPO_DIR/deploy"

echo "=== Storybook Jetson Setup ==="

# 1. Clone or update repo
if [ -d "$REPO_DIR/.git" ]; then
    echo "Repo exists, pulling latest..."
    cd "$REPO_DIR"
    git pull origin main
else
    echo "Cloning repo..."
    git clone git@github.com:joenewbry/storybook.git "$REPO_DIR"
    cd "$REPO_DIR"
fi

# 2. Create venv and install deps
if [ ! -d "$REPO_DIR/.venv" ]; then
    echo "Creating venv..."
    python3 -m venv "$REPO_DIR/.venv"
fi
echo "Installing dependencies..."
"$REPO_DIR/.venv/bin/pip" install -r requirements.txt --quiet

# 3. Create data directories
mkdir -p "$REPO_DIR/data/generated/images"
mkdir -p "$REPO_DIR/data/generated/videos"
mkdir -p "$REPO_DIR/data/generated/composed"

# 4. Copy .env if not exists
if [ ! -f "$REPO_DIR/.env" ]; then
    echo "Creating .env — you'll need to add API keys!"
    cat > "$REPO_DIR/.env" <<EOF
XAI_API_KEY=
ANTHROPIC_API_KEY=
EOF
fi

# 5. Install systemd services
echo "Installing systemd services..."
sudo cp "$DEPLOY_DIR/storybook.service" /etc/systemd/system/
sudo cp "$DEPLOY_DIR/auto-pull.service" /etc/systemd/system/storybook-auto-pull.service
sudo cp "$DEPLOY_DIR/auto-pull.timer" /etc/systemd/system/storybook-auto-pull.timer

# 6. Setup passwordless sudo for auto-pull restart
echo "Setting up sudoers for auto-pull..."
echo "prometheus ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart storybook" | sudo tee /etc/sudoers.d/storybook-auto-pull > /dev/null

# 7. Make auto-pull executable
chmod +x "$DEPLOY_DIR/auto-pull.sh"

# 8. Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable storybook
sudo systemctl start storybook
sudo systemctl enable storybook-auto-pull.timer
sudo systemctl start storybook-auto-pull.timer

echo ""
echo "=== Setup Complete ==="
echo "Storybook: http://localhost:8090"
echo "Auto-pull timer: $(systemctl is-active storybook-auto-pull.timer)"
echo "Main service: $(systemctl is-active storybook)"
echo ""
echo "IMPORTANT: Add API keys to $REPO_DIR/.env"
echo "  XAI_API_KEY=your_key"
echo "  ANTHROPIC_API_KEY=your_key"
