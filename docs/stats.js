/* SiiMatchMind — صفحة «أخبار وأرقام» (#/news). تُستدعى من app.js عبر window.smmNews */
(function () {
  "use strict";
  var D = {
    ar: { title: "أخبار وأرقام", sub: "أرقام من نتائج البطولة المختارة", played: "مباريات", goals: "أهداف", avg: "معدل الأهداف", home: "فوز المضيف", draw: "تعادل", away: "فوز الضيف", biggest: "أكبر انتصار", most: "أكثر مباراة أهدافًا", attack: "الأقوى هجومًا", defense: "الأقوى دفاعًا", last: "آخر النتائج", news: "آخر أخبار كرة القدم", all: "كل الأخبار", empty: "لا توجد نتائج كافية بعد.", gpm: "هدف/مباراة", note: "الأرقام محسوبة من نتائج المباريات المخزّنة في التطبيق." },
    en: { title: "News & Stats", sub: "Numbers from the selected league's results", played: "Matches", goals: "Goals", avg: "Goals per match", home: "Home wins", draw: "Draws", away: "Away wins", biggest: "Biggest win", most: "Highest-scoring match", attack: "Best attack", defense: "Best defence", last: "Latest results", news: "Latest football news", all: "All news", empty: "Not enough results yet.", gpm: "goals/match", note: "Figures are computed from the match results stored in the app." },
    fr: { title: "Actus & chiffres", sub: "Chiffres issus des résultats du championnat choisi", played: "Matchs", goals: "Buts", avg: "Buts par match", home: "Victoires domicile", draw: "Nuls", away: "Victoires extérieur", biggest: "Plus large victoire", most: "Match le plus prolifique", attack: "Meilleure attaque", defense: "Meilleure défense", last: "Derniers résultats", news: "Dernières actus football", all: "Toutes les actus", empty: "Pas encore assez de résultats.", gpm: "buts/match", note: "Chiffres calculés à partir des résultats enregistrés dans l’app." },
    es: { title: "Noticias y cifras", sub: "Cifras de los resultados de la liga elegida", played: "Partidos", goals: "Goles", avg: "Goles por partido", home: "Victorias local", draw: "Empates", away: "Victorias visitante", biggest: "Mayor victoria", most: "Partido con más goles", attack: "Mejor ataque", defense: "Mejor defensa", last: "Últimos resultados", news: "Últimas noticias de fútbol", all: "Todas las noticias", empty: "Aún no hay suficientes resultados.", gpm: "goles/partido", note: "Cifras calculadas con los resultados guardados en la app." },
    tr: { title: "Haber ve rakamlar", sub: "Seçili ligin sonuçlarından rakamlar", played: "Maç", goals: "Gol", avg: "Maç başına gol", home: "Ev sahibi galibiyeti", draw: "Beraberlik", away: "Deplasman galibiyeti", biggest: "En büyük galibiyet", most: "En çok gollü maç", attack: "En iyi hücum", defense: "En iyi savunma", last: "Son sonuçlar", news: "Son futbol haberleri", all: "Tüm haberler", empty: "Henüz yeterli sonuç yok.", gpm: "gol/maç", note: "Rakamlar uygulamada kayıtlı maç sonuçlarından hesaplanır." }
  };
  var CSS = [
    ".st-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:14px 0}",
    ".st-c{background:var(--deep);border:1px solid var(--line);border-radius:var(--r-md);padding:12px 8px;text-align:center}",
    ".st-c b{display:block;font-size:22px;color:var(--green);line-height:1.3}",
    ".st-c span{font-size:12px;color:var(--mute)}",
    ".st-bar{display:flex;height:10px;border-radius:99px;overflow:hidden;margin:8px 0 4px;background:var(--panel)}",
    ".st-bar i{display:block;height:100%}",
    ".st-lg{display:flex;justify-content:space-between;font-size:12px;color:var(--mute)}",
    ".st-row{display:flex;align-items:center;gap:10px;padding:10px 12px;margin:6px 0;background:var(--deep);border:1px solid var(--line);border-radius:var(--r-md)}",
    ".st-row img,.st-row .ph{width:26px;height:26px;object-fit:contain;flex:none}",
    ".st-row .ph{display:inline-flex;align-items:center;justify-content:center;border-radius:50%;background:var(--panel);font-size:10px}",
    ".st-row .n{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}",
    ".st-row .v{font-weight:700;color:var(--green);white-space:nowrap}",
    ".st-sc{direction:ltr;font-weight:700;white-space:nowrap}",
    ".st-two{display:grid;grid-template-columns:1fr;gap:6px}",
    ".st-nw{display:block;padding:10px 12px;margin:6px 0;background:var(--deep);border:1px solid var(--line);border-radius:var(--r-md);font-size:14px;line-height:1.6}",
    ".st-nw small{display:block;color:var(--mute);font-size:11.5px}"
  ].join("\n");
  var injected = false;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function lang() { var l = "ar"; try { l = localStorage.getItem("smm.lang") || document.documentElement.lang || "ar"; } catch (e) { } return D[l] ? l : "ar"; }
  function logo(src, name) {
    var ini = String(name || "?").trim().slice(0, 2).toUpperCase();
    return src ? '<img src="' + esc(src) + '" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.outerHTML=\'<span class=ph>' + esc(ini) + '</span>\'">' : '<span class="ph">' + esc(ini) + "</span>";
  }
  function num(x) { return typeof x === "number" && isFinite(x); }
  function pct(a, n) { return n ? Math.round(a * 100 / n) : 0; }

  function compute(ms) {
    var r = { n: 0, goals: 0, h: 0, d: 0, a: 0, big: null, most: null, teams: {} };
    ms.forEach(function (m) {
      if (!num(m.hg) || !num(m.ag)) return;
      r.n++; r.goals += m.hg + m.ag;
      if (m.hg > m.ag) r.h++; else if (m.hg === m.ag) r.d++; else r.a++;
      var diff = Math.abs(m.hg - m.ag), tot = m.hg + m.ag;
      if (!r.big || diff > r.big.diff || (diff === r.big.diff && tot > r.big.tot)) r.big = { m: m, diff: diff, tot: tot };
      if (!r.most || tot > r.most.tot) r.most = { m: m, tot: tot };
      [[m.home, m.home_name, m.home_logo, m.hg, m.ag], [m.away, m.away_name, m.away_logo, m.ag, m.hg]].forEach(function (t) {
        var o = r.teams[t[0]] || (r.teams[t[0]] = { name: t[1], logo: t[2], p: 0, gf: 0, ga: 0 });
        o.p++; o.gf += t[3]; o.ga += t[4];
      });
    });
    return r;
  }
  function matchLine(m, T) {
    return '<div class="st-row">' + logo(m.home_logo, m.home_name) + '<span class="n">' + esc(m.home_name) + '</span><span class="st-sc">' + m.hg + " - " + m.ag + '</span><span class="n" style="text-align:end">' + esc(m.away_name) + "</span>" + logo(m.away_logo, m.away_name) + "</div>";
  }
  function teamRows(list, key) {
    return list.map(function (t) {
      return '<div class="st-row">' + logo(t.logo, t.name) + '<span class="n">' + esc(t.name) + '</span><span class="v">' + t[key].toFixed(2) + "</span></div>";
    }).join("");
  }

  window.smmNews = async function (view, api) {
    var T = D[lang()];
    if (!injected) { var s = document.createElement("style"); s.textContent = CSS; document.head.appendChild(s); injected = true; }
    var ms = [];
    try { ms = (await api.matches("results")) || []; } catch (e) { }
    var r = compute(ms);
    var h = "<h1>" + T.title + '</h1><p class="muted">' + T.sub + "</p>";
    if (!r.n) {
      h += '<p class="empty">' + T.empty + "</p>";
    } else {
      h += '<div class="st-grid"><div class="st-c"><b>' + r.n + "</b><span>" + T.played + '</span></div><div class="st-c"><b>' + r.goals + "</b><span>" + T.goals + '</span></div><div class="st-c"><b>' + (r.goals / r.n).toFixed(2) + "</b><span>" + T.gpm + "</span></div></div>";
      var ph = pct(r.h, r.n), pd = pct(r.d, r.n), pa = Math.max(0, 100 - ph - pd);
      h += '<div class="st-bar"><i style="width:' + ph + '%;background:var(--green)"></i><i style="width:' + pd + '%;background:var(--amber)"></i><i style="width:' + pa + '%;background:var(--red)"></i></div>' +
        '<div class="st-lg"><span>' + T.home + " " + ph + "%</span><span>" + T.draw + " " + pd + "%</span><span>" + T.away + " " + pa + "%</span></div>";
      h += "<h2>" + T.biggest + "</h2>" + matchLine(r.big.m, T) + "<h2>" + T.most + "</h2>" + matchLine(r.most.m, T);
      var arr = Object.keys(r.teams).map(function (k) { var o = r.teams[k]; o.gfp = o.gf / o.p; o.gap = o.ga / o.p; return o; }).filter(function (o) { return o.p >= 3; });
      if (arr.length) {
        h += "<h2>" + T.attack + "</h2>" + teamRows(arr.slice().sort(function (a, b) { return b.gfp - a.gfp; }).slice(0, 5), "gfp");
        h += "<h2>" + T.defense + "</h2>" + teamRows(arr.slice().sort(function (a, b) { return a.gap - b.gap; }).slice(0, 5), "gap");
      }
      var last = ms.filter(function (m) { return num(m.hg) && num(m.ag); }).sort(function (a, b) { return String(b.date || "") < String(a.date || "") ? -1 : 1; }).slice(0, 8);
      h += "<h2>" + T.last + "</h2>" + last.map(function (m) { return matchLine(m, T); }).join("");
      h += '<p class="cap">' + T.note + "</p>";
    }
    var items = [];
    try {
      var res = await fetch("data/news.json", { cache: "no-cache" });
      if (res.ok) { var d = await res.json(); var cur = lang(); items = (d.items || []).filter(function (x) { return x.lang === cur && /^https?:\/\//.test(x.link || ""); }).slice(0, 6); }
    } catch (e) { }
    if (items.length) {
      h += "<h2>" + T.news + "</h2>" + items.map(function (x) { return '<a class="st-nw" href="' + esc(x.link) + '" target="_blank" rel="noopener">' + esc(x.title) + "<small>" + esc(x.source) + "</small></a>"; }).join("") + '<p><a href="#/press" class="muted">' + T.all + " ›</a></p>";
    }
    view.innerHTML = h;
  };
  if (location.hash === "#/news") window.dispatchEvent(new Event("hashchange"));
})();
