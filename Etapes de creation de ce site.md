# Étapes de création de ce site

Guide réutilisable pour créer tout autre site du même genre, à partir de l'exemple du site
« Prix de l'eau en Tunisie » (https://ah6259.github.io/prix-eau-tunisie/).

## 1. Définir l'idée

- **Ce que le site montre** : ici, les prix de l'eau minérale.
- **Pour qui** : les familles tunisiennes qui achètent l'eau à la stika.
- **Commencer petit** : une seule fonction qui marche (lister les prix), puis ajouter le reste petit à petit (commande, historique…).

## 2. Trouver et récupérer les données

- **Chercher où sont les informations** : sites des supermarchés, comparateurs, API.
- **Tester chaque source** : certaines répondent bien (Carrefour, Géant), d'autres bloquent les robots (Monoprix). Dans ce cas, on cherche une autre voie, par exemple un comparateur comme barka.tn.
- **Écrire un script de collecte** (le « scraper », en Python) qui télécharge les données et les enregistre dans un fichier (ici `produits.json`).
- **Nettoyer les données** : unifier les noms (« Tigen » et « Tijen »), écarter ce qui n'a rien à voir (verres, sodas), rejeter les prix aberrants, vérifier à la main quelques exemples.

## 3. Construire le site

- **Une page simple** en HTML, CSS et JavaScript qui lit le fichier de données et l'affiche.
- **Penser mobile d'abord** : en Tunisie, la plupart des visiteurs sont sur téléphone.
- **Ajouter ce qui est utile** : recherche, filtres, tri, comparaison.
- **En faire une application installable (PWA)** avec un manifeste et un service worker : on l'ajoute à l'écran d'accueil et elle marche hors ligne.
- **Tester sur son PC** : `python -m http.server`, puis http://localhost:8000.

## 4. Mettre en ligne (gratuit)

- **Créer un compte GitHub** et un dépôt qui contient le code.
- **Activer GitHub Pages** : le site est publié gratuitement en https.
- **Automatiser la mise à jour** avec GitHub Actions : chaque jour, le script de collecte tourne tout seul et republie le site. Le PC peut rester éteint.
- **Prévoir les pannes** : si une source ne répond pas, garder les données de la veille plutôt que d'afficher un site vide.

## 5. Écouter les utilisateurs et améliorer

- Adapter le site à la réalité locale : chez nous, afficher la **stika** en plus de la bouteille.
- Corriger ce qui gêne : textes, mentions, présentation.
- Garder une **liste de tâches** (`TODO.md`) pour ne rien oublier.

## 6. Mesurer

- **Statistiques de visite** avec GoatCounter : gratuit, sans cookies. On ajoute une ligne de code au site.

## 7. Être trouvé sur Google (référencement)

- **Un titre et une description** qui reprennent ce que les gens tapent dans Google.
- **Le contenu écrit directement dans la page**, pas seulement affiché par le JavaScript.
- **Une page par sujet précis** : ici, une page par marque.
- **Un plan du site** (`sitemap.xml`).
- **Un aperçu pour Facebook et WhatsApp** : une image et un titre qui s'affichent quand on partage le lien.
- **Déclarer le site dans Google Search Console** : valider avec la balise, envoyer le sitemap, demander l'indexation.
- **Patienter** : quelques jours pour être indexé, quelques semaines pour bien remonter dans les résultats.
- **Vérifier l'indexation** : taper `site:adresse-du-site` dans Google.

## 8. Faire connaître le site

- **Un nom de domaine** facile à retenir (`.tn` ou `.com`).
- **Facebook** : les groupes de bons plans, une page du site, des publications régulières.
- **Vidéos courtes** sur TikTok et en Reels.
- **Le bouche-à-oreille** et WhatsApp.

## Les outils utilisés (tous gratuits)

| Besoin | Outil |
|---|---|
| Récupérer les données | Python + curl |
| Le site | HTML, CSS, JavaScript |
| Stocker le code et l'historique | Git + GitHub |
| Héberger le site | GitHub Pages |
| Mettre à jour tous les jours | GitHub Actions |
| Statistiques | GoatCounter |
| Référencement | Google Search Console |

## En résumé

Une idée simple, des données fiables, un site qui marche sur mobile, une mise en ligne gratuite
et automatique, puis faire connaître le site et l'améliorer avec les retours des visiteurs.
