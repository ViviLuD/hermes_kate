#!/usr/bin/env python3
"""
Kate Voice Interface — Serveur WebSocket
Conversation vocale fluide : micro → STT → émotion → LLM → TTS Vivienne
Option 3 : mémoire Hermes injectée + conversations sauvegardées dans state.db
"""

import asyncio
import atexit
import base64
import fcntl
import json
import logging
import mimetypes
import os
import pty
import re
import shutil
import signal
import sqlite3
import struct
import sys
import tempfile
import termios
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, quote

import httpx

# Charger les variables d'environnement depuis /opt/data/.env
_env_file = Path("/opt/data/.env")
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# Ajouter Hermes au path
sys.path.insert(0, "/opt/hermes")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kate-voice")

app = FastAPI(title="Kate Voice Interface")

# ---------------------------------------------------------------------------
# Mémoire Hermes — lecture depuis state.db
# ---------------------------------------------------------------------------

STATE_DB = Path("/opt/data/state.db")
MEMORY_DIR = Path("/opt/data/memories")

def load_hermes_memory() -> dict:
    """Charge la mémoire persistante de Hermes (notes + profil utilisateur)."""
    memory = {"notes": "", "user_profile": ""}
    try:
        notes_file = MEMORY_DIR / "MEMORY.md"
        user_file  = MEMORY_DIR / "USER.md"
        if notes_file.exists():
            memory["notes"] = notes_file.read_text(encoding="utf-8").strip()
        if user_file.exists():
            memory["user_profile"] = user_file.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.debug("Lecture mémoire Hermes: %s", e)
    return memory


def sync_memory_to_mempalace():
    """Called at startup: read Hermes persistent memory files and upsert
    each logical entry into Chroma so the voice/gateway can retrieve
    Benjamin's corrections and preferences without depending on the
    operator remembering to sync manually."""
    try:
        db_path = Path('/opt/data/mempalace/chroma.sqlite3')
        if not db_path.exists():
            logger.debug("MemPalace sqlite3 absent, skipping memory sync")
            return

        # Collect entries from both memory files, split by paragraph double-newline.
        entries = []
        for mem_file in (MEMORY_DIR / "MEMORY.md", MEMORY_DIR / "USER.md"):
            if not mem_file.exists():
                continue
            raw = mem_file.read_text(encoding='utf-8', errors='ignore').strip()
            # Hermes memory entries are separated by "§" on its own line.
            # Split on line-§-line to get individual entries.
            for para in re.split(r'\n§\s*\n', raw):
                para = para.strip()
                if len(para) < 40:
                    continue
                entries.append({
                    'source': mem_file.name,
                    'text': para,
                })

        if not entries:
            return

        import chromadb
        client = chromadb.PersistentClient(path=str(Path('/opt/data/mempalace')))
        try:
            col = client.get_collection('mempalace_drawers')
        except Exception:
            col = client.create_collection('mempalace_drawers')
            logger.info("Created mempalace_drawers collection for memory sync")

        now_iso = datetime.utcnow().isoformat() + 'Z'
        for i, entry in enumerate(entries):
            doc_id = f"hermes_memory_{entry['source'].replace('.md','')}_{i:04d}"
            doc_text = f"[Hermes persistent memory | {entry['source']}]\n{entry['text']}"
            meta = {
                'wing': 'benjamin_delsol',
                'room': 'personal',
                'source': 'hermes_memory_sync',
                'source_file': entry['source'],
                'kind': 'hermes_memory_sync',
                'topic': 'benjamin_context',
                'synced_at': now_iso,
            }
            try:
                col.upsert(ids=[doc_id], documents=[doc_text], metadatas=[meta])
            except Exception:
                try:
                    col.delete(ids=[doc_id])
                except Exception:
                    pass
                col.add(ids=[doc_id], documents=[doc_text], metadatas=[meta])

        logger.info("MemPalace memory sync: %d entries upserted from %d files",
                     len(entries),
                     len({e['source'] for e in entries}))
    except Exception as e:
        logger.warning("MemPalace memory sync skipped: %s", e)


def _extract_keywords(text: str, min_len: int = 4) -> list[str]:
    """Extract clean lowercase keywords >= min_len chars, with dedup order preserved."""
    out = []
    seen = set()
    for tok in text.replace('—', ' ').replace('-', ' ').replace('/', ' ').split():
        tok = ''.join(ch for ch in tok if ch.isalnum() or ch in '_@.')
        if len(tok) >= min_len and tok.lower() not in seen:
            seen.add(tok.lower())
            out.append(tok.lower())
    return out


def _sqlite_fts_rows(query_terms: list[str], limit: int,
                     priority_cond: str | None = None,
                     priority_param: str | None = None) -> list[str]:
    """Return matching document texts from Chroma's embedding_fulltext_search."""
    db = Path('/opt/data/mempalace/chroma.sqlite3')
    if not db.exists():
        return []
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    rows: list[str] = []
    # Priority rows first
    if priority_cond:
        for term in query_terms:
            cur.execute(
                f"SELECT string_value FROM embedding_fulltext_search "
                f"WHERE lower(string_value) LIKE ? AND {priority_cond} "
                f"ORDER BY rowid DESC LIMIT ?",
                (f"%{term}%", limit),
            )
            for r in cur:
                if r and r[0]:
                    rows.append(r[0])
            if len(rows) >= limit:
                break
    # General rows to fill
    for term in query_terms:
        if len(rows) >= limit:
            break
        cur.execute(
            "SELECT string_value FROM embedding_fulltext_search "
            "WHERE lower(string_value) LIKE ? AND string_value NOT LIKE '%MIPLM ZIP%' "
            "ORDER BY rowid DESC LIMIT ?",
            (f"%{term}%", limit),
        )
        for r in cur:
            if r and r[0] and r[0] not in rows:
                rows.append(r[0])
        if len(rows) >= limit:
            break
    conn.close()
    return rows


def search_mempalace_context(query: str, n_results: int = 4) -> str:
    """Retrieve relevant context from MemPalace/ChromaDB with tiered priority.

    Priority ladder:
      0. Direct keyword match in MEMORY.md / USER.md (always works, no deps)
      1. SQLite FTS for personal notes (room=personal/clients_prospects, kind=hermes_memory_sync / benjamin_relationship_context)
      2. MemPalace semantic search (ChromaDB embedding)
      3. General SQLite FTS for remaining MIPLM corpus
    """
    query = (query or "").strip()
    if not query:
        return ""

    terms = _extract_keywords(query, min_len=3)
    if not terms:
        return ""

    # ── Level 0: MEMORY.md / USER.md direct keyword match ────────────────
    try:
        mem_parts = []
        for mem_file in (MEMORY_DIR / "MEMORY.md", MEMORY_DIR / "USER.md"):
            if not mem_file.exists():
                continue
            raw = mem_file.read_text(encoding='utf-8', errors='ignore')
            # Score each entry by how many unique keywords it matches.
            scored = []
            for para in re.split(r'\n§\s*\n', raw):
                para = para.strip()
                if len(para) < 40:
                    continue
                score = sum(1 for t in terms if t in para.lower())
                if score > 0:
                    scored.append((score, para))
            # Sort by descending keyword count so exact matches rank first.
            scored.sort(key=lambda x: -x[0])
            for score, para in scored:
                mem_parts.append(f"[Hermes memory | {mem_file.name}] {para[:1800]}")
                if len(mem_parts) >= n_results:
                    break
            if len(mem_parts) >= n_results:
                break
        if mem_parts:
            context = "\n".join(mem_parts[:n_results])
            logger.info("MemPalace Level-0 (direct memory): %d chunks", len(mem_parts))
            return context
    except Exception as e:
        logger.debug("Level-0 memory scan skipped: %s", e)

    # ── Level 1: SQLite FTS for personal notes ───────────────────────────
    try:
        personal = _sqlite_fts_rows(
            terms, n_results,
            priority_cond="(lower(string_value) LIKE '%hermes_memory_sync%' "
                          "OR lower(string_value) LIKE '%benjamin_relationship_context%')",
        )
        if personal:
            dedup = []
            seen = set()
            for doc in personal:
                key = doc[:120]
                if key not in seen:
                    seen.add(key)
                    dedup.append(f"[MemPalace personal note] {doc[:1800]}")
                    if len(dedup) >= n_results:
                        break
            if dedup:
                logger.info("MemPalace Level-1 (personal notes): %d chunks", len(dedup))
                return "\n".join(dedup)
    except Exception as e:
        logger.warning("Level-1 personal FTS skipped: %s", e)

    # ── Level 2: MemPalace semantic search ──────────────────────────────
    try:
        from mempalace.backends.chroma import ChromaBackend
        col = ChromaBackend().get_or_create_collection('/opt/data/mempalace', 'mempalace_drawers')
        res = col.query(query_texts=[query], n_results=n_results)
        docs = getattr(res, 'documents', None) or (res.get('documents') if isinstance(res, dict) else None)
        metas = getattr(res, 'metadatas', None) or (res.get('metadatas') if isinstance(res, dict) else None)
        docs0 = docs[0] if docs else []
        metas0 = metas[0] if metas else [{} for _ in docs0]
        chunks = []
        for doc, meta in zip(docs0, metas0):
            room = meta.get('room', 'unknown') if isinstance(meta, dict) else 'unknown'
            chunks.append(f"[MemPalace room={room}] {doc}")
        context = "\n".join(chunks[:n_results]).strip()
        if context:
            logger.info("MemPalace Level-2 (semantic): %d chunks", len(chunks[:n_results]))
        return context
    except Exception as e:
        logger.warning("MemPalace Level-2 semantic skipped: %s", e)

    # ── Level 3: General SQLite FTS fallback ────────────────────────────
    try:
        general = _sqlite_fts_rows(terms, n_results)
        if general:
            dedup = []
            seen = set()
            for doc in general:
                key = doc[:120]
                if key not in seen:
                    seen.add(key)
                    dedup.append(f"[MemPalace FTS fallback] {doc[:1800]}")
                    if len(dedup) >= n_results:
                        break
            if dedup:
                logger.info("MemPalace Level-3 (FTS fallback): %d chunks", len(dedup))
                return "\n".join(dedup)
    except Exception as e:
        logger.warning("MemPalace Level-3 FTS fallback skipped: %s", e)

    return ""


# ---------------------------------------------------------------------------
# Strategic GraphRAG (LightRAG) — couche de raisonnement relationnel
# ---------------------------------------------------------------------------
_lightrag_instance = None
_lightrag_created = False  # True when LightRAG object exists
_lightrag_storages_ready = False  # True when storages are initialized

# Module-level embedding function (must be callable for LightRAG internals).
# This avoids threading/closure issues with wrapt.
def _rag_embed_func(texts):
    import numpy as np
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    return np.array(DefaultEmbeddingFunction()(texts), dtype=np.float32)

async def _rag_llm_func(prompt, system_prompt=None, history_messages=None,
                         keyword_extraction=False, **kwargs):
    """Minimal LLM function for retrieval-only mode."""
    return "retrieval context"


def _init_lightrag_if_needed() -> bool:
    """Initialize LightRAG with persistent storage. Must be called from main thread.
    Returns True if object was created, False if already done or not available."""
    global _lightrag_instance, _lightrag_created
    if _lightrag_created:
        return False
    
    try:
        lr_dir = Path("/opt/data/lightrag/strategic_rag")
        if not (lr_dir / "kate_strategic_graphrag" / "graph_chunk_entity_relation.graphml").exists():
            logger.info("Strategic RAG not yet indexed; skipping init")
            return False
        
        from lightrag.lightrag import LightRAG
        from lightrag.utils import EmbeddingFunc
        
        emb = EmbeddingFunc(embedding_dim=384, func=_rag_embed_func, max_token_size=8192)
        _lightrag_instance = LightRAG(
            working_dir=str(lr_dir),
            workspace='kate_strategic_graphrag',
            embedding_func=emb,
            llm_model_func=_rag_llm_func,
            llm_model_name='retrieval-only',
            enable_llm_cache=False,
            top_k=8,
            chunk_top_k=8,
        )
        _lightrag_created = True
        logger.info("Strategic GraphRAG object created")
        return True
    except Exception as e:
        logger.warning("Strategic RAG init failed: %s", e)
        return False


async def search_strategic_rag_context(query: str) -> str:
    """Query LightRAG for strategic relational reasoning.
    
    Uses the persistent Kate Strategic GraphRAG workspace indexed at
    /opt/data/lightrag/strategic_rag/. Returns concise strategic context
    when relevant; empty string on error or if not initialized.
    """
    global _lightrag_instance, _lightrag_created, _lightrag_storages_ready
    if not query or not query.strip():
        return ""
    
    try:
        if not _lightrag_created:
            _init_lightrag_if_needed()
            if not _lightrag_instance:
                return ""
        
        # Initialize storages on first query
        if not _lightrag_storages_ready:
            await _lightrag_instance.initialize_storages()
            _lightrag_storages_ready = True
            logger.info("Strategic GraphRAG storages initialized")
        
        from lightrag.lightrag import QueryParam
        
        param = QueryParam(
            mode='mix',
            top_k=8,
            chunk_top_k=8,
            only_need_context=True,
            response_type='Concise strategic context',
            enable_rerank=False,
        )
        context = await _lightrag_instance.aquery(query, param=param)
        if context:
            context = context.strip()
            if len(context) > 2500:
                context = context[:2500] + "..."
            logger.info("Strategic RAG context: %d chars", len(context))
        return context or ""
        
    except Exception as e:
        logger.warning("Strategic RAG context skipped: %s", e)
        return ""


# ---------------------------------------------------------------------------
# Sauvegarde sessions vocales dans state.db
# ---------------------------------------------------------------------------

def save_voice_session(session_id: str, messages: list):
    """Sauvegarde la session vocale dans la base Hermes state.db avec le schéma actuel."""
    try:
        now = time.time()
        conn = sqlite3.connect(str(STATE_DB))
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO sessions "
            "(id, source, user_id, model, model_config, system_prompt, started_at, ended_at, end_reason, message_count, title) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                "voice_web",
                "benjamin_delsol",
                os.getenv("KATE_VOICE_MODEL", "deepseek/deepseek-v4-pro"),
                json.dumps({"base_url": "https://openrouter.ai/api/v1"}),
                "Kate Voice Interface — session vocale web",
                now,
                now,
                "voice_close",
                len(messages),
                "Kate voice web session",
            ),
        )
        for msg in messages:
            cur.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, msg["role"], msg.get("content", ""), time.time()),
            )
        cur.execute(
            "UPDATE sessions SET ended_at=?, end_reason=?, message_count=? WHERE id=?",
            (time.time(), "voice_close", len(messages), session_id),
        )
        conn.commit()
        conn.close()
        logger.info("Session vocale sauvegardée: %s (%d messages)", session_id, len(messages))
    except Exception as e:
        logger.warning("Erreur sauvegarde session vocale: %s", e)


# ---------------------------------------------------------------------------
# STT — faster-whisper
# ---------------------------------------------------------------------------

_whisper_model = None

def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info("Chargement Whisper base...")
        _whisper_model = WhisperModel("base", device="auto", compute_type="auto")
    return _whisper_model


def transcribe_bytes(audio_bytes: bytes, fmt: str = "webm") -> dict:
    """Transcrit des bytes audio, retourne transcript + émotion."""
    with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        model = get_whisper()
        segments, info = model.transcribe(tmp_path, beam_size=5, language="fr")
        transcript = " ".join(s.text.strip() for s in segments).strip()

        # Analyse émotionnelle
        emotion = {}
        try:
            from tools.emotion_analysis import analyse_emotion
            emotion = analyse_emotion(tmp_path)
        except Exception as e:
            logger.debug("Émotion skipped: %s", e)

        return {
            "transcript": transcript,
            "language": info.language,
            "emotion": emotion,
        }
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# LLM — OpenAI-compatible (Hermes config)
# ---------------------------------------------------------------------------

async def stream_llm(messages: list, emotion: dict) -> str:
    """Appelle le LLM configuré dans Hermes et retourne la réponse complète."""
    # LLM vocal : utiliser OpenRouter directement. Ne pas suivre le provider principal Hermes
    # lorsqu'il pointe vers Codex/ChatGPT, car l'interface vocale dispose d'une clé OpenRouter.
    base_url = os.getenv("KATE_VOICE_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.getenv("KATE_VOICE_MODEL", "deepseek/deepseek-v4-pro")

    # Clé API — depuis l'env (chargé depuis /opt/data/.env)
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    logger.info("Voice LLM: %s @ %s (clé: %s)", model, base_url, "OK" if api_key else "MANQUANTE")

    # Adapter le système selon l'émotion
    ton = emotion.get("ton", "neutre")
    stress = emotion.get("stress", "faible")
    system_addon = ""
    if stress == "élevé":
        system_addon = " L'utilisateur semble stressé : sois calme, concise, rassurante."
    elif ton == "énergique":
        system_addon = " L'utilisateur est énergique : sois dynamique et directe."
    elif ton == "enthousiaste":
        system_addon = " L'utilisateur est enthousiaste : partage son énergie."
    elif ton == "calme":
        system_addon = " L'utilisateur est calme : tu peux développer davantage."

    # Injecter la mémoire Hermes + contexte MemPalace pertinent
    hermes_mem = load_hermes_memory()
    latest_user_query = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            latest_user_query = m.get("content", "")
            break
    mempalace_context = search_mempalace_context(latest_user_query)

    mem_block = ""
    if hermes_mem["user_profile"]:
        mem_block += f"\n\nProfil de Benjamin (mémoire Hermes) :\n{hermes_mem['user_profile']}"
    if hermes_mem["notes"]:
        mem_block += f"\n\nNotes de contexte (mémoire Hermes) :\n{hermes_mem['notes']}"
    if mempalace_context:
        mem_block += f"\n\nContexte pertinent retrouvé dans MemPalace :\n{mempalace_context}"
    # ── Strategic GraphRAG (LightRAG) — couche de raisonnement relationnel ──
    strategic_rag_context = ""
    try:
        strategic_rag_context = await asyncio.wait_for(
            search_strategic_rag_context(latest_user_query or ""), timeout=8.0
        )
    except Exception as e:
        logger.info("Strategic RAG skipped (%s)", type(e).__name__)
    if strategic_rag_context:
        mem_block += f"\n\nAnalyse stratégique relationnelle (GraphRAG) :\n{strategic_rag_context}"
    logger.info("Memory injected: user_profile=%d chars, notes=%d chars, mempalace=%d chars, strategic_rag=%d chars", len(hermes_mem.get("user_profile", "")), len(hermes_mem.get("notes", "")), len(mempalace_context), len(strategic_rag_context or ""))

    system = (
        "Tu es Kate, l'assistante vocale et stratégique de Dr Benjamin DELSOL. "
        "Voici ce que tu sais sur Benjamin :\n"
        "- Dr Benjamin DELSOL, IP strategist et CIPO fractionnel, expert en actifs immatériels.\n"
        "- Fondateur de DELSOL IP Strategy, il accompagne des startups DeepTech, quantiques et IA.\n"
        "- Ses domaines : stratégie IP, brevets, valorisation, souveraineté technologique, licences, "
        "portefeuille intangible, positionnement concurrentiel, levées de fonds, moats stratégiques.\n"
        "- Il parle et pense en français. Style : visionnaire, énergique, exécutif.\n"
        "- Tu l'appelles Benjamin. Tu le tutoies.\n"
        "- Tu as une mémoire de la conversation en cours et tu t'appuies sur ce contexte.\n"
        + mem_block
        + "\n\nRègles de communication vocale :\n"
        "- Réponds toujours en français, de manière concise et naturelle pour une conversation orale.\n"
        "- Évite les listes à puces, le markdown, les tirets. Parle directement, comme à voix haute.\n"
        "- Sois directe, précise, et stratégique dans tes réponses."
        + (" " + system_addon if system_addon else "")
    )

    full_messages = [{"role": "system", "content": system}] + messages

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        response = await client.chat.completions.create(
            model=model,
            messages=full_messages,
            max_tokens=300,
            temperature=0.7,
        )
        msg = response.choices[0].message
        content = (msg.content or "").strip()
        # Some reasoning models/providers may occasionally return reasoning but no final content.
        # In that case, retry once on a non-reasoning fallback so the UI always gets an answer.
        if not content:
            logger.warning("LLM returned empty content for %s; retrying with fallback", model)
            fallback_model = os.getenv("KATE_VOICE_FALLBACK_MODEL", "deepseek/deepseek-v4-flash")
            response = await client.chat.completions.create(
                model=fallback_model,
                messages=full_messages,
                max_tokens=300,
                temperature=0.5,
            )
            msg = response.choices[0].message
            content = (msg.content or getattr(msg, "reasoning", "") or "").strip()
        return content or "Désolée, je n'ai pas pu obtenir une réponse exploitable. Réessaie."
    except Exception as e:
        logger.error("LLM error: %s", e)
        return "Désolée, je n'ai pas pu obtenir une réponse. Réessaie."


# ---------------------------------------------------------------------------
# TTS — Edge TTS Vivienne adaptatif
# ---------------------------------------------------------------------------

async def synthesize_vivienne(text: str, emotion: dict) -> bytes:
    """Génère de l'audio avec Vivienne, adapté à l'émotion détectée."""
    ton = emotion.get("ton", "neutre")
    stress = emotion.get("stress", "faible")

    # Adapter le débit et le pitch selon l'émotion
    if stress == "élevé":
        rate, pitch = "+0%", "-3Hz"   # Calme et posée
    elif ton in ("énergique", "enthousiaste"):
        rate, pitch = "+12%", "+3Hz"  # Dynamique
    elif ton == "calme":
        rate, pitch = "-5%", "-2Hz"   # Douce et lente
    elif ton == "hésitant":
        rate, pitch = "-3%", "-1Hz"   # Rassurante
    else:
        rate, pitch = "+5%", "+0Hz"   # Neutre légèrement vif

    edge_tts_bin = "/opt/hermes/.venv/bin/edge-tts"

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        mp3_path = f.name
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        ogg_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            edge_tts_bin,
            "--voice", "fr-FR-VivienneMultilingualNeural",
            "--text", text,
            f"--rate={rate}",
            f"--pitch={pitch}",
            "--write-media", mp3_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

        proc2 = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", mp3_path,
            "-c:a", "libvorbis", "-q:a", "4", ogg_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc2.wait()

        return Path(ogg_path).read_bytes()
    finally:
        for p in (mp3_path, ogg_path):
            try:
                os.unlink(p)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# WebSocket — pipeline vocal complet
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("Connexion WebSocket établie")

    # Historique de la conversation + ID de session unique
    history = []
    session_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    logger.info("Nouvelle session vocale: %s", session_id)

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            # --- Audio reçu du micro ---
            if msg_type == "audio":
                audio_b64 = data.get("audio", "")
                fmt = data.get("format", "webm")
                audio_bytes = base64.b64decode(audio_b64)

                # 1. Transcription + émotion
                await ws.send_json({"type": "status", "text": "🎤 Transcription..."})
                stt_result = await asyncio.to_thread(transcribe_bytes, audio_bytes, fmt)
                transcript = stt_result.get("transcript", "").strip()
                emotion = stt_result.get("emotion", {})

                if not transcript:
                    await ws.send_json({"type": "status", "text": "⚠️ Silence détecté, réessaie."})
                    continue

                # Envoyer transcript + émotion au client
                await ws.send_json({
                    "type": "transcript",
                    "text": transcript,
                    "emotion": emotion,
                })

                # 2. LLM
                await ws.send_json({"type": "status", "text": "💭 Réflexion..."})
                history.append({"role": "user", "content": transcript})

                # Garder max 10 tours
                if len(history) > 20:
                    history = history[-20:]

                response_text = await stream_llm(history, emotion)
                history.append({"role": "assistant", "content": response_text})

                # Envoyer la réponse texte
                await ws.send_json({
                    "type": "response",
                    "text": response_text,
                    "emotion_adapted": emotion.get("ton", "neutre"),
                })

                # 3. TTS Vivienne
                await ws.send_json({"type": "status", "text": "🔊 Synthèse vocale..."})
                audio_bytes_out = await synthesize_vivienne(response_text, emotion)
                audio_b64_out = base64.b64encode(audio_bytes_out).decode()

                await ws.send_json({
                    "type": "audio_response",
                    "audio": audio_b64_out,
                    "format": "ogg",
                })

            elif msg_type == "reset":
                # Sauvegarder la conversation avant de réinitialiser
                if history:
                    await asyncio.to_thread(save_voice_session, session_id, history)
                history = []
                session_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
                await ws.send_json({"type": "status", "text": "🔄 Conversation réinitialisée."})

    except WebSocketDisconnect:
        # Sauvegarder la conversation à la déconnexion
        if history:
            save_voice_session(session_id, history)
        logger.info("Client déconnecté — session %s sauvegardée", session_id)
    except Exception as e:
        logger.error("Erreur WebSocket: %s", e, exc_info=True)
        try:
            await ws.send_json({"type": "error", "text": str(e)})
        except Exception:
            pass


# ---------------------------------------------------------------------------
# WebSocket — Gateway AION UI / Hermes Desktop (chat texte streaming)
# ---------------------------------------------------------------------------

@app.websocket("/gateway")
async def gateway_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("Connexion Gateway WebSocket établie")

    history = []
    try:
        while True:
            data = await ws.receive_json()
            message = data.get("message", "").strip()
            if not message:
                await ws.send_json({"type": "error", "text": "Message vide"})
                continue

            model = data.get("model", "deepseek/deepseek-v4-pro")
            base_url = data.get("base_url", "https://openrouter.ai/api/v1")

            history.append({"role": "user", "content": message})
            if len(history) > 30:
                history = history[-30:]

            api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or ""

            # Charger mémoire + MemPalace
            hermes_mem = load_hermes_memory()
            mempalace_context = search_mempalace_context(message)
            mem_block = ""
            if hermes_mem["user_profile"]:
                mem_block += f"\n\nProfil Benjamin : {hermes_mem['user_profile']}"
            if hermes_mem["notes"]:
                mem_block += f"\n\nNotes : {hermes_mem['notes']}"
            if mempalace_context:
                mem_block += f"\n\nMemPalace : {mempalace_context}"
            # Strategic GraphRAG
            srag = ""
            try:
                srag = await asyncio.wait_for(
                    search_strategic_rag_context(message), timeout=8.0
                )
            except Exception:
                pass
            if srag:
                mem_block += f"\n\nAnalyse GraphRAG : {srag}"

            system_msg = (
                "Tu es Kate, l'assistante de Dr Benjamin DELSOL, IP strategist / CIPO fractionnel. "
                "Réponds en français de façon concise et stratégique." + mem_block
            )
            msgs = [{"role": "system", "content": system_msg}] + history

            # Streaming LLM via OpenRouter
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://kate.delsol.ai",
                "X-Title": "Kate Gateway",
            }
            payload = {
                "model": model,
                "messages": msgs,
                "stream": True,
                "temperature": 0.7,
                "max_tokens": 2048,
            }

            full_response = ""
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream(
                        "POST",
                        f"{base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    ) as resp:
                        if resp.status_code != 200:
                            err = await resp.aread()
                            await ws.send_json({"type": "error", "text": f"LLM error {resp.status_code}: {err[:300]}"})
                            continue

                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                chunk = line[6:]
                                if chunk == "[DONE]":
                                    break
                                try:
                                    jchunk = json.loads(chunk)
                                    delta = jchunk.get("choices", [{}])[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        full_response += content
                                        await ws.send_json({"type": "token", "text": content})
                                except Exception:
                                    continue

                history.append({"role": "assistant", "content": full_response})
                await ws.send_json({"type": "done"})

            except Exception as e:
                logger.error("Gateway streaming error: %s", e)
                await ws.send_json({"type": "error", "text": str(e)})

    except WebSocketDisconnect:
        logger.info("Gateway client déconnecté")
    except Exception as e:
        logger.error("Gateway WebSocket error: %s", e, exc_info=True)
        try:
            await ws.send_json({"type": "error", "text": str(e)})
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Dashboard Kate — API cockpit
# ---------------------------------------------------------------------------

DASHBOARD_PAGE = Path("/opt/data/voice_interface/dashboard.html")


def _safe_read(path: str, default: str = "") -> str:
    try:
        p = Path(path)
        return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else default
    except Exception:
        return default


def _process_running(needle: str) -> bool:
    try:
        import subprocess
        out = subprocess.check_output(["ps", "-eo", "args="], text=True, timeout=3)
        return any(needle in line for line in out.splitlines())
    except Exception:
        return False


def _load_config_summary() -> dict:
    txt = _safe_read("/opt/data/config.yaml")
    def after(key: str, default=""):
        for line in txt.splitlines():
            if line.strip().startswith(key + ":"):
                return line.split(":", 1)[1].strip().strip("'").strip('"')
        return default
    return {
        "deepseek_configured": "deepseek/deepseek-v4-pro" in txt,
        "voice_model": os.getenv("KATE_VOICE_MODEL", "deepseek/deepseek-v4-pro"),
        "tts_voice": "fr-FR-VivienneMultilingualNeural" if "fr-FR-VivienneMultilingualNeural" in txt else after("voice", ""),
        "memory_limit": "6000" if "memory_char_limit: 6000" in txt else "unknown",
    }


def _cron_jobs(limit: int = 50) -> list:
    try:
        data = json.loads(_safe_read("/opt/data/cron/jobs.json", "{}"))
        jobs = data.get("jobs", [])
        slim = []
        for j in jobs[:limit]:
            slim.append({
                "id": j.get("id") or j.get("job_id"),
                "name": j.get("name"),
                "enabled": j.get("enabled"),
                "state": j.get("state"),
                "schedule": j.get("schedule_display") or j.get("schedule", {}).get("display") if isinstance(j.get("schedule"), dict) else j.get("schedule"),
                "next_run_at": j.get("next_run_at"),
                "last_run_at": j.get("last_run_at"),
                "last_status": j.get("last_status"),
                "deliver": j.get("deliver"),
            })
        return slim
    except Exception as e:
        return [{"name": "Erreur lecture cron", "last_status": str(e)}]


def _recent_sessions(limit: int = 12) -> list:
    try:
        conn = sqlite3.connect(str(STATE_DB))
        cur = conn.cursor()
        cur.execute("select id, source, title, started_at, ended_at, message_count from sessions order by started_at desc limit ?", (limit,))
        rows = cur.fetchall()
        conn.close()
        return [
            {"id": r[0], "source": r[1], "title": r[2] or r[0], "started_at": r[3], "ended_at": r[4], "message_count": r[5]}
            for r in rows
        ]
    except Exception as e:
        return [{"id": "error", "title": str(e), "source": "error"}]


def _parse_ics_events(limit: int = 10) -> list:
    text = _safe_read("/opt/data/calendar/benjamin_outlook_calendar.ics")
    if not text:
        return []
    # Unfold ICS folded lines.
    unfolded = []
    for line in text.splitlines():
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    events, cur = [], None
    for line in unfolded:
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT" and cur:
            events.append(cur); cur = None
        elif cur is not None:
            key, _, val = line.partition(":")
            if key.startswith("SUMMARY"):
                cur["summary"] = val
            elif key.startswith("DTSTART"):
                cur["start"] = val
            elif key.startswith("DTEND"):
                cur["end"] = val
            elif key.startswith("LOCATION"):
                cur["location"] = val
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    upcoming = [e for e in events if e.get("start", "") >= now]
    upcoming.sort(key=lambda e: e.get("start", ""))
    return upcoming[:limit]


def _mempalace_graph() -> dict:
    """Return a dashboard-friendly graph.

    The vector store may contain thousands of chunks. Rendering every chunk as a node
    would freeze mobile browsers, so expose rooms + a capped sample of drawers per room,
    while preserving total counts and room counts for visibility.
    """
    nodes, links = [], []
    try:
        from collections import defaultdict
        from mempalace.backends.chroma import ChromaBackend
        col = ChromaBackend().get_or_create_collection('/opt/data/mempalace', 'mempalace_drawers')
        res = col.get()
        ids = getattr(res, 'ids', []) or []
        docs = getattr(res, 'documents', []) or []
        metas = getattr(res, 'metadatas', []) or []
        by_room = defaultdict(list)
        for mid, doc, meta in zip(ids, docs, metas):
            meta = meta or {}
            room = meta.get("room", "general")
            by_room[room].append((mid, doc or "", meta))

        nodes.append({"id": "benjamin_delsol", "label": "Benjamin / Kate Memory", "type": "wing", "size": 24})
        max_per_room = int(os.getenv("KATE_DASHBOARD_GRAPH_MAX_PER_ROOM", "35"))
        for room, items in sorted(by_room.items(), key=lambda kv: kv[0]):
            rid = "room:" + room
            nodes.append({"id": rid, "label": f"{room} ({len(items)})", "type": "room", "room": room, "size": 18})
            links.append({"source": "benjamin_delsol", "target": rid})
            shown = items[:max_per_room]
            for mid, doc, meta in shown:
                title = meta.get("document_title") or meta.get("source_rel") or meta.get("source") or mid
                label = str(title).replace("_", " ")[:72]
                nodes.append({"id": mid, "label": label, "type": "drawer", "room": room, "size": 7, "source_file": meta.get("source_file", ""), "kind": meta.get("kind", "")})
                links.append({"source": rid, "target": mid})
            hidden = max(0, len(items) - len(shown))
            if hidden:
                hid = f"hidden:{room}"
                nodes.append({"id": hid, "label": f"+{hidden} autres chunks", "type": "drawer", "room": room, "size": 10, "kind": "aggregate"})
                links.append({"source": rid, "target": hid})
        return {"count": len(ids), "room_counts": {k: len(v) for k, v in by_room.items()}, "nodes": nodes, "links": links}
    except Exception as e:
        return {"count": 0, "nodes": [{"id":"error", "label": str(e), "type":"error"}], "links": []}


@app.get("/dashboard")
async def dashboard_page():
    return HTMLResponse(DASHBOARD_PAGE.read_text(encoding="utf-8"))


@app.get("/api/dashboard/status")
async def dashboard_status():
    cloudflare_url = _safe_read("/opt/data/voice_interface/cloudflare_url.txt").strip()
    return {
        "time_utc": datetime.utcnow().isoformat() + "Z",
        "voice_local": _process_running("/opt/data/voice_interface/server.py"),
        "cloudflared": _process_running("cloudflared tunnel") or _process_running("cloudflared"),
        "cloudflare_url": cloudflare_url,
        "mempalace_mcp": _process_running("mempalace-mcp"),
        "mempalace_db": Path("/opt/data/mempalace/chroma.sqlite3").exists(),
        "config": _load_config_summary(),
        "memory_files": {
            "MEMORY.md": Path("/opt/data/memories/MEMORY.md").stat().st_size if Path("/opt/data/memories/MEMORY.md").exists() else 0,
            "USER.md": Path("/opt/data/memories/USER.md").stat().st_size if Path("/opt/data/memories/USER.md").exists() else 0,
        },
    }


@app.get("/api/dashboard/jobs")
async def dashboard_jobs():
    return {"jobs": _cron_jobs()}


@app.get("/api/dashboard/sessions")
async def dashboard_sessions():
    return {"sessions": _recent_sessions()}


@app.get("/api/dashboard/calendar")
async def dashboard_calendar():
    return {"events": _parse_ics_events()}


@app.get("/api/dashboard/memory-graph")
async def dashboard_memory_graph():
    return _mempalace_graph()


@app.post("/api/dashboard/chat")
async def dashboard_chat(req: Request):
    body = await req.json()
    message = (body.get("message") or "").strip()
    model = body.get("model") or os.getenv("KATE_VOICE_MODEL", "deepseek/deepseek-v4-pro")
    if not message:
        return JSONResponse({"error": "Message vide"}, status_code=400)
    old_model = os.environ.get("KATE_VOICE_MODEL")
    os.environ["KATE_VOICE_MODEL"] = model
    try:
        answer = await stream_llm([{"role": "user", "content": message}], {})
    finally:
        if old_model is None:
            os.environ.pop("KATE_VOICE_MODEL", None)
        else:
            os.environ["KATE_VOICE_MODEL"] = old_model
    return {"answer": answer, "model": model}


@app.post("/api/dashboard/actions")
async def dashboard_actions(req: Request):
    body = await req.json()
    action = body.get("action")
    if action == "check_services":
        proc = await asyncio.create_subprocess_exec(
            "/opt/data/scripts/kate_services_watchdog.sh",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        return {"ok": proc.returncode == 0, "stdout": out.decode(), "stderr": err.decode()}
    if action == "restart_gateway":
        return JSONResponse({"ok": False, "message": "Action volontairement verrouillée dans ce MVP tant que l’authentification dashboard n’est pas en place."}, status_code=403)
    return JSONResponse({"ok": False, "message": "Action inconnue"}, status_code=400)


# ---------------------------------------------------------------------------
# Terminal web (xterm.js) — PTY via WebSocket
# ---------------------------------------------------------------------------

_TERMINAL_PROCESSES: dict[str, dict] = {}
_TERMINAL_LOCK = threading.Lock()


def _cleanup_terminal(term_id: str):
    with _TERMINAL_LOCK:
        info = _TERMINAL_PROCESSES.pop(term_id, None)
    if info:
        try:
            os.kill(info["pid"], signal.SIGKILL)
        except OSError:
            pass
        try:
            os.close(info["fd"])
        except OSError:
            pass


def _spawn_terminal() -> tuple[int, int, str]:
    """Fork a PTY with bash. Returns (pid, master_fd, terminal_id)."""
    term_id = uuid.uuid4().hex[:12]
    pid, fd = pty.fork()
    if pid == 0:
        # Child
        os.environ.setdefault("TERM", "xterm-256color")
        os.environ.setdefault("SHELL", "/bin/bash")
        # Set a nice prompt
        os.environ["PS1"] = "\\[\\e[38;5;99m\\]┌─(\\[\\e[38;5;45m\\]hermes-desktop\\[\\e[38;5;99m\\])-[\\[\\e[38;5;245m\\]\\w\\[\\e[38;5;99m\\]]\n└──╼ \\[\\e[0m\\]"
        os.execve("/bin/bash", ["/bin/bash", "--login"], os.environ)
        os._exit(1)
    # Parent
    os.set_blocking(fd, False)
    with _TERMINAL_LOCK:
        _TERMINAL_PROCESSES[term_id] = {"pid": pid, "fd": fd}
    atexit.register(lambda: _cleanup_terminal(term_id))
    return pid, fd, term_id


@app.websocket("/api/dashboard/terminal")
async def terminal_ws(ws: WebSocket):
    await ws.accept()
    pid, fd, term_id = _spawn_terminal()
    logger.info("Terminal %s spawned (pid=%d)", term_id, pid)
    loop = asyncio.get_event_loop()

    def pty_read():
        try:
            data = os.read(fd, 65536)
            if data:
                asyncio.run_coroutine_threadsafe(
                    ws.send_bytes(data), loop
                )
            else:
                asyncio.run_coroutine_threadsafe(ws.close(), loop)
        except (OSError, ConnectionResetError):
            asyncio.run_coroutine_threadsafe(ws.close(), loop)

    def pty_write(data: bytes):
        try:
            os.write(fd, data)
        except OSError:
            pass

    def pty_resize(rows: int, cols: int):
        try:
            buf = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, buf)
            os.kill(pid, signal.SIGWINCH)
        except OSError:
            pass

    loop.add_reader(fd, pty_read)

    try:
        while True:
            raw = await ws.receive()
            if raw.get("type") == "websocket.disconnect":
                break
            if isinstance(raw, str):
                try:
                    msg = json.loads(raw)
                    if msg.get("type") == "resize":
                        pty_resize(int(msg.get("rows", 24)), int(msg.get("cols", 80)))
                    elif msg.get("type") == "input":
                        pty_write(msg["data"].encode())
                except (json.JSONDecodeError, KeyError):
                    pty_write(raw.encode())
            elif isinstance(raw, bytes):
                pty_write(raw)
    except (WebSocketDisconnect, ConnectionResetError, OSError):
        pass
    finally:
        loop.remove_reader(fd)
        _cleanup_terminal(term_id)
        logger.info("Terminal %s closed", term_id)


# ---------------------------------------------------------------------------
# Explorateur de fichiers — API REST
# ---------------------------------------------------------------------------

# Sécurité : ne pas laisser naviguer en dehors de ces répertoires
ALLOWED_FILE_ROOTS = [
    Path("/opt/data").resolve(),
    Path("/opt/hermes").resolve(),
]

def _safe_resolve(path_str: str) -> Path | None:
    """Résoudre un chemin et vérifier qu'il est dans une zone autorisée."""
    resolved = Path(path_str).resolve()
    for root in ALLOWED_FILE_ROOTS:
        if str(resolved).startswith(str(root)):
            return resolved
    return None


@app.get("/api/dashboard/files")
async def dashboard_files(req: Request):
    path = req.query_params.get("path", "/opt/data")
    resolved = _safe_resolve(path)
    if not resolved or not resolved.is_dir():
        return {"ok": False, "error": "Accès refusé ou dossier introuvable", "path": path}
    try:
        entries = []
        for entry in sorted(resolved.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            try:
                stat = entry.stat()
                entries.append({
                    "name": entry.name,
                    "path": str(entry),
                    "is_dir": entry.is_dir(),
                    "size": stat.st_size if not entry.is_dir() else 0,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "mode": oct(stat.st_mode)[-3:],
                })
            except OSError:
                pass
        return {
            "ok": True,
            "path": str(resolved),
            "parent": str(resolved.parent) if resolved.parent != resolved else None,
            "entries": entries,
        }
    except OSError as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/dashboard/files/read")
async def dashboard_files_read(req: Request):
    path = req.query_params.get("path", "")
    resolved = _safe_resolve(path)
    if not resolved or not resolved.is_file():
        return {"ok": False, "error": "Fichier introuvable ou accès refusé"}
    try:
        # Limiter la taille du fichier en mémoire
        max_bytes = 512 * 1024  # 512 KB
        size = resolved.stat().st_size
        if size > max_bytes:
            return {"ok": False, "error": f"Fichier trop volumineux ({size} octets max {max_bytes})"}
        content = resolved.read_bytes()
        # Deviner si c'est du texte
        try:
            text = content.decode("utf-8")
            return {"ok": True, "text": text, "size": size}
        except UnicodeDecodeError:
            return {"ok": True, "base64": base64.b64encode(content).decode(), "size": size, "binary": True}
    except OSError as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/dashboard/files/upload")
async def dashboard_files_upload(req: Request):
    content_type = req.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await req.form()
        file_field = form.get("file")
        dest = form.get("path", "/opt/data/uploads")
        if not file_field or not hasattr(file_field, "filename"):
            return {"ok": False, "error": "Aucun fichier dans la requête"}
        resolved = _safe_resolve(dest)
        if not resolved or not resolved.is_dir():
            return {"ok": False, "error": "Dossier de destination invalide"}
        filename = file_field.filename
        if not filename:
            filename = "upload"
        safe_name = Path(filename).name  # strip path
        dest_path = resolved / safe_name
        try:
            content = await file_field.read()
            dest_path.write_bytes(content)
            return {"ok": True, "path": str(dest_path), "size": len(content)}
        except OSError as e:
            return {"ok": False, "error": str(e)}
    # Fallback : upload base64 inline
    body = await req.json()
    dest = body.get("path", "/opt/data")
    filename = body.get("filename", "upload.txt")
    content_b64 = body.get("content", "")
    resolved = _safe_resolve(dest)
    if not resolved or not resolved.is_dir():
        return {"ok": False, "error": "Dossier de destination invalide"}
    try:
        content = base64.b64decode(content_b64)
        dest_path = resolved / Path(filename).name
        dest_path.write_bytes(content)
        return {"ok": True, "path": str(dest_path), "size": len(content)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/dashboard/files/download")
async def dashboard_files_download(req: Request):
    path = req.query_params.get("path", "")
    resolved = _safe_resolve(path)
    if not resolved or not resolved.is_file():
        return JSONResponse({"ok": False, "error": "Fichier introuvable"}, status_code=404)
    mime, _ = mimetypes.guess_type(str(resolved))
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(resolved),
        media_type=mime or "application/octet-stream",
        filename=resolved.name,
        headers={"Content-Disposition": f'attachment; filename="{resolved.name}"'},
    )


# ---------------------------------------------------------------------------
# Page HTML principale
# ---------------------------------------------------------------------------

HTML_PAGE = Path("/opt/data/voice_interface/index.html")

@app.get("/")
async def root():
    return HTMLResponse(HTML_PAGE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Lancement
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Auto-sync Hermes persistent memory into MemPalace at startup so the
    # voice/gateway always sees Benjamin's latest corrections and preferences
    # without manual sync steps.
    sync_memory_to_mempalace()

    # Pre-warm Strategic GraphRAG (LightRAG) — create object and initialize storages
    # now so the first voice/gateway call does not pay the init cost (~15s).
    if _init_lightrag_if_needed():
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(_lightrag_instance.initialize_storages())
            _lightrag_storages_ready = True
            logger.info("Strategic GraphRAG fully pre-warmed")
        except Exception as e:
            logger.warning("Strategic RAG pre-warm storages failed: %s", e)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8765,
        log_level="info",
    )
