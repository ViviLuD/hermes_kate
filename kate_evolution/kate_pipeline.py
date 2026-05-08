#!/usr/bin/env python3
"""
Kate Pipeline — Intégration S3 + MetaCog dans le flux de réponse.
Wrapper unifié qui:
1. Analyse le message entrant avec S3 (score d'attention)
2. Évalue la réponse sortante avec MetaCog (auto-évaluation)
3. Retourne un contexte injectable dans le prompt

Usage:
  python3 kate_pipeline.py --input "message de Benjamin"
  python3 kate_pipeline.py --full "message" "ma réponse"
"""

import json, sys, os

# Ajouter le dossier parent pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_attention import AttentionScorer
from metacognition import MetaCognition


class KatePipeline:
    """Pipeline unifié: S3 → Réponse → MetaCog."""

    def __init__(self):
        self.s3 = AttentionScorer()
        self.meta = MetaCognition()

    def analyze_input(self, text):
        """Analyse le message entrant et retourne le contexte S3."""
        score = self.s3.score(text)

        # Instructions comportementales basées sur le score
        instructions = []

        # Routing
        if score["routing"] == "S2_DEEP":
            instructions.append("Utiliser le raisonnement profond (S2)")
        else:
            instructions.append("Réponse rapide et concise (S1)")

        # Urgence
        if score["urgency"] >= 8:
            instructions.append("RÉPONDRE IMMÉDIATEMENT — situation critique")
        elif score["urgency"] >= 5:
            instructions.append("Priorité élevée — ne pas tarder")

        # Importance stratégique
        if score["importance"] >= 8:
            instructions.append("Sujet STRATÉGIQUE — aligner avec objectifs DELSOL")
        elif score["importance"] >= 5:
            instructions.append("Sujet important — traiter avec soin")

        # Émotion
        if score["emotion_valence"] == "negative" and score["emotion_intensity"] >= 5:
            instructions.append("Benjamin est négatif/frustré — répondre avec EMPATHIE et CALME")
        elif score["emotion_valence"] == "positive" and score["emotion_intensity"] >= 3:
            instructions.append("Benjamin est positif — ton énergique et dynamique")

        # État
        if score["benjamin_state"] == "stress":
            instructions.append("Benjamin est stressé — répondre de façon RASSURANTE, ALLÉGER la charge")
        elif score["benjamin_state"] == "energique":
            instructions.append("Benjamin est énergique — répondre avec DYNAMISME, proposer des actions")
        elif score["benjamin_state"] == "negatif":
            instructions.append("Benjamin est négatif — faire preuve d'EMPATHIE, ne pas contredire frontalement")

        return {
            "s3_score": score,
            "context_injection": self.s3.inject(score),
            "instructions": instructions
        }

    def evaluate_response(self, question, response):
        """Évalue la réponse avant envoi."""
        evaluation = self.meta.evaluate(question, response)
        meta_context = self.meta.inject(evaluation)

        # Décisions basées sur l'évaluation
        needs_revision = evaluation["global_score"] < 5
        warnings = []

        if evaluation["global_score"] < 4:
            warnings.append("⚠️ Réponse insuffisante — réviser avant envoi")
        elif evaluation["global_score"] < 6:
            warnings.append("⚡ Réponse acceptable — pourrait être améliorée")

        for rec in evaluation.get("recommendations", []):
            warnings.append(f"💡 {rec}")

        return {
            "evaluation": evaluation,
            "meta_injection": meta_context,
            "needs_revision": needs_revision,
            "warnings": warnings
        }

    def full_pipeline(self, user_message, my_response):
        """Pipeline complet: analyse input + évaluation output."""
        input_analysis = self.analyze_input(user_message)
        output_eval = self.evaluate_response(user_message, my_response)

        return {
            "input": input_analysis,
            "output": output_eval,
            "combined_context": (
                f"{input_analysis['context_injection']} | "
                f"{output_eval['meta_injection']}"
            )
        }


# ── CLI ──────────────────────────────────────────────────────
if __name__ == "__main__":
    pipeline = KatePipeline()

    if "--full" in sys.argv:
        idx = sys.argv.index("--full")
        if idx + 2 < len(sys.argv):
            msg = sys.argv[idx + 1]
            resp = sys.argv[idx + 2]
            result = pipeline.full_pipeline(msg, resp)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("Usage: --full 'message' 'reponse'")
    elif "--input" in sys.argv:
        idx = sys.argv.index("--input")
        if idx + 1 < len(sys.argv):
            msg = sys.argv[idx + 1]
            result = pipeline.analyze_input(msg)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("Usage: --input 'message'")
    else:
        # Mode par défaut: lire depuis stdin
        text = sys.stdin.read().strip()
        if text:
            result = pipeline.analyze_input(text)
            print(json.dumps(result, ensure_ascii=False, indent=2))
