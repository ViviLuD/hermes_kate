#!/usr/bin/env python3
"""
Push the latest dream to the hermes_kate GitHub repo (night-engine branch).
Runs daily after the morning brief (after 06:35).

Process:
1. Check if today's dream exists
2. Read dream JSON
3. Parse dream text for gallery elements
4. Create/update gallery folder with README.md + image
5. Commit and push to night-engine branch
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, date
from pathlib import Path

# Paths
NIGHT_ENGINE_DIR = Path("/opt/data/kate_night_engine")
GIT_REPO_DIR = Path("/root/hermes_kate")
DREAMS_DIR = NIGHT_ENGINE_DIR / "dreams"
IMAGES_DIR = NIGHT_ENGINE_DIR / "images"
ORACLES_DIR = NIGHT_ENGINE_DIR / "oracles"
GALLERY_DIR = GIT_REPO_DIR / "dreams" / "gallery"

# Git config
TOKEN = None
with open("/root/.git-credentials") as f:
    match = re.search(r'https://[^:]+:([^@]+)@github\.com', f.read())
    if match:
        TOKEN = match.group(1)


def get_today():
    """Get today's date string YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def get_oracle_summaries(date_str):
    """Extract summaries from today's oracle files."""
    oracles = []
    for f in sorted(ORACLES_DIR.glob(f"oracle_{date_str}_*.json")):
        try:
            data = json.loads(f.read_text())
            topic = data.get("topic", f.stem.replace(f"oracle_{date_str}_", ""))
            synthesis = data.get("synthesis", data.get("executive_summary", ""))
            forecasts = data.get("forecasts", data.get("predictions", []))
            summary = synthesis[:500] if synthesis else ""
            
            # Extract top predictions
            predictions_list = []
            if isinstance(forecasts, list):
                for fc in forecasts[:3]:
                    if isinstance(fc, dict):
                        text = str(list(fc.values()))[:200] if fc.values() else ""
                        predictions_list.append(text)
            
            oracles.append({
                "topic": topic,
                "summary": summary,
                "predictions": predictions_list
            })
        except Exception as e:
            print(f"  ⚠️ Error reading oracle {f.name}: {e}")
    return oracles


def create_gallery_entry(date_str):
    """Create/update a gallery entry for a specific date."""
    dream_file = DREAMS_DIR / f"dream_{date_str}.json"
    image_file = IMAGES_DIR / f"dream_{date_str}.png"
    svg_file = IMAGES_DIR / f"dream_{date_str}.svg"
    
    if not dream_file.exists():
        print(f"  ❌ No dream found for {date_str}")
        return False
    
    # Create gallery folder
    gallery_entry_dir = GALLERY_DIR / date_str
    gallery_entry_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse dream
    dream = json.loads(dream_file.read_text())
    dream_text = dream.get("dream_text", "")
    
    # Extract title
    title_match = re.search(r'`([^`]+)`\s*(.*?)(?:\n|$)', dream_text)
    dream_title = title_match.group(1) if title_match else "Untitled Dream"
    subtitle = title_match.group(2).strip() if title_match else ""
    
    # Extract noise preview
    noise = dream.get("noise_preview", "")
    seed = dream.get("seed", "N/A")
    critique_turns = dream.get("critique_turns", "N/A")
    
    # Extract gallery elements
    elements = []
    conn_match = re.search(r"## CONNEXIONS IMPOSSIBLES(.*?)(?=##|$)", dream_text, re.DOTALL)
    if conn_match:
        conn_text = conn_match.group(1)
        for line in conn_text.strip().split("\n"):
            line = line.strip().strip("- ").strip()
            if line:
                parts = line.split("—", 1)
                if len(parts) == 2:
                    elements.append((parts[0].strip(), parts[1].strip()))
                else:
                    elements.append((line, ""))
    
    # Extract insight
    insight_match = re.search(r"## INSIGHT VÉRITABLEMENT ABYSSAL(.*?)(?=##|$)", dream_text, re.DOTALL)
    insight = insight_match.group(1).strip() if insight_match else ""
    
    # Extract question
    question_match = re.search(r"## QUESTION(.*?)(?=##|$)", dream_text, re.DOTALL)
    question = question_match.group(1).strip() if question_match else ""
    
    # Get oracles
    oracles = get_oracle_summaries(date_str)
    
    # Copy image
    image_path = None
    if image_file.exists():
        dest_img = gallery_entry_dir / "dream_visual.png"
        shutil.copy2(image_file, dest_img)
        image_path = "dream_visual.png"
    elif svg_file.exists():
        dest_svg = gallery_entry_dir / "dream_visual.svg"
        shutil.copy2(svg_file, dest_svg)
        image_path = "dream_visual.svg"
    
    # Create README
    readme_lines = [
        f"# Kate Dream Gallery — {date_str}\n",
        f"## Dream Title: {dream_title}",
    ]
    if subtitle:
        readme_lines.append(f"**{subtitle}**\n")
    else:
        readme_lines.append("")
    
    readme_lines.append("---\n")
    
    if image_path:
        readme_lines.append(f"## Image\n")
        readme_lines.append(f"![Dream Visual]({image_path})\n")
    
    # Dream narrative
    readme_lines.append("## Dream Narrative\n")
    
    # Extract the main dream body (between title and next section)
    body_match = re.search(r"## LE RÊVE\n(.*?)(?=## CONNEXIONS|## INSIGHT|## QUESTION)", dream_text, re.DOTALL)
    if body_match:
        body = body_match.group(1).strip()
        readme_lines.append(body + "\n")
    
    # Gallery elements table
    if elements:
        readme_lines.append("## Gallery Elements\n")
        readme_lines.append("| Element | Description |")
        readme_lines.append("|---------|-------------|")
        for name, desc in elements:
            readme_lines.append(f"| {name} | {desc} |")
        readme_lines.append("")
    
    # Insight
    if insight:
        readme_lines.append("## Abyssal Insight\n")
        readme_lines.append(insight + "\n")
    
    # Question
    if question:
        readme_lines.append("## Question for the Impossible Matrix\n")
        readme_lines.append(question + "\n")
    
    # Oracles
    if oracles:
        readme_lines.append("## Oracle Predictions\n")
        for o in oracles:
            topic_clean = o["topic"].replace("_", " ").title()
            readme_lines.append(f"### {topic_clean}\n")
            if o["summary"]:
                readme_lines.append(o["summary"][:400] + "\n")
            if o["predictions"]:
                for p in o["predictions"]:
                    if p:
                        readme_lines.append(f"- {p[:150]}")
            readme_lines.append("")
    
    # Metadata
    readme_lines.append("---\n")
    readme_lines.append("## Dream Metadata\n")
    readme_lines.append(f"- **Date:** {dream.get('date', date_str)}")
    readme_lines.append(f"- **Seed:** {seed}")
    readme_lines.append(f"- **Critique Turns:** {critique_turns}")
    readme_lines.append(f"- **Visual:** Generated via Pollinations.ai")
    
    # Count existing gallery entries for series number
    existing = sorted(GALLERY_DIR.glob("20*"))
    try:
        series_num = existing.index(gallery_entry_dir) + 1
    except ValueError:
        series_num = len(existing) + 1
    readme_lines.append(f"- **Series:** Night Engine Dream #{series_num}")
    
    if dream.get("context_summary"):
        readme_lines.append(f"\n*{dream['context_summary'][:200]}*")
    
    readme_lines.append("")
    
    # Write README
    (gallery_entry_dir / "README.md").write_text("\n".join(readme_lines))
    print(f"  ✅ Gallery entry created for {date_str}")
    return True


def update_gallery_index(date_str):
    """Update the gallery index page with the latest entry."""
    index_file = GALLERY_DIR / "README.md"
    
    # Collect all gallery entries
    entries = []
    for entry_dir in sorted(GALLERY_DIR.glob("20*"), reverse=True):
        readme = entry_dir / "README.md"
        if readme.exists():
            # Extract title
            content = readme.read_text()
            title_match = re.search(r"Dream Title: (.+)", content)
            title = title_match.group(1) if title_match else "Untitled"
            entries.append((entry_dir.name, title))
    
    if not entries:
        return False
    
    lines = [
        "# Kate Dream Gallery\n",
        "A curated gallery of Kate's autonomous night dreams. Each entry includes the full dream narrative, AI-generated visual, and accompanying oracle predictions.\n",
        "## Dreams\n",
        "| Date | Dream Title | Visual |",
        "|------|-------------|--------|",
    ]
    
    for date_str, title in entries:
        preview = f"dreams/gallery/{date_str}/dream_visual.png"
        line = f"| [{date_str}](gallery/{date_str}/) | {title} | ![Preview]({preview}) |"
        lines.append(line)
    
    lines.append("\n---\n")
    lines.append("*Updated nightly by Kate Night Engine*\n")
    
    index_file.write_text("\n".join(lines))
    print(f"  ✅ Gallery index updated with {len(entries)} entries")
    return True


def git_push():
    """Commit and push to GitHub."""
    if not TOKEN:
        print("  ❌ No GitHub token found")
        return False
    
    try:
        os.chdir(str(GIT_REPO_DIR))
        
        # Check for changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, check=False
        )
        if not result.stdout.strip():
            print("  ℹ️ No changes to commit")
            return True
        
        # Add all files
        subprocess.run(["git", "add", "-A"], check=True)
        
        # Commit
        date_str = get_today()
        subprocess.run(
            ["git", "commit", "-m", f"feat(dreams): add nightly dream gallery ({date_str})"],
            check=True
        )
        
        # Set remote with token and push
        subprocess.run([
            "git", "remote", "set-url", "origin",
            f"https://ViviLuD:{TOKEN}@github.com/ViviLuD/hermes_kate.git"
        ], check=True)
        
        result = subprocess.run(
            ["git", "push", "origin", "night-engine"],
            capture_output=True, text=True, check=False, timeout=60
        )
        
        if result.returncode == 0:
            print(f"  ✅ Pushed to night-engine branch")
            return True
        else:
            print(f"  ❌ Push failed: {result.stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  ❌ Push timed out")
        return False
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Git error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Main entry point — push latest dream to GitHub gallery."""
    date_str = get_today()
    print(f"🌙 Night Engine GitHub Pusher — {date_str}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    print(f"\n📝 Creating gallery entry for {date_str}...")
    if create_gallery_entry(date_str):
        print(f"\n📇 Updating gallery index...")
        update_gallery_index(date_str)
        
        print(f"\n📤 Pushing to GitHub...")
        if git_push():
            print(f"\n✅ Success! Dream for {date_str} is now live on GitHub.")
        else:
            print(f"\n⚠️ Gallery entry created but push failed.")
    else:
        print(f"\nℹ️ No dream found for {date_str}. Nothing to push.")


if __name__ == "__main__":
    main()
