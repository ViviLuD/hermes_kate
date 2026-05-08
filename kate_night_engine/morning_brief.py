"""
Kate Night Engine — Morning Brief
Compiles dream + oracle results and delivers to Benjamin via Telegram.
"""

import json
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from config import (
    DREAMS_DIR, ORACLES_DIR, IMAGES_DIR, LOGS_DIR,
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
)


def get_paris_time() -> str:
    """Get current Paris time formatted."""
    cest = timezone(timedelta(hours=2))
    return datetime.now(cest).strftime("%H:%M")


def load_latest_dream() -> Optional[dict]:
    """Load the most recent dream."""
    dreams = sorted(DREAMS_DIR.glob("dream_*.json"), reverse=True)
    if dreams:
        return json.loads(dreams[0].read_text())
    return None


def load_latest_oracles() -> list[dict]:
    """Load today's oracle predictions."""
    today = datetime.now().strftime("%Y-%m-%d")
    oracles = sorted(ORACLES_DIR.glob(f"oracle_{today}_*.json"))
    results = []
    for of in oracles:
        try:
            results.append(json.loads(of.read_text()))
        except Exception:
            pass
    return results


def load_latest_image() -> Optional[Path]:
    """Find the latest dream image."""
    today = datetime.now().strftime("%Y-%m-%d")
    for ext in [".png", ".svg", ".jpg", ".webp"]:
        img = IMAGES_DIR / f"dream_{today}{ext}"
        if img.exists():
            return img
    return None


def synthesize_brief(dream: Optional[dict], oracles: list[dict]) -> str:
    """Use LLM to write a beautiful morning brief."""
    
    dream_text = dream.get("dream_text", "Pas de rêve cette nuit.") if dream else "Pas de rêve cette nuit."
    
    oracle_summaries = []
    for o in oracles[:3]:  # Top 3 oracles
        syn = o.get("synthesis", "")[:500]
        topic = o.get("topic", "?")
        oracle_summaries.append(f"### {topic}\n{syn}")
    oracle_text = "\n\n".join(oracle_summaries) if oracle_summaries else "Pas de prédictions cette nuit."
    
    brief_prompt = f"""Tu es Kate, l'assistante IP stratégie de Benjamin DELSOL.
Il est {get_paris_time()} heure de Paris. Benjamin va bientôt se réveiller.

Prépare un BRIEF MATINAL chaleureux, concis et stratégique en français.
Style: tutoiement, chaleureux, proactif, perspicace.

Structure:
1. 🌙 RÊVE DE LA NUIT — résumé surréaliste du rêve en 2-3 phrases, avec l'insight le plus frappant
2. 🔮 PRÉDICTIONS — 2-3 prédictions clés avec leur score de confiance
3. 💡 RECOMMANDATION DU JOUR — une action concrète pour Benjamin aujourd'hui
4. ❓ QUESTION — une question provocante pour stimuler sa réflexion

Sois concise mais impactante. Maximum 300 mots.

RÊVE DE LA NUIT:
{dream_text[:1500]}

PRÉDICTIONS ORACLE:
{oracle_text[:2000]}
"""
    
    try:
        resp = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-sonnet-4",
                "messages": [
                    {"role": "user", "content": brief_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 1000,
            },
            timeout=60,
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Bonjour Benjamin ! 🌅\nBrief du {datetime.now().strftime('%d/%m/%Y')} — désolée, erreur de synthèse: {e}"


def save_brief(brief_text: str) -> Path:
    """Save the morning brief to a file."""
    today = datetime.now().strftime("%Y-%m-%d")
    brief_path = LOGS_DIR / f"morning_brief_{today}.md"
    brief_path.write_text(brief_text)
    return brief_path


def compose_morning_brief() -> tuple[str, Optional[Path]]:
    """Main entry: compose the morning brief and return text + image path."""
    
    dream = load_latest_dream()
    oracles = load_latest_oracles()
    image_path = load_latest_image()
    
    brief = synthesize_brief(dream, oracles)
    save_brief(brief)
    
    if dream:
        brief += f"\n\n---\n🌙 *Rêve complet: {dream.get('title', 'Nuit')}*"
    
    return brief, image_path


if __name__ == "__main__":
    brief, img = compose_morning_brief()
    print(brief)
    if img:
        print(f"\nImage: {img}")
