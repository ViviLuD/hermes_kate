#!/usr/bin/env python3
"""
Kate Morning Brief Delivery — sends the morning brief to Benjamin via Telegram Bot API.
Uses the Telegram bot token from .env to send messages directly.
"""

import json
import sys
from pathlib import Path

# Load env
try:
    from dotenv import load_dotenv
    load_dotenv("/opt/data/.env")
except ImportError:
    pass

import os
import requests

MEMORY_DIR = Path("/opt/data/kate_night_engine/memory")
BRIEF_META = MEMORY_DIR / "latest_brief.json"

# Get Telegram bot token from environment
# The token is stored in the voice interface config
def get_telegram_token():
    """Extract telegram bot token from environment files."""
    # Try environment first
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if token:
        return token
    
    # Try .env
    env_file = Path("/opt/data/.env")
    if env_file.exists():
        for line in env_file.read_text().split("\n"):
            if "TELEGRAM" in line.upper() and "TOKEN" in line.upper():
                if "=" in line:
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    
    # Try voice interface config
    config_path = Path("/opt/data/voice_interface/.env")
    if config_path.exists():
        for line in config_path.read_text().split("\n"):
            if "TELEGRAM" in line.upper() and "TOKEN" in line.upper():
                if "=" in line:
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    
    return None


def send_telegram_message(chat_id: str, text: str, image_path: str = None):
    """Send message and optional image to Telegram."""
    token = get_telegram_token()
    if not token:
        print("[Delivery] No Telegram bot token found — cannot deliver")
        return False
    
    base_url = f"https://api.telegram.org/bot{token}"
    
    # Send text first
    resp = requests.post(f"{base_url}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }, timeout=30)
    
    if resp.status_code != 200:
        print(f"[Delivery] Text send failed: {resp.text}")
        return False
    
    # Send image if provided
    if image_path and Path(image_path).exists():
        with open(image_path, "rb") as f:
            resp = requests.post(f"{base_url}/sendPhoto", 
                data={"chat_id": chat_id},
                files={"photo": f},
                timeout=60,
            )
        if resp.status_code == 200:
            print("[Delivery] Image sent successfully")
        else:
            print(f"[Delivery] Image send failed: {resp.text}")
    
    return True


def main():
    if not BRIEF_META.exists():
        print(f"[Delivery] No brief found at {BRIEF_META}")
        sys.exit(0)
    
    meta = json.loads(BRIEF_META.read_text())
    brief_text = meta.get("brief_text", "Brief indisponible.")
    image_path = meta.get("image_path")
    
    # Benjamin's Telegram chat ID
    chat_id = "1634903384"
    
    success = send_telegram_message(chat_id, brief_text, image_path)
    if success:
        print("[Delivery] Morning brief delivered to Benjamin")
    else:
        print("[Delivery] Delivery failed")


if __name__ == "__main__":
    main()
