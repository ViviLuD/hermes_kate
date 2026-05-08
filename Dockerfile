# Hermes Kate — Dockerfile
# Architecture intégrée : Agent Core + Gateway + Voice + MCPs + Night Engine
# Base: Python 3.11 + Node.js 20 (Playwright, MCP servers, suno-api)

FROM nikolaik/python-nodejs:python3.11-nodejs20

LABEL org.opencontainers.image.title="Hermes Kate"
LABEL org.opencontainers.image.description="DELSOL AI — Sovereign IP & Intangible AI Assistant"
LABEL org.opencontainers.image.authors="Benjamin DELSOL <benjamin@delsol.ai>"

# ── System dependencies ──────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Audio / TTS / STT
    ffmpeg \
    libportaudio2 \
    portaudio19-dev \
    # Build tools
    build-essential \
    cmake \
    pkg-config \
    # Git + SSH
    git \
    openssh-client \
    # Net tools (watchdog, debugging)
    curl \
    wget \
    netcat-openbsd \
    dnsutils \
    # ttyd (web terminal)
    ttyd \
    # gosu (privilege dropping)
    gosu \
    # PDF / image processing
    poppler-utils \
    libopenblas-dev \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Create hermes user ───────────────────────────────────────────
RUN groupadd --system hermes && \
    useradd --system --create-home --gid hermes --shell /bin/bash hermes

# ── Install directory structure ──────────────────────────────────
ENV HERMES_INSTALL=/opt/hermes
ENV HERMES_DATA=/opt/data
ENV HERMES_VENV=/opt/hermes/.venv

RUN mkdir -p ${HERMES_INSTALL} ${HERMES_DATA} && \
    chown -R hermes:hermes ${HERMES_INSTALL} ${HERMES_DATA}

# ── Python virtual environment ───────────────────────────────────
WORKDIR ${HERMES_INSTALL}
RUN python3 -m venv ${HERMES_VENV}
ENV PATH="${HERMES_VENV}/bin:${PATH}"

# ── Install Python dependencies ──────────────────────────────────
# Core
RUN pip install --no-cache-dir \
    openai \
    anthropic \
    google-genai \
    mistralai \
    tiktoken \
    transformers \
    torch --index-url https://download.pytorch.org/whl/cpu \
    tokenizers

# Agent & MCP
RUN pip install --no-cache-dir \
    mcp>=1.27.0 \
    agent-client-protocol \
    chromadb \
    mempalace>=3.3.0 \
    nano-vectordb \
    lightrag-hku \
    honcho-ai

# Voice & Audio
RUN pip install --no-cache-dir \
    faster-whisper \
    edge-tts \
    elevenlabs \
    sounddevice \
    librosa \
    pydub \
    SpeechRecognition

# Messaging
RUN pip install --no-cache-dir \
    python-telegram-bot \
    discord.py \
    slack_bolt \
    lark-oapi

# Web & Infrastructure
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    starlette \
    aiohttp \
    httpx \
    websockets \
    firecrawl-py

# Data & Utils
RUN pip install --no-cache-dir \
    pandas \
    numpy \
    scikit-learn \
    scipy \
    rich \
    pyyaml \
    pydantic \
    croniter \
    tqdm \
    python-dotenv \
    click \
    jinja2

# PDF & Documents
RUN pip install --no-cache-dir \
    weasyprint \
    pdfplumber \
    python-pptx \
    python-docx \
    markdown \
    PyPDF2

# ── Install Hermes Agent ─────────────────────────────────────────
# Clone and install in editable mode
RUN git clone https://github.com/ViviLuD/hermes_kate.git /tmp/hermes_kate && \
    cd /tmp/hermes_kate && \
    # Copy source files
    cp -r hermes_cli hermes_agent gateway agent acp_adapter acp_registry skills scripts tools ${HERMES_INSTALL}/ && \
    cp pyproject.toml requirements.txt setup-hermes.sh ${HERMES_INSTALL}/ && \
    # Install hermes package
    cd ${HERMES_INSTALL} && \
    pip install -e . && \
    # Cleanup
    rm -rf /tmp/hermes_kate

# ── Install Playwright (browser automation) ──────────────────────
RUN npx playwright install --with-deps chromium 2>/dev/null || true

# ── Kate companion services ──────────────────────────────────────
# Voice Interface
RUN mkdir -p ${HERMES_DATA}/voice_interface
COPY voice_interface/ ${HERMES_DATA}/voice_interface/

# Kate Evolution (S3/MetaCog middleware)
RUN mkdir -p ${HERMES_DATA}/kate_evolution
COPY kate_evolution/ ${HERMES_DATA}/kate_evolution/

# Night Engine
RUN mkdir -p ${HERMES_DATA}/kate_night_engine
COPY kate_night_engine/ ${HERMES_DATA}/kate_night_engine/

# Scripts & Watchdog
RUN mkdir -p ${HERMES_DATA}/scripts
COPY scripts/ ${HERMES_DATA}/scripts/

# ── Config templates ─────────────────────────────────────────────
COPY docker/SOUL.md ${HERMES_INSTALL}/docker/SOUL.md
COPY docker/entrypoint.sh /entrypoint.sh
COPY config.yaml.example ${HERMES_INSTALL}/config.yaml.example
COPY .env.example ${HERMES_INSTALL}/.env.example

RUN chmod +x /entrypoint.sh && \
    chown -R hermes:hermes ${HERMES_INSTALL} ${HERMES_DATA}

# ── Volumes ──────────────────────────────────────────────────────
VOLUME ["${HERMES_DATA}/mempalace", "${HERMES_DATA}/sessions", "${HERMES_DATA}/logs"]

# ── Runtime ──────────────────────────────────────────────────────
EXPOSE 8765 8766 4860 8899

USER hermes
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gateway", "run"]
