#!/usr/bin/env python3
"""
Kate Middleware — Microservice d'interception S3 + MetaCog.
Écoute sur le port 8766. Reçoit un message HTTP, retourne le contexte enrichi.

Endpoints:
  POST /s3          → Analyse le message entrant
  POST /meta         → Évalue la réponse
  POST /pipeline     → Analyse complète (message + réponse)
  GET  /health       → Health check

Démarrage:
  python3 middleware.py &
  ou via systemd: systemctl start kate-middleware
"""

import json, sys, os
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_attention import AttentionScorer
from metacognition import MetaCognition

s3 = AttentionScorer()
meta = MetaCognition()


class MiddlewareHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("X-Kate-Middleware", "v1.0")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return ""
        return self.rfile.read(length).decode("utf-8")

    def do_GET(self):
        if self.path == "/health":
            self._send_json({
                "status": "healthy",
                "modules": {"s3": True, "metacog": True},
                "version": "1.0"
            })
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        body = self._read_body()
        
        if self.path == "/s3":
            if not body:
                self._send_json({"error": "Empty body"}, 400)
                return
            result = s3.score(body)
            self._send_json(result)

        elif self.path == "/meta":
            try:
                data = json.loads(body)
                question = data.get("question", "")
                response = data.get("response", "")
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON. Use {question, response}"}, 400)
                return
            result = meta.evaluate(question, response)
            self._send_json(result)

        elif self.path == "/pipeline":
            try:
                data = json.loads(body)
                question = data.get("question", "")
                response = data.get("response", "")
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON. Use {question, response}"}, 400)
                return
            
            s3_result = s3.score(question)
            meta_result = meta.evaluate(question, response) if response else None
            
            instructions = []
            if s3_result["routing"] == "S2_DEEP":
                instructions.append("S2_DEEP")
            if s3_result["urgency"] >= 7:
                instructions.append("PRIORITY_HIGH")
            if s3_result["benjamin_state"] == "stress":
                instructions.append("TONE_CALM")
            elif s3_result["benjamin_state"] == "energique":
                instructions.append("TONE_DYNAMIC")
            if s3_result["emotion_valence"] == "negative":
                instructions.append("TONE_EMPATHETIC")

            self._send_json({
                "s3": s3_result,
                "metacog": meta_result,
                "context": s3.inject(s3_result),
                "instructions": instructions
            })

        else:
            self._send_json({"error": "Not found"}, 404)

    def log_message(self, format, *args):
        pass  # Silencieux en production


def run(port=8766):
    server = HTTPServer(("127.0.0.1", port), MiddlewareHandler)
    print(f"🧠 Kate Middleware — port {port}")
    print(f"   POST /pipeline  → S3 + MetaCog")
    print(f"   POST /s3        → Score d'attention")
    print(f"   POST /meta      → Auto-évaluation")
    print(f"   GET  /health    → Statut")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
        server.shutdown()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    run(port)
