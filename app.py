from __future__ import annotations
import json, os, math
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd

from innovizer.engines import fiche_projet as fp
from innovizer.brique03.interview import Entretien
from innovizer.brique03.runtime import Store

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "DUNASYS_2025_brique01.xlsx"
WEB = ROOT / "web" / "index.html"
STORE = Store(ROOT / "data" / "entretiens")
SESSIONS: dict[str, Entretien] = {}

SHEETS = {
    "controls": "Controles",
    "people": "Annexe personnel",
    "qualification": "Qualification",
    "projects": "Screening projets",
    "times": "Quotites",
    "suppliers": "Fournisseurs",
    "documents": "Documents",
    "evidence": "Couverture preuves",
}


def clean(v):
    if isinstance(v, dict): return {k: clean(x) for k, x in v.items()}
    if isinstance(v, float) and not math.isfinite(v): return None
    if isinstance(v, list): return [clean(x) for x in v]
    if isinstance(v, tuple): return [clean(x) for x in v]
    try:
        if pd.isna(v): return None
    except Exception:
        pass
    if hasattr(v, "item"):
        try: return clean(v.item())
        except Exception: pass
    return v


def read_sheet(key):
    return pd.read_excel(DATA, sheet_name=SHEETS[key])


def records(df, cols=None, limit=None):
    if cols:
        cols = [c for c in cols if c in df.columns]
        df = df[cols]
    if limit:
        df = df.head(limit)
    return [clean(r) for r in df.to_dict("records")]


def projects():
    df = read_sheet("projects")
    cols = ["code_projet","heures","collaborateurs","premier_mois","dernier_mois","statut_screening","motif_ecart","thematique_chapeau","regime","eligibilite","defendabilite","decision"]
    return records(df, cols)


def project_row(code):
    for r in projects():
        if r.get("code_projet") == code:
            return r
    return None


def datahub_summary():
    people = read_sheet("people")
    q = read_sheet("qualification")
    times = read_sheet("times")
    suppliers = read_sheet("suppliers")
    docs = read_sheet("documents")
    controls = read_sheet("controls")
    evidence = read_sheet("evidence")
    technical = q[q.get("filtre_fonction", pd.Series(index=q.index, dtype=str)).astype(str).eq("TECHNIQUE")]
    candidate_suppliers = suppliers[suppliers.get("categorie", pd.Series(index=suppliers.index, dtype=str)).astype(str).isin(["CANDIDAT_SOUS_TRAITANCE","FABRICATION_PROTO","A_QUALIFIER"])]
    controls_bad = controls[~controls.get("statut", pd.Series(index=controls.index, dtype=str)).astype(str).eq("OK")]
    return clean({
        "people_count": len(people),
        "technical_people": len(technical),
        "payroll_gross": float(pd.to_numeric(people.get("Salaire Annuel Brut", 0), errors="coerce").fillna(0).sum()),
        "eligible_employer_contrib": float(pd.to_numeric(people.get("Cotisations Patronales éligibles", 0), errors="coerce").fillna(0).sum()),
        "worked_hours": float(pd.to_numeric(people.get("Nombre d'heures travaillées", 0), errors="coerce").fillna(0).sum()),
        "declared_hours": float(pd.to_numeric(times.get("h_declarees", 0), errors="coerce").fillna(0).sum()),
        "supplier_count": len(suppliers),
        "candidate_suppliers": len(candidate_suppliers),
        "documents_count": len(docs),
        "evidence_covered": int((evidence.get("statut_preuve", pd.Series(index=evidence.index, dtype=str)).astype(str) == "COUVERT").sum()),
        "controls_total": len(controls),
        "controls_attention": len(controls_bad),
    })


def mapper_summary():
    df = read_sheet("projects")
    status = df.get("statut_screening", pd.Series(index=df.index, dtype=str)).fillna("NON_RENSEIGNE").astype(str).value_counts().to_dict()
    themes = df.get("thematique_chapeau", pd.Series(index=df.index, dtype=str)).dropna().astype(str).value_counts().head(10).to_dict()
    total_hours = float(pd.to_numeric(df.get("heures", 0), errors="coerce").fillna(0).sum())
    instruct = df[df.get("statut_screening", pd.Series(index=df.index, dtype=str)).astype(str).eq("A_INSTRUIRE")]
    return clean({
        "project_count": len(df),
        "total_hours": total_hours,
        "to_investigate": len(instruct),
        "status_counts": status,
        "top_themes": themes,
        "top_projects": records(df.sort_values("heures", ascending=False), ["code_projet","heures","collaborateurs","thematique_chapeau","statut_screening","regime","eligibilite","defendabilite"], 15)
    })


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj, ctype="application/json; charset=utf-8"):
        if isinstance(obj, (dict, list)):
            body = json.dumps(clean(obj), ensure_ascii=False).encode()
        elif isinstance(obj, bytes): body = obj
        else: body = str(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw or b"{}")

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._send(200, WEB.read_bytes(), "text/html; charset=utf-8")
        if path == "/api/health":
            return self._send(200, {"ok": True, "version": "0.2.0", "snapshot": DATA.exists()})
        if path == "/api/datahub/summary":
            return self._send(200, datahub_summary())
        if path == "/api/datahub/people":
            return self._send(200, {"people": records(read_sheet("people"), ["Nom - Prénom","Fonction","Salaire Annuel Brut","Cotisations Patronales éligibles","Salaire Annuel Brut Chargé","Nombre d'heures travaillées","Taux horaire"])})
        if path == "/api/datahub/qualification":
            return self._send(200, {"qualification": records(read_sheet("qualification"), ["nom","fonction","filtre_fonction","statut","motif","diplome","annee","domaine","piece"])})
        if path == "/api/datahub/times":
            return self._send(200, {"times": records(read_sheet("times"))})
        if path == "/api/datahub/suppliers":
            return self._send(200, {"suppliers": records(read_sheet("suppliers"), ["compte","libelle","siren","categorie","motif","a_verifier_mesr","montant_annuel","statut_cir","statut_cii","decision"])})
        if path == "/api/datahub/documents":
            return self._send(200, {"documents": records(read_sheet("documents"))})
        if path == "/api/datahub/controls":
            return self._send(200, {"controls": records(read_sheet("controls"))})
        if path == "/api/project-mapper/summary":
            return self._send(200, mapper_summary())
        if path == "/api/projects":
            return self._send(200, {"projects": projects()})
        if path.startswith("/api/interviews/"):
            id_ = path.rstrip('/').split('/')[-1]
            e = SESSIONS.get(id_)
            if not e: return self._send(404, {"error": "session inconnue"})
            return self._send(200, e.export())
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/interviews":
            d = self._body(); code = d.get("code_projet"); row = project_row(code)
            if not row: return self._send(404, {"error": "projet inconnu"})
            ctx = fp.contexte_depuis_snapshot(row); f = fp.FicheProjet(contexte=ctx)
            f.investigation.regime_pressenti = d.get("regime") or row.get("regime") or "A_DETERMINER"
            e = Entretien(f, projets_connus=[x["code_projet"] for x in projects()], interlocuteur=d.get("interlocuteur", ""))
            SESSIONS[e.id] = e; STORE.sauver(e); q = e.prochaine_question()
            return self._send(201, {"id": e.id, "ouverture": e.ouverture(), "question": asdict(q) if q else None, "contexte": asdict(ctx)})
        parts = path.strip('/').split('/')
        if len(parts) == 4 and parts[:2] == ["api", "interviews"] and parts[3] == "answer":
            e = SESSIONS.get(parts[2])
            if not e: return self._send(404, {"error": "session inconnue"})
            cl = e.repondre(self._body().get("reponse", "")); q = e.prochaine_question(); STORE.sauver(e)
            return self._send(200, {"classification": cl, "couverture": e.couverture(), "question": asdict(q) if q else None, "termine": e.termine()})
        if len(parts) == 4 and parts[:2] == ["api", "interviews"] and parts[3] == "finalize":
            e = SESSIONS.get(parts[2])
            if not e: return self._send(404, {"error": "session inconnue"})
            f = e.finaliser(); STORE.sauver(e)
            return self._send(200, {"fiche": asdict(f)})
        return self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        pass


def main():
    port = int(os.getenv("PORT", "3010"))
    print(f"Innovizer Pilot v0.2 → http://localhost:{port}")
    ThreadingHTTPServer(("", port), H).serve_forever()

if __name__ == "__main__": main()
