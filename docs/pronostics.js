(function () {
  "use strict";

  var removed = {};
  var cached = null;
  var loading = false;
  var syncScheduled = false;

  var fallbackData = {
    teams: [
      { id: "celta", name: "سيلتا فيغو", logo: "" },
      { id: "bournemouth", name: "بورنموث", logo: "" },
      { id: "marseille", name: "مارسيليا", logo: "" },
      { id: "levski", name: "ليفسكي صوفيا", logo: "" },
      { id: "olympiacos", name: "أولمبياكوس بيرايوس", logo: "" },
      { id: "milan", name: "ميلان", logo: "" },
      { id: "plzen", name: "فيكتوريا بلزن", logo: "" },
      { id: "benfica", name: "بنفيكا", logo: "" },
      { id: "torreense", name: "تورينس SCU", logo: "" },
      { id: "celtic", name: "سلتيك", logo: "" },
      { id: "palace", name: "كريستال بالاس", logo: "" },
      { id: "sociedad", name: "ريال سوسيداد", logo: "" }
    ],
    analyses: {
      "celta|bournemouth": { market: "من سوف يفوز", prediction: { percent: { home: 52, draw: 26, away: 22 } }, date: "26/11", time: "20:00" },
      "marseille|levski": { market: "من سوف يفوز ومجموع أهداف المباراة أكثر من 2", prediction: { percent: { home: 64, draw: 20, away: 16 } }, date: "26/11", time: "20:00" },
      "olympiacos|milan": { market: "من سوف يفوز في الشوط الأول", prediction: { percent: { home: 34, draw: 35, away: 31 } }, date: "26/11", time: "20:00" },
      "plzen|benfica": { market: "هل كلا الفريقين سيسجل", prediction: { percent: { home: 38, draw: 28, away: 34 } }, date: "26/11", time: "20:00" },
      "torreense|celtic": { market: "مجموع الأهداف أكثر من 2", prediction: { percent: { home: 31, draw: 27, away: 42 } }, date: "26/11", time: "20:00" },
      "palace|sociedad": { market: "من سوف يفوز", prediction: { percent: { home: 49, draw: 27, away: 24 } }, date: "26/11", time: "20:00" }
    }
  };

  function isPronoRoute() {
    var h = (location.hash || "").toLowerCase();
    return h === "#/pronostics" || h.indexOf("pronostics") !== -1;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function view() {
    return document.getElementById("view") || document.querySelector("main .view") || document.querySelector("main");
  }

  function style() {
    if (document.getElementById("smm-prono-slip-css")) return;
    var el = document.createElement("style");
    el.id = "smm-prono-slip-css";
    el.textContent = [
      ".ps-box{max-width:720px;margin:0 auto;border-radius:12px;overflow:hidden;border:1px solid rgba(255,255,255,.15);background:#eef2f7;color:#0f172a}",
      ".ps-head{background:#12284e;color:#fff;padding:10px 12px}",
      ".ps-title{text-align:center;font-weight:800;font-size:18px;color:#facc15;margin-bottom:8px}",
      ".ps-subbar{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;font-size:12px}",
      ".ps-tag{background:#1d3f78;border:1px solid #355f9e;padding:4px 9px;border-radius:6px;font-weight:700}",
      ".ps-qr{background:#16a34a;color:#fff;padding:4px 10px;border-radius:6px;font-weight:800}",
      ".ps-row{display:flex;align-items:stretch;justify-content:space-between;background:#f8fafc;border-bottom:2px solid #cbd5e1}",
      ".ps-row:nth-child(even){background:#e9eff6}",
      ".ps-left{flex:1;padding:8px 10px;display:flex;flex-direction:column;gap:6px;min-width:0}",
      ".ps-mkt{display:inline-block;align-self:flex-start;background:#2a4b91;color:#fff;font-size:11.5px;font-weight:700;padding:3px 10px;border-radius:4px}",
      ".ps-main{display:flex;align-items:center;gap:8px}",
      ".ps-trash{background:transparent;border:none;color:#dc2626;cursor:pointer;padding:4px;display:inline-flex;align-items:center;justify-content:center;flex:none}",
      ".ps-trash svg{width:20px;height:20px;stroke:currentColor;fill:none;stroke-width:2}",
      ".ps-clubs{display:flex;flex-direction:column;gap:5px;flex:1;min-width:0}",
      ".ps-club{display:flex;align-items:center;gap:7px;font-size:13.5px;font-weight:700;color:#1e293b;text-decoration:none}",
      ".ps-club img{width:20px;height:20px;object-fit:contain;flex:none}",
      ".ps-crest{width:20px;height:20px;border-radius:50%;background:#cbd5e1;color:#0f172a;font-size:9px;font-weight:800;display:inline-flex;align-items:center;justify-content:center;flex:none}",
      ".ps-right{width:132px;flex:none;background:#e2e8f0;border-inline-start:1px solid #cbd5e1;padding:6px 8px;display:flex;flex-direction:column;justify-content:space-between;align-items:center;gap:3px;text-align:center;font-size:11px}",
      ".ps-ft{font-weight:800;font-size:12.5px;color:#0f172a}",
      ".ps-ht{font-size:11px;color:#475569;font-weight:700}",
      ".ps-meta{display:flex;align-items:center;gap:4px;flex-wrap:wrap;justify-content:center}",
      ".ps-code{background:#3b66b8;color:#fff;font-weight:700;font-size:10px;padding:2px 6px;border-radius:3px}",
      ".ps-val{background:#1e3a8a;color:#facc15;font-weight:800;font-size:11px;padding:2px 6px;border-radius:3px}",
      ".ps-dt{font-size:10.5px;color:#334155;font-weight:700}"
    ].join("");
    document.head.appendChild(el);
  }

  function market(ph, pd, pa, val) {
    if (val && (val.market || val.pick)) return val.market || val.pick;
    var h = Number(ph) || 0, d = Number(pd) || 0, a = Number(pa) || 0;
    if ((h >= 58 || a >= 58) && (h + a) >= 75) return "من سوف يفوز ومجموع أهداف المباراة أكثر من 2";
    if (h >= 48 || a >= 48) return "من سوف يفوز";
    if (d >= 33) return "من سوف يفوز في الشوط الأول";
    if (Math.abs(h - a) <= 12) return "هل كلا الفريقين سيسجل";
    return "مجموع الأهداف أكثر من 2";
  }

  function crest(logo, name) {
    var code = esc((name || "?").slice(0, 2).toUpperCase());
    if (logo) {
      return '<img src="' + esc(logo) + '" alt="" referrerpolicy="no-referrer" loading="lazy" onerror="this.outerHTML=\'<span class=ps-crest>' + code + '</span>\'">';
    }
    return '<span class="ps-crest">' + code + '</span>';
  }

  function mergeData(raw) {
    return {
      teams: (raw && Array.isArray(raw.teams) && raw.teams.length) ? raw.teams : fallbackData.teams,
      analyses: (raw && raw.analyses && Object.keys(raw.analyses).length) ? raw.analyses : fallbackData.analyses
    };
  }

  function renderHtml(data) {
    var teams = {};
    (data.teams || []).forEach(function (t) {
      if (t.id) teams[t.id] = t;
      if (t.name) teams[t.name] = t;
    });

    var list = Object.entries(data.analyses || {}).filter(function (p) {
      return !removed[p[0]];
    }).slice(0, 40);

    if (!list.length) {
      return '<div class="ps-box"><div class="ps-head"><div class="ps-title">اختياراتي</div></div><p style="padding:12px;">Aucun pronostic disponible.</p></div>';
    }

    var mult = 1;
    var rows = list.map(function (pair, i) {
      var key = pair[0], val = pair[1] || {};
      var parts = key.split("|");
      var rH = parts[0] || "", rA = parts[1] || "";
      var tH = teams[rH] || {}, tA = teams[rA] || {};
      var nH = tH.name || rH, nA = tA.name || rA;

      var pct = (val.prediction && val.prediction.percent) || {};
      var ph = pct.home != null ? pct.home : (pct.H != null ? pct.H : 40);
      var pd = pct.draw != null ? pct.draw : (pct.D != null ? pct.D : 30);
      var pa = pct.away != null ? pct.away : (pct.A != null ? pct.A : 30);

      var maxP = Math.max(Number(ph) || 1, Number(pd) || 1, Number(pa) || 1);
      var odd = (100 / Math.max(maxP, 15)).toFixed(2);
      if (i < 6) mult *= Number(odd);

      var ft = Number(ph) >= Number(pa) ? "1-0" : "0-1";
      var code = "4965" + String(480 + i);
      var href = "#/analyze/" + encodeURIComponent(rH) + "/" + encodeURIComponent(rA);

      return (
        '<div class="ps-row" data-key="' + esc(key) + '">' +
          '<div class="ps-left">' +
            '<span class="ps-mkt">' + esc(market(ph, pd, pa, val)) + '</span>' +
            '<div class="ps-main">' +
              '<button type="button" class="ps-trash" title="Supprimer" aria-label="Supprimer">' +
                '<svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6"/></svg>' +
              '</button>' +
              '<div class="ps-clubs">' +
                '<a class="ps-club" href="' + href + '">' + crest(tH.logo, nH) + '<span>' + esc(nH) + '</span></a>' +
                '<a class="ps-club" href="' + href + '">' + crest(tA.logo, nA) + '<span>' + esc(nA) + '</span></a>' +
              '</div>' +
            '</div>' +
          '</div>' +
          '<div class="ps-right">' +
            '<div class="ps-ft">' + esc(ph) + '% - ' + esc(pa) + '% (' + ft + ')</div>' +
            '<div class="ps-ht">(' + ft + ') • Nul ' + esc(pd) + '%</div>' +
            '<div class="ps-meta">' +
              '<span class="ps-code">' + code + '</span>' +
              '<span class="ps-val">' + odd + '</span>' +
            '</div>' +
            '<div class="ps-dt">' + esc(val.date || "26/11") + ' • ' + esc(val.time || "20:00") + '</div>' +
          '</div>' +
        '</div>'
      );
    }).join("");

    return (
      '<div class="ps-box">' +
        '<div class="ps-head">' +
          '<div class="ps-title">اختياراتي</div>' +
          '<div class="ps-subbar">' +
            '<span class="ps-tag" id="psCount">صفحة 1 • ' + list.length + '</span>' +
            '<span class="ps-tag">المجموع: ' + mult.toFixed(2) + '</span>' +
            '<span class="ps-qr">QR Code</span>' +
          '</div>' +
        '</div>' +
        '<div id="psRows">' + rows + '</div>' +
      '</div>'
    );
  }

  function applyDom(v, data) {
    style();
    v.innerHTML = renderHtml(data);
    v.querySelectorAll(".ps-trash").forEach(function (btn) {
      btn.onclick = function (ev) {
        ev.preventDefault();
        var row = btn.closest(".ps-row");
        if (row) {
          var k = row.getAttribute("data-key");
          if (k) removed[k] = true;
          row.remove();
        }
        var rem = v.querySelectorAll(".ps-row").length;
        var el = document.getElementById("psCount");
        if (el) el.textContent = "صفحة 1 • " + rem;
      };
    });
  }

  function ensureView() {
    if (!isPronoRoute()) return;
    var v = view();
    if (!v || v.querySelector("#psRows")) return;
    if (cached) {
      applyDom(v, cached);
      return;
    }
    applyDom(v, fallbackData);
    if (loading) return;
    loading = true;
    fetch("data/static.json", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        cached = mergeData(d);
        var cur = view();
        if (isPronoRoute() && cur) {
          applyDom(cur, cached);
        }
      })
      .catch(function () {
        cached = fallbackData;
      })
      .finally(function () { loading = false; });
  }

  function scheduleEnsure() {
    if (syncScheduled) return;
    syncScheduled = true;
    requestAnimationFrame(function () {
      syncScheduled = false;
      ensureView();
    });
  }

  function observe() {
    if (!window.MutationObserver || !document.body) return;
    new MutationObserver(function () {
      if (isPronoRoute()) {
        var v = view();
        if (v && !v.querySelector("#psRows")) {
          scheduleEnsure();
        }
      }
    }).observe(document.body, { childList: true, subtree: true });
  }

  window.addEventListener("hashchange", scheduleEnsure);
  window.addEventListener("load", function () {
    observe();
    scheduleEnsure();
  });
  setInterval(function () {
    if (isPronoRoute()) {
      var v = view();
      if (v && !v.querySelector("#psRows")) ensureView();
    }
  }, 200);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      observe();
      scheduleEnsure();
    });
  } else {
    observe();
    scheduleEnsure();
  }
})();
