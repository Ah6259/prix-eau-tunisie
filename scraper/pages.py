"""Génère le contenu statique lisible par Google à partir de web/data/produits.json :
  - la liste des prix écrite dans web/index.html (entre les marqueurs <!--LISTE--> et <!--MARQUES-->),
    remplacée ensuite par l'application JavaScript chez le visiteur ;
  - une page par marque : web/marque/<marque>/index.html ;
  - web/sitemap.xml.

Usage : python scraper/pages.py   (lancé après scrape.py, chaque jour par GitHub Actions)
"""
import html
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SITE = "https://ah6259.github.io/prix-eau-tunisie/"  # à changer avec le nom de domaine
VOLUME_MAX_STIKA = 3

esc = html.escape


def taille_stika(vol):  # même règle que scrape.py et app.js
    return 12 if vol <= 0.75 else 6


def dt(v):
    return f"{v:.3f}".replace(".", ",") + " DT"


def litres(v):
    return f"{round(v * 100)} cl" if v < 1 else f"{v:g} L".replace(".", ",")


def slug(marque):
    return re.sub(r"[^a-z0-9]+", "-", marque.lower()).strip("-")


def nom_marque(m):
    return m[:1] + m[1:].lower()


def formats(data):
    """Regroupe bouteilles et stikas par marque/type/volume, comme app.js."""
    enseignes = data["enseignes"]
    lignes = {}
    for p in data["produits"]:
        n, vol = p["nb_unites"], p["volume_l"]
        stika = n > 1 and n == taille_stika(vol)
        if n > 1 and not stika:
            continue  # autres packs : sans intérêt pour le référencement
        l = lignes.setdefault((p["marque"], p["type"], vol), {
            "marque": p["marque"], "type": p["type"], "volume_l": vol, "image": None,
            "bouteille": [], "stika": [],
        })
        l["image"] = l["image"] or p.get("image")
        for o in p["offres"]:
            (l["stika"] if stika else l["bouteille"]).append((o["prix"], enseignes[o["enseigne"]]["nom"]))
    for l in lignes.values():
        l["bouteille"].sort()
        l["stika"].sort()
        n = taille_stika(l["volume_l"])
        l["n_stika"] = n
        b = l["bouteille"][0][0] if l["bouteille"] else None
        calc = b * n if b is not None and l["volume_l"] < VOLUME_MAX_STIKA else None
        reel = l["stika"][0][0] if l["stika"] else None
        l["prix_bouteille"] = b
        l["prix_stika"] = min(x for x in (calc, reel) if x is not None) if (calc or reel) else None
        l["stika_calcule"] = l["prix_stika"] is not None and l["prix_stika"] == calc and (reel is None or calc < reel)
        l["prix_litre"] = min(x for x in (b, l["prix_stika"] / n if l["prix_stika"] else None) if x is not None) / l["volume_l"]
    par_marque = {}
    for l in sorted(lignes.values(), key=lambda l: (l["type"], l["volume_l"])):
        par_marque.setdefault(l["marque"], []).append(l)
    return par_marque


def tableau(lignes, avec_magasins=False):
    tete = "<th>Format</th><th class=\"num\">Bouteille</th><th class=\"num\">Stika</th>"
    if avec_magasins:
        tete += "<th>Magasins</th>"
    rangs = []
    for l in lignes:
        gaz = '<span class="gaz">gazeuse</span>' if l["type"] == "gazeuse" else ""
        stika = "—" if l["prix_stika"] is None else dt(l["prix_stika"]) + ("<sup>*</sup>" if l["stika_calcule"] else "")
        cel = (f'<td class="format">{litres(l["volume_l"])}{gaz}<br><small>{dt(l["prix_litre"])}/L</small></td>'
               f'<td class="num">{dt(l["prix_bouteille"]) if l["prix_bouteille"] is not None else "—"}</td>'
               f'<td class="num meilleur">{stika}<br><small class="nb">{l["n_stika"]} bouteilles</small></td>')
        if avec_magasins:
            mags = [f"{esc(e)} {dt(p)}" for p, e in l["bouteille"]] + [f"{esc(e)} stika {dt(p)}" for p, e in l["stika"]]
            cel += f'<td class="magasins">{" · ".join(mags)}</td>'
        rangs.append(f"<tr>{cel}</tr>")
    return f"<table><thead><tr>{tete}</tr></thead><tbody>{''.join(rangs)}</tbody></table>"


def vignette(image, marque, prefixe=""):
    if image:
        return f'<div class="vignette"><img src="{prefixe}{esc(image)}" alt="Bouteille d\'eau {esc(nom_marque(marque))}" loading="lazy"></div>'
    return f'<div class="vignette"><span class="initiale">{esc(marque[0])}</span></div>'


def visuel(lignes):
    return next((l["image"] for l in lignes if l["image"] and l["volume_l"] == 1.5), None) or \
        next((l["image"] for l in lignes if l["image"]), None)


def remplacer(texte, marqueur, contenu):
    motif = re.compile(rf"(<!--{marqueur}-->).*?(<!--/{marqueur}-->)", re.S)
    assert motif.search(texte), f"marqueur {marqueur} absent de index.html"
    return motif.sub(lambda m: m.group(1) + contenu + m.group(2), texte)


def page_marque(marque, lignes, maj):
    nom = nom_marque(marque)
    mini_b = min((l["prix_bouteille"] for l in lignes if l["prix_bouteille"]), default=None)
    mini_s = min((l["prix_stika"] for l in lignes if l["prix_stika"]), default=None)
    desc = f"Prix de l'eau minérale {nom} en Tunisie"
    if mini_b:
        desc += f" : bouteille dès {dt(mini_b)}"
    if mini_s:
        desc += f", stika dès {dt(mini_s)}"
    desc += ". Comparez Carrefour, Géant, Monoprix et Aziza, prix mis à jour chaque jour."
    url = f"{SITE}marque/{slug(marque)}/"
    img = visuel(lignes)
    og_img = f"{SITE}{img}" if img else f"{SITE}img/partage.png"
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prix eau {esc(nom)} en Tunisie : bouteille et stika | Prix de l'eau</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="canonical" href="{url}">
  <meta property="og:type" content="website">
  <meta property="og:title" content="Prix eau {esc(nom)} en Tunisie : bouteille et stika">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{og_img}">
  <meta property="og:locale" content="fr_TN">
  <meta name="theme-color" content="#0b6fa4">
  <link rel="icon" href="../../img/icone.svg" type="image/svg+xml">
  <link rel="stylesheet" href="../../style.css">
</head>
<body>
  <header class="entete">
    <div class="entete-in">
      <a class="titre" href="../../">
        <img src="../../img/icone.svg" alt="" width="36" height="36">
        <div>
          <p class="nom-site">Prix de l'eau</p>
          <p class="sous-titre">Eaux minérales en Tunisie · mis à jour le {maj}</p>
        </div>
      </a>
    </div>
  </header>
  <main class="page-marque">
    <p class="fil"><a href="../../">Toutes les marques</a> › {esc(nom)}</p>
    <article class="carte">
      <div class="carte-tete">
        {vignette(img, marque, "../../")}
        <div>
          <h1>Prix de l'eau {esc(nom)} en Tunisie</h1>
          <p class="des">{esc(desc)}</p>
        </div>
      </div>
      {tableau(lignes, avec_magasins=True)}
    </article>
    <p class="retour"><a href="../../">← Comparer avec les autres marques</a></p>
  </main>
  <footer class="pied">
    <p><b>Stika</b> (fardeau) = pack de 6 bouteilles, ou 12 en 50 cl. <sup>*</sup> Prix calculé (nombre de bouteilles × prix bouteille).</p>
    <p>Prix relevés chaque jour sur les sites des enseignes. Les prix en magasin peuvent différer.</p>
  </footer>
  <script data-goatcounter="https://prix-eau-tunisie.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
</body>
</html>
"""


def main():
    data = json.loads((WEB / "data" / "produits.json").read_text(encoding="utf-8"))
    d = datetime.fromisoformat(data["maj"])
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
            "septembre", "octobre", "novembre", "décembre"][d.month - 1]
    maj = f"{d.day} {mois} {d.year}"
    par_marque = formats(data)
    ordre = sorted(par_marque, key=lambda m: min(l["prix_litre"] for l in par_marque[m]))

    # 1. Liste statique dans index.html (remplacée par app.js chez le visiteur)
    cartes = "".join(f"""
      <article class="carte">
        <div class="carte-tete">{vignette(visuel(par_marque[m]), m)}
          <div><h2><a href="marque/{slug(m)}/">{esc(nom_marque(m))}</a></h2></div>
        </div>
        {tableau(par_marque[m])}
      </article>""" for m in ordre)
    liens = "".join(f'<li><a href="marque/{slug(m)}/">Prix eau {esc(nom_marque(m))}</a></li>' for m in sorted(par_marque))
    index = WEB / "index.html"
    t = index.read_text(encoding="utf-8")
    t = remplacer(t, "LISTE", f'<div class="grille">{cartes}\n      </div>')
    t = remplacer(t, "MARQUES", f"<ul>{liens}</ul>")
    t = remplacer(t, "MAJ", maj)
    index.write_text(t, encoding="utf-8")

    # 2. Une page par marque (les anciennes sont supprimées si la marque disparaît)
    dossier = WEB / "marque"
    if dossier.exists():
        shutil.rmtree(dossier)
    for m, lignes in par_marque.items():
        f = dossier / slug(m) / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(page_marque(m, lignes, maj), encoding="utf-8")

    # 3. Plan du site
    jour = d.date().isoformat()
    urls = [SITE] + [f"{SITE}marque/{slug(m)}/" for m in sorted(par_marque)]
    (WEB / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{jour}</lastmod></url>\n" for u in urls)
        + "</urlset>\n", encoding="utf-8")
    print(f"index.html + {len(par_marque)} pages marque + sitemap.xml ({len(urls)} URL)")


if __name__ == "__main__":
    main()
