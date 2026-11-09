# Historique du projet PST – Suivi d'une bulle (état au 9 novembre 2026)

> Ce fichier sert de **point de reprise** pour le prochain TP : il résume ce qui a été décidé, fait, mesuré, ce qui a échoué et ce qui reste à faire.
> Il ne remplace pas le détail de la conversation, mais contient tout ce qu'il faut pour repartir du bon endroit.

---

## 1. Cadre du projet

- **Projet** : Projet Scientifique Transversal (PST), CentraleSupélec. Caractérisation d'un film liquide / de bulles par imagerie rapide (technique de Defocusing évoquée au départ).
- **Profil de l'étudiant** : Master Management / Business Manager, très peu de bases en maths, physique, chimie et Python. Toujours expliquer simplement, fournir des scripts commentés et prêts à l'emploi (Jupyter / Colab, avec `pip install ...`), en français.
- **Méthode de travail demandée** : avancer **étape par étape**, attendre les retours avant l'étape suivante.
- **Calendrier officiel** :
  - 1er décembre 2026 : TD #02 (traitement de données, planification du traitement massif)
  - 15 décembre 2026 : Jalon #01 (soutenance intermédiaire 1)
  - Janvier – mars 2027 : traitement massif (TD #03 à #07)
  - 2 février 2027 : Jalon #02
  - 18 mars 2027, 23h59 : rendu du rapport final
  - 25 mars 2027 : Jalon #03 (soutenance finale)

## 2. Décisions importantes (changements de cap)

1. **Le TP « boîte de Petri » est abandonné** : c'est un projet annexe, il ne sert pas au PST. L'Étape 1 initiale (calibration épaisseur / défocalisation) n'a donc **pas été réalisée**. Le dossier `1. Photos` ne contenait de toute façon aucune photo de Petri.
2. **Nouvel objectif** : analyser **une bulle précise** et en tirer : (1) sa vitesse, (2) l'évolution de son centre, (3) son barycentre, (4) les forces.
3. **Film choisi : celui à 3000 images/s** (`bulles 3000_...`), plus net que celui à 2000 images/s.
4. **Bulle à suivre « de sa création à son éclatement »**, sur le plus d'images possible.
5. Le script doit commencer par « ÉTAPE 1 » (l'ancienne étape Petri étant abandonnée).

## 3. Données

Dossier : `/Users/linopertusa/Desktop/CentraleSupelec/3. Cours/4. Projet Scientifique Transversal/Projet python/1. Photos`

| Film | Images | Cadence | Format |
|---|---|---|---|
| `bulles 2000_C001H001S0001_S1` | 501 TIF | 2000 im/s (Δt = 0,5 ms) | 1024×1024, 12 bits (stocké sur 16 bits, max 65520) |
| `bulles 3000_C001H001S0001_S1` | 501 TIF | 3000 im/s (Δt = 0,33 ms) | idem |

- Date de tournage : 30/10/2026. Scène : **essaim de bulles** sortant d'un diffuseur d'air (pierre à bulles) dans une cuve, avec une couche de mousse en haut de l'image. Un tube est visible à droite.
- L'éclairage **varie d'une image à l'autre** (flicker) : toujours normaliser chaque image par le niveau du fond clair local.
- **Inconnues à obtenir** : l'**échelle (mm par pixel)** et le **liquide** (eau pure ou eau/glycérine 50 %v) du film à 3000 im/s.

## 4. La bulle étiquetée (film 3000 im/s)

- **Naissance** : une bulle accrochée au pied de la pierre (~x=665, y=805) fusionne avec celle du dessus (images ~78 à 84) ; la bulle formée se détache vers l'image 90. Une nouvelle micro-bulle naît alors au même endroit (~image 102).
- **Étiquette de départ** : image **90**, position **(x=673, y=776)**.
- **Montée** : forme d'abord allongée, puis arrondie, puis **aplatie en lentille** (~image 240).
- **Fin de vie** : arrive sous la mousse vers l'image ~393, y reste coincée et s'y **fond** (images 399-411). **Pas d'éclatement visible** : c'est une fusion avec la mousse.
- Une première bulle (étiquette image 1, position (625, 515)) a aussi été suivie sur les images 1-105 pour tester ; elle n'est plus utilisée.

## 5. Fichiers produits

| Fichier | Rôle |
|---|---|
| `Projet python/2. Code/suivi_bulle.py` | **Script principal** (suivi + mesures + forces + contrôle visuel) |
| `Projet python/2. Code/resultats_bulle/suivi_bulle.csv` | Mesures image par image (303 lignes) |
| `.../resultats_bulle/analyse_bulle.png` | Courbes (trajectoire, vitesses, accélération, centre/barycentre, déformation) |
| `.../resultats_bulle/controle_contours.png` et `.mp4` | Contrôle visuel du contour rouge (planche et vidéo) |
| `Projet python/3. Rapport/Presentation_analyse_bulle.pptx` | Diaporama de 16 slides (algorithme + analyse de la bulle + conclusions), avec notes de présentation |
| `Projet python/3. Rapport/Historique_projet_PST_2026-11-09.md` | Ce fichier |

Dépendances du script : `pip install numpy opencv-python scikit-image scipy matplotlib pandas`.

**Paramètres à modifier en tête de `suivi_bulle.py`** : `FILM`, `FPS`, `IMAGE0`, `X0, Y0`, `REINIT`, `PHASE3`, `IMAGE_FIN`, `MM_PAR_PIXEL` (None = résultats en pixels, **pas de forces**), `RHO_L`, `MU_L`, `SIGMA`, `CA`.
Valeurs actuelles : `IMAGE0=90`, `X0,Y0=673,776`, `REINIT=240`, `PHASE3=294`, `IMAGE_FIN=392`, `FPS=3000`, `MM_PAR_PIXEL=None`, eau pure (998 kg/m³, 1 mPa·s, 0,072 N/m) **par défaut, non confirmé**.

## 6. L'algorithme final (ce qui marche)

Pipeline : **étiqueter → contour initial → suivre → affiner → mesurer**.

1. **Contour initial** (`contour_initial`) : anneau de bords nets (gradient de Sobel), fermé puis rempli, enveloppe convexe. Fonctionne bulle claire ou sombre.
2. **Suivi** : le contour précédent est décalé par corrélation d'image (`cv2.matchTemplate`, recherche ±14 px), puis recalé.
3. **3 phases de recalage** :
   - Phase 1 (images 90-239) : `recaler_phase1`, chaque point cherche le bord net le plus proche (±5 px) ; sans bord net, il ne bouge pas.
   - Phase 2 (240-293) : contour **reconstruit à neuf** à l'image 240 (la bulle est devenue une lentille), `recaler_phase2`.
   - Phase 3 (294-392) : **gradient passe-bande** (`gradient_fin`, différence de flous gaussiens σ=0,8 et σ=3) qui efface les halos flous ; le contour fini sert de point de départ à l'image suivante (fenêtre 6 px vers l'intérieur, 12 px vers l'extérieur).
4. **Finition** (`contour_optimal`, programmation dynamique) : pour 360 angles, choix du rayon (±14 px) qui maximise la netteté du bord avec contrainte de continuité ; on ne garde que les bords réellement visibles (continus sur ≥15°) et on referme le contour à partir d'eux. **C'est l'étape clé de la précision.** Elle est appliquée à chaque image pour la sortie, sans alimenter le suivi (sauf en phase 3).
5. **Mesures** : barycentre (centre de masse de la surface), centre (milieu de la boîte englobante), aire, grand/petit axe, orientation ; vitesse et accélération par dérivées de Savitzky-Golay (fenêtre 21), **calculées séparément par phase**.
6. **Forces** (uniquement si `MM_PAR_PIXEL` est renseigné) : Archimède, poids, inertie avec masse ajoutée, traînée déduite par bilan vertical, C_D, Reynolds, Eötvös. Volume estimé par un sphéroïde aplati (V = π/6 · A² · B).

## 7. Résultats (en pixels, 303 images, de l'image 90 à 392, soit 100,7 ms)

- Montée verticale **367 px**, dérive latérale **4,7 px** (1,3 %).
- Vitesse verticale moyenne **≈ 3 640 px/s** (≈ 40 longueurs de bulle par seconde, grand axe moyen 90 px) ; moyenne par tiers du film : **3 615 / 3 504 / 3 765 px/s** ; écart-type **±19 %** → régime de montée quasi stationnaire.
- Oscillations de vitesse vers **≈ 50 Hz** (résolution ≈ 10 Hz) : **hypothèse à confirmer**.
- Rapport grand axe / petit axe : **1,0 (image 147) → 2,9 (image 336)** ; aire projetée ±11 % ; corrélation vitesse–déformation **−0,04** (aucun lien linéaire sur cette bulle) ; orientation +4° → −60°.
- Écart centre / barycentre : **2,5 px en moyenne (2,7 % de la longueur de la bulle)**, 8,3 px au maximum (image 90, bulle étranglée). On retient le barycentre.
- Aucune force calculée à ce jour (échelle manquante).

## 8. Ce qui a échoué (à ne pas refaire)

1. Écart au fond + seuil d'Otsu : fusion avec les bulles voisines.
2. Seuil de noirceur : halos flous inclus.
3. Watershed sur le gradient : crête brillante exclue.
4. Recalage point par point seul : les **bosses vers les halos flous s'accumulent** d'image en image.
5. Fond fixe, seuils plus stricts, contour qui se rétracte, redétection périodique, recalage en boucle sur toute la durée : débordements ou rétrécissement (6 variantes testées).
6. Retirer le lissage angulaire : les bosses reviennent. Le conserver : les pointes de la bulle s'érodent. D'où la finition par programmation dynamique.
7. **Leçon générale** : un contour par « recalage local » est fragile ; le chercher globalement (programmation dynamique) et utiliser un gradient **passe-bande** pour les bords fins sur fond clair.

## 9. Limites connues

- **Tout est en pixels** (pas d'échelle, pas de liquide confirmé).
- **Une seule bulle** : pas de statistique.
- Validation **visuelle uniquement** (pas de vérité terrain). Un score de netteté du bord existe mais favorise les bords internes : à ne pas sur-interpréter.
- Images ~150-170 : le bas de la bulle sombre est **invisible** sur le fond sombre, le contour y est une estimation (droite entre deux bords visibles).
- Image ~364 : une petite goutte brillante sous la bulle est un peu incluse. Image 90 : bulle étranglée, contour convexe par construction.
- Sauts possibles aux jonctions de phases (images 240 et 294) : pics parasites d'accélération.
- L'**accélération** (dérivée seconde) est bruitée ; les premières millisecondes (bord de série) sont peu fiables.
- Après l'image ~393, le suivi est impossible (la bulle se fond dans la mousse).

## 10. À faire au prochain TP (par ordre de priorité)

1. **Mesurer l'échelle (mm par pixel)** : repérer une longueur connue dans l'image (diamètre du tube, largeur de la cuve ; ou photographier une règle). Renseigner `MM_PAR_PIXEL`.
2. **Confirmer le liquide du film à 3000 im/s** (eau pure ou eau/glycérine 50 %v) et ajuster `RHO_L`, `MU_L`, `SIGMA`.
3. Relancer `suivi_bulle.py` : obtenir vitesses en m/s, forces, C_D, Reynolds, Eötvös. Vérifier que la traînée déduite est ≈ la poussée d'Archimède en moyenne.
4. **Suivre d'autres bulles** du même film (autres naissances sur le même site ; la file de bulles à droite, x ≈ 630-680) puis le film à 2000 im/s, pour confirmer les conclusions (une seule bulle à ce stade).
5. Décider si l'on veut **compléter à la main** l'arrivée sous la mousse (images 393-411) ou accepter l'arrêt à 392.
6. **Jalon #01 (15 décembre)** : finaliser le diaporama avec les forces ; ajouter si besoin la problématique du projet (IFPEN) et le dispositif, qui n'ont pas encore été traités.
7. **Rapport final (18 mars 2027)** : structure section par section, avec explications pédagogiques (viscosité, masse volumique, tension de surface) pour un profil manager. Pas encore commencé.

## 11. Comment reprendre

1. Ouvrir `2. Code/suivi_bulle.py`, vérifier les paramètres de la section 1, renseigner `MM_PAR_PIXEL` puis exécuter (≈ 3 minutes).
2. Regarder d'abord `controle_contours.mp4` (contour rouge) avant les courbes.
3. Mettre à jour le diaporama `Presentation_analyse_bulle.pptx` (slides 11 à 14 : chiffres en m/s, forces).
4. Pour une autre bulle : changer `IMAGE0`, `X0, Y0` (repérer la bulle sur une image avec une grille de coordonnées), puis ajuster `REINIT`, `PHASE3`, `IMAGE_FIN` en inspectant le contrôle visuel : les numéros d'images de changement de phase sont **propres à la bulle actuelle**.

## 12. Notes techniques

- Les expérimentations intermédiaires (variantes d'algorithme, figures) ont été faites dans un dossier temporaire de session et **ne sont pas conservées** : seul `suivi_bulle.py` contient l'algorithme final.
- Le diaporama a été construit avec pptxgenjs ; il passe la validation de structure. Les dernières retouches des slides 7, 10 et 16 n'ont pas été revérifiées visuellement : à contrôler à l'ouverture dans PowerPoint.
- Fichiers d'images : TIF 16 bits, lire avec `cv2.imread(chemin, cv2.IMREAD_UNCHANGED)` puis diviser par 65520.
