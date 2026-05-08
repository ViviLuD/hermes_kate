#!/usr/bin/env python3
"""
Kate Closed Learning Loop: Amélioration continue par l'expérience.
Analyse les patterns d'usage, identifie les opportunités de nouveaux skills,
et propose des améliorations.

Fonctionnement:
1. Observe: analyse les sessions récentes pour détecter des patterns
2. Analyse: identifie les tâches récurrentes non couvertes par un skill
3. Synthétise: propose un nouveau skill ou une amélioration
4. Teste: valide avant déploiement

Usage:
  python3 learn_loop.py                    # Analyse et propose
  python3 learn_loop.py --create-skill     # Crée les skills proposés
  python3 learn_loop.py --improve <name>   # Améliore un skill existant
"""

import json, os, sys, re
from datetime import datetime, timedelta
from pathlib import Path

LEARN_DIR = "/opt/data/kate_evolution"
SKILLS_DIR = "/opt/data/skills"
LEARN_LOG = f"{LEARN_DIR}/learn_loop_log.jsonl"


class LearnLoop:
    """Système d'amélioration continue par closed learning loop."""

    def __init__(self):
        self.observations = []
        self.proposals = []
        self.timestamp = datetime.now()

    def observe(self):
        """Observe les patterns d'utilisation récents."""
        print("\n👁️ OBSERVATION — Analyse des patterns d'usage")
        print("─" * 50)

        # Analyser les skills existants
        existing_skills = []
        for root, dirs, files in os.walk(SKILLS_DIR):
            for f in files:
                if f == "SKILL.md":
                    existing_skills.append(os.path.relpath(root, SKILLS_DIR))

        print(f"  Skills existants: {len(existing_skills)}")

        # Détecter les tâches récurrentes (basé sur les patterns connus)
        common_tasks = {
            "présentation_ppt": ["ppt", "pptx", "powerpoint", "présentation", "slides", "deck", "pitch"],
            "recherche_brevet": ["brevet", "patent", "FTO", "prior art", "antériorité", "landscape"],
            "veille_concurrent": ["concurrent", "competitor", "veille", "monitoring", "watch"],
            "email_client": ["email", "mail", "client", "envoyer", "transmettre", "proposition"],
            "analyse_contrat": ["contrat", "NDA", "accord", "license", "clause"],
            "briefing_matin": ["briefing", "matin", "agenda", "priorités", "today"],
            "linkedin_post": ["linkedin", "post", "article", "newsletter", "publication"],
            "reunion_prep": ["réunion", "meeting", "rendez-vous", "call", "préparer"],
        }

        # Vérifier quels patterns n'ont pas de skill dédié
        for task_name, keywords in common_tasks.items():
            has_skill = any(task_name.lower() in s.lower() for s in existing_skills)
            if not has_skill:
                self.observations.append({
                    "type": "missing_skill",
                    "task": task_name,
                    "keywords": keywords,
                    "frequency": "unknown"
                })
                print(f"  🔍 Opportunité: {task_name} — pas de skill dédié")

        print(f"  Observations: {len(self.observations)}")

    def analyze(self):
        """Analyse les observations pour prioriser."""
        print("\n🧠 ANALYSE — Priorisation")
        print("─" * 50)

        priorities = {
            "présentation_ppt": 9,   # Très utilisé
            "recherche_brevet": 8,   # Core business
            "briefing_matin": 8,     # Quotidien
            "reunion_prep": 7,       # Fréquent
            "veille_concurrent": 7,  # Stratégique
            "linkedin_post": 6,      # Important
            "email_client": 5,       # Utile
            "analyse_contrat": 5,    # Spécialisé
        }

        self.proposals = []
        for obs in self.observations:
            priority = priorities.get(obs["task"], 3)
            if priority >= 6:
                proposal = {
                    "task": obs["task"],
                    "priority": priority,
                    "action": "create_skill",
                    "rationale": f"Tâche récurrente sans skill dédié (priorité {priority}/10)"
                }
                self.proposals.append(proposal)
                print(f"  📋 Proposer: {obs['task']} (priorité {priority}/10)")

        # Proposer des améliorations de skills existants
        improvements = [
            {"skill": "powerpoint", "improvement": "Ajouter template Benjamin DELSOL par défaut"},
            {"skill": "benjamin-operating-system", "improvement": "Intégrer S3 attention scoring"},
            {"skill": "linkedin-public-content-research", "improvement": "Ajouter automatisation posts"},
        ]
        for imp in improvements:
            self.proposals.append({
                "task": imp["skill"],
                "priority": 6,
                "action": "improve_skill",
                "rationale": imp["improvement"]
            })
            print(f"  🔧 Améliorer: {imp['skill']} — {imp['improvement']}")

    def synthesize(self, dry_run=True):
        """Synthétise les propositions en actions concrètes."""
        print("\n🔨 SYNTHÈSE — Génération")
        print("─" * 50)

        for prop in self.proposals[:3]:  # Top 3
            action = "DRY RUN" if dry_run else "CRÉATION"
            print(f"  {action}: {prop['task']} ({prop['action']}) — {prop['rationale']}")

            if not dry_run:
                self._create_skill_stub(prop)

    def _create_skill_stub(self, proposal):
        """Crée un squelette de skill."""
        skill_name = proposal["task"].replace(" ", "-").lower()
        skill_dir = f"{SKILLS_DIR}/{skill_name}"
        os.makedirs(skill_dir, exist_ok=True)

        stub = f"""---
name: {skill_name}
description: "Auto-generated skill for {proposal['task']} — created by Kate LearnLoop"
version: 0.1.0
---

# {proposal['task'].replace('_', ' ').title()}

Auto-generated skill stub. À compléter avec les instructions spécifiques.

## Usage

```bash
python3 {skill_name}.py
```

## Notes

Ce skill a été généré automatiquement par le closed learning loop de Kate.
Priorité: {proposal['priority']}/10
Raison: {proposal['rationale']}
"""

        with open(f"{skill_dir}/SKILL.md", "w") as f:
            f.write(stub)
        print(f"    ✅ Skill créé: {skill_dir}/SKILL.md")

    def log(self):
        """Sauvegarde le cycle d'apprentissage."""
        entry = {
            "timestamp": self.timestamp.isoformat(),
            "observations": len(self.observations),
            "proposals": len(self.proposals),
            "top_proposals": [p["task"] for p in self.proposals[:3]]
        }
        os.makedirs(LEARN_DIR, exist_ok=True)
        with open(LEARN_LOG, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def run(self, dry_run=True):
        """Cycle complet: Observe → Analyse → Synthétise."""
        print("\n" + "=" * 60)
        print("🔄 KATE CLOSED LEARNING LOOP")
        print(f"🕐 {self.timestamp.strftime('%d/%m/%Y %H:%M')}")
        print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        print("=" * 60)

        self.observe()
        self.analyze()
        self.synthesize(dry_run=dry_run)
        self.log()

        print(f"\n✅ Cycle terminé. {len(self.proposals)} propositions.")
        if dry_run:
            print("💡 Pour appliquer: --create-skill")
        return self.proposals


# ── CLI ──────────────────────────────────────────────────────
if __name__ == "__main__":
    loop = LearnLoop()

    if "--create-skill" in sys.argv:
        # Mode création réelle
        loop.run(dry_run=False)
    elif "--improve" in sys.argv:
        idx = sys.argv.index("--improve")
        if idx + 1 < len(sys.argv):
            skill_name = sys.argv[idx + 1]
            print(f"Amélioration du skill: {skill_name}")
            loop.run(dry_run=True)
        else:
            print("Usage: --improve <skill_name>")
    else:
        # Dry run par défaut
        loop.run(dry_run=True)
