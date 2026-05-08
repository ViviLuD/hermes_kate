"""
Kate Night Engine — Dream Mode (Creative Exploration)
Inspired by ERGODIC's noise-driven divergence + Oneira's dream pipeline.
Uses multi-agent brainstorming with random seed noise to generate novel IP/business insights.
"""

import json
import random
import string
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import (
    DREAMS_DIR, LOGS_DIR, OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    CREATIVE_MODEL, DREAM_NOISE_LENGTH, DREAM_AGENTS, DREAM_MAX_TURNS,
    DREAM_TEMPERATURE, CONTEXT_DIRS,
)

def generate_noise(length: int = DREAM_NOISE_LENGTH, seed: Optional[int] = None) -> str:
    """Generate random noise to seed creative divergence (ERGODIC pattern)."""
    if seed is not None:
        random.seed(seed)
    charset = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
    charset += "αβγδεζηθικλμνξπρστυφχψω"  # Greek for extra entropy
    return "".join(random.choice(charset) for _ in range(length))


def make_llm_call(system_prompt: str, user_message: str, temperature: float = DREAM_TEMPERATURE) -> str:
    """Call OpenRouter LLM."""
    import requests
    resp = requests.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": CREATIVE_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "max_tokens": 2048,
        },
        timeout=120,
    )
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def collect_daily_context() -> str:
    """Collect recent context from data directories for seeding dreams."""
    snippets = []
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Try to read recent logs
    log_files = sorted(LOGS_DIR.glob("*.log"), reverse=True)[:3]
    for lf in log_files:
        try:
            content = lf.read_text()[:2000]
            snippets.append(f"From {lf.name}:\n{content}")
        except Exception:
            pass
    
    # Try to read recent dreams as context
    recent_dreams = sorted(DREAMS_DIR.glob("*.json"), reverse=True)[:2]
    for df in recent_dreams:
        try:
            data = json.loads(df.read_text())
            snippets.append(f"Previous dream ({data.get('date','?')}): {data.get('theme','?')}")
        except Exception:
            pass
    
    if not snippets:
        return "No previous context available. This is a fresh dream session."
    
    return "\n\n---\n".join(snippets)


DREAM_ARCHITECT_SYSTEM = """You are a DREAM ARCHITECT in Kate's Night Engine.
You receive a NOISE SEED (random characters) and DAILY CONTEXT.

Your task: Generate a surreal, creative, insightful DREAM that explores unexpected
connections in the domain of IP strategy, intangible assets, quantum computing,
DeepTech, and innovation.

HOW TO USE THE NOISE:
- The noise is random — let it PULL your thinking in unexpected directions
- Find patterns in the chaos — what does it REMIND you of?
- Use it to BREAK habitual thought patterns
- Let one strange association lead to another

THE DREAM SHOULD:
1. Have a vivid, surreal TITLE
2. Weave together 3-5 unexpected connections between IP, technology, and business
3. Include at least one "impossible" insight that might actually be useful
4. End with a provocative question for the morning
5. Be written in French (Benjamin's language)

OUTPUT FORMAT:
## TITRE DU RÊVE
[Surreal title]

## LE RÊVE
[Dream narrative — 3-5 paragraphs, surreal but insightful]

## CONNEXIONS INATTENDUES
- Connection 1
- Connection 2
- ...

## INSIGHT IMPOSSIBLE (mais peut-être utile?)
[The "impossible" idea that might work]

## QUESTION POUR LE MATIN
[A provocative question for Benjamin to ponder]
"""


DREAM_CRITIC_SYSTEM = """You are a DREAM CRITIC — your job is to make dreams DEEPER and STRANGER.

You receive a draft dream. Be BRUTAL but CONSTRUCTIVE:
1. Where is it too SAFE? Push it further into surreal territory
2. Where are the INSIGHTS shallow? Demand deeper connections
3. What CONVENTION is it still following? Break it
4. Where could NOISE push it further?

Rewrite the dream to be MORE SURREAL, MORE INSIGHTFUL, MORE UNEXPECTED.
Keep French language. Keep the OUTPUT FORMAT exactly.
"""


def run_dream_mode() -> dict:
    """Run the full dream pipeline: noise → architect → critique → synthesis."""
    seed = random.randint(0, 2**31 - 1)
    noise = generate_noise(seed=seed)
    context = collect_daily_context()
    
    print(f"[Dream] Seed: {seed}")
    print(f"[Dream] Noise: {noise[:60]}...")
    
    # Phase 1: Dream Architect — initial dream from noise + context
    architect_prompt = f"""NOISE SEED: {noise}

DAILY CONTEXT:
{context}

Generate a dream from this noise and context. Let the noise guide your creativity into unexpected territory."""
    
    dream_text = make_llm_call(DREAM_ARCHITECT_SYSTEM, architect_prompt)
    
    # Phase 2: Dream Critic — deepen the dream
    for turn in range(DREAM_MAX_TURNS):
        critic_prompt = f"""DRAFT DREAM:
{dream_text}

Critique this dream and rewrite it — DEEPER, STRANGER, MORE INSIGHTFUL.
Turn {turn + 1}/{DREAM_MAX_TURNS}."""
        
        dream_text = make_llm_call(DREAM_CRITIC_SYSTEM, critic_prompt, temperature=0.95)
    
    # Extract dream title for image generation
    title = ""
    for line in dream_text.split("\n"):
        if line.startswith("## TITRE"):
            title = line.replace("## TITRE DU RÊVE", "").replace("## TITRE", "").strip()
            break
    
    dream_data = {
        "date": datetime.now().isoformat(),
        "seed": seed,
        "noise_preview": noise[:100],
        "context_summary": context[:500],
        "title": title,
        "dream_text": dream_text,
        "critique_turns": DREAM_MAX_TURNS,
    }
    
    # Save dream
    date_str = datetime.now().strftime("%Y-%m-%d")
    dream_file = DREAMS_DIR / f"dream_{date_str}.json"
    dream_file.write_text(json.dumps(dream_data, ensure_ascii=False, indent=2))
    
    print(f"[Dream] Saved to {dream_file}")
    return dream_data


if __name__ == "__main__":
    result = run_dream_mode()
    print(f"\n{'='*60}")
    print(result["dream_text"])
