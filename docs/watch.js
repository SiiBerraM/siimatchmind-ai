/* SiiMatchMind — صفحة «أين تشاهد» (#/watch): القنوات الرسمية الناقلة فقط. لا يبثّ التطبيق أي مباراة. */
(function () {
  "use strict";
  var D = {
    ar: { title: "أين تشاهد", sub: "القنوات الرسمية الناقلة. التطبيق لا يبثّ أي مباراة.", cur: "البطولة المختارة", others: "بطولات أخرى", none: "لم نضف القناة الناقلة لهذه البطولة بعد.", open: "فتح الموقع الرسمي", free: "مجاني", paid: "مدفوع", hl: "ملخصات رسمية", note: "تختلف القنوات الناقلة حسب بلدك وقد تتغير. تحقّق دائمًا من القناة الرسمية.", upd: "آخر تحديث" },
    en: { title: "Where to watch", sub: "Official broadcasters only. This app does not stream any match.", cur: "Selected league", others: "Other leagues", none: "We haven’t added the broadcaster for this league yet.", open: "Open official site", free: "Free", paid: "Paid", hl: "Official highlights", note: "Broadcasters vary by country and may change. Always check the official channel.", upd: "Last update" },
    fr: { title: "Où regarder", sub: "Diffuseurs officiels uniquement. L’app ne diffuse aucun match.", cur: "Championnat choisi", others: "Autres championnats", none: "Le diffuseur de ce championnat n’a pas encore été ajouté.", open: "Ouvrir le site officiel", free: "Gratuit", paid: "Payant", hl: "Résumés officiels", note: "Les diffuseurs varient selon le pays et peuvent changer. Vérifiez toujours la chaîne officielle.", upd: "Dernière mise à jour" },
    es: { title: "Dónde ver", sub: "Solo emisoras oficiales. La app no retransmite ningún partido.", cur: "Liga elegida", others: "Otras ligas", none: "Aún no hemos añadido la emisora de esta liga.", open: "Abrir sitio oficial", free: "Gratis", paid: "De pago", hl: "Resúmenes oficiales", note: "Las emisoras varían según el país y pueden cambiar. Consulta siempre el canal oficial.", upd: "Última actualización" },
    tr: { title: "Nereden izlenir", sub: "Yalnızca resmî yayıncılar. Uygulama hiçbir maçı yayınlamaz.", cur: "Seçili lig", others: "Diğer ligler", none: "Bu ligin yayıncısı henüz eklenmedi.", open: "Resmî siteyi aç", free: "Ücretsiz", paid: "Ücretli", hl: "Resmî özetler", note: "Yayıncılar ülkeye göre değişir ve değişebilir. Her zaman resmî kanalı kontrol edin.", upd: "Son güncelleme" }
  };
  var CSS = [
    ".wt-c{background:var(--deep);border:1px solid var(--line);border-radius:var(--r-md);padding:14px;margin:8px 0}",
    ".wt-c b{display:block;font-size:16px}",
    ".wt-c small{display:block;color:var(--mute);font-size:12px;margin-top:2px}",
    ".wt-c p{font-size:13px;color:var(--mute);margin-top:6px}",
    ".wt-t{display:inline-block;margin-inline-start:8px;padding:1px 9px;border-radius:99px;font-size:11px;font-weight:600;background:rgba(30,212,138,.15);color:var(--green);vertical-align:middle}",
    ".wt-t.p{background:rgba(242,185,75,.15);color:var(--amber)}",
    ".wt-a{display:inline-block;margin-top:10px;padding:7px 16px;border-radius:99px;background:var(--green);color:#042;font-weight:600;font-size:13px}"
  ].join("\n");
  var injected = false;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function lang() { var l = "ar"; try { l = localStorage.getItem("smm.lang") || document.documentElement.lang || "ar"; } catch (e) { } return D[l] ? l : "ar"; }
  function safeUrl(u) { u = String(u == null ? "" : u).trim(); return /^https?:\/\//i.test(u) ? u : ""; }
  function card(b, T) {
    var tag = b.free === true ? '<span class="wt-t">' + T.free + "</span>" : (b.free === false ? '<span class="wt-t p">' + T.paid + "</span>" : "");
    var link = safeUrl(b.link);
    return '<div class="wt-c"><b>' + esc(b.name) + tag + "</b>" + (b.owner ? "<small>" + esc(b.owner) + "</small>" : "") + (b.note ? "<p>" + esc(b.note) + "</p>" : "") +
      (link ? '<a class="wt-a" href="' + esc(link) + '" target="_blank" rel="noopener">' + T.open + "</a>" : "") + "</div>";
  }
  function block(code, e, T) {
    var list = (e && e.broadcasters) || [];
    return "<h2>" + esc(e && e.name ? e.name : code) + (e && e.region ? ' <span class="muted">· ' + esc(e.region) + "</span>" : "") + "</h2>" +
      (list.length ? list.map(function (b) { return card(b, T); }).join("") : '<p class="muted">' + T.none + "</p>");
  }
  window.smmWatch = async function (view) {
    var T = D[lang()];
    if (!injected) { var s = document.createElement("style"); s.textContent = CSS; document.head.appendChild(s); injected = true; }
    var cfg = { leagues: {}, highlights: [] };
    try { var r = await fetch("data/watch.json", { cache: "no-cache" }); if (r.ok) cfg = await r.json(); } catch (e) { }
    var cur = ""; try { cur = localStorage.getItem("smm.league") || ""; } catch (e) { }
    var L = cfg.leagues || {}, h = "<h1>" + T.title + '</h1><p class="muted">' + T.sub + "</p>";
    var curE = L[cur];
    if (curE) h += "<h2>" + T.cur + "</h2>" + block(cur, curE, T).replace(/^<h2>[\s\S]*?<\/h2>/, "<h2>" + esc(curE.name || cur) + "</h2>");
    var rest = Object.keys(L).filter(function (k) { return k !== cur && (L[k].broadcasters || []).length; });
    if (rest.length) h += "<h2>" + T.others + "</h2>" + rest.map(function (k) { return block(k, L[k], T); }).join("");
    if (!curE && !rest.length) h += '<p class="empty">' + T.none + "</p>";
    var hl = (cfg.highlights || []).filter(function (x) { return safeUrl(x.link); });
    if (hl.length) h += "<h2>" + T.hl + "</h2>" + hl.map(function (x) { return card({ name: x.name, note: x.note, link: x.link }, T); }).join("");
    h += '<p class="cap">' + T.note + (cfg.updated ? " · " + T.upd + ": " + esc(cfg.updated) : "") + "</p>";
    view.innerHTML = h;
  };
  if (location.hash === "#/watch") window.dispatchEvent(new Event("hashchange"));
})();
