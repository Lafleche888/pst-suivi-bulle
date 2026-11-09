# ============================================================
# ÉTAPE 1 – Suivi d'UNE bulle étiquetée, de sa naissance à son arrivée à la surface
#           (film 3000 images/s)
#   1. vitesse   2. centre   3. barycentre   4. forces
# Installation (1 fois) :
#   pip install numpy opencv-python scikit-image scipy matplotlib pandas
# ============================================================
import os, glob
import numpy as np, cv2, pandas as pd
import matplotlib.pyplot as plt
from scipy import ndimage as ndi
from scipy.ndimage import map_coordinates, median_filter, gaussian_filter1d
from scipy.signal import savgol_filter
from skimage import measure
from skimage.morphology import convex_hull_image

# ------------------------------------------------------------
# 1) PARAMÈTRES À MODIFIER
# ------------------------------------------------------------
BASE   = "/Users/linopertusa/Desktop/CentraleSupelec/3. Cours/4. Projet Scientifique Transversal/Projet python/1. Photos"
FILM   = "bulles 3000_C001H001S0001_S1"
FPS    = 3000                 # images par seconde (cf. fichier .cihx)

# --- ÉTIQUETTE : la bulle suivie ---
# Naissance : une bulle accrochée au pied de la pierre (~x=665, y=805) fusionne avec celle du dessus
# (images ~78-84), puis la bulle formée se détache (image ~90). On la suit ensuite jusqu'à la surface.
IMAGE0 = 90                   # image de départ (détachement achevé)
X0, Y0 = 673, 776             # position (pixels) de la bulle sur IMAGE0
REINIT = 240                  # image où le contour est reconstruit à neuf (la bulle s'est aplatie en "lentille")
PHASE3 = 294                  # à partir d'ici : bord haut clair sur fond clair -> gradient « passe-bande » (voir gradient_fin)
IMAGE_FIN = 392               # la bulle touche la mousse vers 393 puis s'y fond : le suivi s'arrête avant

# --- ÉCHELLE : à renseigner pour avoir des mm, m/s et des forces ---
MM_PAR_PIXEL = None           # ex. 0.05 (None => résultats en pixels, pas de forces)

# --- LIQUIDE (à confirmer !) ---
RHO_L = 998.0                 # masse volumique [kg/m³]  (eau 20 °C ; eau/glycérine 50 %v ≈ 1130)
MU_L  = 1.0e-3                # viscosité dynamique [Pa·s] (eau ≈ 1e-3 ; eau/glycérine 50 %v ≈ 6e-3)
SIGMA = 0.072                 # tension de surface [N/m]
RHO_G = 1.2                   # masse volumique de l'air [kg/m³]
G     = 9.81
CA    = 0.6                   # coefficient de masse ajoutée (0,5 = sphère ; plus pour une bulle aplatie)

SORTIE = os.path.join(BASE, "..", "2. Code", "resultats_bulle")
os.makedirs(SORTIE, exist_ok=True)

# ------------------------------------------------------------
# 2) OUTILS D'IMAGE
# ------------------------------------------------------------
def lire(n):
    """Lit l'image n (12 bits) et la convertit en nombres entre 0 et 1."""
    f = glob.glob(f"{BASE}/{FILM}/*{n:06d}.tif")[0]
    return cv2.imread(f, cv2.IMREAD_UNCHANGED).astype(np.float32) / 65520

def normalise(im, cx, cy):
    """Corrige les variations d'éclairage : fond clair local ramené à ~1."""
    x1, y1 = max(int(cx) - 130, 0), max(int(cy) - 130, 0)
    return im / np.percentile(im[y1:y1 + 260, x1:x1 + 260], 92)

def gradient(imn):
    """Force des bords (là où l'image change vite = contour de la bulle)."""
    s = cv2.GaussianBlur(imn, (0, 0), 1.0)
    return np.hypot(cv2.Sobel(s, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(s, cv2.CV_32F, 0, 1, ksize=3))

def gradient_fin(imn):
    """Gradient « passe-bande » : ne garde que les bords FINS (la bulle) et supprime les transitions larges
    (halos flous des bulles voisines). C'est ce qui permet de suivre le bord haut clair sur fond clair."""
    bp = cv2.GaussianBlur(imn, (0, 0), 0.8) - cv2.GaussianBlur(imn, (0, 0), 3.0)
    return np.hypot(cv2.Sobel(bp, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(bp, cv2.CV_32F, 0, 1, ksize=3))

H = 70   # demi-taille de la zone de recherche pour (ré)initialiser le contour (px)

def contour_initial(im, cx, cy):
    """Contour de la bulle à partir de l'anneau de bords nets (valable bulle claire ou sombre)."""
    x1, y1 = int(cx) - H, int(cy) - H
    roi = im[y1:y1 + 2 * H, x1:x1 + 2 * H]; roi = roi / np.percentile(roi, 92)
    g = cv2.GaussianBlur(gradient(roi), (0, 0), 1.5)
    yy, xx = np.mgrid[:2 * H, :2 * H]
    g99 = np.percentile(g[np.hypot(xx - H, yy - H) < 40], 99)
    for TH in (0.35, 0.42, 0.28, 0.5, 0.2):                  # on essaie plusieurs seuils
        ed = (g > TH * g99).astype(np.uint8)
        ed = cv2.morphologyEx(ed, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        lab = measure.label(ndi.binary_fill_holes(ed > 0))   # on remplit l'anneau fermé
        cand = [r for r in measure.regionprops(lab) if r.area > 300]
        if not cand: continue
        r = min(cand, key=lambda r: np.hypot(r.centroid[1] - H, r.centroid[0] - H))
        mk = cv2.morphologyEx((lab == r.label).astype(np.uint8), cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))) > 0
        if mk.sum() == 0: continue
        F = np.zeros(im.shape, bool); F[y1:y1 + 2 * H, x1:x1 + 2 * H] = convex_hull_image(mk)
        return F
    raise RuntimeError("Bulle introuvable : vérifier X0, Y0 / REINIT")

def _polaire(mk, nth, rmax):
    cy, cx = ndi.center_of_mass(mk)
    th = np.linspace(0, 2 * np.pi, nth, endpoint=False); rr = np.arange(0, rmax, 0.5)
    X = cx + np.outer(np.cos(th), rr); Y = cy + np.outer(np.sin(th), rr)
    dedans = map_coordinates(mk.astype(float), [Y, X], order=1) > 0.5
    R = np.array([rr[d].max() if d.any() else 0 for d in dedans])
    return cx, cy, th, rr, X, Y, R

def _polygone(shape, cx, cy, th, Rn):
    poly = np.stack([cx + Rn * np.cos(th), cy + Rn * np.sin(th)], 1)
    out = np.zeros(shape, np.uint8); cv2.fillPoly(out, [np.round(poly).astype(np.int32)], 1)
    return out > 0

def recaler_phase1(mk, g, bas=5, haut=5, nth=240, rmax=140):
    """Phase 1 (bulle qui se détache et s'arrondit, fond sombre puis clair).
    Chaque point du contour est recalé sur le bord net le plus proche (±5 px) ;
    s'il n'y a pas de bord net (clair sur clair), il ne bouge pas."""
    cx, cy, th, rr, X, Y, R = _polaire(mk, nth, rmax)
    Gr = map_coordinates(g, [Y, X], order=1)
    seuil = 0.35 * np.median(Gr[np.arange(nth), np.clip((R / 0.5).astype(int), 0, len(rr) - 1)])
    Rn = R.copy()
    for i in range(nth):
        sel = (rr >= R[i] - bas) & (rr <= R[i] + haut)
        j = np.argmax(Gr[i, sel] * np.exp(-0.5 * ((rr[sel] - R[i]) / 3.0) ** 2))   # reste proche de la position précédente
        if Gr[i, sel][j] > seuil: Rn[i] = rr[sel][j]
    Rn = gaussian_filter1d(median_filter(Rn, size=11, mode="wrap"), 3, mode="wrap")
    return _polygone(mk.shape, cx, cy, th, Rn)

def recaler_phase2(mk, g, bas=5, haut=4, nth=240, rmax=110):
    """Phase 2 (bulle aplatie en lentille, fond clair) : recalage sur le pic de gradient (±5 px)."""
    cx, cy, th, rr, X, Y, R = _polaire(mk, nth, rmax)
    Gr = map_coordinates(g, [Y, X], order=1); Rn = R.copy()
    for i in range(nth):
        sel = (rr >= R[i] - bas) & (rr <= R[i] + haut)
        Rn[i] = rr[sel][np.argmax(Gr[i, sel] * (1 + 0.05 * (rr[sel] - R[i])))]
    Rn = gaussian_filter1d(median_filter(Rn, size=11, mode="wrap"), 3, mode="wrap")
    return _polygone(mk.shape, cx, cy, th, Rn)

def contour_optimal(mk, g, W=14, Win=None, Wout=None, nth=360, mu=0.35, out_bias=0.35, seuil_bord=0.45, run=15):
    """FINITION PRÉCISE du contour, par programmation dynamique.
    1) Pour chacun des 360 angles autour de la bulle, on choisit le rayon (à ±W px du contour approximatif)
       qui maximise la netteté du bord, sous la contrainte que le contour reste continu
       (le rayon ne peut pas sauter d'un angle à l'autre) et avec une légère préférence pour le bord extérieur.
       Un halo flou voisin ne peut donc plus créer de « bosse ».
    2) On ne garde que les points réellement appuyés sur un bord net, sur au moins  angles consécutifs ;
       le contour est refermé à partir de ces seuls points (utile quand la bulle sombre se confond avec un fond sombre,
       où aucun bord n'existe : le contour relie alors directement les deux portions de bord visibles)."""
    Win = W if Win is None else Win; Wout = W if Wout is None else Wout     # fenêtre de recherche vers l'intérieur / l'extérieur
    cx, cy, th, rr, X, Y, R = _polaire(mk, nth, 170)
    R = median_filter(R, size=9, mode="wrap").astype(float)
    d = np.arange(-Win, Wout + 0.01, 0.5); K = len(d)
    Xs = cx + np.cos(th)[:, None] * (R[:, None] + d[None, :]); Ys = cy + np.sin(th)[:, None] * (R[:, None] + d[None, :])
    Gs = map_coordinates(g, [Ys, Xs], order=1)
    z = int(round(Win / 0.5)); Gs = Gs / np.median(Gs[:, max(z - 4, 0):z + 5])
    cout = -Gs - out_bias * (d[None, :] / W)                     # on veut un bord net, de préférence extérieur
    C = np.tile(cout, (3, 1)); N = len(C)                        # 3 tours pour que le contour se referme
    acc = np.zeros_like(C); retour = np.zeros(C.shape, np.int16); acc[0] = C[0]
    for i in range(1, N):
        meilleur = np.full(K, 1e9); arg = np.zeros(K, np.int16)
        for dk in range(-2, 3):                                  # le rayon varie d'au plus 1 px par angle
            sh = np.full(K, 1e9)
            if dk < 0: sh[:dk] = acc[i - 1][-dk:]
            elif dk > 0: sh[dk:] = acc[i - 1][:-dk]
            else: sh = acc[i - 1].copy()
            sh = sh + mu * abs(dk); m = sh < meilleur; meilleur[m] = sh[m]; arg[m] = dk
        acc[i] = meilleur + C[i]; retour[i] = arg
    k = int(np.argmin(acc[-1])); chemin = np.zeros(N, int); chemin[-1] = k
    for i in range(N - 1, 0, -1):
        chemin[i - 1] = k - retour[i][k]; k = chemin[i - 1]
    chemin = chemin[nth:2 * nth]
    Rn = gaussian_filter1d(R + d[chemin], 1.0, mode="wrap")
    force = Gs[np.arange(nth), chemin]                           # netteté du bord choisi, pour chaque angle
    ok = (force > seuil_bord) | (ndi.uniform_filter1d(force, 11, mode="wrap") > 1.2 * seuil_bord)
    ok = ndi.binary_opening(np.tile(ok, 3), structure=np.ones(run))[nth:2 * nth]
    if ok.sum() < 60: ok[:] = True                               # sécurité : trop peu de bord net -> on garde tout
    pts = np.stack([cx + Rn[ok] * np.cos(th[ok]), cy + Rn[ok] * np.sin(th[ok])], 1)
    out = np.zeros(mk.shape, np.uint8); cv2.fillPoly(out, [cv2.convexHull(np.round(pts).astype(np.int32))], 1)
    return out > 0

def finition(M, g, **kw):
    """Contour final précis (utilisé pour toutes les mesures)."""
    F = contour_optimal(M, g, **kw)
    return cv2.morphologyEx(F.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))) > 0

# ------------------------------------------------------------
# 3) SUIVI : on décale le contour précédent (corrélation d'image), puis on le recale sur le bord
#    (M = contour de suivi approximatif ; F = contour final précis, utilisé pour toutes les mesures)
# ------------------------------------------------------------
print("Suivi de la bulle…")
im = lire(IMAGE0)
M = contour_initial(im, X0, Y0)
prev = cv2.GaussianBlur(normalise(im, X0, Y0), (0, 0), 1.0)
masques, phase = {IMAGE0: finition(M, gradient(normalise(im, X0, Y0)))}, {IMAGE0: 1}
Fprec = masques[IMAGE0]
for n in range(IMAGE0 + 1, IMAGE_FIN + 1):
    im = lire(n); ys, xs = np.nonzero(Fprec if n >= PHASE3 else M)
    imn = normalise(im, xs.mean(), ys.mean()); ims = cv2.GaussianBlur(imn, (0, 0), 1.0)
    a, b, c, d = xs.min() - 10, xs.max() + 10, ys.min() - 10, ys.max() + 10
    s = 14                                                        # recherche à ±14 px
    res = cv2.matchTemplate(ims[c - s:d + s, a - s:b + s], prev[c:d, a:b], cv2.TM_CCOEFF_NORMED)
    loc = cv2.minMaxLoc(res)[3]; dx, dy = loc[0] - s, loc[1] - s
    Ms = np.roll(np.roll(Fprec if n >= PHASE3 else M, dy, 0), dx, 1)
    if n >= PHASE3:                                               # phase 3 : on repart du contour fini à chaque image
        Fprec = finition(Ms, gradient_fin(imn), W=12, Win=6, Wout=12, out_bias=0.4)
        masques[n] = Fprec; phase[n] = 3; prev = ims
        continue
    if n < REINIT:
        M = recaler_phase1(Ms, gradient(imn)); phase[n] = 1
    else:
        if n == REINIT:                                           # contour reconstruit à neuf sur la "lentille"
            ys, xs = np.nonzero(Ms); M = contour_initial(im, xs.mean(), ys.mean())
        else:
            M = recaler_phase2(Ms, gradient(imn))
        phase[n] = 2
    Fprec = masques[n] = finition(M, gradient(imn)); prev = ims

# ------------------------------------------------------------
# 4) MESURES : centre, barycentre, axes, aire
# ------------------------------------------------------------
lignes = []
for n, M in masques.items():
    r = measure.regionprops(M.astype(np.uint8))[0]
    ys, xs = np.nonzero(M)
    lignes.append(dict(image=n, phase=phase[n], t_s=(n - IMAGE0) / FPS,
        x_bary=r.centroid[1], y_bary=r.centroid[0],                       # BARYCENTRE (centre de masse de la surface)
        x_centre=(xs.min() + xs.max()) / 2, y_centre=(ys.min() + ys.max()) / 2,   # CENTRE (milieu de la boîte englobante)
        aire_px2=r.area, grand_axe_px=r.axis_major_length, petit_axe_px=r.axis_minor_length,
        angle_rad=r.orientation))
t = pd.DataFrame(lignes)
s_mm = MM_PAR_PIXEL if MM_PAR_PIXEL else 1.0
u = "mm" if MM_PAR_PIXEL else "px"
for c in ("x_bary", "y_bary", "x_centre", "y_centre"):
    t[c + "_u"] = t[c] * s_mm
t["ecart_centre_bary_u"] = np.hypot(t.x_bary_u - t.x_centre_u, t.y_bary_u - t.y_centre_u)
t["ratio_axes"] = t.grand_axe_px / t.petit_axe_px                        # déformation (1 = rond)

# ------------------------------------------------------------
# 5) VITESSE ET ACCÉLÉRATION (dérivées lissées, Δt = 1/FPS)
#    calculées séparément pour chaque phase (le contour est reconstruit à REINIT : saut de barycentre possible)
# ------------------------------------------------------------
dt = 1 / FPS
def derive(col, k):
    out = np.zeros(len(t))
    for p in t.phase.unique():
        i = (t.phase == p).values
        fen = min(21, (i.sum() // 2) * 2 - 1)
        out[i] = savgol_filter(t.loc[i, col], fen, 3, deriv=k, delta=dt)
    return out
t["vx_u"] = derive("x_bary_u", 1)
t["vy_u"] = -derive("y_bary_u", 1)               # axe image vers le bas -> on inverse : montée > 0
t["v_u"] = np.hypot(t.vx_u, t.vy_u)
t["ay_u"] = -derive("y_bary_u", 2)

# ------------------------------------------------------------
# 6) FORCES (nécessite l'échelle MM_PAR_PIXEL)
# ------------------------------------------------------------
if MM_PAR_PIXEL:
    m = MM_PAR_PIXEL * 1e-3                                              # m par pixel
    A = t.grand_axe_px * m; B = t.petit_axe_px * m                       # axes [m]
    V = np.pi / 6 * A**2 * B                                             # volume : sphéroïde aplati (2 grands axes = A, 1 petit = B)
    S = t.aire_px2 * m**2                                                # surface projetée [m²]
    v = t.v_u * 1e-3; vy = t.vy_u * 1e-3; ay = t.ay_u * 1e-3
    deq = (6 * V / np.pi) ** (1 / 3)                                     # diamètre équivalent [m]
    t["V_mm3"] = V * 1e9; t["d_eq_mm"] = deq * 1e3
    t["F_poids_uN"]      = -RHO_G * V * G * 1e6                          # poids (vers le bas, négligeable)
    t["F_archimede_uN"]  = RHO_L * V * G * 1e6                           # poussée d'Archimède (vers le haut)
    t["F_inertie_uN"]    = (RHO_G + CA * RHO_L) * V * ay * 1e6           # (masse + masse ajoutée) × accélération
    t["F_trainee_uN"]    = t.F_archimede_uN + t.F_poids_uN - t.F_inertie_uN   # traînée DÉDUITE (bilan vertical)
    t["Cd"]  = 2 * t.F_trainee_uN * 1e-6 / (RHO_L * S * np.maximum(vy, 1e-6) ** 2)
    t["Re"]  = RHO_L * v * deq / MU_L                                    # Reynolds : inertie / viscosité
    t["Eo"]  = (RHO_L - RHO_G) * G * deq**2 / SIGMA                      # Eötvös : gravité / tension de surface
t.to_csv(os.path.join(SORTIE, "suivi_bulle.csv"), index=False)

# ------------------------------------------------------------
# 7) GRAPHIQUES
# ------------------------------------------------------------
tm = t.t_s * 1000
seps = [t.loc[t.phase == p, "t_s"].min() * 1000 for p in (2, 3)]        # instants de changement de méthode de contour
fig, ax = plt.subplots(2, 3, figsize=(16, 8))
ax[0, 0].plot(t.x_bary_u, -t.y_bary_u, "o-", ms=3, label="barycentre")
ax[0, 0].plot(t.x_centre_u, -t.y_centre_u, "s--", ms=3, label="centre (boîte)")
ax[0, 0].set(title="Trajectoire", xlabel=f"x [{u}]", ylabel=f"-y [{u}] (haut = montée)"); ax[0, 0].legend(); ax[0, 0].axis("equal")
ax[0, 1].plot(tm, t.vy_u, label="vitesse verticale (montée)"); ax[0, 1].plot(tm, t.vx_u, label="vitesse horizontale")
ax[0, 1].plot(tm, t.v_u, "k", label="norme |v|"); ax[0, 1].set(title="Vitesse", xlabel="temps [ms]", ylabel=f"[{u}/s]"); ax[0, 1].legend()
ax[0, 2].plot(tm, t.ay_u); ax[0, 2].set(title="Accélération verticale", xlabel="temps [ms]", ylabel=f"[{u}/s²]")
ax[1, 0].plot(tm, t.ecart_centre_bary_u); ax[1, 0].set(title="Écart centre ↔ barycentre", xlabel="temps [ms]", ylabel=f"[{u}]")
ax[1, 1].plot(tm, t.ratio_axes); ax[1, 1].set(title="Déformation : grand axe / petit axe", xlabel="temps [ms]")
if MM_PAR_PIXEL:
    for col, lab in (("F_archimede_uN", "Archimède"), ("F_trainee_uN", "Traînée (déduite)"), ("F_inertie_uN", "Inertie")):
        ax[1, 2].plot(tm, t[col], label=lab)
    ax[1, 2].set(title="Forces verticales", xlabel="temps [ms]", ylabel="[µN]"); ax[1, 2].legend()
else:
    ax[1, 2].text(.5, .5, "Renseigner MM_PAR_PIXEL\npour calculer les forces", ha="center", va="center"); ax[1, 2].axis("off")
for a in ax.flat:
    a.grid(alpha=.3)
for a in (ax[0, 1], ax[0, 2], ax[1, 0], ax[1, 1]):
    for sp in seps: a.axvline(sp, color="gray", ls=":")                 # pointillés = changement de méthode de contour
plt.tight_layout(); plt.savefig(os.path.join(SORTIE, "analyse_bulle.png"), dpi=160); plt.show()

# ------------------------------------------------------------
# 8) CONTRÔLE VISUEL : planche de contours + vidéo zoomée
# ------------------------------------------------------------
def vignette(n, z=3, h=75):
    M = masques[n]; cy, cx = ndi.center_of_mass(M); x1, y1 = int(cx) - h, int(cy) - h
    roi = lire(n)[y1:y1 + 2 * h, x1:x1 + 2 * h]
    g = (255 * (roi / np.percentile(roi, 99.5)).clip(0, 1)).astype(np.uint8)
    c = cv2.cvtColor(cv2.resize(g, None, fx=z, fy=z, interpolation=cv2.INTER_CUBIC), cv2.COLOR_GRAY2BGR)
    for cc in measure.find_contours(np.pad(M[y1:y1 + 2 * h, x1:x1 + 2 * h], 1).astype(float), .5):
        cv2.polylines(c, [((cc[:, ::-1] - .5) * z).astype(np.int32)], True, (0, 0, 255), 1)
    row = t[t.image == n].iloc[0]
    cv2.drawMarker(c, (int((row.x_bary - x1) * z), int((row.y_bary - y1) * z)), (0, 255, 0), cv2.MARKER_CROSS, 14, 2)   # barycentre (vert)
    cv2.drawMarker(c, (int((row.x_centre - x1) * z), int((row.y_centre - y1) * z)), (255, 160, 0), cv2.MARKER_DIAMOND, 10, 2)  # centre (bleu)
    cv2.putText(c, f"image {n}  t={row.t_s*1000:.1f} ms", (6, 22), 0, .6, (0, 255, 255), 2)
    return c

ids = np.linspace(IMAGE0, IMAGE_FIN, 12).astype(int)
v = [vignette(n) for n in ids]
planche = np.vstack([np.hstack(v[i:i + 4]) for i in (0, 4, 8)])
cv2.imwrite(os.path.join(SORTIE, "controle_contours.png"), planche)

taille = vignette(IMAGE0).shape[1::-1]
out = cv2.VideoWriter(os.path.join(SORTIE, "controle_contours.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 15, taille)
for n in masques: out.write(vignette(n))
out.release()
plt.figure(figsize=(16, 12)); plt.imshow(planche[:, :, ::-1]); plt.axis("off"); plt.show()
print("Résultats enregistrés dans :", os.path.abspath(SORTIE))
