/* SiiMatchMind — نظام الإعلانات المرن. يقرأ data/ads.json ويعرض أي نوع إعلان في أماكن محددة. */
(function () {
  "use strict";
  var LBL = { ar: "إعلان", en: "Ad", fr: "Publicité", es: "Anuncio", tr: "Reklam" };
  var CSS = [
    ".smm-ad{margin:14px 0;padding:8px;border:1px solid var(--line);border-radius:var(--r-md);background:rgba(255,255,255,.03);text-align:center;overflow:hidden}",
    ".smm-adl{display:block;font-size:10.5px;color:var(--mute);margin-bottom:6px;text-align:start}",
    ".smm-ad img,.smm-ad video{max-width:100%;height:auto;border-radius:10px;display:block;margin:0 auto}",
    ".smm-ad iframe{width:100%;border:0;border-radius:10px;background:transparent}",
    ".smm-ad .at{display:block;text-align:start}",
    ".smm-ad .at b{display:block;font-size:15px;margin-bottom:2px}",
    ".smm-ad .at p{font-size:13px;color:var(--mute)}",
    ".smm-ad .at u{display:inline-block;margin-top:8px;padding:6px 14px;border-radius:99px;background:var(--green);color:#042;font-weight:600;font-size:13px;text-decoration:none}"
  ].join("\n");

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function safeUrl(u) {
    u = String(u == null ? "" : u).trim();
    if (!u || /^(javascript|data|vbscript|file):/i.test(u)) return "";
    return u;
  }
  function lang() { var l = "ar"; try { l = localStorage.getItem("smm.lang") || document.documentElement.lang || "ar"; } catch (e) { } return LBL[l] ? l : "ar"; }
  function curLeague() { try { return localStorage.getItem("smm.league") || ""; } catch (e) { return ""; } }

  function active(ad, slot, lg, lc, now) {
    if (ad.enabled === false) return false;
    var sl = ad.slots || ad.slot;
    if (sl && [].concat(sl).indexOf(slot) < 0) return false;
    if (ad.lang && [].concat(ad.lang).indexOf(lg) < 0) return false;
    if (ad.league && lc && [].concat(ad.league).indexOf(lc) < 0) return false;
    if (ad.start && now < Date.parse(ad.start)) return false;
    if (ad.end && now > Date.parse(ad.end) + 86400000) return false;
    return true;
  }
  function pick(ads, slot, lg, lc, now, rnd) {
    var pool = (ads || []).filter(function (a) { return active(a, slot, lg, lc, now); });
    if (!pool.length) return null;
    var tot = pool.reduce(function (s, a) { return s + (a.weight > 0 ? a.weight : 1); }, 0);
    var x = (rnd == null ? Math.random() : rnd) * tot;
    for (var i = 0; i < pool.length; i++) { x -= (pool[i].weight > 0 ? pool[i].weight : 1); if (x < 0) return pool[i]; }
    return pool[pool.length - 1];
  }

  var SB = "allow-scripts allow-popups allow-popups-to-escape-sandbox allow-forms";
  function inner(ad) {
    var link = safeUrl(ad.link), src = safeUrl(ad.src), h = parseInt(ad.height, 10) || 120;
    var wrapA = function (x) { return link ? '<a href="' + esc(link) + '" target="_blank" rel="noopener sponsored nofollow">' + x + "</a>" : x; };
    switch (ad.type) {
      case "image": return src ? wrapA('<img src="' + esc(src) + '" alt="' + esc(ad.alt || "") + '" loading="lazy" referrerpolicy="no-referrer">') : "";
      case "video": return src ? wrapA('<video src="' + esc(src) + '" muted autoplay loop playsinline preload="metadata"></video>') : "";
      case "text": return wrapA('<span class="at"><b>' + esc(ad.title) + "</b><p>" + esc(ad.body) + "</p>" + (ad.cta ? "<u>" + esc(ad.cta) + "</u>" : "") + "</span>");
      case "html": case "script":
        if (ad.html) return '<iframe sandbox="' + SB + '" srcdoc="' + esc(ad.html) + '" style="height:' + h + 'px" loading="lazy" referrerpolicy="no-referrer" title="ad"></iframe>';
        return src ? '<iframe sandbox="' + SB + '" src="' + esc(src) + '" style="height:' + h + 'px" loading="lazy" referrerpolicy="no-referrer" title="ad"></iframe>' : "";
      case "embed": return src ? '<iframe sandbox="' + SB + '" src="' + esc(src) + '" style="height:' + h + 'px" loading="lazy" referrerpolicy="no-referrer" title="ad"></iframe>' : "";
      case "trusted": return '<div data-trusted="1">' + (ad.html || "") + "</div>";
      default: return "";
    }
  }
  function html(ad, lg) {
    var b = inner(ad);
    if (!b) return "";
    return '<div class="smm-ad" data-smm-ad="' + esc(ad.id || "") + '"><span class="smm-adl">' + LBL[lg] + "</span>" + b + "</div>";
  }

  var api = { pick: pick, html: html, safeUrl: safeUrl, active: active };
  if (typeof window === "undefined") { module.exports = api; return; }
  window.smmAds = api;

  var CFG = null, view = null, busy = false;
  var DEMO = { enabled: true, top: true, bottom: true, ads: [
    { id: "demo-text", type: "text", slots: ["top"], title: "إعلان تجريبي", body: "هذا مثال على إعلان نصي. يظهر بسبب adsdemo في الرابط فقط.", cta: "اعرف المزيد", link: "https://example.com" },
    { id: "demo-html", type: "html", slots: ["bottom"], height: 90, html: "<body style='margin:0;font-family:sans-serif;background:#12a669;color:#fff;display:flex;align-items:center;justify-content:center;height:90px'>HTML ad (sandbox)</body>" }
  ] };

  function place() {
    if (busy || !CFG || !CFG.enabled || !view) return;
    if (view.querySelector("[data-smm-sentinel]")) return;
    if (!view.children.length || view.querySelector(".empty") && view.children.length < 2) { /* wait for real content */ }
    var h = location.hash || "#/";
    var ex = CFG.exclude || [];
    for (var i = 0; i < ex.length; i++) if (h.indexOf(ex[i]) === 0) { mark(); return; }
    busy = true;
    var lg = lang(), lc = curLeague(), now = Date.now(), put = [];
    if (CFG.top !== false) { var a = pick(CFG.ads, "top", lg, lc, now); if (a) { var x = html(a, lg); if (x) view.insertAdjacentHTML("afterbegin", x); } }
    if (CFG.inline && CFG.inline.selector && CFG.inline.every > 0) {
      var els = view.querySelectorAll(CFG.inline.selector), n = 0, max = CFG.inline.max || 3;
      for (var k = els.length - 1; k >= 0; k--) { if ((k + 1) % CFG.inline.every === 0 && k + 1 < els.length) put.push(els[k]); }
      put.reverse().slice(0, max).forEach(function (el) { var a2 = pick(CFG.ads, "inline", lg, lc, now); if (a2) { var y = html(a2, lg); if (y) el.insertAdjacentHTML("afterend", y); } });
    }
    if (CFG.bottom !== false) { var b = pick(CFG.ads, "bottom", lg, lc, now); if (b) { var z = html(b, lg); if (z) view.insertAdjacentHTML("beforeend", z); } }
    mark();
    // تشغيل إعلانات "trusted" (سكربتات شبكات الإعلان)
    view.querySelectorAll("[data-trusted] script").forEach(function (old) {
      var s = document.createElement("script");
      for (var j = 0; j < old.attributes.length; j++) s.setAttribute(old.attributes[j].name, old.attributes[j].value);
      s.text = old.text; old.replaceWith(s);
    });
    busy = false;
  }
  function mark() { var m = document.createElement("i"); m.hidden = true; m.setAttribute("data-smm-sentinel", "1"); view.appendChild(m); }

  function start() {
    view = document.getElementById("view");
    if (!view) return;
    var st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
    var go = function () { try { place(); } catch (e) { busy = false; } };
    new MutationObserver(function () { window.requestAnimationFrame(go); }).observe(view, { childList: true });
    go();
  }
  function init() {
    if (/[?&]adsdemo/.test(location.search)) { CFG = DEMO; start(); return; }
    fetch("data/ads.json", { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (c) {
      CFG = c; if (c && c.enabled) start();
    }).catch(function () { });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
