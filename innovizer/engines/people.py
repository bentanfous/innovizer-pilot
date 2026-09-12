"""Personnel qualification pre-screening.
This module is deliberately conservative: it structures evidence and flags review;
it does not make a final tax-law eligibility determination.
"""
from __future__ import annotations
import re
import pandas as pd

TECH_PATTERNS = [
    r"ING[ÉE]NIEUR", r"D[ÉE]VELOPPEUR", r"DEVELOPER", r"TECHNI", r"DATA",
    r"ARCHITECT", r"R&D", r"RECHERCHE", r"SCIENT", r"ELECTRON", r"EMBARQU",
    r"SOFTWARE", r"HARDWARE", r"SYSTEM", r"SYST[ÈE]ME", r"DOCTEUR", r"PHD",
]
NON_TECH_PATTERNS = [r"COMMERCIAL", r"RH\b", r"RESSOURCES HUMAINES", r"FINANCE", r"COMPTAB", r"JURIDI", r"MARKETING"]


def _filter_job(job: str) -> str:
    s = str(job or "").upper()
    if any(re.search(p, s) for p in NON_TECH_PATTERNS):
        return "NON_TECHNIQUE"
    if any(re.search(p, s) for p in TECH_PATTERNS):
        return "TECHNIQUE"
    return "A_REVOIR"


def construire(ref: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["nom"] = ref.get("nom", pd.Series(dtype=str))
    out["fonction"] = ref.get("emploi", "")
    out["classification"] = ref.get("classification", "")
    out["debut_contrat"] = ref.get("debut_contrat", "")
    out["mois_presence"] = ref.get("mois_presence", 0)
    out["filtre_fonction"] = out["fonction"].map(_filter_job)
    out["statut"] = out["filtre_fonction"].map({
        "TECHNIQUE": "A_CONFIRMER",
        "NON_TECHNIQUE": "NON_RD_FUNCTION",
        "A_REVOIR": "TO_REVIEW",
    }).fillna("TO_REVIEW")
    out["motif"] = out["filtre_fonction"].map({
        "TECHNIQUE": "profil technique détecté — diplôme/expérience et travaux à confirmer",
        "NON_TECHNIQUE": "fonction non technique détectée",
        "A_REVOIR": "fonction non classée automatiquement",
    })
    for c in ["diplome", "annee", "domaine", "niveau", "piece"]:
        out[c] = ""
    return out
