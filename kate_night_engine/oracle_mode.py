"""
Kate Night Engine — Oracle Mode (Predictive Extrapolation)
Inspired by MIRAI's forecasting methodology and superforecasting principles.
Uses multi-agent reasoning chains with calibrated confidence scoring.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import (
    ORACLES_DIR, LOGS_DIR, OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    ANALYTIC_MODEL, ORACLE_TOPICS, ORACLE_TEMPERATURE,
    CONTEXT_DIRS,
)


def make_llm_call(system_prompt: str, user_message: str) -> str:
    """Call OpenRouter LLM for analytical work."""
    import requests
    resp = requests.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": ANALYTIC_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": ORACLE_TEMPERATURE,
            "max_tokens": 2048,
        },
        timeout=120,
    )
    data = resp.json()
    return data["choices"][0]["message"]["content"]


SIGNAL_COLLECTOR_SYSTEM = """You are a SIGNAL COLLECTOR in Kate's Oracle engine.
Your job: identify key signals and trends that will shape the future of a given domain.

For the assigned TOPIC, provide:
1. KEY SIGNALS (5-8 emerging indicators)
2. DRIVING FORCES (3-5 structural forces)
3. WEAK SIGNALS (2-3 early indicators barely visible now)
4. WILDCARDS (1-2 low-probability, high-impact events)

Be SPECIFIC. Cite real technologies, companies, regulations, market data.
Write in French.

OUTPUT FORMAT:
## SIGNAUX CLÉS
[Numbered list with descriptions]

## FORCES MOTRICES
[Numbered list with analysis]

## SIGNAUX FAIBLES
[Numbered list]

## WILDCARDS
[Numbered list]
"""


FORECASTER_SYSTEM = """You are a FORECASTER in Kate's Oracle engine.
You receive SIGNAL ANALYSIS and must make CALIBRATED PREDICTIONS.

Follow superforecasting principles:
1. Break the question into smaller parts
2. Use base rates when available
3. Update beliefs incrementally
4. Express uncertainty with confidence scores (0.0-1.0)

For each prediction:
- State the PREDICTION clearly with a 12-24 month time horizon
- Give a CONFIDENCE score (0.0-1.0)
- Explain your REASONING CHAIN
- Identify what would PROVE YOU WRONG (falsification condition)

OUTPUT FORMAT:
## PRÉDICTION 1: [Statement]
- Confiance: [0.0-1.0]
- Horizon: [timeframe]
- Chaîne de raisonnement: [3-5 step reasoning]
- Condition de falsification: [what would prove this wrong]

## PRÉDICTION 2: [...]
[etc — 3-5 predictions per topic]
"""


ADVERSARIAL_REVIEWER_SYSTEM = """You are an ADVERSARIAL REVIEWER in Kate's Oracle engine.
Your job: ATTACK the forecaster's predictions.

For each prediction:
1. Find the WEAKEST LINK in the reasoning chain
2. Propose an ALTERNATIVE SCENARIO that leads to the opposite outcome
3. Identify CONFIRMATION BIAS — is the forecaster seeing what they want to see?
4. Adjust the CONFIDENCE score DOWN if warranted

Be BRUTAL. Better to be wrong and calibrated than confident and wrong.

OUTPUT FORMAT:
## ATTAQUE PRÉDICTION 1
- Maillon faible: [analysis]
- Scénario alternatif: [opposite outcome scenario]
- Biais potentiel: [analysis]
- Confiance ajustée: [new score if applicable, with justification]

[Repeat for each prediction]
"""


SYNTHESIZER_SYSTEM = """You are the ORACLE SYNTHESIZER.
You have:
1. SIGNAL ANALYSIS
2. CALIBRATED PREDICTIONS
3. ADVERSARIAL REVIEW

Synthesize into a COHERENT ORACLE BRIEF.

OUTPUT FORMAT:
## SYNTHÈSE ORACLE: [Topic]
## RÉSUMÉ EXÉCUTIF (3-4 phrases)
## PRÉDICTIONS CLÉS (with adjusted confidence)
## SCÉNARIO LE PLUS PROBABLE
## SCÉNARIO ALTERNATIF (si les wildcards se déclenchent)
## RECOMMANDATIONS STRATÉGIQUES POUR BENJAMIN
## INDICATEURS À SURVEILLER
"""


def run_oracle_mode(topic: str) -> dict:
    """Run the full oracle pipeline for one topic."""
    print(f"\n[Oracle] Topic: {topic}")
    
    # Phase 1: Signal Collection
    signal_prompt = f"""TOPIC: {topic}

Today's date: {datetime.now().strftime('%Y-%m-%d')}

Analyze the signals, trends, and forces shaping this domain."""
    signals = make_llm_call(SIGNAL_COLLECTOR_SYSTEM, signal_prompt)
    
    # Phase 2: Forecasting
    forecast_prompt = f"""TOPIC: {topic}

SIGNAL ANALYSIS:
{signals}

Based on these signals, make 3-5 calibrated predictions with 12-24 month horizons."""
    forecasts = make_llm_call(FORECASTER_SYSTEM, forecast_prompt)
    
    # Phase 3: Adversarial Review (MIRAI-style cross-check)
    review_prompt = f"""ORIGINAL TOPIC: {topic}

FORECASTS TO ATTACK:
{forecasts}

Attack each prediction. Find weaknesses, propose alternatives, spot biases."""
    review = make_llm_call(ADVERSARIAL_REVIEWER_SYSTEM, review_prompt)
    
    # Phase 4: Synthesis
    synthesis_prompt = f"""TOPIC: {topic}

SIGNALS: {signals[:1000]}

FORECASTS: {forecasts[:1000]}

ADVERSARIAL REVIEW: {review[:1000]}

Synthesize into a final Oracle Brief."""
    synthesis = make_llm_call(SYNTHESIZER_SYSTEM, synthesis_prompt)
    
    oracle_data = {
        "date": datetime.now().isoformat(),
        "topic": topic,
        "signals": signals,
        "forecasts": forecasts,
        "adversarial_review": review,
        "synthesis": synthesis,
    }
    
    # Save
    slug = topic.lower().replace(" ", "_")[:40]
    date_str = datetime.now().strftime("%Y-%m-%d")
    oracle_file = ORACLES_DIR / f"oracle_{date_str}_{slug}.json"
    oracle_file.write_text(json.dumps(oracle_data, ensure_ascii=False, indent=2))
    
    print(f"[Oracle] Saved to {oracle_file}")
    return oracle_data


def run_all_oracles() -> list[dict]:
    """Run oracle mode for all configured topics."""
    results = []
    for topic in ORACLE_TOPICS:
        try:
            result = run_oracle_mode(topic)
            results.append(result)
            time.sleep(2)  # Rate limit protection
        except Exception as e:
            print(f"[Oracle] Error on '{topic}': {e}")
            results.append({"topic": topic, "error": str(e)})
    return results


if __name__ == "__main__":
    results = run_all_oracles()
    print(f"\n[Oracle] Completed {len(results)} topics")
