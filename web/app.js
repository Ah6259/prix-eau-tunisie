"use strict";

// En Tunisie l'eau se vend surtout par « stika » (pack de 6 bouteilles).
// Les supermarchés en ligne affichent le prix à la bouteille : le prix stika est
// donc calculé (6 × bouteille), sauf quand une enseigne vend réellement la stika.
const STIKA = 6;
const VOLUME_MAX_STIKA = 3; // au-delà (5 L, 6 L, 19 L) ce sont des bonbonnes, pas de stika

const FORMATS = [
  { id: "", nom: "Tous formats", test: () => true },
  { id: "petit", nom: "≤ 0,75 L", test: p => p.nb_unites === 1 && p.volume_l <= 0.75 },
  { id: "1", nom: "1 L", test: p => p.nb_unites === 1 && p.volume_l > 0.75 && p.volume_l < 1.25 },
  { id: "1.5", nom: "1,5 L", test: p => p.nb_unites === 1 && p.volume_l >= 1.25 && p.volume_l < 1.6 },
  { id: "2", nom: "2 L", test: p => p.nb_unites === 1 && p.volume_l >= 1.6 && p.volume_l < VOLUME_MAX_STIKA },
  { id: "bonbonne", nom: "Bonbonnes", test: p => p.nb_unites === 1 && p.volume_l >= VOLUME_MAX_STIKA },
  { id: "pack", nom: "Autres packs", test: p => p.nb_unites > 1 },
];

const etat = { vue: "marques", type: "", format: "", enseignes: new Set(), recherche: "", tri: "litre" };
let DATA = null;
let PRODUITS = [];

const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const dt = v => v.toLocaleString("fr-TN", { minimumFractionDigits: 3, maximumFractionDigits: 3 }) + " DT";
const litres = v => (v < 1 ? `${Math.round(v * 100)} cl` : `${String(v).replace(".", ",")} L`);
const libFormat = p => (p.nb_unites > 1 ? `${p.nb_unites} × ${litres(p.volume_l)}` : litres(p.volume_l));
const nomMarque = m => m.charAt(0) + m.slice(1).toLowerCase();
const minimum = xs => (xs.length ? Math.min(...xs) : null);

function vignette(p, cls = "vignette") {
  const img = p && p.image
    ? `<img src="${esc(p.image)}" alt="" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'initiale',textContent:'${esc(p.marque[0])}'}))">`
    : `<span class="initiale">${esc(p ? p.marque[0] : "?")}</span>`;
  return `<div class="${cls}">${img}</div>`;
}

/** Rattache les vraies stikas (packs de 6) à la bouteille correspondante. */
function preparer(produits) {
  const cle = p => `${p.marque}|${p.type}|${p.volume_l}`;
  const bouteilles = new Map();
  const out = [];
  for (const p of produits) {
    if (p.nb_unites === 1) {
      const b = { ...p, stikaOffres: [] };
      bouteilles.set(cle(p), b);
      out.push(b);
    }
  }
  for (const p of produits) {
    if (p.nb_unites === STIKA && p.volume_l < VOLUME_MAX_STIKA) {
      let b = bouteilles.get(cle(p));
      if (!b) { // stika vendue sans bouteille à l'unité en ligne
        b = { ...p, nb_unites: 1, offres: [], stikaOffres: [] };
        bouteilles.set(cle(p), b);
        out.push(b);
      }
      b.stikaOffres.push(...p.offres);
      b.image = b.image || p.image;
    } else if (p.nb_unites > 1) {
      out.push({ ...p, stikaOffres: [] });
    }
  }
  return out;
}

function produitsFiltres() {
  const fmt = FORMATS.find(f => f.id === etat.format);
  const q = etat.recherche.trim().toUpperCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const garde = o => !etat.enseignes.size || etat.enseignes.has(o.enseigne);
  return PRODUITS
    .filter(p => !etat.type || p.type === etat.type)
    .filter(fmt.test)
    .filter(p => !q || p.marque.includes(q))
    .map(p => {
      const offres = p.offres.filter(garde);
      const stikaOffres = p.stikaOffres.filter(garde).sort((a, b) => a.prix - b.prix);
      if (!offres.length && !stikaOffres.length) return null;
      const prix = offres.length ? offres[0].prix : null;       // bouteille (ou pack pour « autres packs »)
      const stikaPossible = p.nb_unites === 1 && p.volume_l < VOLUME_MAX_STIKA;
      const stikaCalc = stikaPossible && prix !== null ? prix * STIKA : null;
      const stikaReel = minimum(stikaOffres.map(o => o.prix));
      const stika = minimum([stikaCalc, stikaReel].filter(v => v !== null));
      const prixBouteille = minimum([prix, stika !== null ? stika / STIKA : null].filter(v => v !== null));
      const prixLitre = p.nb_unites > 1 ? prix / (p.volume_l * p.nb_unites) : prixBouteille / p.volume_l;
      return {
        ...p, offres, stikaOffres, prix, stika, prixLitre,
        stikaEstReel: stikaReel !== null && stikaReel === stika && (stikaCalc === null || stikaReel < stikaCalc),
        prixTri: p.nb_unites > 1 ? prix : prixBouteille,
      };
    })
    .filter(Boolean);
}

function puceOffre(o, top, prefixe = "") {
  const e = DATA.enseignes[o.enseigne];
  const via = o.via ? ` (relevé via ${o.via})` : "";
  return `<a class="offre${top ? " top" : ""}" href="${esc(o.url)}" target="_blank" rel="noopener" title="${esc(e.nom + " — " + o.nom + via)}">
    <span class="pastille p-${o.enseigne}"></span>${esc(e.nom)}${prefixe} <b>${dt(o.prix)}</b></a>`;
}

function puces(p) {
  const html = p.offres.map((o, i) => puceOffre(o, i === 0 && p.offres.length > 1));
  html.push(...p.stikaOffres.map(o => puceOffre(o, false, " · stika")));
  return `<div class="offres">${html.join("")}</div>`;
}

const cellPrix = v => (v === null ? `<span class="na">—</span>` : dt(v));
function cellStika(p) {
  if (p.stika === null) return `<span class="na" title="${p.nb_unites > 1 ? "Pack" : "Bonbonne : pas de stika"}">—</span>`;
  return `${dt(p.stika)}${p.stikaEstReel ? "" : '<sup class="calc" title="6 × prix bouteille">*</sup>'}`;
}
function cellBouteille(p) {
  if (p.nb_unites > 1) return `<span class="na">—</span>`;
  if (p.prix === null) return `<span class="na" title="Vendue seulement en stika">${dt(p.stika / STIKA)}</span>`;
  return dt(p.prix);
}

const TRIS = {
  litre: (a, b) => a.prixLitre - b.prixLitre,
  prix: (a, b) => a.prixTri - b.prixTri,
  marque: (a, b) => a.marque.localeCompare(b.marque),
};

function rendreMarques(produits) {
  const parMarque = new Map();
  for (const p of produits) {
    if (!parMarque.has(p.marque)) parMarque.set(p.marque, []);
    parMarque.get(p.marque).push(p);
  }
  const marques = [...parMarque.entries()].map(([marque, ps]) => {
    ps.sort((a, b) => a.type.localeCompare(b.type) || a.nb_unites - b.nb_unites || a.volume_l - b.volume_l);
    return {
      marque, ps,
      prixLitre: Math.min(...ps.map(p => p.prixLitre)),
      prixTri: Math.min(...ps.map(p => p.prixTri)),
      // photo : la bouteille de 1,5 L de préférence (format de référence)
      visuel: ps.find(p => p.image && p.volume_l === 1.5 && p.type === "plate") || ps.find(p => p.image) || ps[0],
    };
  });
  marques.sort(TRIS[etat.tri]);

  $("#resume").textContent = `${marques.length} marque${marques.length > 1 ? "s" : ""} · ${produits.length} produit${produits.length > 1 ? "s" : ""}`;
  if (!marques.length) return `<p class="vide">Aucun résultat pour ces filtres.</p>`;

  return `<div class="grille">${marques.map(m => `
    <article class="carte">
      <div class="carte-tete">
        ${vignette(m.visuel)}
        <div>
          <h2>${esc(nomMarque(m.marque))}</h2>
          <div class="des">dès <b>${dt(m.prixLitre)}</b> / litre</div>
        </div>
      </div>
      <table>
        <thead><tr><th>Format</th><th class="num">Bouteille</th><th class="num">Stika (6)</th></tr></thead>
        <tbody>${m.ps.map(p => `
          <tr class="ligne-prix">
            <td class="format">${libFormat(p)}${p.type === "gazeuse" ? '<span class="gaz">gazeuse</span>' : ""}<br><small>${dt(p.prixLitre)}/L</small></td>
            <td class="num">${cellBouteille(p)}</td>
            <td class="num meilleur">${cellStika(p)}</td>
          </tr>
          <tr class="ligne-offres"><td colspan="3">${puces(p)}</td></tr>`).join("")}
        </tbody>
      </table>
    </article>`).join("")}</div>`;
}

function rendreFormats(produits) {
  const blocs = FORMATS.slice(1)
    .filter(f => !etat.format || f.id === etat.format)
    .map(f => ({ f, ps: produits.filter(f.test) }))
    .filter(b => b.ps.length);

  $("#resume").textContent = `${produits.length} produit${produits.length > 1 ? "s" : ""} classés par format`;
  if (!blocs.length) return `<p class="vide">Aucun résultat pour ces filtres.</p>`;

  return blocs.map(({ f, ps }) => {
    ps.sort(TRIS[etat.tri]);
    return `<section class="bloc-format">
      <h2>${esc(f.nom)}</h2>
      <table>
        <thead><tr><th class="rang">#</th><th>Marque</th><th class="num">Bouteille</th><th class="num">Stika (6)</th><th class="num col-litre">Prix / L</th><th class="col-offres">Enseignes</th></tr></thead>
        <tbody>${ps.map((p, i) => `
          <tr>
            <td class="rang">${i + 1}</td>
            <td><div class="marque-cell">${vignette(p, "mini")}<span>${esc(nomMarque(p.marque))} <small>${libFormat(p)}</small>${p.type === "gazeuse" ? '<span class="gaz">gazeuse</span>' : ""}</span></div></td>
            <td class="num">${cellBouteille(p)}</td>
            <td class="num meilleur">${cellStika(p)}</td>
            <td class="num col-litre">${dt(p.prixLitre)}</td>
            <td class="col-offres">${puces(p)}</td>
          </tr>`).join("")}
        </tbody>
      </table>
    </section>`;
  }).join("");
}

function rendre() {
  const produits = produitsFiltres();
  $("#liste").innerHTML = etat.vue === "marques" ? rendreMarques(produits) : rendreFormats(produits);
}

function presser(groupe, bouton) {
  groupe.querySelectorAll(".puce").forEach(b => b.setAttribute("aria-pressed", String(b === bouton)));
}

function initFiltres() {
  const fmt = $("#formats");
  fmt.innerHTML = FORMATS.map(f => `<button class="puce" data-format="${f.id}" aria-pressed="${f.id === ""}">${f.nom}</button>`).join("");
  const ens = $("#enseignes");
  ens.innerHTML = Object.entries(DATA.enseignes).map(([id, e]) =>
    `<button class="puce" data-enseigne="${id}" aria-pressed="false"><span class="pastille p-${id}"></span>${esc(e.nom)}</button>`).join("");

  document.querySelector(".filtres").addEventListener("click", ev => {
    const b = ev.target.closest(".puce");
    if (!b) return;
    const d = b.dataset;
    if ("vue" in d) { etat.vue = d.vue; presser(b.parentElement, b); }
    else if ("type" in d) { etat.type = d.type; presser(b.parentElement, b); }
    else if ("format" in d) { etat.format = d.format; presser(b.parentElement, b); }
    else if ("enseigne" in d) {
      const on = b.getAttribute("aria-pressed") !== "true";
      b.setAttribute("aria-pressed", String(on));
      on ? etat.enseignes.add(d.enseigne) : etat.enseignes.delete(d.enseigne);
    }
    rendre();
  });
  $("#tri").addEventListener("change", e => { etat.tri = e.target.value; rendre(); });
  $("#recherche").addEventListener("input", e => { etat.recherche = e.target.value; rendre(); });
}

async function demarrer() {
  try {
    DATA = await (await fetch("data/produits.json", { cache: "no-cache" })).json();
  } catch (e) {
    $("#liste").innerHTML = `<p class="vide">Impossible de charger les prix. Lancez le site via un serveur web (voir README).</p>`;
    return;
  }
  PRODUITS = preparer(DATA.produits);
  const d = new Date(DATA.maj);
  $("#maj").textContent = "mis à jour le " + d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
  initFiltres();
  if (location.hash === "#formats") document.querySelector('[data-vue="formats"]').click();
  else rendre();
}

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
demarrer();
