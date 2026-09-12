from __future__ import annotations

import json, re, shutil, hashlib, unicodedata
from pathlib import Path
from typing import Iterable
import pandas as pd
import pypdf

from . import config, identity, evidence, controls
from .ingest import paie as ing_paie, bulletins as ing_bul, temps as ing_tps
from .engines import people, assiette as eng_assiette, screening, subcontracting


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _extract_pdf_text(path: Path, max_pages: int = 20) -> str:
    try:
        r = pypdf.PdfReader(str(path))
        return "\n".join((p.extract_text() or "") for p in r.pages[:max_pages])
    except Exception:
        return ""


def _safe_float(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return None
    s = str(v).replace("\u202f", " ").replace("\xa0", " ")
    s = re.sub(r"[^0-9,.-]", "", s)
    if "," in s and "." in s: s = s.replace(".", "").replace(",", ".")
    else: s = s.replace(",", ".")
    try: return float(s)
    except Exception: return None


def _match_person(filename: str, text: str, people_df: pd.DataFrame, aliases: dict) -> str | None:
    if people_df is None or people_df.empty: return None
    hay = _norm(filename + " " + (text[:4000] if text else ""))
    best = (0, None)
    for _, r in people_df.iterrows():
        name = r.get("nom") or r.get("Nom - Prénom") or ""
        key = identity.cle_personne(name, aliases)
        toks = [t for t in _norm(name).split() if len(t) >= 3]
        score = sum(1 for t in toks if t in hay)
        if len(toks) and score == len(toks): score += 3
        if score > best[0]: best = (score, key)
    return best[1] if best[0] >= 2 else None


def _degree_from_text(text: str) -> tuple[str, str, str]:
    t = re.sub(r"\s+", " ", text or " ")
    patterns = [
        (r"(?i)doctorat|ph\.?d", "Doctorat"),
        (r"(?i)dipl[oô]me d['’]ing[ée]nieur|engineer(?:ing)? degree", "Diplôme d'ingénieur"),
        (r"(?i)master(?:\s+of\s+science)?|\bmsc\b", "Master"),
        (r"(?i)licence|bachelor", "Licence/Bachelor"),
        (r"(?i)but|dut|bts", "Bac+2/3 technique"),
    ]
    level = next((label for pat, label in patterns if re.search(pat, t)), "")
    yearm = re.search(r"\b(19|20)\d{2}\b", t)
    year = yearm.group(0) if yearm else ""
    field = ""
    fm = re.search(r"(?i)(informatique|computer science|software|[ée]lectronique|telecom|t[ée]l[ée]communications|data|math[ée]matiques|m[ée]canique|automatique|syst[èe]mes embarqu[ée]s|engineering)", t)
    if fm: field = fm.group(1)
    return level, year, field


def build_documents(raw_root: Path, people_df: pd.DataFrame, aliases: dict) -> tuple[pd.DataFrame, dict]:
    pieces, enrich = [], {}
    for folder, typ in [("cvs", "cv"), ("diplomas", "diplome")]:
        for p in sorted((raw_root/folder).glob("*.pdf")):
            txt = _extract_pdf_text(p)
            person_key = _match_person(p.name, txt, people_df, aliases)
            did = hashlib.sha1((str(p)+str(p.stat().st_size)).encode()).hexdigest()[:12]
            pieces.append({
                "document_id": did, "type": typ, "fichier": p.name, "date": "",
                "entite": "personne", "cle_entite": person_key or "NON_RATTACHE",
                "note": "Rattachement automatique par nom/texte — à confirmer" if person_key else "Rattachement manuel requis"
            })
            if person_key and typ == "diplome":
                lvl, year, field = _degree_from_text(txt)
                enrich[person_key] = {"diplome": lvl, "annee": year, "domaine": field, "piece": p.name}
    return evidence.registre(pieces), enrich


def _read_any_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        for sep in [";", ",", "\t"]:
            try:
                d = pd.read_csv(path, sep=sep)
                if len(d.columns) > 1: return d
            except Exception: pass
        return pd.read_csv(path)
    book = pd.ExcelFile(path)
    # Prefer recognizable ledger sheet, otherwise first non-empty
    pref = [s for s in book.sheet_names if re.search(r"grand|journal|ecriture|ledger|fournisseur", s, re.I)]
    for s in pref + book.sheet_names:
        try:
            d = pd.read_excel(path, sheet_name=s)
            if not d.empty and len(d.columns) >= 2: return d
        except Exception: pass
    return pd.DataFrame()


def _find_col(cols: Iterable, patterns: list[str]) -> str | None:
    for c in cols:
        n = _norm(c)
        if any(re.search(p, n, re.I) for p in patterns): return c
    return None


def build_supplier_table(raw_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    ledger_files = [p for p in (raw_root/"ledger").glob("*") if p.suffix.lower() in (".xlsx", ".xls", ".xlsm", ".csv")]
    entries=[]
    for p in ledger_files:
        d=_read_any_table(p)
        if d.empty: continue
        account=_find_col(d.columns,[r"^COMPTE$",r"ACCOUNT",r"NUMERO COMPTE",r"COMPTE GENERAL"])
        name=_find_col(d.columns,[r"FOURNISSEUR",r"TIERS",r"LIBELLE",r"NOM"])
        siren=_find_col(d.columns,[r"SIREN",r"SIRET"])
        debit=_find_col(d.columns,[r"DEBIT"]); credit=_find_col(d.columns,[r"CREDIT"]); amount=_find_col(d.columns,[r"MONTANT",r"AMOUNT"])
        for _,r in d.iterrows():
            lib=str(r.get(name,"") if name else "").strip()
            acc=str(r.get(account,"") if account else "").strip()
            if not lib and not acc: continue
            val = _safe_float(r.get(amount)) if amount else None
            if val is None:
                dv=_safe_float(r.get(debit)) if debit else 0; cv=_safe_float(r.get(credit)) if credit else 0
                val=(dv or 0)-(cv or 0)
            sv=str(r.get(siren,"") if siren else "")
            entries.append({"compte":acc,"libelle":lib,"siren":sv,"montant":abs(val or 0),"source":p.name})
    led=pd.DataFrame(entries)
    if led.empty:
        base=pd.DataFrame(columns=["compte","libelle","siren","montant_annuel"])
    else:
        base=(led.groupby(["compte","libelle","siren"],dropna=False).montant.sum().reset_index().rename(columns={"montant":"montant_annuel"}))
    # Invoice PDFs enrich / create candidate suppliers
    inv=[]
    for p in sorted((raw_root/"invoices").glob("*.pdf")):
        text=_extract_pdf_text(p,8)
        sirenm=re.search(r"(?i)SIREN\s*[:\-]?\s*((?:\d[ .]?){9})",text)
        siret=re.search(r"(?i)SIRET\s*[:\-]?\s*((?:\d[ .]?){14})",text)
        sirenval=re.sub(r"\D","",(sirenm.group(1) if sirenm else siret.group(1)[:11] if siret else ""))[:9]
        am=None
        for pat in [r"(?i)TOTAL\s+HT\s*[:€ ]+([\d\s.,]+)",r"(?i)MONTANT\s+HT\s*[:€ ]+([\d\s.,]+)"]:
            m=re.search(pat,text)
            if m: am=_safe_float(m.group(1)); break
        # filename is safer than hallucinating supplier from arbitrary first line
        lib=re.sub(r"[_-]+"," ",p.stem).strip()
        inv.append({"fichier":p.name,"libelle":lib,"siren":sirenval,"montant_ht":am,"texte_extrait":text[:1500]})
    invdf=pd.DataFrame(inv)
    if not invdf.empty:
        for _,r in invdf.iterrows():
            if r.get("siren"):
                m = base[base.siren.astype(str).str.replace(r"\D","",regex=True).str[:9] == r.siren] if not base.empty else pd.DataFrame()
                if len(m): continue
            extra={"compte":"","libelle":r.get("libelle",""),"siren":r.get("siren",""),"montant_annuel":r.get("montant_ht") or 0}
            base=pd.concat([base,pd.DataFrame([extra])],ignore_index=True)
    if base.empty: screened=subcontracting.screening_fournisseurs(pd.DataFrame(columns=["compte","libelle"]))
    else:
        core=base[["compte","libelle"]].copy()
        screened=subcontracting.screening_fournisseurs(core)
        screened["siren"] = base["siren"].values
        screened["montant_annuel"] = base["montant_annuel"].values
    return screened, invdf


def build_assets(raw_root: Path) -> pd.DataFrame:
    files=[p for p in (raw_root/"assets").glob("*") if p.suffix.lower() in (".xlsx",".xls",".xlsm",".csv")]
    rows=[]
    for p in files:
        d=_read_any_table(p)
        if d.empty: continue
        designation=_find_col(d.columns,[r"DESIGNATION",r"LIBELLE",r"ASSET",r"IMMOB"])
        gross=_find_col(d.columns,[r"VALEUR BRUTE",r"BRUT",r"ACQUISITION",r"GROSS"])
        depr=_find_col(d.columns,[r"DOTATION",r"AMORT",r"DEPRECIATION"])
        date=_find_col(d.columns,[r"MISE EN SERVICE",r"DATE ACQUIS",r"DATE"])
        for _,r in d.iterrows():
            rows.append({"designation":r.get(designation,"") if designation else "","valeur_brute":_safe_float(r.get(gross)) if gross else None,"dotation_exercice":_safe_float(r.get(depr)) if depr else None,"date":r.get(date,"") if date else "","usage_rd_pct":"","montant_candidat":"","source":p.name})
    return pd.DataFrame(rows)


def build(raw_root: Path, out_xlsx: Path, dossier: config.Dossier, cache_dir: Path) -> dict:
    raw_root=Path(raw_root); out_xlsx=Path(out_xlsx); cache_dir=Path(cache_dir)
    payroll_files=list((raw_root/"payroll").glob("*.xlsx"))+list((raw_root/"payroll").glob("*.xlsm"))
    payslips=list((raw_root/"payslips").glob("*.pdf"))
    timesheets=list((raw_root/"timesheets").glob("*.xlsx"))+list((raw_root/"timesheets").glob("*.xlsm"))
    if not payroll_files: raise ValueError("Ajoute au moins un export brut de paie Excel.")
    if not payslips: raise ValueError("Ajoute les bulletins de paie PDF.")
    if not timesheets: raise ValueError("Ajoute au moins un export de suivi des temps Excel.")

    # payroll
    paie_df=ing_paie.sectionner(ing_paie.load(str(payroll_files[0])))
    rec=ing_paie.payroll_records(paie_df); agg=ing_paie.agregat_annuel(rec)
    # payslips
    bul=ing_bul.parse_annee([str(p) for p in payslips],cache_dir=str(cache_dir),workers=min(4,max(1,len(payslips))))
    if bul.empty: raise ValueError("Les PDF ont été reçus mais aucun bulletin n'a pu être reconnu. Vérifie qu'ils contiennent du texte (pas uniquement des scans).")
    salaries=ing_bul.referentiel_salaries(bul)
    # personnel + assiette
    qual=people.construire(salaries)
    cot=eng_assiette.cotisations_par_classe(rec)
    annexe=eng_assiette.construire_annexe(agg,salaries,cot,bul)
    # docs + enrich qualification
    docs,enrich=build_documents(raw_root,salaries,dossier.alias_personnes)
    if not qual.empty:
        qual["person_key"]=qual.nom.map(lambda n: identity.cle_personne(n,dossier.alias_personnes))
        for i,r in qual.iterrows():
            e=enrich.get(r.person_key)
            if e:
                for c,v in e.items(): qual.at[i,c]=v
                qual.at[i,"statut"]="A_CONFIRMER"
                qual.at[i,"motif"]="diplôme détecté automatiquement — contenu et rattachement à confirmer"
    # time + projects
    ing_tps.HEURES_PAR_JOUR=dossier.heures_par_jour
    tt=ing_tps.charger([str(p) for p in timesheets])
    scr=screening.screening(tt)
    proj=scr[["code_projet"]].copy(); proj["classe"]=scr.eligibilite.map(lambda e:"NON_RD" if e=="NON_ELIGIBLE" else "NON_CLASSE")
    quotas=ing_tps.quotites(tt,proj)
    # controls
    ctrl=[]
    ctrl.extend(ing_paie.controles(paie_df,rec,agg))
    annexe_keys=set(annexe["Nom - Prénom"].map(lambda n: identity.cle_personne(n,dossier.alias_personnes)))
    ctrl.extend(ing_tps.controles(tt,quotas,annexe_keys).to_dict("records"))
    ctrl_df=pd.DataFrame(ctrl)
    # suppliers / invoices / assets
    suppliers,invoices=build_supplier_table(raw_root)
    assets=build_assets(raw_root)
    # evidence coverage
    if qual.empty:
        cov=pd.DataFrame()
    else:
        cov=evidence.couverture(docs,qual,"personne","person_key") if not docs.empty else qual.assign(piece_opposable=False,piece_quelconque=False,statut_preuve="MANQUANT")

    out_xlsx.parent.mkdir(parents=True,exist_ok=True)
    with pd.ExcelWriter(out_xlsx,engine="openpyxl") as w:
        ctrl_df.to_excel(w,"Controles",index=False)
        annexe.to_excel(w,"Annexe personnel",index=False)
        qual.to_excel(w,"Qualification",index=False)
        eng_assiette.synthese_classement(rec).to_excel(w,"Classement cotisations",index=False)
        scr.to_excel(w,"Screening projets",index=False)
        quotas.to_excel(w,"Quotites",index=False)
        suppliers.to_excel(w,"Fournisseurs",index=False)
        docs.to_excel(w,"Documents",index=False)
        cov.to_excel(w,"Couverture preuves",index=False)
        if not invoices.empty: invoices.drop(columns=["texte_extrait"],errors="ignore").to_excel(w,"Factures",index=False)
        if not assets.empty: assets.to_excel(w,"Immobilisations",index=False)
    return {
        "people":len(annexe),"projects":len(scr),"timesheet_rows":len(tt),"payslips":len(bul),
        "documents":len(docs),"suppliers":len(suppliers),"invoices":len(invoices),"assets":len(assets),
        "output":str(out_xlsx)
    }
