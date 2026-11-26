/* SiiMatchMind — صفحة «مباريات اليوم» (#/today) لكل البطولات + رسالة تهنئة الفريق الفائز. */
(function () {
  "use strict";
  var D = {
    ar: { title: "المباريات حسب اليوم", d: ["أمس", "اليوم", "غدًا", "بعد غد"], none: "لا توجد مباريات في هذا اليوم ضمن البطولات المتاحة.", loading: "…", total: "مباراة", cg: "تهنئة من Berra 👑 P.F.I 👑 إلى {team} وجماهيره بهذا الفوز! 🎉", round: "الجولة {n}", vs: "ضد" },
    en: { title: "Matches by day", d: ["Yesterday", "Today", "Tomorrow", "Day after"], none: "No matches on this day in the available competitions.", loading: "…", total: "matches", cg: "Congratulations from Berra 👑 P.F.I 👑 to {team} and its fans on the win! 🎉", round: "Round {n}", vs: "vs" },
    fr: { title: "Matchs par jour", d: ["Hier", "Aujourd’hui", "Demain", "Après-demain"], none: "Aucun match ce jour-là dans les compétitions disponibles.", loading: "…", total: "matchs", cg: "Félicitations de Berra 👑 P.F.I 👑 à {team} et à ses supporters pour cette victoire ! 🎉", round: "Journée {n}", vs: "vs" },
    es: { title: "Partidos por día", d: ["Ayer", "Hoy", "Mañana", "Pasado mañana"], none: "No hay partidos ese día en las competiciones disponibles.", loading: "…", total: "partidos", cg: "¡Felicitaciones de Berra 👑 P.F.I 👑 a {team} y a su afición por la victoria! 🎉", round: "Jornada {n}", vs: "vs" },
    tr: { title: "Güne göre maçlar", d: ["Dün", "Bugün", "Yarın", "Öbür gün"], none: "Mevcut organizasyonlarda bu gün maç yok.", loading: "…", total: "maç", cg: "Berra 👑 P.F.I 👑 {team} ve taraftarlarını bu galibiyetten dolayı tebrik eder! 🎉", round: "{n}. hafta", vs: "vs" }
  };
  var CSS = ".cg{margin:10px 0 14px;padding:10px 14px;border-radius:14px;border:1px solid #b8862b;background:linear-gradient(135deg,#140f03,#2b200a);color:#f3d27a;font-size:13.5px;line-height:1.7;text-align:center;box-shadow:0 6px 18px rgba(0,0,0,.3)}" +
    ".cg b{color:#fff3c4}.td-tabs{display:flex;gap:6px;margin:12px 0}.td-tabs button{flex:1;padding:9px 4px;border-radius:99px;border:1px solid var(--line);background:var(--deep);color:var(--white);font-weight:600;cursor:pointer;font-size:13px}.td-tabs button.on{background:var(--green);color:#042;border-color:var(--green)}" +
    ".td-lg{display:flex;justify-content:space-between;align-items:baseline;margin:18px 0 4px;font-size:15px;font-weight:700}.td-lg small{color:var(--mute);font-weight:400}.td-m .cg{margin:6px 0 10px;font-size:12.5px;padding:7px 10px}";
  var injected = false, cache = null, locales = {};
  function lang() { var l = "ar"; try { l = localStorage.getItem("smm.lang") || document.documentElement.lang || "ar"; } catch (e) { } return D[l] ? l : "ar"; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function ymd(off) { var d = new Date(); d.setDate(d.getDate() + off); return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2); }
  function winner(m) {
    if (!m || m.status !== "played" || typeof m.hg !== "number" || typeof m.ag !== "number" || m.hg === m.ag) return "";
    return m.hg > m.ag ? (m.home_name || (m.home && m.home.name) || "") : (m.away_name || (m.away && m.away.name) || "");
  }
  function congrats(team) { return team ? '<div class="cg">' + D[lang()].cg.replace("{team}", "<b>" + esc(team) + "</b>") + "</div>" : ""; }
  window.smmCongratsText = function (m) { return winner(m); };
  // صفحة التحليل: r.match و r.home.name و r.away.name
  window.smmCongrats = function (r) {
    try {
      var mt = r && r.match; if (!mt || mt.status !== "played" || mt.hg === mt.ag) return "";
      return congrats(mt.hg > mt.ag ? r.home.name : r.away.name);
    } catch (e) { return ""; }
  };
  function crest(name, logo) {
    var ini = String(name || "?").trim().slice(0, 2).toUpperCase();
    return logo ? '<img class="crest" src="' + esc(logo) + '" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="window.__smmPh&&__smmPh(this)" data-n="' + esc(name) + '">' : '<span class="crest ph">' + esc(ini) + "</span>";
  }
  function card(m, T) {
    var played = m.status === "played";
    var mid = played ? m.hg + " - " + m.ag : (m.time ? esc(m.time) : T.vs);
    var w = winner(m);
    return '<div class="td-m"><a class="match" href="#/analyze/' + esc(m.home) + "/" + esc(m.away) + "/" + esc(m.id) + '">' +
      '<div class="meta"><span>' + esc(m.date || "") + "</span><span>" + (m.round ? T.round.replace("{n}", m.round) : "") + "</span></div>" +
      '<div class="row"><div class="tn">' + crest(m.home_name, m.home_logo) + "<span>" + esc(m.home_name) + '</span></div><div class="vs ' + (played ? "" : "pending") + '">' + mid + '</div><div class="tn">' + crest(m.away_name, m.away_logo) + "<span>" + esc(m.away_name) + "</span></div></div></a>" + congrats(w) + "</div>";
  }
  async function data() {
    if (!cache) { try { cache = await (await fetch("data/static.json")).json(); } catch (e) { cache = {}; } }
    var lg = lang();
    if (!locales[lg]) { try { locales[lg] = await (await fetch("locales/" + lg + ".json")).json(); } catch (e) { locales[lg] = {}; } }
    return { d: cache, loc: locales[lg] };
  }
  function build(d, day) {
    var by = d.matches_by_league || {}, names = {}, out = [];
    (d.leagues || []).forEach(function (l) { names[l.code] = l.name; });
    Object.keys(by).forEach(function (code) {
      var seen = {}, list = [];
      ["today", "upcoming", "results"].forEach(function (k) { (by[code][k] || []).forEach(function (m) { if (m.date === day && !seen[m.id]) { seen[m.id] = 1; list.push(m); } }); });
      if (list.length) { list.sort(function (a, b) { return String(a.time || "").localeCompare(String(b.time || "")); }); out.push({ code: code, list: list }); }
    });
    return { groups: out, names: names };
  }
  window.smmToday = async function (view, off) {
    off = typeof off === "number" ? off : 1;
    var T = D[lang()];
    if (!injected) { var s = document.createElement("style"); s.textContent = CSS; document.head.appendChild(s); injected = true; }
    view.innerHTML = "<h1>" + T.title + '</h1><p class="muted">' + T.loading + "</p>";
    var x = await data(), day = ymd(off - 1), b = build(x.d, day), n = 0;
    var h = "<h1>" + T.title + '</h1><div class="td-tabs">' + T.d.map(function (t, i) { return '<button data-o="' + i + '" class="' + (i === off ? "on" : "") + '">' + esc(t) + "</button>"; }).join("") + "</div>";
    if (!b.groups.length) h += '<p class="empty">' + T.none + "</p>";
    b.groups.sort(function (a, c) { return (x.loc["league." + a.code] || b.names[a.code] || a.code).localeCompare(x.loc["league." + c.code] || b.names[c.code] || c.code); });
    b.groups.forEach(function (g) {
      n += g.list.length;
      h += '<div class="td-lg"><span>' + esc(x.loc["league." + g.code] || b.names[g.code] || g.code) + "</span><small>" + g.list.length + "</small></div>" + g.list.map(function (m) { return card(m, T); }).join("");
    });
    view.innerHTML = h;
    view.querySelectorAll(".td-tabs button").forEach(function (bt) { bt.onclick = function () { window.smmToday(view, parseInt(bt.getAttribute("data-o"), 10)); }; });
  };
  if (location.hash === "#/today") window.dispatchEvent(new Event("hashchange"));
})();
