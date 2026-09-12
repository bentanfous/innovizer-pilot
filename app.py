from __future__ import annotations
import json, os, sys
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pandas as pd

from innovizer.engines import fiche_projet as fp
from innovizer.brique03.interview import Entretien
from innovizer.brique03.runtime import Store

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "DUNASYS_2025_brique01.xlsx"
WEB = ROOT / "web" / "index.html"
STORE = Store(ROOT / "data" / "entretiens")
SESSIONS: dict[str, Entretien] = {}

def clean(v):
    if isinstance(v, dict): return {k: clean(x) for k,x in v.items()}
    if isinstance(v, list): return [clean(x) for x in v]
    if pd.isna(v): return None
    if hasattr(v, 'item'):
        try: return v.item()
        except Exception: pass
    return v

def projects():
    df = pd.read_excel(DATA, sheet_name="Screening projets")
    cols = ["code_projet","heures","collaborateurs","premier_mois","dernier_mois","statut_screening","thematique_chapeau","regime","eligibilite","defendabilite","decision"]
    cols = [c for c in cols if c in df.columns]
    return [clean(r) for r in df[cols].to_dict("records")]

def project_row(code):
    for r in projects():
        if r.get("code_projet") == code: return r
    return None

class H(BaseHTTPRequestHandler):
    def _send(self, code, obj, ctype="application/json; charset=utf-8"):
        if isinstance(obj, (dict,list)):
            body=json.dumps(clean(obj), ensure_ascii=False).encode()
        elif isinstance(obj, bytes): body=obj
        else: body=str(obj).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def _body(self):
        n=int(self.headers.get("Content-Length",0)); raw=self.rfile.read(n) if n else b"{}"
        return json.loads(raw or b"{}")
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, WEB.read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/health": return self._send(200,{"ok":True,"version":"0.1.0","snapshot":DATA.exists()})
        if self.path == "/api/projects": return self._send(200,{"projects":projects()})
        if self.path.startswith("/api/interviews/"):
            id_=self.path.rstrip('/').split('/')[-1]; e=SESSIONS.get(id_)
            if not e: return self._send(404,{"error":"session inconnue"})
            return self._send(200,e.export())
        return self._send(404,{"error":"not found"})
    def do_POST(self):
        if self.path == "/api/interviews":
            d=self._body(); code=d.get("code_projet"); row=project_row(code)
            if not row: return self._send(404,{"error":"projet inconnu"})
            ctx=fp.contexte_depuis_snapshot(row); f=fp.FicheProjet(contexte=ctx)
            f.investigation.regime_pressenti=d.get("regime") or row.get("regime") or "A_DETERMINER"
            e=Entretien(f, projets_connus=[x["code_projet"] for x in projects()], interlocuteur=d.get("interlocuteur", ""))
            SESSIONS[e.id]=e; STORE.sauver(e); q=e.prochaine_question()
            return self._send(201,{"id":e.id,"ouverture":e.ouverture(),"question":asdict(q) if q else None,"contexte":asdict(ctx)})
        parts=self.path.strip('/').split('/')
        if len(parts)==4 and parts[:2]==["api","interviews"] and parts[3]=="answer":
            e=SESSIONS.get(parts[2]);
            if not e: return self._send(404,{"error":"session inconnue"})
            cl=e.repondre(self._body().get("reponse", "")); q=e.prochaine_question(); STORE.sauver(e)
            return self._send(200,{"classification":cl,"couverture":e.couverture(),"question":asdict(q) if q else None,"termine":e.termine()})
        if len(parts)==4 and parts[:2]==["api","interviews"] and parts[3]=="finalize":
            e=SESSIONS.get(parts[2]);
            if not e: return self._send(404,{"error":"session inconnue"})
            f=e.finaliser(); STORE.sauver(e)
            return self._send(200,{"fiche":asdict(f)})
        return self._send(404,{"error":"not found"})
    def log_message(self, fmt,*args): pass

def main():
    port=int(os.getenv("PORT","3010"))
    print(f"Innovizer Pilot v0.1 → http://localhost:{port}")
    print("Snapshot Dunasys 2025 chargé. Ctrl+C pour arrêter.")
    ThreadingHTTPServer(("",port),H).serve_forever()

if __name__ == "__main__": main()
