# Prix de l'eau en Tunisie

Comparateur de prix des eaux minérales vendues en Tunisie : site web + application installable (PWA) sur téléphone.

## Structure

```
scraper/scrape.py      collecte des prix (Carrefour, Géant, Monoprix, Aziza)
scraper/raw/           réponses brutes des sites (pour contrôle)
web/                   le site (HTML/CSS/JS statique, sans build)
web/data/produits.json données générées par le scraper
web/img/produits/      photos des bouteilles téléchargées
```

## Mettre à jour les prix

```
python scraper/scrape.py
```

Python 3 et `curl` suffisent (curl est fourni avec Windows 10/11).

## Voir le site en local

```
cd web
python -m http.server 8000
```

puis ouvrir http://localhost:8000. Sur téléphone, « Ajouter à l'écran d'accueil » installe l'application.

## En ligne

Site : https://ah6259.github.io/prix-eau-tunisie/

Le workflow `.github/workflows/maj-et-deploiement.yml` tourne chaque jour à 6h (heure de Tunis),
à chaque push sur `main`, et à la demande (onglet Actions > « Run workflow ») :
il relève les prix, commite `web/data` et `web/img` s'ils ont changé (d'où un historique des prix
dans git), puis publie `web/` sur GitHub Pages.

Si une source est en panne, ses prix du dernier relevé réussi sont conservés
(voir `sources` dans `produits.json`). Après un relevé automatique, faire `git pull`
avant de modifier le code en local.

## Sources

| Enseigne  | Méthode                                              |
|-----------|------------------------------------------------------|
| Carrefour | API GraphQL du site carrefour.tn, catégorie « Eaux » |
| Géant     | Page « Eaux » de geantdrive.tn (magasin Tunis City)  |
| Monoprix  | Via le comparateur barka.tn (le site Monoprix bloque les robots) |
| Aziza     | Via le comparateur barka.tn                          |

Les produits sont regroupés par marque + type (plate/gazeuse) + format. Garde-fous :
- seules les marques d'eau connues sont retenues (`MARQUES_EAU` dans le script),
- les « fardeaux / lots » sans nombre de bouteilles explicite sont écartés,
- les prix hors de 0,25–2,5 DT/L, ou supérieurs au double de l'offre la moins chère du même produit, sont écartés (erreurs fréquentes chez Aziza).
