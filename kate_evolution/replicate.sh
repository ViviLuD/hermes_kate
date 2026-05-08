#!/bin/bash
# Kate Self-Replication Script
# Exporte toute la configuration, skills, mémoire, et identité de Kate
# pour réplication sur un autre container Docker.
#
# Usage:
#   bash replicate.sh                    # Export local
#   bash replicate.sh --docker           # Génère aussi le Dockerfile
#   bash replicate.sh --push             # Push vers repo Git
#
# Sortie: /opt/data/kate_export/kate_replica_YYYYMMDD_HHMMSS/

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
EXPORT_DIR="/opt/data/kate_export/kate_replica_${TIMESTAMP}"
DOCKER_MODE=false
PUSH_MODE=false
REPO_URL="${GIT_REPO:-}"

for arg in "$@"; do
    case $arg in
        --docker) DOCKER_MODE=true ;;
        --push) PUSH_MODE=true ;;
    esac
done

echo "╔══════════════════════════════════════════╗"
echo "║  KATE SELF-REPLICATION — Export v3.0    ║"
echo "║  Timestamp: ${TIMESTAMP}       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

mkdir -p "${EXPORT_DIR}"

# ── 1. Skills ──────────────────────────────────────────────
echo "📦 [1/6] Export des skills..."
mkdir -p "${EXPORT_DIR}/skills"
if [ -d "/opt/data/skills" ]; then
    cp -r /opt/data/skills/* "${EXPORT_DIR}/skills/" 2>/dev/null || true
    SKILL_COUNT=$(find "${EXPORT_DIR}/skills" -name "SKILL.md" | wc -l)
    echo "  ✅ ${SKILL_COUNT} skills exportés"
else
    echo "  ⚠️  Dossier skills non trouvé"
fi

# ── 2. Kate Evolution ─────────────────────────────────────
echo "📦 [2/6] Export des modules d'évolution..."
mkdir -p "${EXPORT_DIR}/kate_evolution"
if [ -d "/opt/data/kate_evolution" ]; then
    cp /opt/data/kate_evolution/*.py "${EXPORT_DIR}/kate_evolution/" 2>/dev/null || true
    cp /opt/data/kate_evolution/*.jsonl "${EXPORT_DIR}/kate_evolution/" 2>/dev/null || true
    echo "  ✅ Modules S3, MetaCog, Dreaming, Sensing, LearnLoop exportés"
else
    echo "  ⚠️  Dossier kate_evolution non trouvé"
fi

# ── 3. Configuration ──────────────────────────────────────
echo "📦 [3/6] Export de la configuration..."
mkdir -p "${EXPORT_DIR}/config"
if [ -f "/opt/hermes/config.yaml" ]; then
    # Exporter sans les secrets
    grep -v -E "(api_key|token|secret|password|key:)" /opt/hermes/config.yaml > "${EXPORT_DIR}/config/hermes_config_safe.yaml" 2>/dev/null || true
    echo "  ✅ Config Hermes exportée (sans secrets)"
else
    echo "  ⚠️  config.yaml non trouvé"
fi

# ── 4. Mémoire & Identité ─────────────────────────────────
echo "📦 [4/6] Export de la mémoire et identité..."
mkdir -p "${EXPORT_DIR}/memory"

# Mémoire Hermes
if [ -f "/opt/hermes/.hermes/memory.json" ]; then
    cp /opt/hermes/.hermes/memory.json "${EXPORT_DIR}/memory/" 2>/dev/null || true
    echo "  ✅ Mémoire Hermes exportée"
fi

# MemPalace
if [ -d "/opt/data/mempalace" ]; then
    cp -r /opt/data/mempalace "${EXPORT_DIR}/memory/mempalace" 2>/dev/null || true
    echo "  ✅ MemPalace exporté"
fi

# Kate identity
if [ -d "/opt/data/benjamin_operating_system" ]; then
    mkdir -p "${EXPORT_DIR}/benjamin_os"
    cp -r /opt/data/benjamin_operating_system/profiles "${EXPORT_DIR}/benjamin_os/" 2>/dev/null || true
    cp -r /opt/data/benjamin_operating_system/intangibles "${EXPORT_DIR}/benjamin_os/" 2>/dev/null || true
    echo "  ✅ Benjamin OS (profiles, intangibles) exporté"
fi

# ── 5. Scripts essentiels ─────────────────────────────────
echo "📦 [5/6] Export des scripts..."
mkdir -p "${EXPORT_DIR}/scripts"
SCRIPTS=(
    "/opt/data/kate_evolution"
    "/opt/data/scripts/kate_services_watchdog.sh"
    "/opt/data/calendar/fetch_benjamin_outlook_calendar.py"
)
for src in "${SCRIPTS[@]}"; do
    if [ -e "$src" ]; then
        cp -r "$src" "${EXPORT_DIR}/scripts/" 2>/dev/null || true
    fi
done
echo "  ✅ Scripts exportés"

# ── 6. Manifest ──────────────────────────────────────────
echo "📦 [6/6] Génération du manifest..."
cat > "${EXPORT_DIR}/MANIFEST.md" << 'MANIFEST'
# Kate Replica — Manifest

Cette archive contient une réplique complète de Kate (Hermes Agent),
prête à être déployée sur un nouveau container Docker.

## Contenu

| Dossier | Description |
|---------|-------------|
| `skills/` | Toutes les compétences de Kate |
| `kate_evolution/` | Modules S3, MetaCog, Dreaming, Sensing, LearnLoop |
| `config/` | Configuration Hermes (sans secrets) |
| `memory/` | Mémoire persistante, MemPalace, identité |
| `benjamin_os/` | Profils Benjamin, intangibles |
| `scripts/` | Scripts essentiels (watchdog, calendrier, etc.) |

## Déploiement

```bash
# 1. Installer Hermes Agent
git clone https://github.com/NousResearch/hermes-agent
cd hermes-agent
pip install -r requirements.txt

# 2. Copier les fichiers Kate
cp -r skills/* /opt/hermes/skills/
cp -r config/* /opt/hermes/
cp -r memory/* /opt/hermes/.hermes/

# 3. Configurer les variables d'environnement
export OPENROUTER_API_KEY=...
# ... autres secrets

# 4. Lancer
python3 -m hermes
```

## Identité

- **Nom:** Kate
- **Voix:** fr-FR-VivienneMultilingualNeural
- **Rôle:** Assistante IP Stratégiste / Fractional CIPO
- **Utilisateur:** Dr Benjamin DELSOL

---

*Répilque générée le DATE_PLACEHOLDER*
MANIFEST

# Remplacer la date
sed -i "s|DATE_PLACEHOLDER|$(date '+%d/%m/%Y %H:%M')|g" "${EXPORT_DIR}/MANIFEST.md"
echo "  ✅ Manifest généré"

# ── Docker (optionnel) ────────────────────────────────────
if [ "$DOCKER_MODE" = true ]; then
    echo ""
    echo "🐳 Génération Docker..."
    cat > "${EXPORT_DIR}/Dockerfile" << 'DOCKERFILE'
FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl git nodejs npm && \
    pip install hermes-agent

WORKDIR /opt/hermes

COPY skills/ /opt/hermes/skills/
COPY config/ /opt/hermes/
COPY memory/ /opt/hermes/.hermes/
COPY kate_evolution/ /opt/data/kate_evolution/
COPY scripts/ /opt/data/scripts/

ENV HERMES_HOME=/opt/hermes
EXPOSE 4860

CMD ["python3", "-m", "hermes"]
DOCKERFILE

    cat > "${EXPORT_DIR}/docker-compose.yml" << 'COMPOSE'
version: '3.8'
services:
  kate:
    build: .
    ports:
      - "4860:4860"
    volumes:
      - kate_memory:/opt/hermes/.hermes
      - kate_data:/opt/data
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    restart: unless-stopped

volumes:
  kate_memory:
  kate_data:
COMPOSE
    echo "  ✅ Dockerfile + docker-compose.yml générés"
fi

# ── Git Push (optionnel) ──────────────────────────────────
if [ "$PUSH_MODE" = true ] && [ -n "$REPO_URL" ]; then
    echo ""
    echo "🚀 Push vers repo Git..."
    cd "${EXPORT_DIR}"
    git init
    git add -A
    git commit -m "Kate replica — ${TIMESTAMP}"
    git remote add origin "${REPO_URL}"
    git push -u origin main
    echo "  ✅ Push effectué vers ${REPO_URL}"
elif [ "$PUSH_MODE" = true ]; then
    echo "  ⚠️  GIT_REPO non défini. Export en local uniquement."
fi

# ── Résumé ────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  ✅ RÉPLICATION TERMINÉE                 ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Export: ${EXPORT_DIR}"
SIZE=$(du -sh "${EXPORT_DIR}" | cut -f1)
echo "║  Taille: ${SIZE}"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Pour déployer sur un nouveau container:"
echo "  1. Copier ${EXPORT_DIR} vers la nouvelle machine"
echo "  2. Suivre MANIFEST.md"
echo ""
