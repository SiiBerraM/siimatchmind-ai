(function () {
  "use strict";
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function getView() {
    return document.getElementById("view") || document.querySelector("main .view") || document.querySelector("main");
  }
  async function renderPronostics() {
    if (location.hash !== "#/pronostics") return;
    var view = getView();
    if (!view) return;
    view.innerHTML = '<h1>Pronostics Football</h1><p class="muted">Chargement...</p>';
    try {
      var r = await fetch("data/static.json", { cache: "no-store" });
      var d = await r.json();
      var analyses = d.analyses || {};
      var entries = Object.entries(analyses).slice(0, 80);
      if (!entries.length) {
        view.innerHTML = '<h1>Pronostics Football</h1><p class="muted">Aucun pronostic disponible.</p>';
        return;
      }
      var cards = entries.map(function (pair) {
        var key = pair[0], val = pair[1] || {};
        var parts = key.split("|");
        var h = parts[0] || "", a = parts[1] || "";
        var pct = (val.prediction && val.prediction.percent) || {};
        var ph = pct.home != null ? pct.home : (pct.H != null ? pct.H : "-");
        var pd = pct.draw != null ? pct.draw : (pct.D != null ? pct.D : "-");
        var pa = pct.away != null ? pct.away : (pct.A != null ? pct.A : "-");
        return '<a class="match" href="#/analyze/' + encodeURIComponent(h) + '/' + encodeURIComponent(a) + '">' +
          '<div><strong>' + esc(h) + ' vs ' + esc(a) + '</strong></div>' +
          '<div class="muted">' + esc(ph) + '% / ' + esc(pd) + '% / ' + esc(pa) + '%</div></a>';
      }).join("");
      view.innerHTML = '<h1>Pronostics Football</h1><div class="list">' + cards + '</div>';
    } catch (e) {
      view.innerHTML = '<h1>Pronostics Football</h1><p class="err">' + esc(e && e.message || e) + '</p>';
    }
  }
  window.addEventListener("hashchange", function () { setTimeout(renderPronostics, 30); });
  if (location.hash === "#/pronostics") setTimeout(renderPronostics, 60);
})();
