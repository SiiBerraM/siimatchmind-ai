/* SiiMatchMind — القائمة الرئيسية (ملف مستقل لا يعدّل app.js) */
(function () {
  "use strict";
  var WYDAD_ID = "h824552", RAJA_ID = "h831360";

  var L = {
    ar: { news: "أخبار وأرقام", menu: "القائمة", close: "إغلاق", home: "الرئيسية", standings: "الترتيب", analyze: "التحليل", teams: "الفرق", saved: "المحفوظات", press: "الصحافة", quality: "الجودة", about: "من نحن", wydad: "الوداد البيضاوي", raja: "الرجاء البيضاوي", disc: "الشعارات ملك لأصحابها، والتطبيق غير تابع لهم رسميًا." },
    en: { news: "News & Stats", menu: "Menu", close: "Close", home: "Home", standings: "Table", analyze: "Analysis", teams: "Teams", saved: "Saved", press: "Press", quality: "Quality", about: "About", wydad: "Wydad AC", raja: "Raja CA", disc: "Logos belong to their owners; this app is not officially affiliated." },
    fr: { news: "Actus & chiffres", menu: "Menu", close: "Fermer", home: "Accueil", standings: "Classement", analyze: "Analyse", teams: "Équipes", saved: "Favoris", press: "Presse", quality: "Qualité", about: "À propos", wydad: "Wydad AC", raja: "Raja CA", disc: "Les logos appartiennent à leurs propriétaires ; l’application n’est pas affiliée officiellement." },
    es: { news: "Noticias y cifras", menu: "Menú", close: "Cerrar", home: "Inicio", standings: "Clasificación", analyze: "Análisis", teams: "Equipos", saved: "Guardados", press: "Prensa", quality: "Calidad", about: "Acerca de", wydad: "Wydad AC", raja: "Raja CA", disc: "Los logotipos pertenecen a sus propietarios; la app no está afiliada oficialmente." },
    tr: { news: "Haber ve rakamlar", menu: "Menü", close: "Kapat", home: "Ana sayfa", standings: "Sıralama", analyze: "Analiz", teams: "Takımlar", saved: "Kaydedilenler", press: "Basın", quality: "Kalite", about: "Hakkında", wydad: "Wydad AC", raja: "Raja CA", disc: "Logolar sahiplerine aittir; uygulama resmî olarak bağlı değildir." }
  };

  var ITEMS = [
    ["home", "#/", '<path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>'],
    ["news", "#/news", '<path d="M13 3L4 14h7l-1 7 9-11h-7z"/>'],
    ["standings", "#/standings", '<path d="M4 5h16M4 10h16M4 15h10M4 20h7"/>'],
    ["analyze", "#/analyze", '<path d="M4 20V10m6 10V4m6 16v-7m5 7H3"/>'],
    ["teams", "#/teams", '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6M16 5a3.2 3.2 0 0 1 0 6m2 3.2c2 .7 3.5 2.5 3.5 5.8"/>'],
    ["saved", "#/saved", '<path d="M6 3h12v18l-6-4-6 4z"/>'],
    ["press", "#/press", '<path d="M4 5h13v14H6a2 2 0 0 1-2-2zM17 9h3v8a2 2 0 0 1-2 2M8 9h5M8 13h5"/>'],
    ["quality", "#/quality", '<path d="M4 12l5 5L20 6"/>'],
    ["about", "#/about", '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>']
  ];

  var CSS = [
    "body::before{content:'';position:fixed;left:50%;top:48%;width:min(80vw,430px);aspect-ratio:455/575;transform:translate(-50%,-50%);background:url(icons/morocco.png) center/contain no-repeat;opacity:.14;pointer-events:none;z-index:5;-webkit-mask-image:radial-gradient(ellipse at center,#000 42%,transparent 72%);mask-image:radial-gradient(ellipse at center,#000 42%,transparent 72%)}",
    ".top,main{position:relative;z-index:1}",
    ".top .brand{margin-inline-end:auto}",
    ".smm-mb{display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;order:-1;flex:none;border-radius:12px;border:1px solid var(--line);background:rgba(255,255,255,.05);color:var(--white);cursor:pointer;padding:0}",
    ".smm-mb svg{width:22px;height:22px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round}",
    ".smm-ov{position:fixed;inset:0;background:rgba(3,10,22,.6);-webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px);opacity:0;visibility:hidden;transition:opacity .25s,visibility .25s;z-index:900}",
    ".smm-ov.open{opacity:1;visibility:visible}",
    ".smm-dr{position:fixed;top:0;bottom:0;inset-inline-start:0;width:min(84vw,340px);display:flex;flex-direction:column;background:linear-gradient(170deg,var(--deep),var(--night) 75%);border-inline-end:1px solid var(--line);box-shadow:0 0 40px rgba(0,0,0,.45);transform:translateX(-105%);transition:transform .3s cubic-bezier(.2,.8,.2,1);z-index:901;padding:env(safe-area-inset-top,0px) 0 env(safe-area-inset-bottom,0px);overflow-y:auto;visibility:hidden}",
    "html[dir='rtl'] .smm-dr{transform:translateX(105%)}",
    "html .smm-dr.open,html[dir='rtl'] .smm-dr.open{transform:none;visibility:visible}",
    ".smm-hd{display:flex;align-items:center;justify-content:space-between;padding:18px 18px 12px}",
    ".smm-bd{font-weight:700;font-size:18px}.smm-bd span{color:var(--green)}",
    ".smm-x{width:36px;height:36px;border-radius:50%;border:1px solid var(--line);background:rgba(255,255,255,.05);color:var(--white);font-size:22px;line-height:1;cursor:pointer}",
    ".smm-ls{display:flex;flex-direction:column;gap:4px;padding:6px 12px}",
    ".smm-ls a{display:flex;align-items:center;gap:14px;padding:13px 14px;border-radius:14px;font-weight:500;border:1px solid transparent;transition:background .2s}",
    ".smm-ls a svg{width:22px;height:22px;stroke:var(--green);fill:none;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round;flex:none}",
    ".smm-ls a:active,.smm-ls a.on{background:rgba(30,212,138,.12);border-color:rgba(30,212,138,.35)}",
    ".smm-ft{margin-top:auto;padding:18px 18px 20px;border-top:1px solid var(--line)}",
    ".smm-lg{display:flex;justify-content:space-between;align-items:flex-start;direction:ltr}",
    ".smm-cl{display:flex;flex-direction:column;align-items:center;gap:8px;width:46%;text-align:center;font-size:12px;color:var(--mute)}",
    ".smm-bg{width:76px;height:76px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.07);border:1px solid var(--line);box-shadow:0 6px 18px rgba(0,0,0,.3)}",
    ".smm-bg img{width:58px;height:58px;object-fit:contain}",
    ".smm-bg b{font-size:15px;color:var(--white)}",
    ".smm-dc{margin-top:14px;font-size:11px;line-height:1.6;color:var(--mute);text-align:center}"
  ].join("\n");

  var lang = function () {
    var l = "ar";
    try { l = localStorage.getItem("smm.lang") || document.documentElement.lang || "ar"; } catch (e) { }
    return L[l] ? l : "ar";
  };

  var st = document.createElement("style");
  st.textContent = CSS;
  document.head.appendChild(st);

  var ov = document.createElement("div"); ov.className = "smm-ov";
  var dr = document.createElement("aside"); dr.className = "smm-dr";
  dr.setAttribute("role", "dialog"); dr.setAttribute("aria-modal", "true");
  document.body.appendChild(ov); document.body.appendChild(dr);

  var btn = document.createElement("button");
  btn.type = "button"; btn.className = "smm-mb";
  btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg>';
  function attach() {
    if (btn.isConnected) return;
    var top = document.querySelector(".top");
    if (top) top.insertAdjacentElement("afterbegin", btn);
  }
  attach();
  var topEl = document.querySelector(".top");
  if (topEl && window.MutationObserver) new MutationObserver(attach).observe(topEl, { childList: true, subtree: true });
  window.addEventListener("hashchange", attach);

  var logos = null, loading = false;
  function loadLogos(cb) {
    if (logos || loading) return;
    loading = true;
    fetch("data/static.json").then(function (r) { return r.json(); }).then(function (d) {
      logos = {};
      (d.teams || []).forEach(function (t) {
        if (t.id === WYDAD_ID || t.id === RAJA_ID) logos[t.id] = t.logo || "";
      });
      cb();
    }).catch(function () { logos = {}; cb(); });
  }

  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  function club(id, name, ph) {
    var src = logos && logos[id];
    var inner = src ? '<img src="' + esc(src) + '" alt="" referrerpolicy="no-referrer" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement(\'b\'),{textContent:\'' + ph + '\'}))">' : "<b>" + ph + "</b>";
    return '<div class="smm-cl"><div class="smm-bg">' + inner + "</div><span>" + esc(name) + "</span></div>";
  }

  function render() {
    var T = L[lang()];
    var h = location.hash || "#/";
    btn.setAttribute("aria-label", T.menu);
    dr.setAttribute("aria-label", T.menu);
    var links = ITEMS.map(function (it) {
      var on = it[1] === "#/" ? (h === "#/" || h === "#" || h === "") : h.indexOf(it[1]) === 0;
      return '<a href="' + it[1] + '" class="' + (on ? "on" : "") + '"><svg viewBox="0 0 24 24">' + it[2] + "</svg><span>" + esc(T[it[0]]) + "</span></a>";
    }).join("");
    dr.innerHTML =
      '<div class="smm-hd"><div class="smm-bd">SiiMatchMind <span>AI</span></div><button type="button" class="smm-x" aria-label="' + esc(T.close) + '">×</button></div>' +
      '<nav class="smm-ls">' + links + "</nav>" +
      '<div class="smm-ft"><div class="smm-lg">' + club(RAJA_ID, T.raja, "RCA") + club(WYDAD_ID, T.wydad, "WAC") + '</div><p class="smm-dc">' + esc(T.disc) + "</p></div>";
    dr.querySelector(".smm-x").onclick = close;
  }

  function open() {
    render();
    loadLogos(render);
    ov.classList.add("open"); dr.classList.add("open");
    document.body.style.overflow = "hidden";
  }
  function close() {
    ov.classList.remove("open"); dr.classList.remove("open");
    document.body.style.overflow = "";
  }

  btn.addEventListener("click", open);
  ov.addEventListener("click", close);
  dr.addEventListener("click", function (e) { if (e.target.closest && e.target.closest("a")) close(); });
  window.addEventListener("hashchange", close);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });
  render();
  window.smmMenu = { open: open, close: close };
})();
