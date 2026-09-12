"""Quick CLI smoke test on the bundled Dunasys snapshot."""
from pathlib import Path
import pandas as pd
from innovizer.engines import fiche_projet as fp
from innovizer.brique03.runtime import executer_cli, Store

p=Path(__file__).parent/'data'/'DUNASYS_2025_brique01.xlsx'
df=pd.read_excel(p, sheet_name='Screening projets')
r=df[df.statut_screening.eq('A_INSTRUIRE')].iloc[0].to_dict()
ctx=fp.contexte_depuis_snapshot(r)
f=fp.FicheProjet(ctx); f.investigation.regime_pressenti='CIR'
reponses=[
"Le problème était difficile car au départ la solution existante ne fonctionnait pas dans notre contexte.",
"Nous avons examiné les solutions existantes du marché mais elles ne couvraient pas notre besoin et étaient insuffisantes.",
"Nous ne savions pas si l'approche pouvait converger avec un taux d'erreur sous 5 %, sans garantie de résultat.",
"Nous avons testé plusieurs approches et retenu la seconde parce qu'elle permettait de mieux isoler le phénomène.",
"Nous avons défini un protocole de test avec mesures, campagnes d'essais et indicateurs quantifiés sur plusieurs mois.",
"Une piste a été abandonnée car elle était instable et le taux de faux positifs restait trop élevé.",
"Nous avons validé une partie du résultat ; la généralisation reste ouverte et nous avons documenté les limites.",
"L'équipe d'ingénieurs a travaillé avec du matériel de test dédié, sans sous-traitant sur ce sous-ensemble.",
"Les preuves sont dans Git, les comptes-rendus datés de 2025, les tickets et les rapports de test.",
"Non, pas d'autre projet identifié à ce stade."
]
e,fiche=executer_cli(f,reponses=reponses,interlocuteur='CTO',store=Store(Path(__file__).parent/'data'/'entretiens'),silencieux=True)
print('Projet:',fiche.contexte.code_projet)
print('Couverture:',fiche.synthese.couverture_pct,'%')
print('Défendabilité:',fiche.synthese.defendabilite)
print('Red flags:',[x['code'] for x in fiche.synthese.red_flags])
print('Session:',e.id)
