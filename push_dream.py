#!/usr/bin/env python3
"""Push a specific dream to the GitHub gallery."""
import json, re, shutil, subprocess, os, sys
from pathlib import Path

DREAMS_DIR = Path("/opt/data/kate_night_engine/dreams")
IMAGES_DIR = Path("/opt/data/kate_night_engine/images")
GALLERY_DIR = Path("/opt/data/hermes_kate/dreams/gallery")
DATE_STR = sys.argv[1] if len(sys.argv) > 1 else "2026-05-25"

dream_file = DREAMS_DIR / f"dream_{DATE_STR}.json"
image_file = IMAGES_DIR / f"dream_{DATE_STR}.png"

if not dream_file.exists():
    print(f"No dream for {DATE_STR}")
    sys.exit(1)

# Parse dream
dream = json.loads(dream_file.read_text())
dream_text = dream.get("dream_text", "")

# Extract title
title_match = re.search(r'`([^`]+)`\s*(.*?)(?:\n|$)', dream_text)
dream_title = title_match.group(1) if title_match else "Untitled Dream"
subtitle = title_match.group(2).strip() if title_match else ""

# Metadata
seed = dream.get("seed", "N/A")
critique_turns = dream.get("critique_turns", "N/A")

# Extract body between LE RÊVE and next section
body_match = re.search(r'## LE RÊVE\n(.*?)(?=## ANTI-CONNEXIONS|## CONNEXIONS)', dream_text, re.DOTALL)
body = body_match.group(1).strip() if body_match else ""

# Extract anti-connections
anti_conn_match = re.search(r'## ANTI-CONNEXIONS AUTOPHAGES\n(.*?)(?=## ANTI-INSIGHT|$)', dream_text, re.DOTALL)
anti_conns = anti_conn_match.group(1).strip() if anti_conn_match else ""

# Extract insight
insight_match = re.search(r'## ANTI-INSIGHT.*?(.*?)(?=## QUESTION|$)', dream_text, re.DOTALL)
insight = insight_match.group(1).strip() if insight_match else ""

# Extract question
question_match = re.search(r'## QUESTION QUI S\'AUTO-BREVETTE\n(.*?)(?=⚠️|---|\Z)', dream_text, re.DOTALL)
question = question_match.group(1).strip() if question_match else ""

# Create gallery entry dir
entry_dir = GALLERY_DIR / DATE_STR
entry_dir.mkdir(parents=True, exist_ok=True)

# Copy image
if image_file.exists():
    shutil.copy2(image_file, entry_dir / "dream_visual.png")

# Build README
lines = [
    f"# Kate Dream Gallery — {DATE_STR}",
    f"## Dream Title: {dream_title}",
]
if subtitle:
    lines.append(f"**{subtitle}**\n")
else:
    lines.append("")
lines.extend(["---", ""])

# Image
if image_file.exists():
    lines.extend([f"![Dream Visual](dream_visual.png)", ""])

# Body
if body:
    lines.extend(["## Dream Narrative\n", body, ""])

# Anti-connections
if anti_conns:
    lines.extend(["## Anti-Connections Autophages\n", anti_conns, ""])

# Insight
if insight:
    lines.extend(["## Abyssal Insight\n", insight, ""])

# Question
if question:
    lines.extend(["## Question for the Impossible Matrix\n", question, ""])

# Metadata
lines.extend([
    "---",
    "## Dream Metadata",
    f"- **Date:** {DATE_STR}",
    f"- **Seed:** {seed}",
    f"- **Critique Turns:** {critique_turns}",
    "- **Visual:** Generated via Pollinations.ai",
])

# Series number
existing = sorted([d for d in GALLERY_DIR.glob("20*") if d.is_dir()])
series_num = len(existing) + 1
lines.append(f"- **Series:** Night Engine Dream #{series_num}")
lines.extend(["", "*Dream generated autonomously by Kate Night Engine*", ""])

(entry_dir / "README.md").write_text("\n".join(lines))
print(f"✅ Created gallery entry for {DATE_STR} ({dream_title})")

# Update index
entries = []
for d in sorted(GALLERY_DIR.glob("20*"), reverse=True):
    if not d.is_dir():
        continue
    rd = d / "README.md"
    title = "Untitled"
    if rd.exists():
        m = re.search(r"Dream Title: (.+)", rd.read_text())
        if m:
            title = m.group(1)
    entries.append((d.name, title))

idx_lines = [
    "# Kate Dream Gallery\n",
    "A curated gallery of Kate's autonomous night dreams.\n",
    "| Date | Dream Title |\n|------|-------------|",
]
for ds, t in entries:
    idx_lines.append(f"| [{ds}](gallery/{ds}/) | {t} |")

idx_lines.extend(["\n---\n", "*Updated by Kate Night Engine*", ""])
(GALLERY_DIR / "README.md").write_text("\n".join(idx_lines))
print(f"✅ Gallery index updated ({len(entries)} entries)")

# Git commit and push
os.chdir("/opt/data/hermes_kate")
subprocess.run(["git", "add", "-A"], check=True)
subprocess.run(
    ["git", "commit", "-m", f"feat(dreams): add gallery entry for {DATE_STR} ({dream_title})"],
    capture_output=True, text=True, check=True
)
result = subprocess.run(
    ["git", "push", "origin", "night-engine"],
    capture_output=True, text=True, timeout=60
)
if result.returncode == 0:
    print(f"✅ Pushed to GitHub (night-engine branch)")
else:
    print(f"❌ Push failed: {result.stderr[:300]}")
