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
      ".pr-slip{max-width:680px;margin:0 auto;font-family:system-ui,sans-serif}",
      ".pr-top{background:#0f2347;color:#fff;border-radius:10px 10px 0 0;padding:10px 12px;border:1px solid #1e3a6e}",
      ".pr-top-title{text-align:center;font-weight:800;font-size:17px;color:#facc15;margin-bottom:8px}",
      ".pr-top-bar{display:flex;justify-content:space-between;align-items:center;gap:6px;flex-wrap:wrap;font-size:12px}",
      ".pr-pill{background:#183466;border:1px solid #2b4c8c;padding:4px 8px;border-radius:6px;font-weight:700}",
      ".pr-qr{background:#16a34a;color:#fff;padding:4px 10px;border-radius:6px;font-weight:800}",
      ".pr-list{display:flex;flex-direction:column;background:#e2e8f0;color:#0f172a;border-radius:0 0 10px 10px;overflow:hidden;border:1px solid #cbd5e1;border-top:none}",
      ".pr-item{display:flex;justify-content:space-between;align-items:stretch;background:#f1f5f9;border-bottom:2px solid #cbd5e1}",
      ".pr-item:nth-child(even){background:#e8eef5}",
      ".pr-main{flex:1;padding:8px 10px;display:flex;flex-direction:column;gap:6px;min-width:0}",
      ".pr-mkt{display:inline-block;align-self:flex-start;background:#29488d;color:#fff;font-size:11.5px;font-weight:700;padding:3px 9px;border-radius:4px;box-shadow:0 1px 2px rgba(0,0,0,.15)}",
      ".pr-body{display:flex;align-items:center;gap:8px}",
      ".pr-del{background:transparent;border:none;color:#dc2626;cursor:pointer;padding:4px;display:flex;align-items:center;justify-content:center;flex:none}",
      ".pr-del svg{width:20px;height:20px;stroke:currentColor;fill:none;stroke-width:2}",
      ".pr-teams{display:flex;flex-direction:column;gap:5px;flex:1;min-width:0}",
      ".pr-team{display:flex;align-items:center;gap:7px;font-weight:700;font-size:13.5px;color:#1e293b;text-decoration:none}",
      ".pr-team img{width:20px;height:20px;object-fit:contain;flex:none}",
      ".pr-badge{width:20px;height:20px;border-radius:50%;background:#cbd5e1;color:#1e293b;font-size:9px;font-weight:800;display:inline-flex;align-items:center;justify-content:center;flex:none}",
      ".pr-side{width:118px;flex:none;background:#e2e8f0;border-inline-start:1px solid #cbd5e1;padding:7px 8px;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:4px;text-align:center;font-size:11.5px}",
      ".pr-score{font-weight:800;font-size:13px;color:#0f172a}",
      ".pr-sub{color:#475569;font-size:11px}",
      ".pr-code-row{display:flex;align-items:center;gap:4px;flex-wrap:wrap;justify-content:center}",
      ".pr-code{background:#3b66b8;color:#fff;font-weight:700;font-size:10.5px;padding:2px 6px;border-radius:3px}",
      ".pr-odd{background:#1e3a8a;color:#facc15;font-weight:800;font-size:11px;padding:2px 7px;border-radius:3px}"
    ].join("");
    document.head.appendChild(st);
  }

  function marketLabel(ph, pd, pa, val) {
    if (val && (val.market || val.pick)) return val.market || val.pick;
    var h = Number(ph) || 0, d = Number(pd) || 0, a = Number(pa) || 0;
    if (h >= 60) return "من سوف يفوز (1) • مجموع الأهداف +1.5";
    if (a >= 60) return "من سوف يفوز (2) • مجموع الأهداف +1.5";
    if (h >= 48) return "من سوف يفوز (1)";
    if (a >= 48) return "من سوف يفوز (2)";
    if (d >= 34) return "تعادل أو فوز مزدوج (1X / X2)";
    return "هل كلا الفريقين سيسجل";
  }

  function teamLogo(logo, name) {
    var abbr = esc((name || "?").slice(0, 2).toUpperCase());
    if (logo) {
      return '<img src="' + esc(logo) + '" alt="" referrerpolicy="no-referrer" loading="lazy" onerror="this.outerHTML=\'<span class=pr-badge>' + abbr + '</span>\'">';
    }
    return '<span class="pr-badge">' + abbr + '</span>';
  }

  async function renderPronostics() {
    if (location.hash !== "#/pronostics") return;
    var view = getView();
    if (!view) return;
    ensureStyle();
    view.innerHTML = '<div class="pr-slip"><div class="pr-top"><div class="pr-top-title">Pronostics</div></div><p class="muted" style="padding:12px;">Chargement...</p></div>';

    try {
      var r = await fetch("data/static.json", { cache: "no-store" });
      var d = await r.json();
      var teamsMap = {};
      (d.teams || []).forEach(function (t) {
        if (t.id) teamsMap[t.id] = t;
        if (t.name) teamsMap[t.name] = t;
      });

      var analyses = d.analyses || {};
      var entries = Object.entries(analyses).slice(0, 50);

      if (!entries.length) {
        view.innerHTML = '<div class="pr-slip"><div class="pr-top"><div class="pr-top-title">Pronostics</div></div><p class="muted" style="padding:12px;">Aucun pronostic disponible.</p></div>';
        return;
      }

      var totalOdds = 1;
      var cardsHtml = entries.map(function (pair, idx) {
        var key = pair[0], val = pair[1] || {};
        var parts = key.split("|");
        var rawH = parts[0] || "", rawA = parts[1] || "";
        var infoH = teamsMap[rawH] || {};
        var infoA = teamsMap[rawA] || {};
        var nameH = infoH.name || rawH;
        var nameA = infoA.name || rawA;

        var pct = (val.prediction && val.prediction.percent) || {};
        var ph = pct.home != null ? pct.home : (pct.H != null ? pct.H : 40);
        var pd = pct.draw != null ? pct.draw : (pct.D != null ? pct.D : 30);
        var pa = pct.away != null ? pct.away : (pct.A != null ? pct.A : 30);

        var maxP = Math.max(Number(ph) || 1, Number(pd) || 1, Number(pa) || 1);
        var odd = (100 / Math.max(maxP, 15)).toFixed(2);
        if (idx < 5) totalOdds *= Number(odd);

        var mkt = marketLabel(ph, pd, pa, val);
        var code = "4965" + String(480 + idx);
        var href = "#/analyze/" + encodeURIComponent(rawH) + "/" + encodeURIComponent(rawA);

        return (
          '<div class="pr-item" data-odd="' + odd + '">' +
            '<div class="pr-main">' +
              '<span class="pr-mkt">' + esc(mkt) + '</span>' +
              '<div class="pr-body">' +
                '<button type="button" class="pr-del" title="Supprimer" aria-label="Supprimer">' +
                  '<svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6"/></svg>' +
                '</button>' +
                '<div class="pr-teams">' +
                  '<a class="pr-team" href="' + href + '">' + teamLogo(infoH.logo, nameH) + '<span>' + esc(nameH) + '</span></a>' +
                  '<a class="pr-team" href="' + href + '">' + teamLogo(infoA.logo, nameA) + '<span>' + esc(nameA) + '</span></a>' +
                '</div>' +
              '</div>' +
            '</div>' +
            '<div class="pr-side">' +
              '<div class="pr-score">' + esc(ph) + '% - ' + esc(pa) + '%</div>' +
              '<div class="pr-sub">(Nul ' + esc(pd) + '%)</div>' +
              '<div class="pr-code-row">' +
                '<span class="pr-code">' + code + '</span>' +
                '<span class="pr-odd">' + odd + '</span>' +
              '</div>' +
            '</div>' +
          '</div>'
        );
      }).join("");

      view.innerHTML =
        '<div class="pr-slip">' +
          '<div class="pr-top">' +
            '<div class="pr-top-title">Pronostics • اختياراتي</div>' +
            '<div class="pr-top-bar">' +
              '<span class="pr-pill" id="prCount">' + entries.length + ' matchs</span>' +
              '<span class="pr-pill">Top 5 Cote: ' + totalOdds.toFixed(2) + '</span>' +
              '<span class="pr-qr">Pronostics AI</span>' +
            '</div>' +
          '</div>' +
          '<div class="pr-list" id="prList">' + cardsHtml + '</div>' +
        '</div>';

      view.querySelectorAll(".pr-del").forEach(function (btn) {
        btn.addEventListener("click", function (ev) {
          ev.preventDefault();
          var card = btn.closest(".pr-item");
          if (card) card.remove();
          var rem = view.querySelectorAll(".pr-item").length;
          var cntEl = document.getElementById("prCount");
          if (cntEl) cntEl.textContent = rem + " matchs";
        });
      });
    } catch (e) {
      view.innerHTML = '<h1>Pronostics</h1><p class="err">' + esc(e && e.message || e) + '</p>';
    }
  }

  window.addEventListener("hashchange", function () { setTimeout(renderPronostics, 30); });
  if (location.hash === "#/pronostics") setTimeout(renderPronostics, 60);
})();
