"""Collecte des prix des eaux minérales en Tunisie.

Sources :
  - Carrefour Tunisie : API GraphQL (catégorie « Eaux »)
  - Géant Drive       : page catégorie « Eaux » (HTML PrestaShop)
  - Barka.tn          : comparateur, utilisé pour Monoprix et Aziza

Sortie : web/data/produits.json + images dans web/img/produits/
Usage  : python scraper/scrape.py
"""
import hashlib
import html
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import subprocess
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "web" / "data" / "produits.json"
IMG_DIR = ROOT / "web" / "img" / "produits"
RAW_DIR = ROOT / "scraper" / "raw"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"


def http_get(url, params=None, timeout=60):
    """GET via curl : les sites visés refusent python-requests (403 Carrefour,
    chaîne de certificats incomplète chez Géant) mais acceptent curl."""
    if params:
        url += "?" + urlencode({k: v for k, v in params.items() if v is not None})
    r = subprocess.run(
        ["curl", "-sSL", "--fail", "-A", UA, "--max-time", str(timeout), url],
        capture_output=True, timeout=timeout + 10,
    )
    if r.returncode:
        raise RuntimeError(f"curl {r.returncode} {url}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


# Marques d'eau embouteillée connues sur le marché tunisien
MARQUES_EAU = {
    "AQUALINE", "BARGOU", "BEYA", "BRIMA", "BULLA REGIA", "CRISTALINE", "DELICE", "DENYA",
    "DIMA", "ELIXIR", "FOURAT", "GARCI", "HAYET", "JANNET", "JEKTISS", "MAIN", "MARWA",
    "MAY", "MELINA", "MELLITI", "MIRA", "OKTOR", "PALMA", "PRIMAQUA", "PRISTINE", "RIM",
    "ROYAL", "SABRINE", "SAFIA", "SAHA", "TIBA", "TIJEN", "VIVIAN",
}

ENSEIGNES = {
    "carrefour": {"nom": "Carrefour", "site": "https://www.carrefour.tn"},
    "geant": {"nom": "Géant", "site": "https://www.geantdrive.tn"},
    "monoprix": {"nom": "Monoprix", "site": "https://courses.monoprix.tn"},
    "aziza": {"nom": "Aziza", "site": "https://aziza.tn"},
}

# Orthographes différentes d'une même marque selon les enseignes
ALIAS_MARQUES = {
    "PRESTINE": "PRISTINE",
    "TIGEN": "TIJEN",
    "JEKTIS": "JEKTISS",
    "MAY TUNISIA": "MAY",
    "SAFIA AIN MIZEB": "SAFIA",
    "ROYAL BLEU": "ROYAL",
    "ROYAL_BLEU": "ROYAL",
    "ROYALE": "ROYAL",
}


# ---------------------------------------------------------------- utilitaires
def sans_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm_marque(s):
    s = sans_accents(html.unescape(s or "")).upper().strip()
    s = re.sub(r"\s+", " ", s)
    return ALIAS_MARQUES.get(s, s)


def parse_prix(s):
    """'0,640 DT' / '0.64 dt' / 0.64 -> 0.64"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = re.search(r"\d+(?:[.,]\d+)?", s.replace(" ", ""))
    return float(m.group().replace(",", ".")) if m else None


def parse_volume(*textes):
    """Cherche un volume (en litres) et un nombre d'unités dans les textes.
    Retourne (volume_litres, nb_unites) ; ex. 'Pack 6x1.5L' -> (1.5, 6)."""
    t = " ".join(sans_accents(html.unescape(x or "")) for x in textes).upper()
    t = t.replace(",", ".")
    nb = 1
    m = re.search(r"(\d+)\s*[X×]\s*(\d+(?:\.\d+)?)\s*(CL|ML|L)\b", t)
    if m:
        nb = int(m.group(1))
        v, u = float(m.group(2)), m.group(3)
    else:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(CL|ML|L|LITRES?)\b", t)
        if not m:
            return None, nb
        v, u = float(m.group(1)), m.group(2)
        m2 = re.search(r"(?:PACK|LOT)\s*(?:DE\s*)?(\d+)|(\d+)\s*X\b|\bX\s*(\d+)\b", t)
        if m2:
            nb = int(next(g for g in m2.groups() if g))
    if u == "CL":
        v /= 100
    elif u == "ML":
        v /= 1000
    return round(v, 3), nb


def type_eau(*textes):
    t = sans_accents(" ".join(x or "" for x in textes)).lower()
    return "gazeuse" if re.search(r"gaz|petillant", t) else "plate"


def trouver_marque(marque, nom=""):
    """Marque normalisée si c'est une marque d'eau connue, sinon None.
    Si le champ marque est vide/générique, on la cherche dans le nom."""
    m = norm_marque(marque)
    if m in MARQUES_EAU:
        return m
    n = norm_marque(nom)
    for x in sorted(MARQUES_EAU, key=len, reverse=True):
        if re.search(rf"\b{x}\b", n):
            return x
    return None


def est_eau(nom, marque=""):
    t = sans_accents(f"{nom}").lower()
    if not re.search(r"\beaux?\b", t) and "primaqua" not in sans_accents(marque).lower():
        return False
    exclus = (r"verre|service|carafe|pichet|distributeur|geranium|senteur|aromatis|atomiseur|demineralis|bouillotte|micellaire"
              r"|fruit|citron|poire|pomme|peche|menthe|fraise|ananas|deli.?o|^consigne|avec consigne")
    return not re.search(exclus, t) and trouver_marque(marque, nom) is not None


def taille_stika(volume_l):
    """Bouteilles par stika (« fardeau ») : 12 pour les petites bouteilles, 6 sinon.
    Constaté sur les prix Aziza : un fardeau de 50 cl coûte ~12 × le prix bouteille."""
    return 12 if volume_l <= 0.75 else 6


def lire_pack(nom, taille):
    """Analyse un pack (« fardeau », « lot », « pack »).
    Retourne None si ce n'est pas un pack, "ambigu" si la quantité est illisible,
    sinon (volume_bouteille_l, nb_bouteilles_total)."""
    t = sans_accents(f"{nom} {taille}").lower().replace(",", ".")
    if not re.search(r"fardeau|\blot\b|\bpack\b", t):
        return None
    # volume d'une bouteille : le premier volume plausible (≤ 2,5 L) ; « 18L » est un total
    vol = None
    for v, u in re.findall(r"(\d+(?:\.\d+)?)\s*(ml|cl|l)\b", t):
        v = float(v)
        if u == "cl":
            v /= 100
        elif u == "ml":
            v = v if v < 10 else v / 1000  # « 1.5ML » = faute de saisie pour 1,5 L
        if 0.2 <= v <= 2.5:
            vol = round(v, 3)
            break
    if vol is None:
        return "ambigu"
    # nombre total de bouteilles
    m = re.search(r"(\d+)\s*[x×*]\s*\d|\d(?:\.\d+)?\s*l?\s*[x×*]\s*(\d+)|(?:lot|pack) de (\d+) (?:bouteilles|eaux)", t)
    if m:
        return vol, int(next(g for g in m.groups() if g))
    m = re.search(r"(\d+)\s*fardeaux?", t)
    return vol, (int(m.group(1)) if m else 1) * taille_stika(vol)


def telecharger_image(url):
    if not url:
        return None
    ext = Path(url.split("?")[0]).suffix.lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    nom = hashlib.md5(url.encode()).hexdigest()[:12] + ext
    dest = IMG_DIR / nom
    if not dest.exists():
        try:
            dest.write_bytes(http_get(url, timeout=30))
        except Exception as e:
            print(f"  ! image {url}: {e}", file=sys.stderr)
            return None
    return f"img/produits/{nom}"


# ---------------------------------------------------------------- Carrefour
def carrefour():
    q = """{products(filter:{category_uid:{eq:"Mzc1Nw=="}},pageSize:200){items{
        name sku url_key short_description{html}
        small_image{url}
        price_range{minimum_price{final_price{value} regular_price{value}}}}}}"""
    q = re.sub(r"\s+", " ", q)  # le pare-feu de Carrefour rejette les requêtes multi-lignes
    items = json.loads(http_get("https://www.carrefour.tn/graphql", {"query": q}))["data"]["products"]["items"]
    (RAW_DIR / "carrefour.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    out = []
    for it in items:
        nom = it["name"].strip()
        desc = re.sub(r"<[^>]+>", " ", it["short_description"]["html"] or "")
        m = re.search(r"(?:minerale|gazeifiee|source)\s+(.+?)(?:\s+\d.*)?$", sans_accents(nom), re.I)
        marque = m.group(1) if m else nom
        marque = trouver_marque(re.sub(r"\b(avec|sans) consigne\b", "", marque, flags=re.I), nom)
        if not marque or not est_eau(nom, marque):
            continue
        vol, nb = parse_volume(nom, desc)
        p = it["price_range"]["minimum_price"]
        out.append({
            "enseigne": "carrefour", "marque": marque, "nom": nom, "description": desc.strip(),
            "volume_l": vol, "nb_unites": nb, "type": type_eau(nom, desc),
            "prix": p["final_price"]["value"], "prix_barre": p["regular_price"]["value"],
            "ean": it["sku"], "url": f"https://www.carrefour.tn/{it['url_key']}.html",
            "image_src": it["small_image"]["url"],
        })
    return out


# ---------------------------------------------------------------- Géant
def geant():
    h = http_get("https://www.geantdrive.tn/tunis-city/11-eaux").decode("utf-8", errors="replace")
    (RAW_DIR / "geant.html").write_text(h, encoding="utf-8")
    out = []
    for bloc in h.split('<article class="product-miniature')[1:]:
        g = lambda pat: (re.search(pat, bloc, re.S) or [None, None])[1]
        nom = html.unescape(g(r'itemprop="name"><a[^>]*>([^<]+)</a>') or "").strip()
        marque = html.unescape(g(r'class="manufacturer_product[^"]*">\s*([^<]+?)\s*</p>') or "")
        desc = re.sub(r"<[^>]+>", " ", g(r'itemprop="description"[^>]*>(.*?)</div>') or "")
        desc = html.unescape(re.sub(r"\s+", " ", desc)).strip()
        prix = parse_prix(g(r'class="price">([^<]+)<'))
        barre = parse_prix(g(r'class="regular-price">([^<]+)<'))
        if not nom or prix is None or not est_eau(nom, marque):
            continue
        vol, nb = parse_volume(nom, desc)
        out.append({
            "enseigne": "geant", "marque": trouver_marque(marque, nom), "nom": nom, "description": desc,
            "volume_l": vol, "nb_unites": nb, "type": type_eau(nom, desc),
            "prix": prix, "prix_barre": barre or prix,
            "ean": None, "url": g(r'href="([^"]+)" class="thumbnail'),
            "image_src": g(r'data-full-size-image-url="([^"]+)"') or g(r'<img[^>]+src="([^"]+)"'),
        })
    return out


# ---------------------------------------------------------------- Barka (Monoprix, Aziza)
def barka(requetes=("eau minerale", "eau gazeuse", "eau de source"), max_pages=40):
    vus, out, brut = set(), [], []

    def ajouter(bp):
        shop = sans_accents(bp.get("shop_name") or "").lower()
        prix = parse_prix(bp.get("product_price"))
        nom, marque = (bp.get("name") or "").strip(), bp.get("brand") or ""
        taille = " ".join(bp.get("size") or [])
        pack = lire_pack(nom, taille)
        # Carrefour et Géant sont relevés directement ; Barka ne sert pour eux qu'aux packs
        if shop not in ("monoprix", "aziza") and not (shop in ("carrefour", "geant") and pack):
            return
        if not prix or not est_eau(nom, marque) or pack == "ambigu":
            return
        cle = (shop, bp.get("_id") or bp.get("product_url"))
        if cle in vus:
            return
        vus.add(cle)
        extra = {}
        if pack:
            vol, nb = pack
            stika = taille_stika(vol)
            if nb % stika == 0 and nb > stika:
                # lot de plusieurs stikas : ramené au prix d'une stika
                extra = {"lot_stikas": nb // stika, "prix_lot": prix}
                prix, nb = round(prix / (nb // stika), 3), stika
        else:
            vol, nb = parse_volume(taille, nom, bp.get("description") or "")
        out.append({
            **extra,
            "enseigne": shop, "marque": trouver_marque(marque, nom), "nom": nom, "description": taille,
            "volume_l": vol, "nb_unites": nb, "type": type_eau(nom, bp.get("category") or ""),
            "prix": prix, "prix_barre": parse_prix(bp.get("regular_price")) or prix,
            "ean": bp.get("_id") if re.fullmatch(r"\d{13}", str(bp.get("_id") or "")) else None,
            "url": bp.get("product_url"), "image_src": bp.get("imageSrc"),
            "via": "barka.tn",
        })

    recherches = [(q, max_pages) for q in requetes] + [(f"eau {m.lower()}", 2) for m in sorted(MARQUES_EAU)]
    for q, n_pages in recherches:
        token, pages_sans_eau = None, 0
        for _ in range(n_pages):
            d = json.loads(http_get("https://barka.tn/api/search", {"q": q, "per_page": 20, "searchAfter": token}))
            brut.extend(d.get("products", []))
            eau_sur_page = False
            for p in d.get("products", []):
                bp = p["base_product"]
                if est_eau(bp.get("name") or "", bp.get("brand") or ""):
                    eau_sur_page = True
                for x in [bp] + (p.get("matches") or []):
                    ajouter(x)
            token = (d.get("meta") or {}).get("nextPageToken")
            pages_sans_eau = 0 if eau_sur_page else pages_sans_eau + 1
            if not token or pages_sans_eau >= 3:
                break
            time.sleep(0.5)
    (RAW_DIR / "barka.json").write_text(json.dumps(brut, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


# ---------------------------------------------------------------- assemblage
def anciennes_offres(ancien, enseignes):
    """Offres des enseignes données, reconstruites depuis un produits.json précédent."""
    out = []
    for p in ancien["produits"]:
        for o in p["offres"]:
            if o["enseigne"] in enseignes:
                out.append({
                    **{k: p[k] for k in ("marque", "type", "volume_l", "nb_unites", "ean")},
                    **o, "description": "", "prix_barre": o.get("prix_barre") or o["prix"],
                    "image_src": None, "image_locale": p.get("image"),
                })
    return out


def main():
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    ancien = json.loads(OUT_JSON.read_text(encoding="utf-8")) if OUT_JSON.exists() else None
    offres, sources, echecs = [], {}, 0
    for nom, f, enseignes in (("Carrefour", carrefour, {"carrefour"}), ("Géant", geant, {"geant"}),
                              ("Barka", barka, {"monoprix", "aziza"})):
        try:
            res = f()
            if not res:
                raise RuntimeError("aucune offre trouvée")
            print(f"{nom}: {len(res)} offres")
            offres += res
            sources[nom] = {"ok": True, "maj": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        except Exception as e:
            # Source en panne : on reprend ses prix du dernier relevé réussi plutôt que de la vider
            echecs += 1
            print(f"! {nom} en échec : {e}", file=sys.stderr)
            prec = (ancien or {}).get("sources", {}).get(nom, {}).get("maj") or (ancien or {}).get("maj")
            sources[nom] = {"ok": False, "maj": prec}
            if ancien:
                repris = anciennes_offres(ancien, enseignes)
                print(f"  -> reprise de {len(repris)} offres du relevé précédent")
                offres += repris
    if echecs == 3:
        sys.exit("Toutes les sources sont en échec : produits.json n'est pas modifié.")

    # Regroupe les offres en produits : même marque + type + volume + nb d'unités
    produits = {}
    for o in offres:
        if not o["marque"] or o["volume_l"] is None:
            print(f"  ? ignoré (marque/volume inconnu) : {o['enseigne']} {o['nom']} {o['description']}")
            continue
        cle = (o["marque"], o["type"], o["volume_l"], o["nb_unites"])
        p = produits.setdefault(cle, {
            "id": re.sub(r"[^a-z0-9]+", "-", f"{o['marque']}-{o['type']}-{o['nb_unites']}x{o['volume_l']}l".lower()),
            "marque": o["marque"], "type": o["type"], "volume_l": o["volume_l"],
            "nb_unites": o["nb_unites"], "ean": None, "image": None, "offres": [],
        })
        p["ean"] = p["ean"] or o["ean"]
        # une seule offre par enseigne : on garde la moins chère
        exist = next((x for x in p["offres"] if x["enseigne"] == o["enseigne"]), None)
        if exist and exist["prix"] <= o["prix"]:
            continue
        if exist:
            p["offres"].remove(exist)
        p["offres"].append({k: o.get(k) for k in ("enseigne", "prix", "prix_barre", "url", "nom", "via", "image_src", "image_locale", "lot_stikas", "prix_lot")
                            if o.get(k) is not None or k in ("prix_barre", "url")})

    # Prix aberrants (packs vendus comme bouteilles unitaires, surtout chez Aziza)
    PRIX_LITRE_MIN, PRIX_LITRE_MAX = 0.25, 2.5
    for cle, p in list(produits.items()):
        litres = p["volume_l"] * p["nb_unites"]
        ok = [x for x in p["offres"] if PRIX_LITRE_MIN <= x["prix"] / litres <= PRIX_LITRE_MAX]
        if ok:
            mini = min(x["prix"] for x in ok)
            ok = [x for x in ok if x["prix"] <= 2 * mini]
        for x in p["offres"]:
            if x not in ok:
                print(f"  ? prix aberrant écarté : {x['enseigne']} {x['nom']} {p['nb_unites']}x{p['volume_l']}L {x['prix']} DT")
        if ok:
            p["offres"] = ok
        else:
            del produits[cle]

    # Stikas : le prix par bouteille doit rester cohérent avec le prix à l'unité de la
    # même marque (les libellés de packs d'Aziza sont souvent faux)
    for cle, p in list(produits.items()):
        n = p["nb_unites"]
        if n == 1 or n != taille_stika(p["volume_l"]):
            continue
        unite = produits.get((p["marque"], p["type"], p["volume_l"], 1))
        if not unite:
            continue
        ref = min(x["prix"] for x in unite["offres"]) * n
        ok = [x for x in p["offres"] if 0.6 * ref <= x["prix"] <= 1.3 * ref]
        for x in p["offres"]:
            if x not in ok:
                print(f"  ? stika incohérente écartée : {x['enseigne']} {x['nom']} {p['marque']} {n}x{p['volume_l']}L "
                      f"{x['prix']} DT (attendu ~{ref:.2f})")
        if ok:
            p["offres"] = ok
        else:
            del produits[cle]

    # Image : priorité Carrefour (fond blanc, bonne qualité), puis Géant, Monoprix, Aziza
    ordre = ["carrefour", "geant", "monoprix", "aziza"]
    for p in produits.values():
        p["offres"].sort(key=lambda x: x["prix"])
        for e in ordre:
            src = next((x["image_src"] for x in p["offres"] if x["enseigne"] == e and x["image_src"]), None)
            if src and (img := telecharger_image(src)):
                p["image"] = img
                break
        if not p["image"]:  # offres reprises d'un relevé précédent : on garde leur image
            p["image"] = next((x["image_locale"] for x in p["offres"]
                               if x.get("image_locale") and (ROOT / "web" / x["image_locale"]).exists()), None)
        for x in p["offres"]:
            x.pop("image_src", None)
            x.pop("image_locale", None)
            if not x.get("via"):
                x.pop("via", None)
        total_l = p["volume_l"] * p["nb_unites"]
        p["prix_min"] = p["offres"][0]["prix"]
        p["prix_litre_min"] = round(p["prix_min"] / total_l, 3) if total_l else None

    # Supprime les images qui ne sont plus référencées
    utilisees = {Path(p["image"]).name for p in produits.values() if p["image"]}
    for f in IMG_DIR.iterdir():
        if f.is_file() and f.name not in utilisees:
            f.unlink()

    liste = sorted(produits.values(), key=lambda p: (p["marque"], p["type"], p["nb_unites"], p["volume_l"]))
    data = {
        "maj": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "devise": "TND",
        "enseignes": ENSEIGNES,
        "sources": sources,
        "produits": liste,
    }
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(liste)} produits, {len({p['marque'] for p in liste})} marques -> {OUT_JSON}")


if __name__ == "__main__":
    main()
