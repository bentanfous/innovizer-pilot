"""Structured project fiche used by Eva and downstream eligibility review."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import json
import pandas as pd

AXES_CIR = ["probleme","etat_art","verrou","hypotheses","essais","echecs","resultats","moyens","preuves"]

@dataclass
class Axe:
    etat: str = "VIDE"
    contenu: str = ""
    challenge: str = ""
    citations: list = field(default_factory=list)
    preuves_demandees: list = field(default_factory=list)

@dataclass
class Contexte:
    code_projet: str
    heures: float = 0.0
    periode: str = ""
    collaborateurs: list = field(default_factory=list)
    thematique: str = ""
    regime_initial: str = "A_DETERMINER"
    metadata: dict = field(default_factory=dict)

@dataclass
class Investigation:
    regime_pressenti: str = "A_DETERMINER"
    interlocuteur: str = ""
    date_entretien: str = ""
    transcript_id: str = ""
    duree_min: int = 0
    axes: dict = field(default_factory=lambda: {a: Axe() for a in AXES_CIR})
    axes_cii: dict = field(default_factory=dict)

@dataclass
class Synthese:
    couverture_pct: int = 0
    defendabilite: str = "FAIBLE"
    score_defendabilite: int = 0
    red_flags: list = field(default_factory=list)
    questions_ouvertes: list = field(default_factory=list)
    pieces_a_reclamer: list = field(default_factory=list)
    liens_verrou: list = field(default_factory=list)
    revue_experte_requise: bool = True

@dataclass
class FicheProjet:
    contexte: Contexte
    investigation: Investigation = field(default_factory=Investigation)
    synthese: Synthese = field(default_factory=Synthese)
    def to_json(self):
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def synthetiser(f: FicheProjet) -> Synthese:
    axes = list(f.investigation.axes.items()) + list(f.investigation.axes_cii.items())
    if not axes:
        return Synthese()
    rank = {"VIDE":0, "PARTIEL":0.5, "COMPLET":1}
    score = sum(rank.get(a.etat, 0) for _, a in axes) / len(axes)
    pct = int(round(score*100))
    if pct >= 80:
        defend, ds = "FORTE", 85
    elif pct >= 55:
        defend, ds = "MOYENNE", 60
    else:
        defend, ds = "FAIBLE", 35
    red=[]; openq=[]; pieces=[]
    for name, a in axes:
        if a.etat != "COMPLET":
            openq.append({"axe": name, "etat": a.etat})
        if a.etat == "VIDE" and name in {"etat_art","verrou","essais","preuves"}:
            red.append({"code": f"MISSING_{name.upper()}", "axe": name})
        for p in a.preuves_demandees:
            if p not in pieces: pieces.append(p)
    return Synthese(couverture_pct=pct, defendabilite=defend,
                    score_defendabilite=ds, red_flags=red,
                    questions_ouvertes=openq, pieces_a_reclamer=pieces,
                    liens_verrou=list(f.synthese.liens_verrou),
                    revue_experte_requise=True)


def contexte_depuis_brique01(code_projet: str, data: dict, alias=None) -> Contexte:
    alias = alias or {}
    tt = data.get("temps")
    scr = data.get("screening_projets")
    if tt is None or len(tt) == 0:
        return Contexte(code_projet=code_projet)
    m = tt[tt.code_projet.astype(str) == str(code_projet)].copy()
    heures = float(m.heures.sum()) if len(m) else 0.0
    if len(m):
        mi, ma = int(m.mois.min()), int(m.mois.max())
        periode = f"{mi:02d}/2025 → {ma:02d}/2025"
    else: periode = ""
    collabs=[]
    for pk, g in m.groupby("person_key"):
        collabs.append(dict(nom=str(pk), emploi="", statut_qualif="A_CONFIRMER", heures=round(float(g.heures.sum()),2)))
    collabs=sorted(collabs, key=lambda x:x["heures"], reverse=True)
    theme=""; regime="A_DETERMINER"
    if scr is not None and len(scr):
        r=scr[scr.code_projet.astype(str)==str(code_projet)]
        if len(r):
            theme=str(r.iloc[0].get("thematique_chapeau") or "")
            regime=str(r.iloc[0].get("regime") or "A_DETERMINER")
    return Contexte(code_projet=code_projet, heures=heures, periode=periode,
                    collaborateurs=collabs, thematique=theme, regime_initial=regime)


def contexte_depuis_snapshot(row: dict) -> Contexte:
    n=int(row.get("collaborateurs") or 0)
    collabs=[dict(nom=f"Collaborateur {i+1}", emploi="", statut_qualif="A_CONFIRMER", heures=0) for i in range(min(n,3))]
    p1=row.get("premier_mois"); p2=row.get("dernier_mois")
    periode=""
    if pd.notna(p1) and pd.notna(p2): periode=f"{int(p1):02d}/2025 → {int(p2):02d}/2025"
    return Contexte(code_projet=str(row.get("code_projet","")), heures=float(row.get("heures") or 0),
                    periode=periode, collaborateurs=collabs,
                    thematique=str(row.get("thematique_chapeau") or ""),
                    regime_initial=str(row.get("regime") or "A_DETERMINER"), metadata=row)
