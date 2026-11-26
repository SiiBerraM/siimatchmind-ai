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

  function ensureStyle() {
    if (document.getElementById("smm-prono-style")) return;
    var st = document.createElement("style");
    st.id = "smm-prono-style";
    st.textContent = [
      ".pr-wrap{display:flex;flex-direction:column;gap:10px;margin-top:10px}",
      ".pr-card{display:flex;justify-content:space-between;align-items:stretch;gap:10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.12);border-radius:10px;overflow:hidden}",
      ".pr-left{flex:1;padding:10px 12px;display:flex;flex-direction:column;gap:6px}",
      ".pr-mkt{display:inline-block;align-self:flex-start;background:#1e3a8a;color:#fff;font-size:12px;font-weight:700;padding:3px 8px;border-radius:4px}",
      ".pr-row{display:flex;align-items:center;gap:8px;font-weight:700;font-size:14px}",
      ".pr-del{background:transparent;border:none;color:#f87171;cursor:pointer;padding:2px 6px;font-size:15px}",
      ".pr-right{min-width:96px;padding:10px;background:rgba(255,255,255,.03);border-inline-start:1px dashed rgba(255,255,255,.15);display:flex;flex-direction:column;justify-content:center;align-items:center;gap:4px;font-size:12px;text-align:center}",
      ".pr-main{font-weight:800;font-size:13px;color:#facc15}"
    ].join("");
    document.head.appendChild(st);
  }

  async function renderPronostics() {
    if (location.hash !== "#/pronostics") return;
    var view = getView();
    if (!view) return;
    ensureStyle();
    view.innerHTML = '<h1>Pronostics</h1><p class="muted">Chargement...</p>';

    try {
      var r = await fetch("data/static.json", { cache: "no-store" });
      var d = await r.json();
      var analyses = d.analyses || {};
      var entries = Object.entries(analyses).slice(0, 60);

      if (!entries.length) {
        view.innerHTML = '<h1>Pronostics</h1><p class="muted">Aucun pronostic disponible.</p>';
        return;
      }

      var cardsHtml = entries.map(function (pair, idx) {
        var key = pair[0], val = pair[1] || {};
        var parts = key.split("|");
        var h = parts[0] || "", a = parts[1] || "";
        var pct = (val.prediction && val.prediction.percent) || {};
        var ph = pct.home != null ? pct.home : (pct.H != null ? pct.H : "-");
        var pd = pct.draw != null ? pct.draw : (pct.D != null ? pct.D : "-");
        var pa = pct.away != null ? pct.away : (pct.A != null ? pct.A : "-");
        var market = val.market || val.pick || val.league || "1X2";
        var href = "#/analyze/" + encodeURIComponent(h) + "/" + encodeURIComponent(a);

        return (
          '<div class="pr-card" data-idx="' + idx + '">' +
            '<div class="pr-left">' +
              '<span class="pr-mkt">' + esc(market) + '</span>' +
              '<div class="pr-row">' +
                '<button type="button" class="pr-del" title="Remove" aria-label="Remove">🗑</button>' +
                '<a href="' + href + '" style="color:inherit;text-decoration:none;">' + esc(h) + '</a>' +
              '</div>' +
              '<div class="pr-row">' +
                '<a href="' + href + '" style="color:inherit;text-decoration:none;">' + esc(a) + '</a>' +
              '</div>' +
            '</div>' +
            '<div class="pr-right">' +
              '<span class="pr-main">' + esc(ph) + '% / ' + esc(pd) + '% / ' + esc(pa) + '%</span>' +
              '<span class="muted">H / D / A</span>' +
            '</div>' +
          '</div>'
        );
      }).join("");

      view.innerHTML = '<h1>Pronostics</h1><div class="pr-wrap" id="prList">' + cardsHtml + '</div>';

      view.querySelectorAll(".pr-del").forEach(function (btn) {
        btn.addEventListener("click", function (ev) {
          ev.preventDefault();
          var card = btn.closest(".pr-card");
          if (card) card.remove();
        });
      });
    } catch (e) {
      view.innerHTML = '<h1>Pronostics</h1><p class="err">' + esc(e && e.message || e) + '</p>';
    }
  }

  window.addEventListener("hashchange", function () { setTimeout(renderPronostics, 30); });
  if (location.hash === "#/pronostics") setTimeout(renderPronostics, 60);
})();
