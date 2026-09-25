"""Génère le contenu statique pour le référencement, à partir de web/data/produits.json :
  - web/index.html : liste des prix, résumé du jour, FAQ, liens, données structurées
    (entre les marqueurs <!--XXX--> ... <!--/XXX-->) ; la liste est remplacée par app.js chez le visiteur ;
  - une page par marque : web/marque/<marque>/index.html ;
  - une page par format : web/format/<format>/index.html ;
  - web/404.html et web/sitemap.xml.

Usage : python scraper/pages.py   (lancé après scrape.py, chaque jour par GitHub Actions)
"""
import html
import json
import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SITE = "https://ah6259.github.io/prix-eau-tunisie/"  # à changer avec le nom de domaine
CHEMIN = "/prix-eau-tunisie/"                         # chemin du site sur le serveur (pour la page 404)
GOATCOUNTER = '<script data-goatcounter="https://prix-eau-tunisie.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>'
VOLUME_MAX_STIKA = 3

# slug, nom affiché, test sur le volume (mêmes seuils que app.js)
FORMATS = [
    ("50-cl", "50 cl", lambda v: v <= 0.75),
    ("1-l", "1 L", lambda v: 0.75 < v < 1.25),
    ("1-5-l", "1,5 L", lambda v: 1.25 <= v < 1.6),
    ("2-l", "2 L", lambda v: 1.6 <= v < VOLUME_MAX_STIKA),
    ("bonbonne", "bonbonne (5 à 19 L)", lambda v: v >= VOLUME_MAX_STIKA),
]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

esc = html.escape


# ---------------------------------------------------------------- utilitaires
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


def liste_fr(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " et " + xs[-1]


def format_de(vol):
    return next(f for f in FORMATS if f[2](vol))


def ld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>"


def fil_ariane(elements):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(elements)]}


# ---------------------------------------------------------------- données
def lignes_produits(data):
    """Une ligne par marque/type/volume, avec offres bouteille et stika (comme app.js)."""
    ens = data["enseignes"]
    lignes = {}
    for p in data["produits"]:
        n, vol = p["nb_unites"], p["volume_l"]
        est_stika = n > 1 and n == taille_stika(vol)
        if n > 1 and not est_stika:
            continue  # autres packs
        l = lignes.setdefault((p["marque"], p["type"], vol), {
            "marque": p["marque"], "type": p["type"], "volume_l": vol, "image": None, "bouteille": [], "stika": []})
        l["image"] = l["image"] or p.get("image")
        for o in p["offres"]:
            (l["stika"] if est_stika else l["bouteille"]).append((o["prix"], ens[o["enseigne"]]["nom"], o.get("url")))
    for l in lignes.values():
        l["bouteille"].sort()
        l["stika"].sort()
        n = l["n_stika"] = taille_stika(l["volume_l"])
        b = l["prix_bouteille"] = l["bouteille"][0][0] if l["bouteille"] else None
        calc = b * n if b is not None and l["volume_l"] < VOLUME_MAX_STIKA else None
        reel = l["stika"][0][0] if l["stika"] else None
        candidats = [x for x in (calc, reel) if x is not None]
        l["prix_stika"] = min(candidats) if candidats else None
        l["stika_calcule"] = calc is not None and l["prix_stika"] == calc and (reel is None or calc < reel)
        par_bouteille = [x for x in (b, l["prix_stika"] / n if l["prix_stika"] else None) if x is not None]
        l["prix_litre"] = min(par_bouteille) / l["volume_l"]
        l["format"] = format_de(l["volume_l"])[0]
        l["nom"] = f"{nom_marque(l['marque'])} {litres(l['volume_l'])}" + (" gazeuse" if l["type"] == "gazeuse" else "")
        # enseigne la moins chère (bouteille, sinon stika)
        l["meilleure_enseigne"] = (l["bouteille"] or l["stika"])[0][1]
    return sorted(lignes.values(), key=lambda l: (l["marque"], l["type"], l["volume_l"]))


def visuel(lignes):
    return next((l["image"] for l in lignes if l["image"] and l["volume_l"] == 1.5), None) or \
        next((l["image"] for l in lignes if l["image"]), None)


# ---------------------------------------------------------------- fragments HTML
def vignette(image, marque, prefixe=""):
    if image:
        return f'<div class="vignette"><img src="{prefixe}{esc(image)}" alt="Bouteille d\'eau minérale {esc(nom_marque(marque))}" loading="lazy"></div>'
    return f'<div class="vignette"><span class="initiale">{esc(marque[0])}</span></div>'


def cell_stika(l):
    if l["prix_stika"] is None:
        return "—"
    return dt(l["prix_stika"]) + ("<sup>*</sup>" if l["stika_calcule"] else "") + \
        f'<br><small class="nb">{l["n_stika"]} bouteilles</small>'


def lien_magasin(prix, enseigne, url, stika=False):
    txt = f"{esc(enseigne)}{' stika' if stika else ''} {dt(prix)}"
    return f'<a href="{esc(url)}" rel="noopener" target="_blank">{txt}</a>' if url else txt


def tableau_marque(lignes, prefixe):
    rangs = []
    for l in lignes:
        gaz = '<span class="gaz">gazeuse</span>' if l["type"] == "gazeuse" else ""
        mags = [lien_magasin(*o) for o in l["bouteille"]] + [lien_magasin(*o, stika=True) for o in l["stika"]]
        rangs.append(
            f'<tr><td class="format"><a href="{prefixe}format/{l["format"]}/">{litres(l["volume_l"])}</a>{gaz}'
            f'<br><small>{dt(l["prix_litre"])}/L</small></td>'
            f'<td class="num">{dt(l["prix_bouteille"]) if l["prix_bouteille"] is not None else "—"}</td>'
            f'<td class="num meilleur">{cell_stika(l)}</td>'
            f'<td class="magasins">{" · ".join(mags)}</td></tr>')
    return ('<table><thead><tr><th>Format</th><th class="num">Bouteille</th><th class="num">Stika</th>'
            f'<th>Magasins</th></tr></thead><tbody>{"".join(rangs)}</tbody></table>')


def tableau_accueil(lignes):
    rangs = []
    for l in lignes:
        gaz = '<span class="gaz">gazeuse</span>' if l["type"] == "gazeuse" else ""
        rangs.append(
            f'<tr><td class="format">{litres(l["volume_l"])}{gaz}<br><small>{dt(l["prix_litre"])}/L</small></td>'
            f'<td class="num">{dt(l["prix_bouteille"]) if l["prix_bouteille"] is not None else "—"}</td>'
            f'<td class="num meilleur">{cell_stika(l)}</td></tr>')
    return ('<table><thead><tr><th>Format</th><th class="num">Bouteille</th><th class="num">Stika</th></tr></thead>'
            f'<tbody>{"".join(rangs)}</tbody></table>')


def page(titre, description, url, prefixe, corps, jsonld, maj, image=None):
    og_img = f"{SITE}{image}" if image else f"{SITE}img/partage.png"
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(titre)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{url}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Prix de l'eau">
  <meta property="og:title" content="{esc(titre)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{og_img}">
  <meta property="og:locale" content="fr_TN">
  <meta name="twitter:card" content="summary_large_image">
  {"".join(ld(x) for x in jsonld)}
  <meta name="theme-color" content="#0b6fa4">
  <link rel="icon" href="{prefixe}img/icone.svg" type="image/svg+xml">
  <link rel="stylesheet" href="{prefixe}style.css">
</head>
<body>
  <header class="entete">
    <div class="entete-in">
      <a class="titre" href="{prefixe or './'}">
        <img src="{prefixe}img/icone.svg" alt="" width="36" height="36">
        <div>
          <p class="nom-site">Prix de l'eau</p>
          <p class="sous-titre">Eaux minérales en Tunisie · mis à jour le {maj}</p>
        </div>
      </a>
    </div>
  </header>
  <main class="page-texte">
{corps}
  </main>
  <footer class="pied">
    <p><b>Stika</b> (fardeau) = pack de 6 bouteilles, ou 12 en 50 cl. <sup>*</sup> Prix calculé (nombre de bouteilles × prix bouteille).</p>
    <p>Prix relevés chaque jour sur les sites des enseignes. Les prix en magasin peuvent différer.</p>
  </footer>
  {GOATCOUNTER}
</body>
</html>
"""


def nav_formats(prefixe, sauf=None):
    return "<ul>" + "".join(f'<li><a href="{prefixe}format/{s}/">Prix eau {esc(n)}</a></li>'
                            for s, n, _ in FORMATS if s != sauf) + "</ul>"


# ---------------------------------------------------------------- pages marque
def page_marque(marque, lignes, toutes, maj, jour):
    nom = nom_marque(marque)
    url = f"{SITE}marque/{slug(marque)}/"
    enseignes = sorted({e for l in lignes for _, e, _ in l["bouteille"] + l["stika"]})
    b = min((l for l in lignes if l["prix_bouteille"] is not None), key=lambda l: l["prix_bouteille"], default=None)
    s = min((l for l in lignes if l["prix_stika"] is not None), key=lambda l: l["prix_stika"], default=None)

    desc = f"Prix de l'eau minérale {nom} en Tunisie"
    if b:
        desc += f" : bouteille dès {dt(b['prix_bouteille'])}"
    if s:
        desc += f", stika dès {dt(s['prix_stika'])}"
    desc += ". Comparez Carrefour, Géant, Monoprix et Aziza."

    # texte descriptif généré à partir des prix
    formats_txt = liste_fr([litres(v) for v in sorted({l["volume_l"] for l in lignes})])
    phrases = [f"L'eau {esc(nom)} est vendue en {formats_txt} chez {esc(liste_fr(enseignes))}."]
    if b:
        phrases.append(f"La bouteille la moins chère coûte {dt(b['prix_bouteille'])} ({litres(b['volume_l'])} chez {esc(b['meilleure_enseigne'])}).")
    if s:
        phrases.append(f"Une stika de {s['n_stika']} bouteilles de {litres(s['volume_l'])} revient à {dt(s['prix_stika'])}"
                       + (" (6 × prix bouteille)." if s["stika_calcule"] and s["n_stika"] == 6 else
                          f" ({s['n_stika']} × prix bouteille)." if s["stika_calcule"] else " (prix réel d'une stika)."))
    # classement dans le format principal (1,5 L si possible)
    ref = next((l for l in lignes if l["format"] == "1-5-l" and l["type"] == "plate"), None) or lignes[0]
    concurrents = sorted((l for l in toutes if l["format"] == ref["format"] and l["type"] == ref["type"]), key=lambda l: l["prix_litre"])
    rang = next(i for i, l in enumerate(concurrents) if l is ref) + 1
    fmt_nom = format_de(ref["volume_l"])[1]
    if len(concurrents) > 1:
        phrases.append(f"Au litre, {esc(nom)} {litres(ref['volume_l'])} est {'la moins chère' if rang == 1 else f'classée {rang}e'} "
                       f"sur {len(concurrents)} marques en {esc(fmt_nom)}.")
    autres = [l for l in concurrents if l["marque"] != marque][:6]
    autres_html = "".join(f'<li><a href="../{slug(l["marque"])}/">{esc(nom_marque(l["marque"]))}</a> : '
                          f'{dt(l["prix_litre"])}/L</li>' for l in autres)

    img = visuel(lignes)
    corps = f"""    <p class="fil"><a href="../../">Accueil</a> › <a href="../../#marques">Marques</a> › {esc(nom)}</p>
    <article class="carte">
      <div class="carte-tete">
        {vignette(img, marque, "../../")}
        <div>
          <h1>Prix de l'eau {esc(nom)} en Tunisie</h1>
          <p class="des">Bouteille et stika, mis à jour le {maj}</p>
        </div>
      </div>
      <div class="texte"><p>{" ".join(phrases)}</p></div>
      {tableau_marque(lignes, "../../")}
    </article>
    <section class="liens">
      <h2>Autres marques d'eau en {esc(fmt_nom)}</h2>
      <ul>{autres_html}</ul>
      <p><a href="../../format/{ref['format']}/">Voir le classement complet en {esc(fmt_nom)}</a></p>
      <h2>Prix par format</h2>
      {nav_formats("../../")}
    </section>
    <p class="retour"><a href="../../">← Comparer toutes les marques</a></p>"""

    produits = []
    for l in lignes:
        offres, suffixe = (l["bouteille"], "") if l["bouteille"] else (l["stika"], f" (stika de {l['n_stika']})")
        prix = [o[0] for o in offres]
        produits.append({
            "@context": "https://schema.org", "@type": "Product",
            "name": f"Eau minérale {l['nom']}{suffixe}",
            "brand": {"@type": "Brand", "name": nom},
            **({"image": f"{SITE}{l['image']}"} if l["image"] else {}),
            "offers": {"@type": "AggregateOffer", "priceCurrency": "TND",
                       "lowPrice": f"{min(prix):.3f}", "highPrice": f"{max(prix):.3f}", "offerCount": len(prix)},
        })
    jsonld = [fil_ariane([("Accueil", SITE), (f"Eau {nom}", url)]),
              {"@context": "https://schema.org", "@type": "WebPage", "name": f"Prix de l'eau {nom} en Tunisie",
               "url": url, "dateModified": jour, "inLanguage": "fr-TN"}] + produits
    return page(f"Prix eau {nom} en Tunisie : bouteille et stika", desc, url, "../../", corps, jsonld, maj, img)


# ---------------------------------------------------------------- pages format
def page_format(fslug, fnom, lignes, maj, jour):
    url = f"{SITE}format/{fslug}/"
    lignes = sorted(lignes, key=lambda l: l["prix_litre"])
    moins, plus = lignes[0], lignes[-1]
    stika = fslug != "bonbonne"
    n = taille_stika(moins["volume_l"])
    ecart = round((plus["prix_litre"] / moins["prix_litre"] - 1) * 100)
    phrases = [f"Classement de {len(lignes)} eaux minérales en {esc(fnom)} vendues en Tunisie, de la moins chère à la plus chère au litre."]
    phrases.append(f"La moins chère aujourd'hui : <a href=\"../../marque/{slug(moins['marque'])}/\">{esc(moins['nom'])}</a> à "
                   f"{dt(moins['prix_litre'])} le litre" + (f", soit {dt(moins['prix_stika'])} la stika de {n} bouteilles." if stika and moins["prix_stika"] else "."))
    phrases.append(f"La plus chère : {esc(plus['nom'])} à {dt(plus['prix_litre'])} le litre, {ecart} % de plus.")
    if stika:
        phrases.append(f"En {esc(fnom)}, une stika compte {n} bouteilles.")
    rangs = "".join(
        f'<tr><td class="rang">{i + 1}</td>'
        f'<td><a href="../../marque/{slug(l["marque"])}/">{esc(nom_marque(l["marque"]))}</a> <small>{litres(l["volume_l"])}</small>'
        f'{"<span class=\"gaz\">gazeuse</span>" if l["type"] == "gazeuse" else ""}</td>'
        f'<td class="num">{dt(l["prix_bouteille"]) if l["prix_bouteille"] is not None else "—"}</td>'
        f'<td class="num meilleur">{cell_stika(l) if stika else "—"}</td>'
        f'<td class="num">{dt(l["prix_litre"])}</td><td>{esc(l["meilleure_enseigne"])}</td></tr>'
        for i, l in enumerate(lignes))
    titre = f"Prix eau {fnom} en Tunisie : classement bouteille et stika" if stika else f"Prix eau en {fnom} en Tunisie : classement"
    desc = (f"Eau minérale en {fnom} la moins chère en Tunisie : {moins['nom']} à {dt(moins['prix_litre'])}/L. "
            f"Classement de {len(lignes)} marques, bouteille et stika.")
    corps = f"""    <p class="fil"><a href="../../">Accueil</a> › Formats › {esc(fnom)}</p>
    <article class="carte">
      <div class="carte-tete"><div>
        <h1>Prix de l'eau en {esc(fnom)} en Tunisie</h1>
        <p class="des">Classement du moins cher au plus cher au litre, mis à jour le {maj}</p>
      </div></div>
      <div class="texte"><p>{" ".join(phrases)}</p></div>
      <table><thead><tr><th class="rang">#</th><th>Marque</th><th class="num">Bouteille</th><th class="num">Stika</th>
        <th class="num">Prix / L</th><th>Moins cher chez</th></tr></thead><tbody>{rangs}</tbody></table>
    </article>
    <section class="liens">
      <h2>Autres formats</h2>
      {nav_formats("../../", sauf=fslug)}
    </section>
    <p class="retour"><a href="../../">← Retour au comparateur</a></p>"""
    jsonld = [fil_ariane([("Accueil", SITE), (f"Eau en {fnom}", url)]),
              {"@context": "https://schema.org", "@type": "ItemList", "name": f"Eaux minérales en {fnom} les moins chères",
               "itemListOrder": "https://schema.org/ItemListOrderAscending", "numberOfItems": len(lignes),
               "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": l["nom"],
                                    "url": f"{SITE}marque/{slug(l['marque'])}/"} for i, l in enumerate(lignes)]}]
    return page(titre, desc, url, "../../", corps, jsonld, maj)


# ---------------------------------------------------------------- accueil
def resume_et_faq(lignes, nb_marques):
    """Résumé du jour et FAQ ; les mêmes textes servent au HTML et aux données structurées."""
    # Pour le résumé et la FAQ, on ne cite que des prix confirmés par un prix bouteille
    # (un prix issu d'un seul lot, sans prix bouteille, peut être une erreur de l'enseigne)
    fiables = [l for l in lignes if l["prix_bouteille"] is not None and l["type"] == "plate"]

    def extremes(volume):
        ls = sorted((l for l in fiables if l["volume_l"] == volume and l["prix_stika"]), key=lambda l: l["prix_stika"])
        return (ls[0], ls[-1]) if ls else (None, None)

    s15_min, s15_max = extremes(1.5)
    s05_min, s05_max = extremes(0.5)
    gagnants = Counter(l["bouteille"][0][1] for l in lignes if len(l["bouteille"]) > 1)
    champion, nb_gagne = gagnants.most_common(1)[0] if gagnants else (None, 0)
    compares = sum(gagnants.values())
    moins_litre = min((l for l in fiables if l["format"] in ("1-5-l", "2-l")), key=lambda l: l["prix_litre"])

    points = []
    if s15_min:
        points.append(f"Stika de 6 × 1,5 L : de <b>{dt(s15_min['prix_stika'])}</b> ({esc(nom_marque(s15_min['marque']))}) "
                      f"à {dt(s15_max['prix_stika'])} ({esc(nom_marque(s15_max['marque']))}).")
    if s05_min:
        points.append(f"Stika de 12 × 50 cl : de <b>{dt(s05_min['prix_stika'])}</b> ({esc(nom_marque(s05_min['marque']))}) "
                      f"à {dt(s05_max['prix_stika'])} ({esc(nom_marque(s05_max['marque']))}).")
    points.append(f"Eau la moins chère au litre : <b>{esc(moins_litre['nom'])}</b>, {dt(moins_litre['prix_litre'])} le litre.")
    if champion:
        points.append(f"Enseigne la plus souvent la moins chère : <b>{esc(champion)}</b> ({nb_gagne} produits sur {compares} comparés).")
    points.append(f"{nb_marques} marques d'eau minérale suivies chez Carrefour, Géant, Monoprix et Aziza.")
    resume = ('<section class="resume-jour"><h2>Les prix de l\'eau aujourd\'hui</h2><ul>'
              + "".join(f"<li>{p}</li>" for p in points) + "</ul></section>")

    faq = [("Qu'est-ce qu'une stika d'eau ?",
            "La stika, aussi appelée fardeau, est le pack d'eau minérale vendu en Tunisie : 6 bouteilles pour les "
            "formats de 1 L à 2 L, et 12 bouteilles pour les petites bouteilles de 50 cl.")]
    if s15_min:
        faq.append(("Combien coûte une stika d'eau en Tunisie ?",
                    f"Aujourd'hui, une stika de 6 bouteilles de 1,5 L coûte de {dt(s15_min['prix_stika'])} "
                    f"({nom_marque(s15_min['marque'])}) à {dt(s15_max['prix_stika'])} ({nom_marque(s15_max['marque'])})."
                    + (f" En 50 cl, la stika de 12 bouteilles coûte de {dt(s05_min['prix_stika'])} à {dt(s05_max['prix_stika'])}." if s05_min else "")))
    faq.append(("Quelle est l'eau minérale la moins chère en Tunisie ?",
                f"Au litre, la moins chère aujourd'hui en grande bouteille est {moins_litre['nom']}, à "
                f"{dt(moins_litre['prix_litre'])} le litre. Le classement complet par format est mis à jour chaque jour."))
    if champion:
        faq.append(("Où acheter l'eau minérale la moins chère ?",
                    f"Parmi les produits vendus dans plusieurs enseignes, {champion} propose le prix le plus bas "
                    f"pour {nb_gagne} produits sur {compares}. Les écarts restent faibles d'une enseigne à l'autre, "
                    "le choix de la marque compte davantage."))
    faq.append(("Les prix sont-ils à jour ?",
                "Oui, les prix sont relevés chaque jour sur les sites de Carrefour, Géant, Monoprix et Aziza. "
                "Les prix en magasin peuvent différer légèrement des prix en ligne."))
    faq_html = ('<section class="faq"><h2>Questions fréquentes</h2>'
                + "".join(f"<h3>{esc(q)}</h3><p>{esc(r)}</p>" for q, r in faq) + "</section>")
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": r}} for q, r in faq]}
    return resume, faq_html, faq_ld


def remplacer(texte, marqueur, contenu):
    motif = re.compile(rf"(<!--{marqueur}-->).*?(<!--/{marqueur}-->)", re.S)
    assert motif.search(texte), f"marqueur {marqueur} absent de index.html"
    return motif.sub(lambda m: m.group(1) + contenu + m.group(2), texte)


def page_404():
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Page introuvable | Prix de l'eau</title>
  <meta name="robots" content="noindex">
  <base href="{CHEMIN}">
  <link rel="icon" href="img/icone.svg" type="image/svg+xml">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main class="page-texte">
    <article class="carte"><div class="texte">
      <h1>Page introuvable</h1>
      <p>Cette page n'existe pas ou a été déplacée.</p>
      <p><a href="./">← Voir les prix de l'eau en Tunisie</a></p>
    </div></article>
  </main>
</body>
</html>
"""


# ---------------------------------------------------------------- principal
def main():
    data = json.loads((WEB / "data" / "produits.json").read_text(encoding="utf-8"))
    d = datetime.fromisoformat(data["maj"])
    maj, jour = f"{d.day} {MOIS[d.month - 1]} {d.year}", d.date().isoformat()
    lignes = lignes_produits(data)
    par_marque = {}
    for l in lignes:
        par_marque.setdefault(l["marque"], []).append(l)
    ordre = sorted(par_marque, key=lambda m: min(l["prix_litre"] for l in par_marque[m]))

    # 1. Accueil
    cartes = "".join(f"""
      <article class="carte">
        <div class="carte-tete">{vignette(visuel(par_marque[m]), m)}
          <div><h2><a href="marque/{slug(m)}/">{esc(nom_marque(m))}</a></h2></div>
        </div>
        {tableau_accueil(par_marque[m])}
      </article>""" for m in ordre)
    resume, faq_html, faq_ld = resume_et_faq(lignes, len(par_marque))
    site_ld = {"@context": "https://schema.org", "@type": "WebSite", "name": "Prix de l'eau", "url": SITE,
               "inLanguage": "fr-TN", "description": "Comparateur des prix de l'eau minérale en Tunisie : bouteille et stika."}
    page_ld = {"@context": "https://schema.org", "@type": "WebPage", "name": "Prix de l'eau minérale en Tunisie",
               "url": SITE, "dateModified": jour, "inLanguage": "fr-TN"}
    index = WEB / "index.html"
    t = index.read_text(encoding="utf-8")
    t = remplacer(t, "LISTE", f'<div class="grille">{cartes}\n      </div>')
    t = remplacer(t, "RESUME", resume)
    t = remplacer(t, "FORMATS", nav_formats(""))
    t = remplacer(t, "MARQUES", '<ul id="marques">' + "".join(
        f'<li><a href="marque/{slug(m)}/">Prix eau {esc(nom_marque(m))}</a></li>' for m in sorted(par_marque)) + "</ul>")
    t = remplacer(t, "FAQ", faq_html)
    t = remplacer(t, "JSONLD", ld(site_ld) + ld(page_ld) + ld(faq_ld))
    t = remplacer(t, "MAJ", maj)
    index.write_text(t, encoding="utf-8")

    # 2. Pages marque et format (régénérées entièrement chaque jour)
    for dossier in ("marque", "format"):
        if (WEB / dossier).exists():
            shutil.rmtree(WEB / dossier)
    for m, ls in par_marque.items():
        f = WEB / "marque" / slug(m) / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(page_marque(m, ls, lignes, maj, jour), encoding="utf-8")
    pages_format = []
    for fslug, fnom, _ in FORMATS:
        ls = [l for l in lignes if l["format"] == fslug]
        if not ls:
            continue
        f = WEB / "format" / fslug / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(page_format(fslug, fnom, ls, maj, jour), encoding="utf-8")
        pages_format.append(fslug)

    # 3. Page 404 et plan du site
    (WEB / "404.html").write_text(page_404(), encoding="utf-8")
    urls = [SITE] + [f"{SITE}format/{s}/" for s in pages_format] + [f"{SITE}marque/{slug(m)}/" for m in sorted(par_marque)]
    (WEB / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{jour}</lastmod></url>\n" for u in urls)
        + "</urlset>\n", encoding="utf-8")
    print(f"index.html + {len(par_marque)} pages marque + {len(pages_format)} pages format + 404 + sitemap ({len(urls)} URL)")


if __name__ == "__main__":
    main()
