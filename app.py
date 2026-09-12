from __future__ import annotations
import json, os, math, re
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd

from innovizer.engines import fiche_projet as fp
from innovizer.brique03.interview import Entretien
from innovizer.brique03.runtime import Store

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web" / "index.html"
UPLOAD_DIR = Path(os.getenv("INNOVIZER_UPLOAD_DIR", ROOT / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
STORE = Store(ROOT / "data" / "entretiens")
SESSIONS: dict[str, Entretien] = {}

FILES = {
    "brique01": UPLOAD_DIR / "brique01.xlsx",
    "projects": UPLOAD_DIR / "screening_projets.xlsx",
    "subcontracting": UPLOAD_DIR / "screening_soustraitance.xlsx",
}
META = UPLOAD_DIR / "metadata.json"

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

REQUIRED_B01 = {"Controles", "Annexe personnel", "Qualification", "Screening projets", "Quotites", "Fournisseurs", "Documents", "Couverture preuves"}


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


def load_meta():
    if META.exists():
        try: return json.loads(META.read_text(encoding="utf-8"))
        except Exception: return {}
    return {}


def save_meta(meta):
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def dataset_status():
    meta = load_meta()
    return {
        "ready": FILES["brique01"].exists(),
        "files": {
            k: {"uploaded": p.exists(), "name": meta.get(k, {}).get("name"), "size": p.stat().st_size if p.exists() else 0}
            for k, p in FILES.items()
        },
        "storage_note": "Les fichiers du pilote sont stockés sur le filesystem Railway et peuvent être perdus lors d'un redeploy. Ajouter un Railway Volume avant une utilisation production."
    }


def require_dataset():
    if not FILES["brique01"].exists():
        raise FileNotFoundError("Aucun dossier Brique 01 n'a encore été importé.")


def read_sheet(key):
    require_dataset()
    # Allow specialist workbooks to override the consolidated Brique 01 workbook.
    if key == "projects" and FILES["projects"].exists():
        return pd.read_excel(FILES["projects"], sheet_name="Screening projets")
    if key == "suppliers" and FILES["subcontracting"].exists():
        book = pd.ExcelFile(FILES["subcontracting"])
        sheet = "Screening fournisseurs" if "Screening fournisseurs" in book.sheet_names else "Fournisseurs"
        return pd.read_excel(FILES["subcontracting"], sheet_name=sheet)
    return pd.read_excel(FILES["brique01"], sheet_name=SHEETS[key])


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
        "project_count": len(df), "total_hours": total_hours, "to_investigate": len(instruct),
        "status_counts": status, "top_themes": themes,
        "top_projects": records(df.sort_values("heures", ascending=False), ["code_projet","heures","collaborateurs","thematique_chapeau","statut_screening","regime","eligibilite","defendabilite"], 15)
    })


def validate_xlsx(kind: str, path: Path):
    try:
        book = pd.ExcelFile(path)
    except Exception as e:
        return False, f"Fichier Excel illisible : {e}"
    sheets = set(book.sheet_names)
    if kind == "brique01":
        missing = sorted(REQUIRED_B01 - sheets)
        if missing:
            return False, "Onglets requis manquants : " + ", ".join(missing)
    elif kind == "projects" and "Screening projets" not in sheets:
        return False, "L'onglet 'Screening projets' est requis."
    elif kind == "subcontracting" and not ({"Screening fournisseurs", "Fournisseurs"} & sheets):
        return False, "Un onglet 'Screening fournisseurs' ou 'Fournisseurs' est requis."
    return True, None


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
        self.end_headers(); self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0)); raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw or b"{}")

    def _excel_error(self, e):
        code = 409 if isinstance(e, FileNotFoundError) else 500
        return self._send(code, {"error": str(e)})

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"): return self._send(200, WEB.read_bytes(), "text/html; charset=utf-8")
        if path == "/api/health": return self._send(200, {"ok": True, "version": "0.3.0", "dataset": dataset_status()})
        if path == "/api/dataset/status": return self._send(200, dataset_status())
        try:
            if path == "/api/datahub/summary": return self._send(200, datahub_summary())
            if path == "/api/datahub/people": return self._send(200, {"people": records(read_sheet("people"), ["Nom - Prénom","Fonction","Salaire Annuel Brut","Cotisations Patronales éligibles","Salaire Annuel Brut Chargé","Nombre d'heures travaillées","Taux horaire"])})
            if path == "/api/datahub/qualification": return self._send(200, {"qualification": records(read_sheet("qualification"), ["nom","fonction","filtre_fonction","statut","motif","diplome","annee","domaine","piece"])})
            if path == "/api/datahub/times": return self._send(200, {"times": records(read_sheet("times"))})
            if path == "/api/datahub/suppliers": return self._send(200, {"suppliers": records(read_sheet("suppliers"), ["compte","libelle","siren","categorie","motif","a_verifier_mesr","montant_annuel","statut_cir","statut_cii","decision","agrement_cir","agrement_cii","validite_annee"])})
            if path == "/api/datahub/documents": return self._send(200, {"documents": records(read_sheet("documents"))})
            if path == "/api/datahub/controls": return self._send(200, {"controls": records(read_sheet("controls"))})
            if path == "/api/project-mapper/summary": return self._send(200, mapper_summary())
            if path == "/api/projects": return self._send(200, {"projects": projects()})
        except Exception as e:
            return self._excel_error(e)
        if path.startswith("/api/interviews/"):
            id_ = path.rstrip('/').split('/')[-1]; e = SESSIONS.get(id_)
            if not e: return self._send(404, {"error": "session inconnue"})
            return self._send(200, e.export())
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path.startswith("/api/uploads/"):
            kind = path.rstrip('/').split('/')[-1]
            if kind not in FILES: return self._send(404, {"error": "type d'import inconnu"})
            name = self.headers.get("X-Filename", "upload.xlsx")
            if not name.lower().endswith((".xlsx", ".xlsm")):
                return self._send(400, {"error": "Le MVP v0.3 accepte actuellement les fichiers Excel .xlsx/.xlsm."})
            n = int(self.headers.get("Content-Length", 0))
            if n <= 0: return self._send(400, {"error": "fichier vide"})
            if n > 25 * 1024 * 1024: return self._send(413, {"error": "fichier > 25 Mo"})
            tmp = FILES[kind].with_suffix(".uploading.xlsx")
            tmp.write_bytes(self.rfile.read(n))
            ok, err = validate_xlsx(kind, tmp)
            if not ok:
                tmp.unlink(missing_ok=True); return self._send(400, {"error": err})
            tmp.replace(FILES[kind])
            meta = load_meta(); meta[kind] = {"name": re.sub(r"[^A-Za-z0-9._ -]", "_", name), "size": n}; save_meta(meta)
            SESSIONS.clear()
            return self._send(201, {"ok": True, "kind": kind, "dataset": dataset_status()})
        if path == "/api/interviews":
            try:
                d = self._body(); code = d.get("code_projet"); row = project_row(code)
            except Exception as e: return self._excel_error(e)
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
            f = e.finaliser(); STORE.sauver(e); return self._send(200, {"fiche": asdict(f)})
        return self._send(404, {"error": "not found"})

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path == "/api/dataset":
            for p in FILES.values(): p.unlink(missing_ok=True)
            META.unlink(missing_ok=True); SESSIONS.clear()
            return self._send(200, {"ok": True, "dataset": dataset_status()})
        return self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args): pass


def main():
    port = int(os.getenv("PORT", "3010"))
    print(f"Innovizer Pilot v0.3 → http://localhost:{port}")
    ThreadingHTTPServer(("", port), H).serve_forever()

if __name__ == "__main__": main()
