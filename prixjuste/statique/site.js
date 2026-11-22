// PrixJuste : construit les liens « nouvelle issue » pré-remplis et lit la courbe au doigt.
// Aucun jeton, aucune donnée envoyée ailleurs que sur GitHub, par l'utilisateur lui-même.
(function () {
  "use strict";

  function issueUrl(depot, titre, corps, etiquette) {
    return "https://github.com/" + depot + "/issues/new?" + new URLSearchParams({
      title: titre, body: corps, labels: etiquette
    }).toString().replace(/\+/g, "%20");
  }

  function val(form, nom) {
    var el = form.elements[nom];
    return el ? String(el.value || "").trim() : "";
  }

  // ------------------------------------------------------------ ajouter un objet
  var ajout = document.querySelector(".form-ajout");
  if (ajout) {
    var params = new URLSearchParams(location.search);
    if (params.get("objet")) ajout.elements.objet.value = params.get("objet");
    // conseil de taille d'après le profil (pointure habituelle, ajustements connus par marque)
    var profil = JSON.parse(ajout.dataset.profil || "{}");
    var conseil = ajout.querySelector(".conseil-taille");
    var chaussure = /chaussure|basket|sneaker|boot|botte|bottine|mocassin|derby|sandale|running|timberland/i;
    function conseiller() {
      var t = val(ajout, "objet").toLowerCase(), txt = "";
      var marques = profil.marques || {};
      var m = Object.keys(marques).filter(function (k) { return t.indexOf(k) >= 0; })[0];
      if (profil.pointure && (chaussure.test(t) || (m && marques[m].pointure))) {
        var p = parseFloat(String(profil.pointure).replace(",", "."));
        if (m && marques[m].pointure) {
          txt = "Pointure conseillée : " + String(p + marques[m].pointure).replace(".", ",") + " — " + marques[m].pourquoi + ".";
        } else {
          txt = "Ta pointure habituelle : " + String(p).replace(".", ",") + ".";
        }
      }
      conseil.textContent = txt;
      conseil.hidden = !txt;
    }
    ajout.elements.objet.addEventListener("input", conseiller);
    conseiller();

    ajout.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var objet = val(ajout, "objet");
      if (!objet) return;
      var urgence = (ajout.querySelector("input[name=urgence]:checked") || {}).value || "pas_urgent";
      var lignes = ["Objet : " + objet];
      if (val(ajout, "taille")) lignes.push("Taille : " + val(ajout, "taille"));
      if (val(ajout, "coloris")) lignes.push("Coloris : " + val(ajout, "coloris"));
      lignes.push("Urgence : " + urgence);
      if (val(ajout, "avant")) lignes.push("Avant le : " + val(ajout, "avant"));
      if (val(ajout, "budget")) lignes.push("Budget : " + val(ajout, "budget"));
      var liens = val(ajout, "liens").split(/\s+/).filter(function (u) { return /^https?:\/\//i.test(u); });
      lignes.push("Liens :");
      lignes = lignes.concat(liens.length ? liens : ["(aucun : à identifier)"]);
      lignes.push("", "<!-- prixjuste:ajout -->");
      location.href = issueUrl(ajout.dataset.depot, "Ajout : " + objet, lignes.join("\n"), "ajout");
    });
  }

  // ------------------------------------------------------------ j'ai vu un prix
  var fp = document.querySelector(".form-prix");
  if (fp) {
    fp.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var prix = val(fp, "prix");
      if (!prix) return;
      var lignes = ["Article : " + fp.dataset.article, "Prix : " + prix];
      if (val(fp, "barre")) lignes.push("Prix barré : " + val(fp, "barre"));
      lignes.push("Marchand : " + (val(fp, "marchand") || "vu par toi"));
      if (val(fp, "date")) lignes.push("Date : " + val(fp, "date"));
      lignes.push("Rupture : " + (fp.elements.rupture.checked ? "oui" : "non"), "", "<!-- prixjuste:prix -->");
      location.href = issueUrl(fp.dataset.depot, "Prix vu : " + fp.dataset.nom + " à " + prix + " €", lignes.join("\n"), "prix");
    });
  }

  // ------------------------------------------------------------ je l'ai acheté
  var fa = document.querySelector(".form-achat");
  if (fa) {
    fa.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var prix = val(fa, "prix");
      if (!prix) return;
      var lignes = ["Article : " + fa.dataset.article, "Prix : " + prix, "Marchand : " + (val(fa, "marchand") || "?")];
      if (val(fa, "date")) lignes.push("Date : " + val(fa, "date"));
      lignes.push("", "<!-- prixjuste:achat -->");
      location.href = issueUrl(fa.dataset.depot, "Achat : " + fa.dataset.nom + " à " + prix + " €", lignes.join("\n"), "achat");
    });
  }

  // ------------------------------------------------------------ dates du jour par défaut
  document.querySelectorAll(".form-prix input[type=date], .form-achat input[type=date]").forEach(function (el) {
    if (el.value) return;
    var d = new Date();
    el.value = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  });

  // ------------------------------------------------------------ lecture de la courbe
  document.querySelectorAll(".courbe[data-points]").forEach(function (fig) {
    var donnees = JSON.parse(fig.dataset.points);
    var sortie = fig.querySelector(".lecture");
    fig.querySelectorAll(".courbe-svg").forEach(function (svg) {
      var pts = donnees[svg.classList.contains("courbe-large") ? "large" : "etroite"] || [];
      var curseur = svg.querySelector(".curseur");
      var vb = svg.viewBox.baseVal;
      function lire(ev) {
        if (!pts.length) return;
        var r = svg.getBoundingClientRect();
        var x = (ev.clientX - r.left) / r.width * 100;
        var best = pts[0];
        pts.forEach(function (p) { if (Math.abs(p[0] - x) < Math.abs(best[0] - x)) best = p; });
        curseur.setAttribute("cx", best[0] / 100 * vb.width);
        curseur.setAttribute("cy", best[1] / 100 * vb.height);
        curseur.classList.add("vu");
        sortie.textContent = best[2];
      }
      svg.addEventListener("pointermove", lire);
      svg.addEventListener("pointerdown", lire);
    });
  });
})();

// Carte 9:16 « preuve » : dessinée sur un canevas, téléchargée en PNG. Rien n'est envoyé nulle part.
(function () {
  "use strict";
  var bouton = document.querySelector(".bouton-carte");
  if (!bouton) return;
  var ENCRE = "#1A1917", PAPIER = "#F3EFE6", GRIS = "#57534C";
  var TAMPON = { achete: "#1F6B45", attends: "#23479A", surveille: "#9A5B12", bidon: "#B3261E", donnees: "#7A766E" };
  var COND = '"IBM Plex Sans Condensed", "Arial Narrow", sans-serif', MONO = '"IBM Plex Mono", monospace';

  function lignes(ctx, texte, largeur) {
    var mots = String(texte).split(/\s+/), res = [], cour = "";
    mots.forEach(function (m) {
      var essai = cour ? cour + " " + m : m;
      if (ctx.measureText(essai).width > largeur && cour) { res.push(cour); cour = m; } else { cour = essai; }
    });
    if (cour) res.push(cour);
    return res;
  }

  function perfore(ctx, y) {
    ctx.fillStyle = "rgba(26,25,23,.35)";
    for (var x = 84; x < 1000; x += 18) { ctx.beginPath(); ctx.arc(x, y, 3, 0, 7); ctx.fill(); }
  }

  function dessiner(d) {
    var cv = document.createElement("canvas");
    cv.width = 1080; cv.height = 1920;
    var ctx = cv.getContext("2d");
    ctx.fillStyle = PAPIER; ctx.fillRect(0, 0, 1080, 1920);
    var M = 84, L = 1080 - 2 * M, y = 150;

    ctx.fillStyle = ENCRE; ctx.font = "700 46px " + COND; ctx.textBaseline = "alphabetic";
    ctx.fillText("PRIX", M, y);
    var w = ctx.measureText("PRIX ").width;
    ctx.fillRect(M + w, y - 42, ctx.measureText("JUSTE").width + 14, 52);
    ctx.fillStyle = PAPIER; ctx.fillText("JUSTE", M + w + 7, y);
    ctx.fillStyle = GRIS; ctx.font = "400 26px " + MONO; ctx.textAlign = "right";
    ctx.fillText("relevé du " + d.date, 1080 - M, y); ctx.textAlign = "left";
    perfore(ctx, y + 44);

    y += 170; ctx.fillStyle = ENCRE; ctx.font = "700 92px " + COND;
    lignes(ctx, d.nom.toUpperCase(), L).slice(0, 3).forEach(function (l) { ctx.fillText(l, M, y); y += 88; });
    ctx.fillStyle = GRIS; ctx.font = "400 28px " + MONO;
    lignes(ctx, d.variante, L).slice(0, 2).forEach(function (l) { ctx.fillText(l, M, y); y += 40; });

    y += 70; ctx.fillStyle = GRIS; ctx.font = "500 26px " + MONO; ctx.fillText("MEILLEUR PRIX RELEVÉ", M, y);
    y += 150; ctx.fillStyle = ENCRE; ctx.font = "700 170px " + MONO; ctx.fillText(d.prix, M - 6, y);
    y += 60; ctx.font = "400 30px " + MONO; ctx.fillStyle = GRIS;
    var sous = "chez " + d.chez + " · le " + d.le;
    if (d.barre) sous = "prix barré affiché " + d.barre + " (" + d.remise + ") · " + sous;
    lignes(ctx, sous, L).slice(0, 2).forEach(function (l) { ctx.fillText(l, M, y); y += 42; });

    // tampon : sa propre bande, il ne couvre jamais le texte
    var couleur = TAMPON[d.classe] || TAMPON.donnees;
    var h = d.tampon.length > 1 ? 190 : 140 + (d.sous ? 40 : 0);
    ctx.save(); ctx.translate(1080 - M - 230, y + 40 + h / 2); ctx.rotate(-6 * Math.PI / 180);
    ctx.globalAlpha = .9; ctx.strokeStyle = couleur; ctx.fillStyle = couleur;
    ctx.lineWidth = 8; ctx.strokeRect(-220, -h / 2, 440, h);
    ctx.lineWidth = 3; ctx.strokeRect(-204, -h / 2 + 16, 408, h - 32);
    ctx.font = "700 " + (d.tampon.length > 1 ? 54 : 80) + "px " + COND; ctx.textAlign = "center";
    var ty = d.tampon.length > 1 ? -12 : (d.sous ? 6 : 28);
    d.tampon.forEach(function (t, i) { ctx.fillText(t.split("").join(String.fromCharCode(8202)), 0, ty + i * 58); });
    if (d.sous) { ctx.font = "700 26px " + MONO; ctx.fillText(d.sous, 0, ty + 46); }
    ctx.restore();

    y += h + 130; ctx.fillStyle = ENCRE; ctx.font = "700 48px " + COND;
    lignes(ctx, d.titre.toUpperCase(), L).slice(0, 2).forEach(function (l) { ctx.fillText(l, M, y); y += 54; });
    ctx.font = "400 30px " + MONO;
    lignes(ctx, d.explication, L).slice(0, 4).forEach(function (l) { ctx.fillText(l, M, y); y += 44; });

    // courbe en escalier : 12 mois
    var gx = M, gy = y + 50, gw = L, gh = Math.min(300, 1640 - gy);
    if (d.serie.length > 1 && gh > 120) {
      var xs = d.serie.map(function (p) { return p[0]; }), ps = d.serie.map(function (p) { return p[1]; });
      var x0 = Math.min.apply(null, xs), x1 = 0, lo = Math.min.apply(null, ps), hi = Math.max.apply(null, ps);
      var pad = Math.max((hi - lo) * .15, 8); lo -= pad; hi += pad;
      var X = function (v) { return gx + (v - x0) / ((x1 - x0) || 1) * gw; };
      var Y = function (v) { return gy + (hi - v) / (hi - lo) * gh; };
      ctx.strokeStyle = "rgba(26,25,23,.35)"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(gx, gy + gh); ctx.lineTo(gx + gw, gy + gh); ctx.stroke();
      ctx.strokeStyle = ENCRE; ctx.lineWidth = 4; ctx.beginPath();
      d.serie.forEach(function (p, i) {
        var x = X(p[0]), yy = Y(p[1]);
        if (i === 0) ctx.moveTo(x, yy); else { ctx.lineTo(x, Y(d.serie[i - 1][1])); ctx.lineTo(x, yy); }
      });
      ctx.lineTo(X(0), Y(d.serie[d.serie.length - 1][1])); ctx.stroke();
      d.serie.forEach(function (p) {
        ctx.beginPath(); ctx.arc(X(p[0]), Y(p[1]), 8, 0, 7);
        if (p[2] === "archive") { ctx.fillStyle = PAPIER; ctx.fill(); ctx.lineWidth = 3; ctx.stroke(); }
        else { ctx.fillStyle = ENCRE; ctx.fill(); }
      });
      ctx.fillStyle = GRIS; ctx.font = "400 24px " + MONO;
      var leg = "meilleur prix du jour, 12 derniers mois" + (d.min ? " · plus bas " + d.min + " le " + d.min_le : "");
      lignes(ctx, leg, L).slice(0, 2).forEach(function (l, i) { ctx.fillText(l, gx, gy + gh + 44 + i * 34); });
    }

    perfore(ctx, 1760);
    ctx.fillStyle = GRIS; ctx.font = "400 24px " + MONO;
    ctx.fillText(d.fiabilite, M, 1812);
    lignes(ctx, "Prix réellement relevés : sites marchands, archives du web, saisies. Aucun contournement.", L)
      .slice(0, 2).forEach(function (l, i) { ctx.fillText(l, M, 1850 + i * 34); });
    return cv;
  }

  bouton.addEventListener("click", function () {
    var d = JSON.parse(bouton.dataset.carte);
    (document.fonts ? document.fonts.ready : Promise.resolve()).then(function () {
      var cv = dessiner(d);
      cv.toBlob(function (blob) {
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "prixjuste-" + d.nom.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") + ".png";
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
      }, "image/png");
    });
  });
})();

// Plan d'achat sous budget : le budget mensuel reste sur cet appareil (localStorage), rien n'est envoyé.
(function () {
  "use strict";
  var bloc = document.querySelector(".plan[data-plan]");
  if (!bloc) return;
  // <repartir> même algorithme que prixjuste/plan.py:repartir (testé contre lui)
  function repartir(cands, budget) {
    var plafond = budget > 0 ? budget : Infinity, depense = {}, plan = {}, hors = [], total = 0, maintenant = 0;
    var minP = function (a) { return Math.min.apply(null, a.mois.map(function (m) { return m[1]; })); };
    var ordre = cands.articles.map(function (a, i) { return [a, i]; }).sort(function (x, y) {
      var a = x[0], b = y[0];
      return (a.mois.length - b.mois.length) || ((b.maintenant - minP(b)) - (a.maintenant - minP(a))) || (x[1] - y[1]);
    }).map(function (x) { return x[0]; });
    ordre.forEach(function (a) {
      var choix = a.mois.slice().sort(function (x, y) { return (x[1] - y[1]) || (x[0] < y[0] ? -1 : x[0] > y[0] ? 1 : 0); });
      var ok = choix.filter(function (m) { return (depense[m[0]] || 0) + m[1] <= plafond; })[0];
      if (!ok) { hors.push(a.id); return; }
      depense[ok[0]] = (depense[ok[0]] || 0) + ok[1];
      (plan[ok[0]] = plan[ok[0]] || []).push([a.id, ok[1]]);
      total += ok[1]; maintenant += a.maintenant;
    });
    var tri = {};
    Object.keys(plan).sort().forEach(function (k) { tri[k] = plan[k]; });
    return { mois: tri, hors: hors, total: Math.round(total * 100) / 100, economie: Math.round((maintenant - total) * 100) / 100 };
  }
  // </repartir>
  var MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
  var cands = JSON.parse(bloc.dataset.plan), noms = {};
  cands.articles.forEach(function (a) { noms[a.id] = a.nom; });
  var champ = bloc.querySelector("input"), frise = bloc.querySelector(".frise"), bilan = bloc.querySelector(".plan-bilan");
  function eur(x) { return x.toLocaleString("fr-FR", { maximumFractionDigits: x % 1 ? 2 : 0, minimumFractionDigits: x % 1 ? 2 : 0 }) + " €"; }
  function el(tag, cls, txt) { var n = document.createElement(tag); if (cls) n.className = cls; if (txt != null) n.textContent = txt; return n; }
  function afficher() {
    var budget = parseFloat(String(champ.value).replace(",", ".").replace(/[^\d.]/g, "")) || 0;
    try { localStorage.setItem("prixjuste-budget-mois", champ.value); } catch (e) { /* stockage indisponible */ }
    var r = repartir(cands, budget);
    frise.textContent = "";
    Object.keys(r.mois).forEach(function (k) {
      var li = el("li"), somme = 0, ul = el("ul");
      var plusieurs = r.mois[k].length > 1;
      r.mois[k].forEach(function (x) { somme += x[1]; ul.appendChild(el("li", null, noms[x[0]] + (plusieurs ? " · " + eur(x[1]) : ""))); });
      li.appendChild(el("span", "f-mois", MOIS[+k.slice(5) - 1] + " " + k.slice(0, 4)));
      li.appendChild(ul);
      li.appendChild(el("span", "f-total", eur(Math.round(somme * 100) / 100)));
      frise.appendChild(li);
    });
    var txt = r.total ? "Total estimé " + eur(Math.round(r.total)) + " · " + (r.economie > 0.5
      ? "économie attendue " + eur(Math.round(r.economie)) + " par rapport à tout acheter aujourd'hui."
      : "pas d'économie attendue : acheter maintenant revient au même.") : "";
    if (r.hors.length) txt += (txt ? " " : "") + "Hors budget avant sa date limite : " + r.hors.map(function (i) { return noms[i]; }).join(", ") + ".";
    bilan.textContent = txt;
  }
  try { champ.value = localStorage.getItem("prixjuste-budget-mois") || ""; } catch (e) { /* idem */ }
  champ.addEventListener("input", afficher);
  afficher();
})();


// Pistes immédiates sous « Qu'est-ce que tu veux acheter ? » : ce qui est déjà dans ta liste, et les prix
// existants chez les comparateurs (ouverts par toi, dans un nouvel onglet). Rien n'est relevé ni envoyé ici.
(function () {
  "use strict";
  var form = document.querySelector("form.demande[data-liste]");
  if (!form) return;
  var champ = form.querySelector("#objet"), zone = form.querySelector(".pistes");
  var liste = JSON.parse(form.dataset.liste || "[]");
  function norm(t) { return String(t).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); }
  function lien(url, texte) {
    var a = document.createElement("a");
    a.href = url; a.textContent = texte; a.target = "_blank"; a.rel = "noopener";
    return a;
  }
  function majour() {
    var q = champ.value.trim();
    zone.textContent = "";
    if (q.length < 3) { zone.hidden = true; return; }
    var mots = norm(q).split(/\s+/).filter(function (m) { return m.length > 2; });
    var deja = liste.filter(function (a) {
      var n = norm(a.nom);
      return mots.length && mots.every(function (m) { return n.indexOf(m) >= 0; });
    });
    if (deja.length) {
      var p1 = document.createElement("p");
      p1.appendChild(document.createTextNode("Déjà dans ta liste : "));
      deja.slice(0, 3).forEach(function (a, i) {
        if (i) p1.appendChild(document.createTextNode(" · "));
        var x = lien("a/" + a.id + ".html", a.nom); x.removeAttribute("target"); p1.appendChild(x);
      });
      zone.appendChild(p1);
    }
    var e = encodeURIComponent(q);
    var p2 = document.createElement("p");
    p2.appendChild(document.createTextNode("Voir tout de suite les modèles et prix existants : "));
    [["https://www.idealo.fr/prechcat.html?q=" + e, "idealo"],
     ["https://ledenicheur.fr/search?search=" + e, "Le Dénicheur"],
     ["https://www.google.com/search?tbm=shop&q=" + e, "Google Shopping"]].forEach(function (c, i) {
      if (i) p2.appendChild(document.createTextNode(" · "));
      p2.appendChild(lien(c[0], c[1]));
    });
    zone.appendChild(p2);
    var p3 = document.createElement("p");
    p3.className = "pistes-suivre";
    p3.textContent = "« Suivre » : PrixJuste te propose des modèles avec photo (d'ici 3 h au plus), puis relève leurs prix chaque jour. Avec un lien produit, c'est en 2 minutes.";
    zone.appendChild(p3);
    zone.hidden = false;
  }
  champ.addEventListener("input", majour);
  majour();
})();
