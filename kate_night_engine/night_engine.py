#!/usr/bin/env python3
"""
Kate Night Engine — Main Orchestrator
════════════════════════════════════

Cron-driven nighttime autonomous work system for Kate (Hermes Agent).
Integrates patterns from:
  - ARIS (Auto-Research-In-Sleep): autonomous overnight loops
  - Oneira: dream pipeline (context → synthesis → visual → delivery)
  - ERGODIC: noise-driven creative divergence
  - MIRAI: calibrated forecasting with adversarial review

Schedule (configurable):
  02:00 — Dream Mode: creative exploration with noise seeds
  03:00 — Oracle Mode: predictive extrapolation on strategic topics
  06:30 — Morning Brief: compiled results delivered to Benjamin

Usage:
  python night_engine.py dream      # Run dream mode only
  python night_engine.py oracle     # Run oracle mode only
  python night_engine.py brief      # Compose morning brief only
  python night_engine.py all        # Run everything (for cron)
  python night_engine.py cron       # Setup crontab
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    DREAMS_DIR, ORACLES_DIR, IMAGES_DIR, LOGS_DIR, MEMORY_DIR,
    DREAM_HOUR, ORACLE_HOUR, BRIEF_HOUR,
)
from dream_mode import run_dream_mode
from oracle_mode import run_all_oracles
from dream_image import generate_dream_image, generate_fallback_visual
from morning_brief import compose_morning_brief, load_latest_dream, load_latest_image


# === Logging ===
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / f"night_engine_{datetime.now().strftime('%Y-%m-%d')}.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("night_engine")


def log_step(message: str):
    """Log and print a step marker."""
    log.info(message)
    print(f"[NightEngine] {message}")


def run_dream_with_image():
    """Run dream mode and generate an image from the dream."""
    log_step("🌙 Starting Dream Mode...")
    
    try:
        dream_data = run_dream_mode()
        title = dream_data.get("title", "Rêve")
        dream_text = dream_data["dream_text"]
        
        log_step("🎨 Generating dream image...")
        try:
            image_path = generate_dream_image(dream_text, title)
            if not image_path:
                image_path = generate_fallback_visual(dream_text, title)
                log_step(f"⚠️  Using fallback image: {image_path}")
            else:
                log_step(f"✅ Dream image saved: {image_path}")
        except Exception as e:
            log.warning(f"Image generation failed: {e}")
            image_path = generate_fallback_visual(dream_text, title)
            log_step(f"⚠️  Using fallback image: {image_path}")
        
        return dream_data, image_path
        
    except Exception as e:
        log.error(f"Dream mode failed: {e}")
        return None, None


def run_all_oracle_predictions():
    """Run oracle mode for all topics."""
    log_step("🔮 Starting Oracle Mode...")
    try:
        results = run_all_oracles()
        log_step(f"✅ Oracle complete: {len(results)} topics")
        return results
    except Exception as e:
        log.error(f"Oracle mode failed: {e}")
        return []


def deliver_morning_brief():
    """Generate and save morning brief. The cron runner handles Telegram delivery."""
    log_step("📋 Composing Morning Brief...")
    try:
        brief_text, image_path = compose_morning_brief()
        log_step(f"✅ Morning brief ready ({len(brief_text)} chars)")
        
        # Save brief metadata for cron runner
        meta = {
            "timestamp": datetime.now().isoformat(),
            "brief_text": brief_text,
            "image_path": str(image_path) if image_path else None,
        }
        (MEMORY_DIR / "latest_brief.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
        
        print("\n" + "="*70)
        print(brief_text)
        print("="*70)
        if image_path:
            print(f"\n📸 Image: {image_path}")
        
        return brief_text, image_path
    except Exception as e:
        log.error(f"Brief composition failed: {e}")
        return None, None


def run_all():
    """Run the complete night sequence: dream → oracle → brief."""
    log_step("══════ KATE NIGHT ENGINE STARTING ══════")
    log_step(f"Time: {datetime.now().isoformat()}")
    
    # 1. Dream Mode
    dream_data, image_path = run_dream_with_image()
    
    # Sync dream registry
    try:
        from dream_registry import sync_registry
        sync_registry()
    except Exception as e:
        log.warning(f"Registry sync failed (non-critical): {e}")
    
    # 2. Oracle Mode
    oracle_results = run_all_oracle_predictions()
    
    # 3. Morning Brief
    brief_text, brief_image = deliver_morning_brief()
    
    log_step("══════ KATE NIGHT ENGINE COMPLETE ══════")
    
    results = {
        "dream": dream_data is not None,
        "dream_title": dream_data.get("title", "N/A") if dream_data else "FAILED",
        "oracles": len(oracle_results),
        "brief": brief_text is not None,
        "image": str(image_path) if image_path else None,
    }
    
    (MEMORY_DIR / "last_run.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    return results


def setup_cron():
    """Print cron setup instructions."""
    script_path = Path(__file__).resolve()
    engine_dir = Path(__file__).parent
    
    cron_lines = f"""
# Kate Night Engine — Autonomous Night Work
# Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}
# To install: crontab -e and paste these lines

# Dream Mode — 2:00 AM Paris time
0 2 * * * cd {engine_dir} && {sys.executable} {script_path} dream >> {LOGS_DIR}/cron_dream.log 2>&1

# Oracle Mode — 3:00 AM Paris time
0 3 * * * cd {engine_dir} && {sys.executable} {script_path} oracle >> {LOGS_DIR}/cron_oracle.log 2>&1

# Morning Brief Delivery — 6:30 AM Paris time
30 6 * * * cd {engine_dir} && {sys.executable} {script_path} brief >> {LOGS_DIR}/cron_brief.log 2>&1
"""
    
    print(cron_lines)
    
    cron_file = MEMORY_DIR / "crontab.txt"
    cron_file.write_text(cron_lines)
    print(f"Cron config saved to: {cron_file}")
    print("\nTo install: crontab {cron_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nCommands: dream | oracle | brief | all | cron")
        sys.exit(0)
    
    cmd = sys.argv[1].lower()
    
    if cmd == "dream":
        run_dream_with_image()
    elif cmd == "oracle":
        run_all_oracle_predictions()
    elif cmd == "brief":
        deliver_morning_brief()
    elif cmd == "all":
        run_all()
    elif cmd == "cron":
        setup_cron()
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: dream | oracle | brief | all | cron")
        sys.exit(1)
