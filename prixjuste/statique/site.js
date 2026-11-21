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
    if (fp.elements.date && !fp.elements.date.value) {
      var d = new Date();
      fp.elements.date.value = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
    }
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
