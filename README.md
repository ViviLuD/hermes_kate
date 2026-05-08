# Hermes Kate 🧠

**DELSOL AI — Sovereign IP & Intangible AI Assistant**

Architecture de l'assistant IA de Dr Benjamin DELSOL, spécialisé en stratégie de propriété intellectuelle, actifs intangibles, DeepTech, et souveraineté technologique.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   HERMES KATE STACK                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  HERMES CORE │  │    VOICE     │  │  MIDDLEWARE  │  │
│  │  Gateway +   │  │  Interface   │  │  S3 / Meta-  │  │
│  │  CLI + Agent │  │  WS :8765    │  │  Cog :8766   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                  │          │
│  ┌──────┴─────────────────┴──────────────────┴───────┐  │
│  │              MCP SERVERS (7 actifs)                │  │
│  │  MemPalace │ Ruflo │ Chart │ Yahoo │ World │ USPTO │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │             NIGHT ENGINE (autonome)               │   │
│  │  02:00 Dream │ 03:00 Oracle │ 06:35 Briefing     │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  MemPalace │ LightRAG │ ChromaDB │ state.db      │   │
│  │              MEMORY LAYER                         │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Telegram │ Discord │ CLI │ Voice │ Web Terminal  │   │
│  │              ACCESS POINTS                        │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| **Hermes Core** | — | Agent runtime, gateway (Telegram/Discord/CLI), smart model routing |
| **Voice Interface** | `:8765` | WebSocket + REST, STT (Whisper), TTS (Vivienne edge-tts), HeyGen avatars |
| **S3/MetaCog Middleware** | `:8766` | Attention scoring, metacognition, graceful degradation |
| **Night Engine** | — | Cycle nocturne autonome : rêves (02h), oracles (03h), briefings (06h35) |
| **Cloudflare Tunnel** | — | Exposition publique sans ouvrir les ports (optionnel, via profile `tunnel`) |

### MCP Servers

| MCP Server | Provider | Rôle |
|-----------|----------|------|
| **MemPalace** | `/opt/data/mempalace` | Mémoire vectorielle (ChromaDB), Knowledge Graph, AAAK compression |
| **Ruflo** | NPM `ruflo@latest` | Multi-agent orchestration, swarm topology, task claims, browser automation |
| **USPTO Patent** | Python (patent-mcp-server) | Recherche brevets US (PPUBS), ODP, PTAB, litiges |
| **World Intel** | Python (world-intel-mcp) | 113+ tools : marchés, conflits, cyber, climat, espace, supply chain |
| **Yahoo Finance** | NPM `yahoo-finance-mcp` | Quotes, historiques, fondamentaux, news financières |
| **AntV Chart** | NPM `@antv/mcp-server-chart` | Génération de graphiques (bar, line, pie, radar, scatter, etc.) |
| **CompanyScope** | NPM `companyscope-mcp` | Profils entreprises, brevets, news, tech stack, finances |

### Memory Architecture

```
┌─────────────────────────────────────────────────────┐
│ Couche 1: MemPalace Index (compact, ~90% token save)│
│ Couche 2: Timeline Context (chronologique)           │
│ Couche 3: Full Drawer (verbatim, via MCP)            │
├─────────────────────────────────────────────────────┤
│ ChromaDB  │  SQLite KG  │  LightRAG (284 nodes)     │
│ HNSW embedding index │ Strategic GraphRAG reasoning │
└─────────────────────────────────────────────────────┘
```

---

## Déploiement Rapide

### Prérequis

- Docker 24+ & Docker Compose v2
- 4 Go RAM minimum, 20 Go disque
- Clés API : OpenRouter (obligatoire) + optionnelles (OpenAI, Anthropic, Telegram, ElevenLabs)

### Installation (5 minutes)

```bash
# 1. Cloner
git clone https://github.com/ViviLuD/hermes_kate.git
cd hermes_kate

# 2. Configurer
cp .env.example .env
# → Éditer .env avec vos clés API

cp config.yaml.example /opt/data/config.yaml 2>/dev/null || cp config.yaml.example ./data/config.yaml
# → Ajuster si nécessaire

# 3. Créer le dossier de données
mkdir -p data/{mempalace,sessions,logs,skills,audio_cache}

# 4. Lancer
docker compose up -d

# 5. Vérifier
docker compose logs -f hermes
docker compose ps
```

### Vérification

```bash
# Health check
curl http://localhost:8765/health

# Terminal Web (Hermes Desktop)
# → http://localhost:4860 (user: DELSOL-AI-HERMES)

# Logs
docker compose logs -f hermes voice middleware night-engine
```

### Avec Cloudflare Tunnel (accès public)

```bash
# Renseigner CLOUDFLARE_TUNNEL_TOKEN dans .env
docker compose --profile tunnel up -d cloudflared
```

---

## Structure du Repo

```
hermes_kate/
├── Dockerfile                  # Build multi-service
├── docker-compose.yml          # Orchestration
├── config.yaml.example         # Configuration Hermes
├── .env.example                # Variables d'environnement
├── docker/
│   ├── entrypoint.sh           # Bootstrap + privilege dropping
│   └── SOUL.md                 # Identité Kate
├── skills/                     # Skills modulaires
├── scripts/                    # Utilitaires (watchdog, health, index)
├── voice_interface/            # Interface vocale Kate
├── kate_evolution/             # S3/MetaCog middleware + scheduler
├── kate_night_engine/          # Moteur de nuit autonome
└── data/                       # Volume Docker (créé au runtime)
```

---

## Smart Model Routing

Hermes route automatiquement les tâches vers le meilleur modèle :

| Type de tâche | Modèle | Coût |
|--------------|--------|------|
| Simple / rapide | DeepSeek V4 Flash | $ |
| Code / analyse | DeepSeek V4 Pro | $$ |
| Stratégique IP / brevet | Claude Sonnet 4.6 | $$$ |
| Génération texte IP | GPT-5.5 / OpenAI Codex | $$$ |

---

## Night Engine

Cycle nocturne autonome :

| Heure (Paris) | Phase | Description |
|---------------|-------|-------------|
| 02:00 | 🌙 Dream | Génération créative onirique (Pollinations.ai) |
| 03:00 | 🔮 Oracle | 5 prédictions stratégiques (IP, quantum, IA, deeptech) |
| 06:25 | 📇 Registry | Mise à jour galerie des rêves |
| 06:35 | 📋 Briefing | Synthèse + recommandation + livraison Telegram |
| 06:40 | 📤 GitHub Push | Publication automatique sur le repo |

---

## Maintenance

```bash
# Mise à jour
git pull
docker compose build --no-cache
docker compose up -d

# Sauvegarde
tar -czf hermes-backup-$(date +%Y%m%d).tar.gz data/

# Restauration
tar -xzf hermes-backup-YYYYMMDD.tar.gz
docker compose down && docker compose up -d

# Nettoyage
docker compose down
docker system prune -f
```

---

## FAQ

**Q: Pourquoi tant de MCP servers ?**
R: Chaque MCP est un domaine d'expertise spécialisé. Ils tournent en parallèle avec chargement à la demande via le gateway Hermes. L'overhead mémoire est ~100 Mo par MCP.

**Q: Puis-je désactiver certains services ?**
R: Oui, commentez les services dans `docker-compose.yml`. Minimum viable : `hermes` seul.

**Q: Le state.db fait 147 Mo, c'est normal ?**
R: Oui, il contient l'historique des sessions, les checkpoints, et les hooks d'apprentissage. Purge automatique configurable dans `config.yaml`.

---

## Écosystème & Dépendances

### Repos GitHub utilisés

| Repo | Rôle |
|------|------|
| [ViviLuD/hermes_kate](https://github.com/ViviLuD/hermes_kate) | Déploiement Kate : Docker, configs, voice, night engine, scripts |
| [marc-shade/world-intel-mcp](https://github.com/marc-shade/world-intel-mcp) | MCP 113 tools : géopolitique, marchés, conflits, cyber, climat |
| [Stewyboy1990/companyscope-mcp](https://github.com/Stewyboy1990/companyscope-mcp) | MCP profils entreprises, brevets, news, tech stack |
| [Cyreslab-AI/crunchbase-mcp-server](https://github.com/Cyreslab-AI/crunchbase-mcp-server) | MCP données Crunchbase |
| [assafelovic/gptr-mcp](https://github.com/assafelovic/gptr-mcp) | MCP GPT Researcher (recherche web autonome) |
| [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | GPT Researcher full version |
| [eliasbiondo/linkedin-mcp-server](https://github.com/eliasbiondo/linkedin-mcp-server) | MCP accès données LinkedIn |
| [wanshuiyin/Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) | Aris Night — inspiration pour le Night Engine |
| [ruvnet/claude-flow](https://github.com/ruvnet/claude-flow) | Ruflo — orchestration multi-agent Claude Code |
| [openswarm-ai/openswarm](https://github.com/openswarm-ai/openswarm) | Framework swarm agentique distribué |
| [RobThePCGuy/Claude-Patent-Creator](https://github.com/RobThePCGuy/Claude-Patent-Creator) | Rédaction brevets par IA (exploré, pas en production) |
| [laguerric/Oneira](https://github.com/laguerric/Oneira) | Agent IA autonome (exploré) |
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | Agents de trading multi-actifs (exploré) |
| [SOCIALPINE/ergodic-pipeline](https://github.com/SOCIALPINE/ergodic-pipeline) | Pipeline de données ergodiques (exploré) |

### Packages Python (pip)

| Package | Version | Rôle |
|---------|---------|------|
| `hermes-agent` | latest (Nous Research, MIT) | Framework IA auto-améliorant |
| `mempalace-mcp` | 3.3.4 | Mémoire persistante + Knowledge Graph vectoriel (HNSW) |
| `lightrag-hku` | latest | GraphRAG stratégique relationnel |
| `edge-tts` | ≥7.2.7 | TTS gratuit — voix Fr-FR-Vivienne |

### Packages Node.js (npm global)

| Package | Rôle |
|---------|------|
| `@anthropic-ai/claude-code` | Claude Code CLI |
| `ruflo` | Orchestration multi-agent, swarm, mémoire vectorielle |
| `@marp-team/marp-cli` | Présentations Markdown → PDF/PPTX |
| `@slidev/cli` | Présentations interactives |
| `pptxgenjs` | Génération PPTX programmatique |
| `@antv/mcp-server-chart` | MCP 27 types de graphiques |
| `yahoo-finance-mcp` | MCP données financières Yahoo |
| `@anthropic/mcp-server-patent` | MCP recherche brevets US (PPUBS, ODP, PTAB) |

---

## Licence

Propriétaire — DELSOL AI. Usage interne et clients autorisés.

## Contact

Dr Benjamin DELSOL — [delsol.ai](https://delsol.ai)
