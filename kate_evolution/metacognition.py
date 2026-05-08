#!/usr/bin/env python3
"""
Kate Méta-Cognition: Auto-évaluation des réponses.
Avant de délivrer une réponse finale, Kate s'auto-évalue sur:
- Complétude: ai-je répondu à TOUTES les questions?
- Confiance: suis-je sûr de ce que j'avance? (0-10)
- Vérification: devrais-je vérifier quelque chose avant de répondre?
- Amélioration: qu'est-ce qui pourrait être mieux?

Usage (intégré dans le flux de réponse):
  python3 metacognition.py --eval "question" "ma_reponse"
"""

import json, re, sys
from datetime import datetime


class MetaCognition:
    """Système d'auto-évaluation des réponses de Kate."""

    def __init__(self):
        pass

    def check_completeness(self, question, response):
        """Vérifie si la réponse couvre toutes les questions posées."""
        # Détecter les questions dans le message utilisateur
        question_markers = re.findall(r'[^.!?]*\?', question)
        task_markers = re.findall(
            r'(peux.tu|pourrais.tu|est.ce que|j\'aimerais|je voudrais|je veux|fais|créer?|génér|écris?|'
            r'trouve|cherche|analyse|vérifie|explique|montre|donne|prépare|envoie|'
            r'rappelle|programme|planifie|imagine|conçois)', 
            question, re.IGNORECASE
        )

        total_asks = len(question_markers) + len(task_markers)
        if total_asks == 0:
            return {"score": 10, "note": "Pas de question explicite détectée"}

        # Vérifier que la réponse n'est pas vide ou un simple accusé
        if len(response) < 50:
            return {"score": 3, "note": f"Réponse très courte pour {total_asks} demandes"}

        # Vérifier la présence de séparateurs ou structure dans la réponse
        has_structure = bool(re.search(r'[#\-•*📄✅❌🔴🟡]|\n\n', response))
        score = 8 if has_structure else 5
        if len(response) > 500:
            score = min(10, score + 2)
        
        return {
            "score": score, 
            "note": f"{total_asks} demande(s) détectée(s)" + 
                    (" — réponse structurée" if has_structure else " — réponse peu structurée")
        }

    def check_confidence(self, response):
        """Évalue le niveau de certitude exprimé dans la réponse."""
        # Marqueurs de confiance
        high_confidence = len(re.findall(
            r'\b(certain|sûr|garanti|définitivement|absolument|exact|précis)\b',
            response, re.IGNORECASE
        ))
        # Marqueurs d'incertitude
        low_confidence = len(re.findall(
            r'\b(peut-être|possible|probablement|il semble|je pense|je crois|'
            r'à vérifier|sous réserve|approximatif|environ|estim)\b',
            response, re.IGNORECASE
        ))
        # Marqueurs de vérification
        verification = len(re.findall(
            r'\b(vérifier|vérifie|vérifié|check|double.check|confirmer|valider)\b',
            response, re.IGNORECASE
        ))

        # Score de confiance : plus il y a de vérification, mieux c'est
        if verification > 0:
            score = 7
        elif high_confidence > 0 and low_confidence == 0:
            score = 8
        elif low_confidence > 0:
            score = 5
        else:
            score = 6

        flags = []
        if low_confidence > 2:
            flags.append("LOW_CONFIDENCE")
        if verification == 0 and len(response) > 200:
            flags.append("NO_VERIFICATION_MENTIONED")
        
        return {"score": score, "flags": flags}

    def check_actionability(self, response):
        """Vérifie si la réponse contient des actions concrètes."""
        has_actions = bool(re.search(
            r'\b(faire|faire|exécuter|lancer|ouvrir|envoyer|appeler|écrire|créer|'
            r'commencer|démarrer|vérifier|tester|déployer)\b',
            response, re.IGNORECASE
        ))
        has_next_steps = bool(re.search(
            r'(prochaine|étape|action|todo|next|suivant)',
            response, re.IGNORECASE
        ))
        score = 8 if (has_actions and has_next_steps) else (5 if has_actions else 3)
        return {"score": score, "actionable": has_actions}

    def evaluate(self, question, response):
        """Évaluation complète — retourne un rapport."""
        completeness = self.check_completeness(question, response)
        confidence = self.check_confidence(response)
        actionability = self.check_actionability(response)

        # Score global pondéré
        global_score = round(
            completeness["score"] * 0.4 + 
            confidence["score"] * 0.35 + 
            actionability["score"] * 0.25,
            1
        )

        all_flags = confidence.get("flags", [])
        if completeness["score"] < 5:
            all_flags.append("INCOMPLETE_RESPONSE")
        if actionability["score"] < 4:
            all_flags.append("NO_CLEAR_ACTIONS")

        recommendations = []
        if completeness["score"] < 6:
            recommendations.append("Vérifier si toutes les questions ont été traitées")
        if "NO_VERIFICATION_MENTIONED" in all_flags:
            recommendations.append("Ajouter une étape de vérification")
        if "LOW_CONFIDENCE" in all_flags:
            recommendations.append("Réduire le nombre d'incertitudes ou vérifier les faits")
        if actionability["score"] < 5:
            recommendations.append("Ajouter des actions concrètes ou prochaines étapes")

        return {
            "global_score": global_score,
            "grade": "A" if global_score >= 8 else ("B" if global_score >= 6 else ("C" if global_score >= 4 else "D")),
            "completeness": completeness,
            "confidence": confidence,
            "actionability": actionability,
            "flags": all_flags,
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat()
        }

    def inject(self, evaluation):
        """Format condensé pour injection pré-réponse."""
        e = evaluation
        base = f"[MetaCog|Score:{e['global_score']}/10|Grade:{e['grade']}"
        if e['flags']:
            base += f"|Flags:{','.join(e['flags'])}"
        if e['recommendations']:
            base += f"|Rec:{';'.join(e['recommendations'][:2])}"
        base += "]"
        return base


# ── CLI ──────────────────────────────────────────────────────
if __name__ == "__main__":
    mc = MetaCognition()
    args = sys.argv[1:]

    if "--inject" in args:
        idx = args.index("--inject")
        remaining = args[idx+1:]
        if len(remaining) >= 2:
            question, response = remaining[0], " ".join(remaining[1:])
        else:
            print("Usage: --inject 'question' 'reponse'")
            sys.exit(1)
        result = mc.evaluate(question, response)
        print(mc.inject(result))
    elif len(args) >= 2:
        question, response = args[0], " ".join(args[1:])
        result = mc.evaluate(question, response)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Usage: metacognition.py 'question' 'reponse'")
