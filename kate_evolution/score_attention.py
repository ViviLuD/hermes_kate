#!/usr/bin/env python3
"""
Kate Mini-S3: Score d'Attention — Module de modulation cognitive.
Évalue urgence, importance, émotion, complexité. Route S1 (rapide) ou S2 (profond).
Détecte l'état émotionnel de Benjamin pour adapter le ton de la réponse.

Usage:
  python3 score_attention.py "message texte"
  echo "message" | python3 score_attention.py
  python3 score_attention.py --inject "message"  # format condensé pour contexte
"""

import json, re, sys
from datetime import datetime

# ── Pattern libraries ─────────────────────────────────────────
URGENCY = {
    "immediate": [
        r"urgent", r"immédiat", r"maintenant", r"tout de suite", r"appelle",
        r"crise", r"d'urgence", r"asap", r"problème", r"bloqu", r"down",
        r"panne", r"plantage", r"erreur critique", r"ne fonctionne plus",
        r"ne marche plus", r"cassé", r"besoin d'aide", r"aide moi",
        r"stp", r"s'il te plaît", r"s'il vous plaît", r"vite", r"dépêche",
        r"dans \d+ minutes", r"dans \d+ min", r"\d+min", r"tout de suite",
        r"perdu", r"volé", r"attaque", r"piraté", r"hack"
    ],
    "soon": [
        r"aujourd'hui", r"ce matin", r"cet après-midi", r"ce soir",
        r"d'ici", r"avant", r"délai", r"deadline", r"échéance",
        r"rappelle", r"n'oublie pas", r"pense à", r"bientôt",
        r"demain", r"cette semaine", r"semaine prochaine",
        r"dans \d+ heures", r"dans \d+ jours"
    ]
}

IMPORTANCE = {
    "strategic": [
        r"stratég", r"client", r"contrat", r"brevet", r"\bIP\b", r"\bip\b",
        r"FTO", r"fto", r"valorisation", r"investis", r"funding", r"levée",
        r"Qnity", r"qnity", r"QUADELA", r"quadela", r"DELSOL", r"delsol",
        r"Étienne", r"Etienne", r"étienne", r"etienne", r"ABER", r"aber",
        r"offre", r"proposition", r"pitch", r"deck", r"présentation",
        r"intangible", r"quantum", r"DeepTech", r"deeptech",
        r"souveraineté", r"moat", r"valuation", r"licensing",
        r"investisseur", r"investor", r"due dilig", r"audit",
        r"portefeuille", r"portfolio", r"propriété intellectuelle",
        r"intellectual property", r"trade secret", r"secret d'affaires",
        r"open source", r"opensource", r"innovation", r"startup",
        r"Magali", r"Rémi", r"Singapour", r"INTA", r"Hautier"
    ],
    "tactical": [
        r"tâche", r"action", r"rappel", r"document", r"fichier",
        r"email", r"mail", r"calendrier", r"réunion", r"meeting",
        r"appel", r"call", r"téléphone", r"NDA", r"nda",
        r"envoyer", r"transmettre", r"partager", r"préparer",
        r"message", r"note", r"compte-rendu", r"cr", r"rapport",
        r"pdf", r"PPTX", r"pptx", r"powerpoint"
    ]
}

EMOTION = {
    "positive": [
        r"merci", r"génial", r"parfait", r"excellent", r"super",
        r"thanks", r"thank you", r"good", r"great", r"awesome",
        r"bravo", r"bien joué", r"top", r"cool", r"nice",
        r"j'adore", r"j'aime", r"magnifique", r"formidable",
        r"heureux", r"content", r"ravi", r"impressionn"
    ],
    "negative": [
        r"problème", r"erreur", r"faux", r"mauvais", r"nul",
        r"déçu", r"inquiet", r"stress", r"stressé", r"énervé",
        r"agacé", r"colère", r"fatigué", r"épuisé", r"dépassé",
        r"pas bon", r"ne convient pas", r"ne va pas", r"bof",
        r"désolé", r"pardon", r"je m'excuse", r"inquiétant",
        r"peur", r"angoissé", r"triste", r"déprimé", r"frustr"
    ]
}

COMPLEXITY = {
    "high": [
        r"architecture", r"concevoir", r"créer", r"développer", r"build",
        r"imaginer", r"recherche", r"analys", r"implémenter",
        r"code", r"script", r"programme", r"système", r"plateforme",
        r"plusieurs", r"tous", r"chaque", r"entière", r"complet",
        r"transformer", r"construire", r"évolution", r"réplication",
        r"mémoire", r"cognition", r"swarm", r"learning"
    ],
    "medium": [
        r"modifier", r"changer", r"ajouter", r"améliorer",
        r"corriger", r"fixer", r"réparer", r"optimiser"
    ]
}

BENJAMIN_STATE = {
    "stress": [r"stress", r"inquiet", r"dépassé", r"chargé", r"fatigué", r"épuisé", r"surchargé"],
    "energique": [r"génial", r"super", r"excellent", r"parfait", r"allons-y", r"fonce", r"top", r"idée", r"inspir"],
    "negatif": [r"déçu", r"pas bon", r"nul", r"énervé", r"agacé", r"ne convient pas", r"frustr"],
    "collaboratif": [r"peux-tu", r"peux tu", r"est-ce que", r"pourrais-tu", r"j'aimerais", r"j aimerais", r"je voudrais"],
}


class AttentionScorer:
    def __init__(self):
        self.s2_threshold = 5  # Route vers S2 si un score >= 5

    def _count_matches(self, text_lower, patterns):
        return sum(1 for p in patterns if re.search(p, text_lower))

    def score_urgency(self, text):
        imm = self._count_matches(text, URGENCY["immediate"])
        soon = self._count_matches(text, URGENCY["soon"])
        return min(10, round(imm * 2.5 + soon * 1.2, 1))

    def score_importance(self, text):
        strat = self._count_matches(text, IMPORTANCE["strategic"])
        tact = self._count_matches(text, IMPORTANCE["tactical"])
        return min(10, round(strat * 2.0 + tact * 0.8, 1))

    def score_emotion(self, text):
        pos = self._count_matches(text, EMOTION["positive"])
        neg = self._count_matches(text, EMOTION["negative"])
        intensity = min(10, (pos + neg) * 2)
        if pos > neg:
            valence = "positive"
        elif neg > pos:
            valence = "negative"
        else:
            valence = "neutral"
        return {"intensity": intensity, "valence": valence}

    def score_complexity(self, text):
        high = self._count_matches(text, COMPLEXITY["high"])
        med = self._count_matches(text, COMPLEXITY["medium"])
        score = min(10, round(high * 2.0 + med * 1.0, 1))
        words = len(text.split())
        if words > 200:
            score = min(10, score + 3)
        elif words > 100:
            score = min(10, score + 1.5)
        elif words > 50:
            score = min(10, score + 0.5)
        return score

    def detect_state(self, text):
        scores = {}
        for state, patterns in BENJAMIN_STATE.items():
            scores[state] = self._count_matches(text, patterns)
        if any(scores.values()):
            return max(scores, key=scores.get)
        return "neutre"

    def score(self, text):
        """Score complet — retourne un dict."""
        t = text.lower()
        urgency = self.score_urgency(t)
        importance = self.score_importance(t)
        emotion = self.score_emotion(t)
        complexity = self.score_complexity(t)
        state = self.detect_state(t)

        attention = round(
            urgency * 0.35 + importance * 0.30 + complexity * 0.20 + emotion["intensity"] * 0.15, 1
        )

        route_s2 = any(x >= self.s2_threshold for x in [urgency, importance, complexity, emotion["intensity"]])

        flags = []
        if urgency >= 8: flags.append("CRITICAL_URGENCY")
        if importance >= 8: flags.append("STRATEGIC_PRIORITY")
        if emotion["valence"] == "negative" and emotion["intensity"] >= 5: flags.append("EMOTIONAL_SUPPORT")
        if state == "stress": flags.append("BENJAMIN_STRESSED")
        if state == "energique": flags.append("BENJAMIN_ENERGIZED")
        if state == "negatif": flags.append("BENJAMIN_NEGATIVE")
        if complexity >= 7: flags.append("HIGH_COMPLEXITY")

        return {
            "attention_score": attention,
            "urgency": urgency,
            "importance": importance,
            "emotion_intensity": emotion["intensity"],
            "emotion_valence": emotion["valence"],
            "complexity": complexity,
            "benjamin_state": state,
            "routing": "S2_DEEP" if route_s2 else "S1_FAST",
            "flags": flags,
            "timestamp": datetime.now().isoformat()
        }

    def inject(self, score):
        """Format condensé pour injection dans le contexte."""
        r = score
        base = (
            f"[S3|Att:{r['attention_score']}/10|"
            f"Urg:{r['urgency']}/10|Imp:{r['importance']}/10|"
            f"Emo:{r['emotion_valence']}({r['emotion_intensity']}/10)|"
            f"Cpx:{r['complexity']}/10|"
            f"Route:{r['routing']}|"
            f"Ben:{r['benjamin_state']}"
        )
        if r['flags']:
            base += f"|Flags:{','.join(r['flags'])}"
        base += "]"
        return base


# ── CLI ──────────────────────────────────────────────────────
if __name__ == "__main__":
    scorer = AttentionScorer()
    args = sys.argv[1:]

    if "--inject" in args:
        idx = args.index("--inject")
        text = " ".join(args[idx+1:]) if idx+1 < len(args) else sys.stdin.read().strip()
        result = scorer.score(text)
        print(scorer.inject(result))
    elif args:
        text = " ".join(args)
        result = scorer.score(text)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        text = sys.stdin.read().strip()
        if text:
            result = scorer.score(text)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"error": "No input"}, ensure_ascii=False))
