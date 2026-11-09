# PST – Suivi d'une bulle par imagerie rapide

Projet Scientifique Transversal (CentraleSupélec, 2026-2027). Analyse d'un film de caméra rapide (3 000 images/s) montrant un essaim de bulles : une bulle est étiquetée puis suivie de sa naissance jusqu'à son arrivée sous la mousse, pour mesurer sa **trajectoire, sa vitesse, son centre, son barycentre, sa déformation** et, à terme, les **forces** qui s'exercent sur elle.

> État : **résultats en pixels**. L'échelle (mm par pixel) et le liquide du film restent à confirmer ; les forces ne sont donc pas encore calculées.

## Contenu

| Dossier | Rôle |
|---|---|
| `2. Code/suivi_bulle.py` | Script principal : suivi, mesures, forces (si l'échelle est renseignée), contrôle visuel |
| `2. Code/resultats_bulle/` | Résultats : `suivi_bulle.csv`, `analyse_bulle.png`, `controle_contours.png` / `.mp4` |
| `3. Rapport/Presentation_analyse_bulle.pptx` (+ `.pdf`) | Diaporama : analyse de l'algorithme et de la bulle |
| `3. Rapport/Historique_projet_PST_2026-11-09.md` | Historique détaillé et point de reprise |
| `1. Photos/` | Films bruts, **non inclus** (voir `1. Photos/LISEZMOI.md`) |

## Utilisation

```bash
pip install numpy opencv-python scikit-image scipy matplotlib pandas
```

1. Placer les films dans `1. Photos/` (voir `1. Photos/LISEZMOI.md`).
2. Ouvrir `2. Code/suivi_bulle.py`, **adapter `BASE`** (chemin absolu du dossier `1. Photos`) et, si connus, `MM_PAR_PIXEL` et les propriétés du liquide (`RHO_L`, `MU_L`, `SIGMA`).
3. Exécuter le script (≈ 3 minutes). Regarder d'abord `controle_contours.mp4` (contour rouge), puis les courbes.

Les numéros d'images (`IMAGE0`, `REINIT`, `PHASE3`, `IMAGE_FIN`) et la position de départ (`X0`, `Y0`) sont propres à la bulle analysée.

## Méthode (résumé)

**Étiqueter → contour initial → suivre → affiner → mesurer.**

- Le contour initial vient d'un anneau de bords nets (gradient), fermé puis rempli.
- Le suivi décale le contour précédent par corrélation d'image, puis le recale sur le bord.
- La **finition par programmation dynamique** cherche, sur 360 angles, le meilleur contour continu et ne s'appuie que sur les bords réellement visibles.
- Un **gradient passe-bande** supprime les halos flous des bulles voisines et permet de suivre le bord clair sur fond clair.

## Résultats (303 images, 100,7 ms)

- Montée de 367 px pour 4,7 px de dérive latérale ; vitesse verticale moyenne ≈ 3 640 px/s (±19 %), stable par tiers du film.
- Rapport grand axe / petit axe de 1,0 à 2,9 ; aire projetée ±11 % ; corrélation vitesse–déformation ≈ −0,04.
- Centre et barycentre à 2,7 % de la longueur de la bulle près.
- Fin de vie : fusion avec la couche de mousse (pas d'éclatement visible).

## Limites

Résultats en pixels, une seule bulle, validation visuelle sans vérité terrain, contour estimé là où le bord est invisible (images ≈ 150-170), accélération bruitée. Détails et pistes dans `3. Rapport/Historique_projet_PST_2026-11-09.md`.
