"""
Kate Night Engine — Dream Image Generator
Converts dream narratives into visual images using OpenRouter's DALL-E.
"""

import json
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional
import requests

from config import (
    IMAGES_DIR, OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    IMAGE_MODEL,
)


def extract_image_prompt(dream_text: str) -> str:
    """Extract a visual prompt from the dream text using an LLM."""
    resp = requests.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "anthropic/claude-sonnet-4",
            "messages": [
                {
                    "role": "system",
                    "content": """You extract visual prompts from dream narratives.
Given a dream text, create a SINGLE sentence in English that describes the most 
visually striking, surreal scene from the dream. Make it evocative and concrete.

Focus on: colors, lighting, mood, composition, surreal elements.

Output ONLY the prompt, nothing else. Maximum 200 characters."""
                },
                {
                    "role": "user",
                    "content": f"""Dream text:
{dream_text}

Extract the visual prompt for an AI image generator:"""
                },
            ],
            "temperature": 0.7,
            "max_tokens": 150,
        },
        timeout=30,
    )
    data = resp.json()
    prompt = data["choices"][0]["message"]["content"].strip()
    # Ensure English
    if len(prompt) > 200:
        prompt = prompt[:200]
    return prompt


def generate_dream_image(dream_text: str, dream_title: str = "") -> Optional[Path]:
    """Generate an image from the dream using Pollinations.ai (free, no API key)."""
    
    visual_prompt = extract_image_prompt(dream_text)
    print(f"[DreamImage] Visual prompt: {visual_prompt}")
    
    # Use Pollinations.ai — free image generation, no API key needed
    import urllib.parse
    prompt_encoded = urllib.parse.quote(visual_prompt[:300])
    
    # Try Pollinations first (free)
    image_url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1024&height=1024&nologo=true&seed={hash(dream_title) % 100000}"
    
    try:
        img_resp = requests.get(image_url, timeout=60)
        if img_resp.status_code == 200 and len(img_resp.content) > 1000:
            date_str = datetime.now().strftime("%Y-%m-%d")
            img_path = IMAGES_DIR / f"dream_{date_str}.png"
            img_path.write_bytes(img_resp.content)
            print(f"[DreamImage] Pollinations.ai saved to {img_path}")
            return img_path
    except Exception as e:
        print(f"[DreamImage] Pollinations failed: {e}")
    
    # Fallback: scenic text-based SVG
    return None


def generate_fallback_visual(dream_text: str, dream_title: str) -> Path:
    """Generate a simple colored SVG as fallback if image generation fails."""
    import hashlib
    h = hashlib.md5(dream_title.encode()).hexdigest()
    color1 = f"#{h[:6]}"
    color2 = f"#{h[6:12]}"
    
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024">
  <defs>
    <radialGradient id="bg" cx="50%" cy="50%" r="70%">
      <stop offset="0%" style="stop-color:#1a1a2e"/>
      <stop offset="100%" style="stop-color:#0f0f1a"/>
    </radialGradient>
  </defs>
  <rect width="1024" height="1024" fill="url(#bg)"/>
  <text x="512" y="400" text-anchor="middle" fill="{color1}" font-size="48" font-family="serif" opacity="0.9">🌙 Rêve Nocturne</text>
  <text x="512" y="480" text-anchor="middle" fill="{color2}" font-size="28" font-family="serif" opacity="0.7">{dream_title[:60]}</text>
  <text x="512" y="550" text-anchor="middle" fill="#555" font-size="18" font-family="monospace" opacity="0.5">{datetime.now().strftime('%d.%m.%Y')}</text>
</svg>"""
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    img_path = IMAGES_DIR / f"dream_{date_str}.svg"
    img_path.write_text(svg)
    return img_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        dream_file = Path(sys.argv[1])
        dream = json.loads(dream_file.read_text())
        img = generate_dream_image(dream["dream_text"], dream.get("title", ""))
        print(f"Image: {img}")
