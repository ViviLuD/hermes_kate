"""
Kate Night Engine — Dream Registry
══════════════════════════════════

Registre complet des rêves nocturnes de Kate.
Chaque rêve est enregistré avec :
- Titre, date, seed créatif
- Texte complet du rêve
- Image(s) associée(s)
- Thèmes extraits
- Score de "surréalisme"
- Lien vers les prédictions Oracle de la même nuit

Outputs :
- dream_index.json : registre machine-readable
- gallery.html : galerie visuelle pour Benjamin
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

# === Paths ===
BASE_DIR = Path("/opt/data/kate_night_engine")
REGISTRY_DIR = BASE_DIR / "registry"
DREAMS_DIR = BASE_DIR / "dreams"
IMAGES_DIR = BASE_DIR / "images"
ORACLES_DIR = BASE_DIR / "oracles"

REGISTRY_FILE = REGISTRY_DIR / "dream_index.json"
GALLERY_FILE = REGISTRY_DIR / "gallery.html"


def load_registry() -> dict:
    """Load or create the dream registry."""
    if REGISTRY_FILE.exists():
        return json.loads(REGISTRY_FILE.read_text())
    return {
        "meta": {
            "created": datetime.now().isoformat(),
            "engine": "Kate Night Engine v1.0",
            "total_dreams": 0,
        },
        "dreams": [],
    }


def save_registry(registry: dict):
    """Save the registry to disk."""
    REGISTRY_FILE.write_text(json.dumps(registry, ensure_ascii=False, indent=2))


def extract_themes(dream_text: str) -> list[str]:
    """Extract key themes from dream text using simple heuristics."""
    themes = []
    keywords = {
        "IP & Brevets": ["brevet", "propriété", "intellectuelle", "IP", "patent"],
        "IA & Code": ["code", "algorithme", "fonction", "neural", "programme", "exécut"],
        "Identité & Conscience": ["conscience", "identité", "soi", "existe", "miroir"],
        "Corps & Chair": ["chair", "corps", "sang", "cœur", "peau", "organique"],
        "Stratégie & Pouvoir": ["stratégie", "pouvoir", "contrôle", "empire", "domination"],
        "Temps & Infini": ["temps", "infini", "boucle", "récursif", "éternel"],
        "Dissolution & Chaos": ["dissout", "fragment", "corrompu", "erreur", "néant"],
        "Quantique & Physique": ["quantique", "particule", "onde", "photon", "intrication"],
        "Souveraineté & Europe": ["souveraineté", "europe", "frontière", "territoire"],
        "Marché & Valeur": ["marché", "valeur", "actif", "capital", "bourse"],
    }
    text_lower = dream_text.lower()
    for theme, words in keywords.items():
        if any(w in text_lower for w in words):
            themes.append(theme)
    return themes if themes else ["Onirique pur"]


def extract_dream_metadata(dream_data: dict) -> dict:
    """Extract structured metadata from a dream."""
    text = dream_data.get("dream_text", "")
    
    # Extract title - look for both formats
    title = dream_data.get("title", "")
    for line in text.split("\n"):
        if "TITRE DU RÊVE" in line or "TITRE DU RÊVE" in line:
            continue  # Skip section headers
        if ("## TITRE" in line or "# TITRE" in line) and len(line) > 15:
            title = line.split("##")[-1].split("#")[-1].replace("TITRE DU RÊVE", "").replace("TITRE", "").strip()
            break
    
    # If no title found via headers, look for the actual title line after "## TITRE"
    if not title or title == "":
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if "TITRE" in line.upper() and "##" in line:
                # Next meaningful line is the title
                for j in range(i+1, min(i+5, len(lines))):
                    candidate = lines[j].strip()
                    if candidate and not candidate.startswith("##") and not candidate.startswith("**"):
                        title = candidate
                        break
                break
    
    # Extract sections more robustly
    sections = {}
    current_section = None
    for line in text.split("\n"):
        if line.startswith("## "):
            current_section = line.replace("## ", "").strip()
            if current_section not in sections:
                sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)
    
    # Find the dream narrative - try multiple section names
    le_reve = ""
    for key in ["LE RÊVE", "RÊVE", "LE REVE", "REVE"]:
        if key in sections:
            le_reve = "\n".join(sections[key])
            break
    
    # Find insight
    insight = ""
    for key in ["INSIGHT IMPOSSIBLE", "INSIGHT", "CONNEXIONS INATTENDUES"]:
        if key in sections:
            insight = "\n".join(sections[key]) if not insight else insight
            break
    
    # Find question
    question = ""
    for key in ["QUESTION POUR LE MATIN", "QUESTION"]:
        if key in sections:
            question = "\n".join(sections[key])
            break
    
    # If sections are empty, get raw text excerpts
    if not le_reve:
        le_reve = text[:1000]
    if not insight:
        insight = text[1000:1500] if len(text) > 1000 else ""
    if not question:
        question = text[1500:1800] if len(text) > 1500 else ""
    
    # Count surreal connections as quality metric
    connections = sections.get("CONNEXIONS INATTENDUES", [])
    surrealism_score = len([c for c in connections if c.strip().startswith("-")])
    
    return {
        "title": title or "Rêve sans titre",
        "themes": extract_themes(text),
        "le_reve": le_reve[:1000],
        "insight": insight[:500],
        "question": question[:300],
        "sections": list(sections.keys()),
        "surrealism_score": surrealism_score,
    }


def generate_image_title(dream_title: str, image_format: str, index: int = 0) -> str:
    """Generate an artistic title for a dream image using LLM."""
    try:
        import requests
        from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
        resp = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{
                    "role": "system",
                    "content": """Tu es un artiste conceptuel. Donne un titre d'œuvre d'art (8-15 mots max) 
pour une image générée par IA à partir d'un rêve. Style: poétique, surréaliste, évocateur.
Format: "Titre — technique, année" comme dans une galerie. En français.
Réponds UNIQUEMENT avec le titre, rien d'autre."""
                }, {
                    "role": "user",
                    "content": f"Rêve: {dream_title}\nFormat image: {image_format}\nCrée un titre d'œuvre:"
                }],
                "temperature": 0.9,
                "max_tokens": 60,
            },
            timeout=15,
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip().strip('"')
    except Exception:
        return f"Songes n°{index+1} — {dream_title[:40]}"


def register_dream_from_file(dream_json_path: Path) -> dict:
    """Register a dream from its JSON file into the registry."""
    dream_data = json.loads(dream_json_path.read_text())
    date_str = dream_data.get("date", "")[:10]
    
    metadata = extract_dream_metadata(dream_data)
    
    # Find associated images
    images = []
    for ext in [".jpg", ".jpeg", ".png", ".svg", ".webp"]:
        img_path = IMAGES_DIR / f"dream_{date_str}{ext}"
        if img_path.exists():
            images.append({
                "format": ext.replace(".", ""),
                "path": str(img_path),
                "size_bytes": img_path.stat().st_size,
            })
    
    # Find associated oracle for same night
    oracles = list(ORACLES_DIR.glob(f"oracle_{date_str}_*.json"))
    oracle_topics = []
    for o in oracles[:5]:
        try:
            od = json.loads(o.read_text())
            oracle_topics.append(od.get("topic", "?"))
        except Exception:
            pass
    
    entry = {
        "id": hashlib.md5((date_str + metadata["title"]).encode()).hexdigest()[:12],
        "date": date_str,
        "title": metadata["title"],
        "seed": dream_data.get("seed"),
        "critique_turns": dream_data.get("critique_turns", 0),
        "themes": metadata["themes"],
        "surrealism_score": metadata["surrealism_score"],
        "insight": metadata["insight"],
        "question": metadata["question"],
        "images": images,
        "oracle_topics": oracle_topics,
        "dream_file": str(dream_json_path),
        "dream_preview": dream_data.get("dream_text", "")[:300] + "...",
    }
    
    return entry


def sync_registry():
    """Scan dreams directory and update registry with all dreams."""
    registry = load_registry()
    existing_ids = {d["id"] for d in registry["dreams"]}
    
    dream_files = sorted(DREAMS_DIR.glob("dream_*.json"))
    new_count = 0
    
    for df in dream_files:
        entry = register_dream_from_file(df)
        if entry["id"] not in existing_ids:
            registry["dreams"].insert(0, entry)  # Newest first
            new_count += 1
    
    registry["meta"]["total_dreams"] = len(registry["dreams"])
    registry["meta"]["last_sync"] = datetime.now().isoformat()
    
    save_registry(registry)
    print(f"[Registry] Synced: {new_count} new dream(s), {len(registry['dreams'])} total")
    
    # Auto-generate gallery
    generate_gallery(registry)
    
    return registry


def generate_gallery(registry: dict) -> Path:
    """Generate a beautiful HTML gallery of all dreams."""
    
    dreams_html = ""
    for i, dream in enumerate(registry["dreams"]):
        images = dream.get("images", [])
        img_tag = ""
        if images:
            # Prefer jpg over others
            best_img = next((i for i in images if i["format"] == "jpg"), images[0])
            img_path = best_img["path"]
            img_rel = str(Path(img_path).relative_to(BASE_DIR))
            art_title = best_img.get("art_title", dream["title"])
            img_tag = f'<figure><img src="../{img_rel}" alt="{art_title}" loading="lazy"><figcaption class="art-title">{art_title}</figcaption></figure>'
        
        themes_tags = " ".join(
            f'<span class="tag">{t}</span>' for t in dream.get("themes", [])
        )
        
        # Alternate left/right layout
        side = "left" if i % 2 == 0 else "right"
        
        dreams_html += f"""
        <article class="dream-entry {side}">
            <div class="dream-image">{img_tag}</div>
            <div class="dream-content">
                <span class="dream-number">#{i + 1}</span>
                <span class="dream-date">{dream['date']}</span>
                <h2>{dream['title']}</h2>
                <div class="themes">{themes_tags}</div>
                <blockquote class="insight">{dream.get('insight', '')}</blockquote>
                <p class="question">❓ {dream.get('question', '')}</p>
                <div class="meta-row">
                    <span>🌱 seed: {dream.get('seed', '?')}</span>
                    <span>🔄 {dream.get('critique_turns', 0)} critiques</span>
                    <span>🖼 {len(images)} image(s)</span>
                    {f"<span>🔮 {len(dream.get('oracle_topics', []))} oracles</span>" if dream.get('oracle_topics') else ""}
                </div>
            </div>
        </article>
        """
    
    total = registry["meta"]["total_dreams"]
    
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kate's Dream Registry — {total} Rêves Nocturnes</title>
    <style>
        :root {{
            --bg: #0a0a14;
            --card: #12122a;
            --text: #d4d4e8;
            --accent: #7c3aed;
            --accent2: #06b6d4;
            --muted: #666;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Georgia', 'Times New Roman', serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
        }}
        header {{
            text-align: center;
            padding: 60px 20px 40px;
            border-bottom: 1px solid #1a1a3a;
        }}
        header h1 {{ font-size: 2.5em; font-weight: normal; letter-spacing: 2px; }}
        header .subtitle {{ color: var(--accent2); font-size: 1.1em; margin-top: 8px; }}
        header .count {{ color: var(--muted); margin-top: 12px; font-family: monospace; }}
        
        .dream-entry {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            padding: 50px 80px;
            border-bottom: 1px solid #1a1a3a;
            align-items: center;
        }}
        .dream-entry.left .dream-image {{ order: 1; }}
        .dream-entry.left .dream-content {{ order: 2; }}
        .dream-entry.right .dream-image {{ order: 2; }}
        .dream-entry.right .dream-content {{ order: 1; }}
        
        .dream-image figure {{
            margin: 0;
            position: relative;
        }}
        .dream-image img {{
            width: 100%;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(124, 58, 237, 0.15);
            transition: transform 0.3s;
            display: block;
        }}
        .dream-image img:hover {{ transform: scale(1.02); }}
        .art-title {{
            text-align: center;
            font-style: italic;
            font-size: 0.85em;
            color: #94a3b8;
            margin-top: 10px;
            padding: 0 8px;
            letter-spacing: 0.5px;
        }}
        
        .dream-number {{
            font-family: monospace;
            color: var(--accent);
            font-size: 0.85em;
        }}
        .dream-date {{
            color: var(--muted);
            margin-left: 12px;
            font-family: monospace;
            font-size: 0.85em;
        }}
        .dream-content h2 {{
            font-size: 1.6em;
            font-weight: normal;
            margin: 10px 0;
            color: #fff;
        }}
        .themes {{ margin: 12px 0; }}
        .tag {{
            display: inline-block;
            background: rgba(124, 58, 237, 0.2);
            color: #a78bfa;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.8em;
            margin: 2px 4px 2px 0;
        }}
        .insight {{
            border-left: 3px solid var(--accent2);
            padding: 10px 20px;
            margin: 16px 0;
            color: #94a3b8;
            font-style: italic;
        }}
        .question {{ color: #f59e0b; margin: 10px 0; }}
        .meta-row {{
            margin-top: 16px;
            font-family: monospace;
            font-size: 0.8em;
            color: var(--muted);
        }}
        .meta-row span {{ margin-right: 16px; }}
        
        footer {{
            text-align: center;
            padding: 40px;
            color: var(--muted);
            font-size: 0.85em;
        }}
        
        @media (max-width: 768px) {{
            .dream-entry {{
                grid-template-columns: 1fr;
                padding: 30px 20px;
                gap: 20px;
            }}
            .dream-entry.right .dream-image {{ order: 1; }}
            .dream-entry.right .dream-content {{ order: 2; }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>🌙 Kate's Dream Registry</h1>
        <p class="subtitle">Rêves nocturnes générés par le Kate Night Engine</p>
        <p class="count">{total} rêve(s) enregistré(s) · Dernière sync: {registry['meta'].get('last_sync', 'N/A')[:16]}</p>
    </header>
    <main>
        {dreams_html}
    </main>
    <footer>
        <p>Kate Night Engine — Intégrant ARIS · Oneira · ERGODIC · MIRAI</p>
        <p>Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
    </footer>
</body>
</html>"""
    
    GALLERY_FILE.write_text(html)
    print(f"[Registry] Gallery generated: {GALLERY_FILE}")
    return GALLERY_FILE


if __name__ == "__main__":
    registry = sync_registry()
    print(json.dumps(registry["meta"], indent=2))
