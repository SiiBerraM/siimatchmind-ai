(function () {
  "use strict";

  var TARGET_HASH = "#/pronostics";
  var removed = Object.create(null);
  var sharedCache = null;
  var sharedPromise = null;
  var expandedKey = null;
  var obs = null;
  var obsTarget = null;
  var renderTimer = null;

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
      "celta|bournemouth": { market: "من سوف يفوز", prediction: { percent: { home: 52, draw: 26, away: 22 }, xg: { home: 1.55, away: 0.92 }, most_likely_score: "1-0", confidence: 74, reason: "تفوق على الأرض" }, date: "26/11", time: "20:00" },
      "marseille|levski": { market: "من سوف يفوز ومجموع أهداف المباراة أكثر من 2", prediction: { percent: { home: 64, draw: 20, away: 16 }, xg: { home: 2.15, away: 0.78 }, most_likely_score: "2-0", confidence: 81, reason: "ضغط هجومي عالٍ" }, date: "26/11", time: "20:00" },
      "olympiacos|milan": { market: "من سوف يفوز في الشوط الأول", prediction: { percent: { home: 34, draw: 35, away: 31 }, xg: { home: 1.12, away: 1.18 }, most_likely_score: "1-1", confidence: 62, reason: "تقارب فني واضح" }, date: "26/11", time: "20:00" },
      "plzen|benfica": { market: "هل كلا الفريقين سيسجل", prediction: { percent: { home: 38, draw: 28, away: 34 }, xg: { home: 1.34, away: 1.42 }, most_likely_score: "1-1", confidence: 69, reason: "معدل تهديف متبادل" }, date: "26/11", time: "20:00" },
      "torreense|celtic": { market: "مجموع الأهداف أكثر من 2", prediction: { percent: { home: 31, draw: 27, away: 42 }, xg: { home: 1.05, away: 1.78 }, most_likely_score: "1-2", confidence: 72, reason: "نجاعة هجومية للضيف" }, date: "26/11", time: "20:00" },
      "palace|sociedad": { market: "من سوف يفوز", prediction: { percent: { home: 49, draw: 27, away: 24 }, xg: { home: 1.48, away: 1.01 }, most_likely_score: "1-0", confidence: 67, reason: "تماسك دفاعي محلي" }, date: "26/11", time: "20:00" }
    }
  };

  function isPronoHash(h) {
    var s = String(h || location.hash || "").toLowerCase();
    return s === TARGET_HASH || s.indexOf("pronostics") !== -1;
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
      ".ps-qr{background:#16a34a;color:#fff;padding:4px 10px;border-radius:6px;font-weight:800;border:none;cursor:pointer}",
      ".ps-row{display:flex;align-items:stretch;justify-content:space-between;background:#f8fafc;border-bottom:2px solid #cbd5e1;cursor:pointer}",
      ".ps-row:nth-child(even){background:#e9eff6}",
      ".ps-left{flex:1;padding:8px 10px;display:flex;flex-direction:column;gap:6px;min-width:0}",
      ".ps-topmeta{display:flex;align-items:center;gap:6px;flex-wrap:wrap}",
      ".ps-mkt{display:inline-block;background:#2a4b91;color:#fff;font-size:11.5px;font-weight:700;padding:3px 10px;border-radius:4px}",
      ".ps-pill{display:inline-block;background:#dbeafe;color:#1e3a8a;font-size:10.5px;font-weight:700;padding:2px 7px;border-radius:4px}",
      ".ps-main{display:flex;align-items:center;gap:8px}",
      ".ps-trash{background:transparent;border:none;color:#dc2626;cursor:pointer;padding:4px;display:inline-flex;align-items:center;justify-content:center;flex:none}",
      ".ps-trash svg{width:20px;height:20px;stroke:currentColor;fill:none;stroke-width:2}",
      ".ps-clubs{display:flex;flex-direction:column;gap:5px;flex:1;min-width:0}",
      ".ps-club{display:flex;align-items:center;gap:7px;font-size:13.5px;font-weight:700;color:#1e293b;text-decoration:none}",
      ".ps-club img{width:20px;height:20px;object-fit:contain;flex:none}",
      ".ps-crest{width:20px;height:20px;border-radius:50%;background:#cbd5e1;color:#0f172a;font-size:9px;font-weight:800;display:inline-flex;align-items:center;justify-content:center;flex:none}",
      ".ps-extra{display:none;font-size:11px;color:#334155;background:#e2e8f0;padding:6px 8px;border-radius:6px;line-height:1.5}",
      ".ps-row.is-open .ps-extra{display:block}",
      ".ps-right{width:136px;flex:none;background:#e2e8f0;border-inline-start:1px solid #cbd5e1;padding:6px 8px;display:flex;flex-direction:column;justify-content:space-between;align-items:center;gap:3px;text-align:center;font-size:11px}",
      ".ps-ft{font-weight:800;font-size:12.5px;color:#0f172a}",
      ".ps-ht{font-size:11px;color:#475569;font-weight:700}",
      ".ps-meta{display:flex;align-items:center;gap:4px;flex-wrap:wrap;justify-content:center}",
      ".ps-code{background:#3b66b8;color:#fff;font-weight:700;font-size:10px;padding:2px 6px;border-radius:3px}",
      ".ps-val{background:#1e3a8a;color:#facc15;font-weight:800;font-size:11px;padding:2px 6px;border-radius:3px}",
      ".ps-dt{font-size:10.5px;color:#334155;font-weight:700}"
    ].join("");
    (document.head || document.documentElement).appendChild(el);
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
      return '<img src="' + esc(logo) + '" alt="" referrerpolicy="no-referrer" onerror="this.outerHTML=\'<span class=ps-crest>' + code + '</span>\'">';
    }
    return '<span class="ps-crest">' + code + '</span>';
  }

  function mergeData(raw) {
    return {
      teams: (raw && Array.isArray(raw.teams) && raw.teams.length) ? raw.teams : fallbackData.teams,
      analyses: (raw && raw.analyses && Object.keys(raw.analyses).length) ? raw.analyses : fallbackData.analyses
    };
  }

  function buildTeamMap(teams) {
    var map = Object.create(null);
    for (var i = 0; i < (teams || []).length; i++) {
      var t = teams[i];
      if (!t) continue;
      if (t.id) map[t.id] = t;
      if (t.name) map[t.name] = t;
    }
    return map;
  }

  function extractInsights(val, ph, pd, pa, ft) {
    var pred = (val && val.prediction) || {};
    var xg = pred.xg || val.xg || {};
    var xgh = xg.home != null ? Number(xg.home).toFixed(2) : (Number(ph) / 36).toFixed(2);
    var xga = xg.away != null ? Number(xg.away).toFixed(2) : (Number(pa) / 36).toFixed(2);
    var score = pred.most_likely_score || val.most_likely_score || ft;
    var maxP = Math.max(Number(ph) || 0, Number(pd) || 0, Number(pa) || 0);
    var conf = pred.confidence != null ? pred.confidence : (val.confidence != null ? val.confidence : Math.min(92, Math.max(50, Math.round(maxP + 12))));
    var reason = pred.reason || val.reason || (Array.isArray(pred.reasons) && pred.reasons[0]) || "تحليل الإحصاءات والنسب";
    return { xgh: xgh, xga: xga, score: score, conf: conf, reason: reason };
  }

  function renderHtml(data) {
    var teams = buildTeamMap(data.teams);
    var entries = Object.entries(data.analyses || {});
    var list = [];
    for (var k = 0; k < entries.length && list.length < 40; k++) {
      if (!removed[entries[k][0]]) list.push(entries[k]);
    }

    if (!list.length) {
      return '<div class="ps-box"><div class="ps-head"><div class="ps-title">اختياراتي</div></div><p style="padding:12px;">لا توجد توقعات متاحة حالياً.</p></div>';
    }

    var mult = 1;
    var rows = list.map(function (pair, i) {
      var key = pair[0], val = pair[1] || {};
      var parts = key.split("|");
      var rH = parts[0] || "", rA = parts[1] || "";
      var tH = teams[rH] || {}, tA = teams[rA] || {};
      var nH = tH.name || rH, nA = tA.name || rA;

      var pct = (val.prediction && val.prediction.percent) || val.percent || {};
      var ph = pct.home != null ? pct.home : (pct.H != null ? pct.H : 40);
      var pd = pct.draw != null ? pct.draw : (pct.D != null ? pct.D : 30);
      var pa = pct.away != null ? pct.away : (pct.A != null ? pct.A : 30);

      var maxP = Math.max(Number(ph) || 1, Number(pd) || 1, Number(pa) || 1);
      var odd = (100 / Math.max(maxP, 15)).toFixed(2);
      if (i < 6) mult *= Number(odd);

      var ft = Number(ph) >= Number(pa) ? "1-0" : "0-1";
      var info = extractInsights(val, ph, pd, pa, ft);
      var code = "4965" + String(480 + i);
      var href = "#/analyze/" + encodeURIComponent(rH) + "/" + encodeURIComponent(rA);
      var openClass = expandedKey === key ? " is-open" : "";

      return (
        '<div class="ps-row' + openClass + '" data-key="' + esc(key) + '">' +
          '<div class="ps-left">' +
            '<div class="ps-topmeta">' +
              '<span class="ps-mkt">' + esc(market(ph, pd, pa, val)) + '</span>' +
              '<span class="ps-pill">ثقة ' + esc(info.conf) + '%</span>' +
              '<span class="ps-pill">xG ' + esc(info.xgh) + ' - ' + esc(info.xga) + '</span>' +
            '</div>' +
            '<div class="ps-main">' +
              '<button type="button" class="ps-trash" title="حذف" aria-label="حذف">' +
                '<svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6"/></svg>' +
              '</button>' +
              '<div class="ps-clubs">' +
                '<a class="ps-club" href="' + href + '">' + crest(tH.logo, nH) + '<span>' + esc(nH) + '</span></a>' +
                '<a class="ps-club" href="' + href + '">' + crest(tA.logo, nA) + '<span>' + esc(nA) + '</span></a>' +
              '</div>' +
            '</div>' +
            '<div class="ps-extra">' +
              'النتيجة المرجحة: <b>' + esc(info.score) + '</b> • السبب: <b>' + esc(info.reason) + '</b>' +
            '</div>' +
          '</div>' +
          '<div class="ps-right">' +
            '<div class="ps-ft">' + esc(ph) + '% - ' + esc(pa) + '% (' + esc(info.score) + ')</div>' +
            '<div class="ps-ht">تعادل ' + esc(pd) + '% • xG ' + esc(info.xgh) + '/' + esc(info.xga) + '</div>' +
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
            '<button type="button" class="ps-qr" id="psRefreshBtn">تحديث</button>' +
          '</div>' +
        '</div>' +
        '<div id="psRows">' + rows + '</div>' +
      '</div>'
    );
  }

  function bindEvents(v) {
    v.querySelectorAll(".ps-trash").forEach(function (btn) {
      btn.onclick = function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        var row = btn.closest(".ps-row");
        if (!row) return;
        var k = row.getAttribute("data-key");
        if (k) removed[k] = true;
        row.remove();
        var rem = v.querySelectorAll(".ps-row").length;
        var el = document.getElementById("psCount");
        if (el) el.textContent = "صفحة 1 • " + rem;
      };
    });

    v.querySelectorAll(".ps-row").forEach(function (row) {
      row.onclick = function (ev) {
        if (ev.target.closest("a") || ev.target.closest(".ps-trash")) return;
        var k = row.getAttribute("data-key");
        var isOpen = row.classList.toggle("is-open");
        expandedKey = isOpen ? k : null;
      };
    });

    var refBtn = document.getElementById("psRefreshBtn");
    if (refBtn) {
      refBtn.onclick = function () {
        fetchData(true).then(function (d) {
          renderToView(d, true);
        });
      };
    }
  }

  function renderToView(data, force) {
    var v = view();
    if (!v || !isPronoHash()) return;
    if (!force && v.getAttribute("data-ps-ready") === "1" && v.querySelector(".ps-box")) return;
    if (obs) obs.disconnect();
    style();
    v.innerHTML = renderHtml(data);
    v.setAttribute("data-ps-ready", "1");
    bindEvents(v);
    attachObserver(v);
  }

  function fetchData(force) {
    if (sharedCache && !force) return Promise.resolve(sharedCache);
    if (sharedPromise && !force) return sharedPromise;

    var url = force ? ("data/static.json?t=" + Date.now()) : "data/static.json";
    sharedPromise = fetch(url)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        sharedCache = mergeData(d);
        sharedPromise = null;
        return sharedCache;
      })
      .catch(function () {
        sharedCache = sharedCache || fallbackData;
        sharedPromise = null;
        return sharedCache;
      });

    return sharedPromise;
  }

  function syncProno() {
    if (!isPronoHash()) return;
    renderToView(sharedCache || fallbackData, false);
    fetchData(false).then(function (d) {
      renderToView(d, !sharedCache);
    });
  }

  function scheduleSync() {
    if (renderTimer) clearTimeout(renderTimer);
    renderTimer = setTimeout(function () {
      renderTimer = null;
      syncProno();
    }, 50);
  }

  function attachObserver(v) {
    if (!window.MutationObserver || !v) return;
    if (obs && obsTarget === v) {
      obs.observe(v, { childList: true });
      return;
    }
    if (obs) obs.disconnect();
    obsTarget = v;
    obs = new MutationObserver(function () {
      if (isPronoHash() && !v.querySelector(".ps-box")) {
        scheduleSync();
      }
    });
    obs.observe(v, { childList: true });
  }

  window.addEventListener("hashchange", scheduleSync);
  window.addEventListener("pageshow", scheduleSync);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", syncProno, { once: true });
  } else {
    syncProno();
  }
})();
