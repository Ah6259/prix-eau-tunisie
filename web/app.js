"use strict";

const FORMATS = [
  { id: "", nom: "Tous formats", test: () => true },
  { id: "petit", nom: "≤ 0,75 L", test: p => p.nb_unites === 1 && p.volume_l <= 0.75 },
  { id: "1", nom: "1 L", test: p => p.nb_unites === 1 && p.volume_l > 0.75 && p.volume_l < 1.25 },
  { id: "1.5", nom: "1,5 L", test: p => p.nb_unites === 1 && p.volume_l >= 1.25 && p.volume_l < 1.6 },
  { id: "2", nom: "2 L", test: p => p.nb_unites === 1 && p.volume_l >= 1.6 && p.volume_l < 3 },
  { id: "bonbonne", nom: "Bonbonnes", test: p => p.nb_unites === 1 && p.volume_l >= 3 },
  { id: "pack", nom: "Packs", test: p => p.nb_unites > 1 },
];

const etat = { vue: "marques", type: "", format: "", enseignes: new Set(), recherche: "", tri: "litre" };
let DATA = null;

const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const dt = v => v.toLocaleString("fr-TN", { minimumFractionDigits: 3, maximumFractionDigits: 3 }) + " DT";
const litres = v => (v < 1 ? `${Math.round(v * 100)} cl` : `${String(v).replace(".", ",")} L`);
const libFormat = p => (p.nb_unites > 1 ? `${p.nb_unites} × ${litres(p.volume_l)}` : litres(p.volume_l));
const nomMarque = m => m.charAt(0) + m.slice(1).toLowerCase();

function vignette(p, cls = "vignette") {
  const img = p && p.image
    ? `<img src="${esc(p.image)}" alt="" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'initiale',textContent:'${esc(p.marque[0])}'}))">`
    : `<span class="initiale">${esc(p ? p.marque[0] : "?")}</span>`;
  return `<div class="${cls}">${img}</div>`;
}

/** Offres visibles d'un produit selon le filtre enseignes, triées par prix. */
function offresVisibles(p) {
  return p.offres.filter(o => !etat.enseignes.size || etat.enseignes.has(o.enseigne));
}

function produitsFiltres() {
  const fmt = FORMATS.find(f => f.id === etat.format);
  const q = etat.recherche.trim().toUpperCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  return DATA.produits
    .filter(p => !etat.type || p.type === etat.type)
    .filter(fmt.test)
    .filter(p => !q || p.marque.includes(q))
    .map(p => {
      const offres = offresVisibles(p);
      if (!offres.length) return null;
      const prix = offres[0].prix;
      return { ...p, offres, prix, prixLitre: prix / (p.volume_l * p.nb_unites) };
    })
    .filter(Boolean);
}

function puceOffre(o, top) {
  const e = DATA.enseignes[o.enseigne];
  const via = o.via ? ` (relevé via ${o.via})` : "";
  return `<a class="offre${top ? " top" : ""}" href="${esc(o.url)}" target="_blank" rel="noopener" title="${esc(e.nom + " — " + o.nom + via)}">
    <span class="pastille p-${o.enseigne}"></span>${esc(e.nom)} <b>${dt(o.prix)}</b></a>`;
}

function rendreMarques(produits) {
  const parMarque = new Map();
  for (const p of produits) {
    if (!parMarque.has(p.marque)) parMarque.set(p.marque, []);
    parMarque.get(p.marque).push(p);
  }
  let marques = [...parMarque.entries()].map(([marque, ps]) => {
    ps.sort((a, b) => a.type.localeCompare(b.type) || a.nb_unites - b.nb_unites || a.volume_l - b.volume_l);
    return {
      marque, ps,
      minLitre: Math.min(...ps.map(p => p.prixLitre)),
      minPrix: Math.min(...ps.map(p => p.prix)),
      // photo : la bouteille de 1,5 L de préférence (format de référence)
      visuel: ps.find(p => p.image && p.volume_l === 1.5 && p.type === "plate") || ps.find(p => p.image) || ps[0],
    };
  });
  const tri = { litre: (a, b) => a.minLitre - b.minLitre, prix: (a, b) => a.minPrix - b.minPrix, marque: (a, b) => a.marque.localeCompare(b.marque) };
  marques.sort(tri[etat.tri]);

  $("#resume").textContent = `${marques.length} marque${marques.length > 1 ? "s" : ""} · ${produits.length} produit${produits.length > 1 ? "s" : ""}`;
  if (!marques.length) return `<p class="vide">Aucun résultat pour ces filtres.</p>`;

  return `<div class="grille">${marques.map(m => `
    <article class="carte">
      <div class="carte-tete">
        ${vignette(m.visuel)}
        <div>
          <h2>${esc(nomMarque(m.marque))}</h2>
          <div class="des">dès <b>${dt(m.minLitre)}</b> / litre</div>
        </div>
      </div>
      <table>
        <thead><tr><th>Format</th><th>Où l'acheter</th></tr></thead>
        <tbody>${m.ps.map(p => `
          <tr>
            <td class="format">${libFormat(p)}${p.type === "gazeuse" ? '<span class="gaz">gazeuse</span>' : ""}<br><small>${dt(p.prixLitre)}/L</small></td>
            <td><div class="offres">${p.offres.map((o, i) => puceOffre(o, i === 0 && p.offres.length > 1)).join("")}</div></td>
          </tr>`).join("")}
        </tbody>
      </table>
    </article>`).join("")}</div>`;
}

function rendreFormats(produits) {
  const blocs = FORMATS.slice(1)
    .filter(f => !etat.format || f.id === etat.format)
    .map(f => ({ f, ps: produits.filter(f.test) }))
    .filter(b => b.ps.length);
  const tri = { litre: (a, b) => a.prixLitre - b.prixLitre, prix: (a, b) => a.prix - b.prix, marque: (a, b) => a.marque.localeCompare(b.marque) };

  $("#resume").textContent = `${produits.length} produit${produits.length > 1 ? "s" : ""} classés par format`;
  if (!blocs.length) return `<p class="vide">Aucun résultat pour ces filtres.</p>`;

  return blocs.map(({ f, ps }) => {
    ps.sort(tri[etat.tri]);
    return `<section class="bloc-format">
      <h2>${esc(f.nom)}</h2>
      <table>
        <thead><tr><th class="rang">#</th><th>Marque</th><th class="num">Meilleur prix</th><th class="num col-litre">Prix / L</th><th>Enseignes</th></tr></thead>
        <tbody>${ps.map((p, i) => `
          <tr>
            <td class="rang">${i + 1}</td>
            <td><div class="marque-cell">${vignette(p, "mini")}<span>${esc(nomMarque(p.marque))} <small>${libFormat(p)}</small>${p.type === "gazeuse" ? '<span class="gaz">gazeuse</span>' : ""}</span></div></td>
            <td class="num meilleur">${dt(p.prix)}</td>
            <td class="num col-litre">${dt(p.prixLitre)}</td>
            <td><div class="offres">${p.offres.map((o, j) => puceOffre(o, j === 0 && p.offres.length > 1)).join("")}</div></td>
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
  const d = new Date(DATA.maj);
  $("#maj").textContent = "mis à jour le " + d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
  initFiltres();
  if (location.hash === "#formats") document.querySelector('[data-vue="formats"]').click();
  else rendre();
}

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
demarrer();
