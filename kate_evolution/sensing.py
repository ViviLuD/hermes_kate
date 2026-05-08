#!/usr/bin/env python3
"""
Kate Sensing v2: Module de perception ambiante enrichi.
Sources corrigées + veille GitHub intégrée.

Sources:
- Flux RSS brevets (EPO, USPTO, WIPO, IAM, IPKat, arXiv)
- GitHub API (repos IP/patent/quantum/DeepTech)
- Calendrier Outlook

Usage:
  python3 sensing.py              # Scan complet
  python3 sensing.py --rss-only
  python3 sensing.py --github-only
  python3 sensing.py --watch      # Mode continu
"""

import json, os, sys, subprocess, re
from datetime import datetime

SENSING_DIR = "/opt/data/kate_evolution"
SIGNALS_LOG = f"{SENSING_DIR}/signals_log.jsonl"

# ── RSS Feeds (URLs corrigées) ────────────────────────────────
PATENT_FEEDS = {
    "EPO":"https://news.google.com/rss/search?q=EPO+patent+brevet+office+europeen&hl=fr&ceid=FR:fr",
    "USPTO":"https://news.google.com/rss/search?q=USPTO+patent+US+patent+office&hl=en&ceid=US:en",
    "WIPO":"https://www.wipo.int/pressroom/en/rss.xml",
    "IAM":"https://www.iam-media.com/rss",
    "IPKat":"https://ipkitten.blogspot.com/feeds/posts/default",
    "Quantum_arXiv":"https://rss.arxiv.org/rss/quant-ph",
    "AI_arXiv":"https://rss.arxiv.org/rss/cs.AI",
}

# ── GitHub Search Queries ─────────────────────────────────────
GITHUB_QUERIES = [
    ("patent+analysis+tool", "Patent Analysis"),
    ("IP+management+open+source", "IP Management"),
    ("freedom+to+operate", "FTO Tools"),
    ("quantum+computing+software", "Quantum Computing"),
    ("trade+secret+management", "Trade Secrets"),
    ("patent+landscape", "Patent Landscape"),
    ("intellectual+property+AI", "IP + AI"),
    ("patent+search+engine", "Patent Search"),
    ("deep+tech+startup", "DeepTech"),
    ("quantum+machine+learning", "Quantum ML"),
]

KEYWORDS = [
    "quantum", "patent", "intellectual property", "trade secret",
    "AI Act", "artificial intelligence", "deep tech", "semiconductor",
    "chip", "qubit", "sovereignty", "valuation", "licensing",
    "FRAND", "SEP", "standard essential", "open source",
    "EPO", "UPC", "Unified Patent Court", "NIS2", "data act",
    "inventorship", "innovation", "startup", "intangible",
    "brevet", "propriété intellectuelle",
]


class KateSensing:
    def __init__(self):
        self.signals = []
        self.alerts = []
        self.timestamp = datetime.now()

    def log(self, source, title, summary="", relevance=0, url=None):
        signal = {
            "ts": self.timestamp.isoformat(),
            "source": source,
            "title": title[:200],
            "summary": summary[:300],
            "relevance": min(10, relevance),
            "url": url
        }
        self.signals.append(signal)
        if relevance >= 7:
            self.alerts.append(signal)
        return signal

    def _relevance(self, text):
        """Score de pertinence basé sur les mots-clés."""
        t = text.lower()
        score = 0
        for kw in KEYWORDS:
            if kw.lower() in t:
                score += 2
        return min(10, score)

    def scan_rss(self):
        """Scanne les flux RSS avec URLs corrigées."""
        print("\n📡 SCAN RSS")
        print("─" * 50)

        for name, url in PATENT_FEEDS.items():
            try:
                r = subprocess.run(
                    ["curl", "-s", "-L", "--max-time", "12", "-A", "KateSensing/2.0", url],
                    capture_output=True, text=True, timeout=18
                )
                if r.returncode == 0 and len(r.stdout) > 50:
                    # Extraire les infos du flux
                    titles = re.findall(r'<title[^>]*>(.*?)</title>', r.stdout)
                    descs = re.findall(r'<description[^>]*>(.*?)</description>', r.stdout)
                    links = re.findall(r'<link[^>]*>(https?://[^<]+)</link>', r.stdout)

                    found = 0
                    for i, title in enumerate(titles[:8]):
                        title_clean = re.sub(r'<[^>]+>', '', title).strip()
                        if title_clean and len(title_clean) > 15:
                            rel = self._relevance(title_clean)
                            desc = ""
                            if i < len(descs):
                                desc = re.sub(r'<[^>]+>', '', descs[i])[:200]
                            url_sig = links[i] if i < len(links) else None

                            self.log(name, title_clean, desc, rel, url_sig)
                            found += 1

                    print(f"  ✅ {name}: {found} signaux")
                else:
                    print(f"  ❌ {name}: pas de contenu (HTTP {r.returncode})")
            except Exception as e:
                print(f"  ❌ {name}: {e}")

    def scan_github(self):
        """Scanne l'API GitHub pour les repos pertinents."""
        print("\n🐙 SCAN GITHUB")
        print("─" * 50)

        for query, label in GITHUB_QUERIES:
            try:
                url = f"https://api.github.com/search/repositories?q={query}&sort=updated&per_page=3"
                r = subprocess.run(
                    ["curl", "-s", "--max-time", "10", "-A", "KateSensing/2.0", url],
                    capture_output=True, text=True, timeout=15
                )
                if r.returncode == 0:
                    try:
                        data = json.loads(r.stdout)
                        items = data.get("items", [])
                        for repo in items[:3]:
                            title = f"{repo['full_name']} ⭐{repo['stargazers_count']}"
                            desc = repo.get("description", "") or ""
                            repo_url = repo["html_url"]
                            rel = self._relevance(f"{label} {title} {desc}")
                            self.log(f"GitHub/{label}", title, desc, rel, repo_url)
                        print(f"  ✅ {label}: {len(items[:3])} repos")
                    except json.JSONDecodeError:
                        print(f"  ⚠️  {label}: rate-limited ou JSON invalide")
                else:
                    print(f"  ❌ {label}: HTTP {r.returncode}")
            except Exception as e:
                print(f"  ❌ {label}: {e}")

    def scan_calendar(self):
        """Vérifie le calendrier de Benjamin."""
        print("\n📅 CALENDRIER")
        print("─" * 50)
        script = "/opt/data/calendar/fetch_benjamin_outlook_calendar.py"
        if os.path.exists(script):
            try:
                r = subprocess.run(["python3", script, "3"], capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    print("  ✅ 3 jours récupérés")
                    self.log("calendar", "Calendrier 3j mis à jour", "", 2)
                else:
                    print(f"  ⚠️  Erreur")
            except Exception as e:
                print(f"  ❌ {e}")
        else:
            print("  ❌ Script introuvable")

    def generate_report(self):
        """Rapport de synthèse."""
        print("\n" + "=" * 60)
        print(f"📊 RAPPORT SENSING — {self.timestamp.strftime('%d/%m %H:%M')}")
        print(f"   Signaux: {len(self.signals)} | Alertes: {len(self.alerts)}")
        print("=" * 60)

        if self.alerts:
            print("\n🚨 ALERTES:")
            for a in self.alerts:
                print(f"  [{a['relevance']}/10] {a['source']}: {a['title'][:90]}")

        if self.signals:
            os.makedirs(SENSING_DIR, exist_ok=True)
            with open(SIGNALS_LOG, "a") as f:
                for s in self.signals:
                    f.write(json.dumps(s, ensure_ascii=False) + "\n")

    def run(self):
        print("\n🔮 KATE SENSING v2")
        self.scan_rss()
        self.scan_github()
        self.scan_calendar()
        self.generate_report()


if __name__ == "__main__":
    sensor = KateSensing()
    if "--rss-only" in sys.argv:
        sensor.scan_rss()
        sensor.generate_report()
    elif "--github-only" in sys.argv:
        sensor.scan_github()
        sensor.generate_report()
    else:
        sensor.run()
