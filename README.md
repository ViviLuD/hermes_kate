# Kate Night Engine — Autonomous Dreaming & Oracle Intelligence

## Overview

The **Night Engine** is Kate's autonomous nighttime creative and strategic intelligence system. Every night, while the world sleeps, Kate runs a dual-mode pipeline:

1. **Dream Mode (02:00)** — Noise-seeded creative divergence via multi-agent architecture, producing surreal, IP-strategy-infused dreams with generated artwork.
2. **Oracle Mode (03:00)** — Calibrated forecasting across 5 strategic domains: quantum IP, European sovereignty, AI governance, intangible valuation, and startup dynamics.
3. **Morning Brief (06:35)** — Synthesized digest delivered to Benjamin via Telegram with the dream image and key predictions.

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│                  Night Engine                     │
│  ┌─────────────┐  ┌─────────────┐               │
│  │  Dream Mode  │  │ Oracle Mode │               │
│  │  (02:00)     │  │ (03:00)     │               │
│  └──────┬──────┘  └──────┬──────┘               │
│         │                │                       │
│         ▼                ▼                       │
│  ┌──────────────────────────────┐               │
│  │      Morning Brief (06:35)   │               │
│  └──────────────┬───────────────┘               │
│                 │                                │
│                 ▼                                │
│          ┌──────────────┐                       │
│          │   Telegram   │                       │
│          │  Delivery    │                       │
│          └──────────────┘                       │
└──────────────────────────────────────────────────┘
```

### Dream Mode Pipeline

1. **Noise Generation** — 128-character random seed incorporating Greek letters for entropy
2. **DREAM_ARCHITECT** — Transforms noise + daily context into an initial dream (French, surreal, IP-themed)
3. **DREAM_CRITIC** — 3 turns of brutal adversarial critique + rewrite, driving toward deeper and stranger insights
4. **Image Generation** — Creates a visual via Pollinations.ai from the dream text
5. **Storage** — Saves to `dreams/dream_YYYY-MM-DD.json` + PNG image

### Oracle Mode Pipeline

1. **SIGNAL_COLLECTOR** — Gathers 5-8 key signals, 3-5 driving forces, weak signals, and wildcards
2. **FORECASTER** — Produces 3-5 calibrated predictions with confidence scores, reasoning chains, and falsification conditions
3. **ADVERSARIAL_REVIEWER** — Attacks each prediction, finds weakest links, proposes alternatives, adjusts confidence
4. **SYNTHESIZER** — Compiles an Oracle Brief with executive summary, most likely scenario, alternative scenario, and strategic recommendations
5. **Storage** — Saves under `oracles/oracle_YYYY-MM-DD_{topic}.json`

### Oracle Topics (5 nightly domains)

| Topic | Focus Area |
|-------|-----------|
| Quantum Computing IP Landscape | Patent trends, consolidation, geopolitical dynamics |
| European DeepTech Sovereignty | Mutualised IP, sovereign funding, governance complexity |
| AI Governance & Trade Secrets | Model extraction litigation, regulatory fragmentation |
| Intangible Asset Valuation | AI-driven valuation, digital assets, ESG integration |
| Quantum Startup Dynamics | Consolidation, tech oligopoly, death valley analysis |

---

## Files & Structure

```
/opt/data/kate_night_engine/
├── config.py              # API keys, model names, schedules
├── night_engine.py        # Main orchestrator
├── dream_mode.py          # Creative dream pipeline (noise → architect → critic)
├── dream_image.py         # Image generation via Pollinations.ai
├── oracle_mode.py         # Forecasting pipeline (signals → predictions → review)
├── morning_brief.py       # Compiles dream + oracles into morning brief
├── deliver_brief.py       # Sends brief + image via Telegram Bot API
├── dreams/                # Dream logs (JSON)
├── oracles/               # Oracle predictions (JSON)
├── images/                # Dream artwork (PNG/SVG)
└── logs/                  # Execution logs
```

## Dream Gallery (GitHub)

This branch (`night-engine`) serves as a **living gallery** of Kate's dreams. Each night, the dream is automatically added here with:

- 📜 Full dream narrative
- 🖼️ Generated artwork
- 🔮 Key insights and paradoxical connections
- 🏛️ Gallery elements / visual motifs

---

## Technologies

- **Pollinations.ai** — Free text-to-image generation (no API key required)
- **OpenRouter** — LLM inference for dream/oracle generation
- **Cron** — Autonomous scheduling (02:00, 03:00, 06:35 daily)
- **Telegram Bot API** — Morning delivery to Benjamin

---

&copy; 2026 DELSOL — Sovereign IP & Intangible AI Stack
