#!/bin/bash
set -e

# --- Configuration ---
APP_ROOT="/var/www/stock.wael.work.gd"
DATA_DIR="$APP_ROOT/data"
STATIC_DIR="$APP_ROOT/frontend"
USER="stock"

# --- 1. Install System Dependencies ---
echo "Installing system dependencies..."
sudo pacman -Syu --noconfirm
sudo pacman -S --noconfirm python python-pip nginx redis sqlite3

# --- 2. Setup User and Directories ---
echo "Setting up user and directories..."
if ! id "$USER" &>/dev/null; then
    sudo useradd -r -s /usr/bin/nologin "$USER"
fi

sudo mkdir -p "$APP_ROOT" "$DATA_DIR" "$STATIC_DIR"

# --- 3. Deploy Files (Assuming we are in the repo root) ---
echo "Deploying application files..."
sudo cp -r backend "$APP_ROOT/"
sudo cp -r config "$APP_ROOT/"
sudo cp -r frontend/* "$STATIC_DIR/"
sudo cp -r data/news_events.json "$DATA_DIR/"

# --- 4. Python Virtual Environment ---
echo "Setting up Python virtual environment..."
sudo python -m venv "$APP_ROOT/venv"
sudo "$APP_ROOT/venv/bin/pip" install --upgrade pip
sudo "$APP_ROOT/venv/bin/pip" install -r "$APP_ROOT/backend/requirements.txt"

# --- 5. Environment Configuration ---
echo "Configuring environment..."
sudo "$APP_ROOT/venv/bin/python" scripts/generate_env.py
if [ ! -f "$APP_ROOT/config/.env" ]; then
    sudo cp "$APP_ROOT/config/.env.production" "$APP_ROOT/config/.env"
fi

# --- 6. Database Initialization ---
echo "Initializing database..."
if [ ! -f "$DATA_DIR/market.db" ]; then
    sudo sqlite3 "$DATA_DIR/market.db" < "$APP_ROOT/backend/app/schema.sql"
fi

# --- 7. Permissions ---
echo "Setting permissions..."
sudo chown -R "$USER:$USER" "$APP_ROOT"
# Allow other users (like MCSManager) to read/execute in the directory
sudo chmod -R 755 "$APP_ROOT"
sudo chmod 600 "$APP_ROOT/config/.env"
sudo chown -R nginx:nginx "$STATIC_DIR"

# --- 8. Systemd Service ---
echo "Installing systemd service..."
sudo cp "$APP_ROOT/config/stock-backend.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable redis
sudo systemctl start redis
sudo systemctl enable stock-backend
sudo systemctl start stock-backend

echo "Setup complete. The application is now running."
echo "Nginx configuration still needs to be manually linked or verified in /etc/nginx/."
