(function () {
  "use strict";

  var TARGET_HASH = "#/pronostics";
  var removed = Object.create(null);
  var staticCache = null;
  var ledgerCache = null;
  var loadPromise = null;
  var selectedLeague = "ALL";
  var expandedKey = null;
  var obs = null;
  var obsTarget = null;
  var renderTimer = null;

  var leagueLabels = {
    BSA: "الدوري البرازيلي (BSA)",
    BL1: "الدوري الألماني (BL1)",
    FL1: "الدوري الفرنسي (FL1)",
    PD: "الدوري الإسباني (PD)",
    PL: "الدوري الإنجليزي (PL)",
    ELC: "دوري البطولة الإنجليزية (ELC)",
    DED: "الدوري الهولندي (DED)",
    SA: "الدوري الإيطالي (SA)",
    PPL: "الدوري البرتغالي (PPL)",
    CL: "دوري أبطال أوروبا (CL)"
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
      ".ps-box{max-width:860px;margin:0 auto;border-radius:12px;overflow:hidden;border:1px solid rgba(255,255,255,.15);background:#eef2f7;color:#0f172a}",
      ".ps-head{background:#12284e;color:#fff;padding:12px}",
      ".ps-title{text-align:center;font-weight:800;font-size:18px;color:#facc15;margin-bottom:8px}",
      ".ps-subbar{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;font-size:11.5px}",
      ".ps-tag{background:#1d3f78;border:1px solid #355f9e;padding:4px 9px;border-radius:6px;font-weight:700}",
      ".ps-qr{background:#16a34a;color:#fff;padding:5px 11px;border-radius:6px;font-weight:800;border:none;cursor:pointer}",
      ".ps-filters{display:flex;gap:6px;flex-wrap:wrap;padding:10px 12px;background:#dce5f0;border-bottom:1px solid #cbd5e1}",
      ".ps-fbtn{border:1px solid #94a3b8;background:#fff;color:#0f172a;padding:4px 10px;border-radius:999px;font-size:11px;font-weight:700;cursor:pointer}",
      ".ps-fbtn.is-active{background:#12284e;color:#facc15;border-color:#12284e}",
      ".ps-league-sec{margin-bottom:6px}",
      ".ps-league-hd{display:flex;align-items:center;justify-content:space-between;background:#1e3a6d;color:#fff;padding:7px 12px;font-size:12.5px;font-weight:800}",
      ".ps-league-cnt{background:#facc15;color:#0f172a;padding:1px 8px;border-radius:999px;font-size:11px}",
      ".ps-row{display:flex;align-items:stretch;justify-content:space-between;background:#f8fafc;border-bottom:1px solid #cbd5e1;cursor:pointer}",
      ".ps-row:nth-child(even){background:#eef3f9}",
      ".ps-left{flex:1;padding:8px 10px;display:flex;flex-direction:column;gap:6px;min-width:0}",
      ".ps-topmeta{display:flex;align-items:center;gap:6px;flex-wrap:wrap}",
      ".ps-mkt{display:inline-block;background:#2a4b91;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px}",
      ".ps-pill{display:inline-block;background:#dbeafe;color:#1e3a8a;font-size:10.5px;font-weight:700;padding:2px 7px;border-radius:4px}",
      ".ps-res-ok{background:#dcfce7;color:#166534}",
      ".ps-res-no{background:#fee2e2;color:#991b1b}",
      ".ps-res-ip{background:#fef9c3;color:#854d0e}",
      ".ps-main{display:flex;align-items:center;gap:8px}",
      ".ps-trash{background:transparent;border:none;color:#dc2626;cursor:pointer;padding:4px;display:inline-flex;align-items:center;justify-content:center;flex:none}",
      ".ps-trash svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:2}",
      ".ps-clubs{display:flex;flex-direction:column;gap:4px;flex:1;min-width:0}",
      ".ps-club{display:flex;align-items:center;gap:7px;font-size:13px;font-weight:700;color:#1e293b;text-decoration:none}",
      ".ps-club img{width:18px;height:18px;object-fit:contain;flex:none}",
      ".ps-crest{width:18px;height:18px;border-radius:50%;background:#cbd5e1;color:#0f172a;font-size:8.5px;font-weight:800;display:inline-flex;align-items:center;justify-content:center;flex:none}",
      ".ps-extra{display:none;font-size:11px;color:#334155;background:#e2e8f0;padding:6px 8px;border-radius:6px;line-height:1.6}",
      ".ps-row.is-open .ps-extra{display:block}",
      ".ps-right{width:168px;flex:none;background:#e2e8f0;border-inline-start:1px solid #cbd5e1;padding:6px 8px;display:flex;flex-direction:column;justify-content:space-between;align-items:center;gap:3px;text-align:center;font-size:10.5px}",
      ".ps-ft{font-weight:800;font-size:11.5px;color:#0f172a}",
      ".ps-ht{font-size:10.5px;color:#475569;font-weight:700}",
      ".ps-meta{display:flex;align-items:center;gap:4px;flex-wrap:wrap;justify-content:center}",
      ".ps-code{background:#3b66b8;color:#fff;font-weight:700;font-size:10px;padding:2px 6px;border-radius:3px}",
      ".ps-val{background:#1e3a8a;color:#facc15;font-weight:800;font-size:10.5px;padding:2px 6px;border-radius:3px}",
      ".ps-dt{font-size:10px;color:#334155;font-weight:700}"
    ].join("");
    (document.head || document.documentElement).appendChild(el);
  }

  function leagueName(code) {
    var c = String(code || "OTHER");
    return leagueLabels[c] || ("دوري " + c);
  }

  function crest(logo, name) {
    var code = esc((name || "?").slice(0, 2).toUpperCase());
    if (logo) {
      return '<img src="' + esc(logo) + '" alt="" referrerpolicy="no-referrer" onerror="this.outerHTML=\'<span class=ps-crest>' + code + '</span>\'">';
    }
    return '<span class="ps-crest">' + code + '</span>';
  }

  function buildTeamMap(staticObj) {
    var map = Object.create(null);
    var teams = (staticObj && Array.isArray(staticObj.teams)) ? staticObj.teams : [];
    for (var i = 0; i < teams.length; i++) {
      var t = teams[i];
      if (!t) continue;
      if (t.id) map[t.id] = t;
      if (t.name) map[t.name] = t;
    }
    return map;
  }

  function pctArr(arr) {
    if (!Array.isArray(arr) || arr.length < 3) return [0, 0, 0];
    return [
      Math.round((Number(arr[0]) || 0) * 100),
      Math.round((Number(arr[1]) || 0) * 100),
      Math.round((Number(arr[2]) || 0) * 100)
    ];
  }

  function pickIdx(arr) {
    if (!Array.isArray(arr) || arr.length < 3) return 0;
    var best = 0;
    for (var i = 1; i < 3; i++) {
      if ((Number(arr[i]) || 0) > (Number(arr[best]) || 0)) best = i;
    }
    return best;
  }

  function labelOutcome(idx, nH, nA) {
    if (idx === 0) return "فوز " + nH;
    if (idx === 1) return "تعادل";
    return "فوز " + nA;
  }

  function collectItems(staticObj, ledgerObj) {
    var teamMap = buildTeamMap(staticObj);
    var items = [];
    var seen = Object.create(null);
    var preds = (ledgerObj && ledgerObj.predictions) || {};

    Object.keys(preds).forEach(function (id) {
      var p = preds[id] || {};
      var key = id + "|" + (p.home || "") + "|" + (p.away || "");
      if (removed[key]) return;
      seen[(p.home || "") + "|" + (p.away || "")] = true;

      var tH = teamMap[p.home] || {};
      var tA = teamMap[p.away] || {};
      var nH = tH.name || p.home || "فريق 1";
      var nA = tA.name || p.away || "فريق 2";
      var fin = Array.isArray(p.final) ? p.final : (Array.isArray(p.model) ? p.model : [0.34, 0.33, 0.33]);
      var mod = Array.isArray(p.model) ? p.model : fin;
      var finPct = pctArr(fin);
      var modPct = pctArr(mod);
      var bestIdx = pickIdx(fin);
      var maxProb = Math.max(Number(fin[bestIdx]) || 0.25, 0.15);
      var odd = (1 / maxProb).toFixed(2);
      var res = p.result || null;
      var statusBadge = '<span class="ps-pill ps-res-ip">قيد الانتظار</span>';
      var resText = "لم تُسجل نتيجة بعد";

      if (res && res.hg != null && res.ag != null) {
        var isHit = Number(res.outcome) === bestIdx;
        resText = "النتيجة: " + res.hg + " - " + res.ag + " • الفائز الفعلي: " + labelOutcome(Number(res.outcome), nH, nA);
        statusBadge = isHit
          ? '<span class="ps-pill ps-res-ok">✓ إصابة (' + esc(res.hg) + '-' + esc(res.ag) + ')</span>'
          : '<span class="ps-pill ps-res-no">✕ خطأ (' + esc(res.hg) + '-' + esc(res.ag) + ')</span>';
      }

      items.push({
        key: key,
        id: id,
        league: p.league || "OTHER",
        rH: p.home || "",
        rA: p.away || "",
        nH: nH,
        nA: nA,
        logoH: tH.logo || "",
        logoA: tA.logo || "",
        date: p.date || "-",
        loggedAt: p.logged_at || "",
        statusAtLog: p.status_at_log || "",
        finPct: finPct,
        modPct: modPct,
        marketText: labelOutcome(bestIdx, nH, nA),
        odd: odd,
        statusBadge: statusBadge,
        resText: resText,
        hasMarketBlend: Array.isArray(p.market)
      });
    });

    var analyses = (staticObj && staticObj.analyses) || {};
    Object.keys(analyses).forEach(function (k) {
      if (seen[k]) return;
      var parts = k.split("|");
      var rH = parts[0] || "", rA = parts[1] || "";
      var itemKey = "st|" + k;
      if (removed[itemKey]) return;
      var val = analyses[k] || {};
      var tH = teamMap[rH] || {}, tA = teamMap[rA] || {};
      var nH = tH.name || rH, nA = tA.name || rA;
      var pct = (val.prediction && val.prediction.percent) || val.percent || {};
      var ph = Number(pct.home != null ? pct.home : (pct.H != null ? pct.H : 40)) || 0;
      var pd = Number(pct.draw != null ? pct.draw : (pct.D != null ? pct.D : 30)) || 0;
      var pa = Number(pct.away != null ? pct.away : (pct.A != null ? pct.A : 30)) || 0;
      var bestIdx = pickIdx([ph / 100, pd / 100, pa / 100]);
      var maxP = Math.max(ph, pd, pa, 15);

      items.push({
        key: itemKey,
        id: k,
        league: val.league || "STATIC",
        rH: rH,
        rA: rA,
        nH: nH,
        nA: nA,
        logoH: tH.logo || "",
        logoA: tA.logo || "",
        date: val.date || "26/11",
        loggedAt: val.time || "20:00",
        statusAtLog: "static",
        finPct: [Math.round(ph), Math.round(pd), Math.round(pa)],
        modPct: [Math.round(ph), Math.round(pd), Math.round(pa)],
        marketText: val.market || val.pick || labelOutcome(bestIdx, nH, nA),
        odd: (100 / maxP).toFixed(2),
        statusBadge: '<span class="ps-pill ps-res-ip">تحليل ثابت</span>',
        resText: "مصدر البيانات: static.json",
        hasMarketBlend: false
      });
    });

    items.sort(function (a, b) {
      return String(b.date || "").localeCompare(String(a.date || "")) || String(b.id).localeCompare(String(a.id));
    });

    return items;
  }

  function renderHtml(staticObj, ledgerObj) {
    var allItems = collectItems(staticObj, ledgerObj);
    var leagueCounts = Object.create(null);
    allItems.forEach(function (it) {
      leagueCounts[it.league] = (leagueCounts[it.league] || 0) + 1;
    });

    var leagues = Object.keys(leagueCounts).sort(function (a, b) {
      return leagueCounts[b] - leagueCounts[a];
    });

    if (selectedLeague !== "ALL" && !leagueCounts[selectedLeague]) {
      selectedLeague = "ALL";
    }

    var filtered = selectedLeague === "ALL"
      ? allItems
      : allItems.filter(function (it) { return it.league === selectedLeague; });

    var grouped = Object.create(null);
    filtered.forEach(function (it) {
      if (!grouped[it.league]) grouped[it.league] = [];
      grouped[it.league].push(it);
    });

    var activeLeagues = Object.keys(grouped);
    var sum = (ledgerObj && ledgerObj.summary) || {};
    var accPct = (sum.final_all && sum.final_all.accuracy != null)
      ? (Number(sum.final_all.accuracy) * 100).toFixed(1) + "%"
      : "-";

    var filterButtons = [
      '<button type="button" class="ps-fbtn' + (selectedLeague === "ALL" ? " is-active" : "") + '" data-league="ALL">الكل (' + allItems.length + ')</button>'
    ].concat(leagues.map(function (lg) {
      var act = selectedLeague === lg ? " is-active" : "";
      return '<button type="button" class="ps-fbtn' + act + '" data-league="' + esc(lg) + '">' + esc(leagueName(lg)) + ' (' + leagueCounts[lg] + ')</button>';
    })).join("");

    var sectionsHtml = activeLeagues.map(function (lg) {
      var rowsHtml = grouped[lg].map(function (it, idx) {
        var href = "#/analyze/" + encodeURIComponent(it.rH) + "/" + encodeURIComponent(it.rA);
        var openClass = expandedKey === it.key ? " is-open" : "";
        var code = "4965" + String(480 + idx);
        return (
          '<div class="ps-row' + openClass + '" data-key="' + esc(it.key) + '">' +
            '<div class="ps-left">' +
              '<div class="ps-topmeta">' +
                '<span class="ps-mkt">' + esc(it.marketText) + '</span>' +
                it.statusBadge +
                (it.hasMarketBlend ? '<span class="ps-pill">دمج السوق</span>' : '') +
              '</div>' +
              '<div class="ps-main">' +
                '<button type="button" class="ps-trash" title="إخفاء" aria-label="إخفاء">' +
                  '<svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6"/></svg>' +
                '</button>' +
                '<div class="ps-clubs">' +
                  '<a class="ps-club" href="' + href + '">' + crest(it.logoH, it.nH) + '<span>' + esc(it.nH) + '</span></a>' +
                  '<a class="ps-club" href="' + href + '">' + crest(it.logoA, it.nA) + '<span>' + esc(it.nA) + '</span></a>' +
                '</div>' +
              '</div>' +
              '<div class="ps-extra">' +
                '<div><b>' + esc(it.resText) + '</b></div>' +
                '<div>النموذج (Model): ' + esc(it.nH) + ' ' + it.modPct[0] + '% • تعادل ' + it.modPct[1] + '% • ' + esc(it.nA) + ' ' + it.modPct[2] + '%</div>' +
                '<div>المعرف: <code>' + esc(it.id) + '</code> • التسجيل: ' + esc(it.loggedAt || "-") + '</div>' +
              '</div>' +
            '</div>' +
            '<div class="ps-right">' +
              '<div class="ps-ft">' + it.finPct[0] + '% - ' + it.finPct[1] + '% - ' + it.finPct[2] + '%</div>' +
              '<div class="ps-ht">Final (1 - X - 2)</div>' +
              '<div class="ps-meta">' +
                '<span class="ps-code">' + code + '</span>' +
                '<span class="ps-val">' + it.odd + '</span>' +
              '</div>' +
              '<div class="ps-dt">' + esc(it.date) + '</div>' +
            '</div>' +
          '</div>'
        );
      }).join("");

      return (
        '<div class="ps-league-sec">' +
          '<div class="ps-league-hd">' +
            '<span>' + esc(leagueName(lg)) + '</span>' +
            '<span class="ps-league-cnt">' + grouped[lg].length + ' مباراة</span>' +
          '</div>' +
          rowsHtml +
        '</div>'
      );
    }).join("");

    return (
      '<div class="ps-box">' +
        '<div class="ps-head">' +
          '<div class="ps-title">سجل التوقعات والدوريات</div>' +
          '<div class="ps-subbar">' +
            '<span class="ps-tag" id="psCount">المعروض: ' + filtered.length + '</span>' +
            '<span class="ps-tag">الدوريات: ' + leagues.length + '</span>' +
            '<span class="ps-tag">مسجل: ' + esc(sum.logged != null ? sum.logged : allItems.length) + ' | محسم: ' + esc(sum.settled != null ? sum.settled : "-") + '</span>' +
            '<span class="ps-tag">الدقة: ' + esc(accPct) + '</span>' +
            '<button type="button" class="ps-qr" id="psRefreshBtn">تحديث</button>' +
          '</div>' +
        '</div>' +
        '<div class="ps-filters">' + filterButtons + '</div>' +
        '<div id="psRows">' + (sectionsHtml || '<p style="padding:12px;">لا توجد مباريات مطابقة.</p>') + '</div>' +
      '</div>'
    );
  }

  function bindEvents(v) {
    v.querySelectorAll(".ps-fbtn").forEach(function (btn) {
      btn.onclick = function () {
        selectedLeague = btn.getAttribute("data-league") || "ALL";
        renderToView(staticCache, ledgerCache, true);
      };
    });

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
        if (el) el.textContent = "المعروض: " + rem;
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
        fetchAll(true).then(function (pair) {
          renderToView(pair[0], pair[1], true);
        });
      };
    }
  }

  function renderToView(sObj, lObj, force) {
    var v = view();
    if (!v || !isPronoHash()) return;
    if (!force && v.getAttribute("data-ps-ready") === "1" && v.querySelector(".ps-box")) return;
    if (obs) obs.disconnect();
    style();
    v.innerHTML = renderHtml(sObj, lObj);
    v.setAttribute("data-ps-ready", "1");
    bindEvents(v);
    attachObserver(v);
  }

  function fetchJson(path, force) {
    var url = force ? (path + "?t=" + Date.now()) : path;
    return fetch(url).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }

  function fetchAll(force) {
    if (staticCache && ledgerCache && !force) {
      return Promise.resolve([staticCache, ledgerCache]);
    }
    if (loadPromise && !force) return loadPromise;

    loadPromise = Promise.all([
      fetchJson("data/static.json", force),
      fetchJson("data/ledger.json", force)
    ]).then(function (res) {
      staticCache = res[0] || staticCache || { teams: [], analyses: {} };
      ledgerCache = res[1] || ledgerCache || { predictions: {}, summary: {} };
      loadPromise = null;
      return [staticCache, ledgerCache];
    });

    return loadPromise;
  }

  function syncProno() {
    if (!isPronoHash()) return;
    renderToView(staticCache, ledgerCache, false);
    fetchAll(false).then(function (pair) {
      renderToView(pair[0], pair[1], true);
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
