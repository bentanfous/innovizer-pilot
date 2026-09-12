# Innovizer Pilot v0.4 — Raw Sources → Data Hub → Project Mapper → Eva

Cette version ne demande plus un fichier « Brique 01 » pré-consolidé.
L'utilisateur dépose directement les sources disponibles et Innovizer construit le Data Hub.

## Sources acceptées dans l'interface

Obligatoires pour construire le MVP actuel :
- **Export brut de paie / livre de paie** : `.xlsx` / `.xlsm`
- **Bulletins de paie** : plusieurs `.pdf` texte
- **Suivi des temps** : plusieurs `.xlsx` / `.xlsm`

Optionnelles :
- **CV** : PDF
- **Diplômes** : PDF
- **Grand livre** : Excel ou CSV
- **Factures fournisseurs** : PDF
- **Registre des immobilisations** : Excel ou CSV

## Ce que le moteur construit

1. Personnel et coût employeur
2. Qualification préliminaire du personnel
3. Temps et projets candidats
4. Screening des projets
5. Fournisseurs / candidats sous-traitance depuis le grand livre et les factures
6. Evidence Hub à partir des CV et diplômes
7. Contrôles de réconciliation
8. Workbook consolidé interne `uploads/brique01.xlsx`
9. Project Mapper
10. Audit Eva

## Important — formats MVP

Le parseur de paie et le parseur de temps réutilisent les profils testés sur les exports PayFit/Dunasys fournis pendant le pilote. Un export d'un autre éditeur peut nécessiter un profil de mapping supplémentaire.

Les PDF doivent contenir du texte exploitable. L'OCR des scans n'est volontairement pas activé dans ce MVP.

## Railway

Le déploiement est prêt pour Railway.

- Build : `pip install -r requirements.txt`
- Start : `python app.py`
- Health : `/api/health`

### Stockage

Les données RH sont confidentielles. Pour un test réel :
- repo GitHub **privé** ;
- ne jamais mettre les fichiers RH dans GitHub ;
- configurer un **Railway Volume** et pointer `INNOVIZER_RAW_DIR` et `INNOVIZER_UPLOAD_DIR` vers ce volume avant un usage durable.

## API raw ingestion

- `GET /api/raw/status`
- `POST /api/raw/config`
- `POST /api/raw/upload/{kind}` avec `X-Filename`
- `POST /api/raw/build`
- `DELETE /api/raw`

`kind` : `payroll`, `payslips`, `timesheets`, `cvs`, `diplomas`, `ledger`, `invoices`, `assets`.
