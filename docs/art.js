/* SiiMatchMind — رسومات أصلية (SVG): بانر الملعب في الرئيسية، وحالات «لا توجد بيانات». */
(function () {
  "use strict";
  var CSS = [
    "#smmHero{margin:6px 16px 0;max-width:608px;margin-inline:auto;padding-inline:16px;display:none}",
    "#smmHero.on{display:block}",
    "#smmHero svg{display:block;width:100%;height:auto;border-radius:var(--r-lg);border:1px solid var(--line);box-shadow:0 10px 28px rgba(0,0,0,.28)}",
    ".smm-move{animation:smmMove 9s linear infinite alternate}",
    "@keyframes smmMove{from{transform:translateX(-120px)}to{transform:translateX(120px)}}",
    ".smm-spin{transform-box:fill-box;transform-origin:center;animation:smmSpin 9s linear infinite alternate}",
    "@keyframes smmSpin{from{transform:rotate(0)}to{transform:rotate(720deg)}}",
    ".smm-gl{animation:smmGlow 5s ease-in-out infinite alternate}",
    "@keyframes smmGlow{from{opacity:.55}to{opacity:1}}",
    "@media (prefers-reduced-motion:reduce){.smm-move,.smm-spin,.smm-gl{animation:none}}",
    ".smm-em{display:block;width:150px;height:auto;margin:6px auto 0;opacity:.95}",
    ".empty.has-art{display:flex;flex-direction:column;align-items:center;gap:4px}"
  ].join("\n");

  var BALL = '<g><circle r="15" fill="#fff"/><polygon points="0,-6 5.7,-1.9 3.5,4.9 -3.5,4.9 -5.7,-1.9" fill="#0b1b33"/>' +
    '<g stroke="#0b1b33" stroke-width="1.3" stroke-linecap="round"><path d="M0-6V-14M5.7-1.9L13.3-4.3M3.5 4.9L8.2 11.3M-3.5 4.9L-8.2 11.3M-5.7-1.9L-13.3-4.3"/></g>' +
    '<circle r="15" fill="none" stroke="rgba(0,0,0,.25)" stroke-width="1"/></g>';

  var HERO = '<svg viewBox="0 0 400 112" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="football pitch">' +
    '<defs>' +
    '<linearGradient id="hg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0d3a5f"/><stop offset="1" stop-color="#082a49"/></linearGradient>' +
    '<radialGradient id="hl" cx=".5" cy=".5" r=".6"><stop offset="0" stop-color="#1ed48a" stop-opacity=".38"/><stop offset="1" stop-color="#1ed48a" stop-opacity="0"/></radialGradient>' +
    '<pattern id="hs" width="40" height="112" patternUnits="userSpaceOnUse"><rect width="20" height="112" fill="#fff" opacity=".025"/></pattern>' +
    '</defs>' +
    '<rect width="400" height="112" fill="url(#hg)"/><rect width="400" height="112" fill="url(#hs)"/>' +
    '<ellipse class="smm-gl" cx="200" cy="56" rx="170" ry="70" fill="url(#hl)"/>' +
    '<g fill="none" stroke="#fff" stroke-opacity=".22" stroke-width="1.6">' +
    '<rect x="14" y="12" width="372" height="88" rx="6"/><path d="M200 12V100"/><circle cx="200" cy="56" r="22"/>' +
    '<rect x="14" y="30" width="46" height="52"/><rect x="14" y="43" width="18" height="26"/>' +
    '<rect x="340" y="30" width="46" height="52"/><rect x="368" y="43" width="18" height="26"/>' +
    '<path d="M60 44a16 16 0 0 1 0 24M340 44a16 16 0 0 0 0 24"/></g>' +
    '<circle cx="200" cy="56" r="2.6" fill="#fff" fill-opacity=".5"/>' +
    '<g class="smm-move"><ellipse cx="200" cy="74" rx="15" ry="3.2" fill="#000" opacity=".28"/>' +
    '<g transform="translate(200 56)"><g class="smm-spin">' + BALL + '</g></g></g>' +
    '</svg>';

  var EMPTY = '<svg class="smm-em" viewBox="0 0 160 110" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
    '<defs><pattern id="en" width="8" height="8" patternUnits="userSpaceOnUse"><path d="M0 0L8 8M8 0L0 8" stroke="#9db3cf" stroke-opacity=".35" stroke-width=".8"/></pattern></defs>' +
    '<ellipse cx="80" cy="98" rx="62" ry="7" fill="#1ed48a" opacity=".18"/>' +
    '<rect x="26" y="26" width="108" height="66" fill="url(#en)" opacity=".8"/>' +
    '<path d="M26 92V26h108v66" fill="none" stroke="#f5f8fc" stroke-opacity=".85" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>' +
    '<g transform="translate(104 82) scale(.8)">' + BALL + '</g></svg>';

  function inject() {
    var st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
  }
  function isHome() { var h = location.hash; return !h || h === "#" || h === "#/" ; }

  function start() {
    var view = document.getElementById("view");
    if (!view) return;
    inject();
    var hero = document.createElement("div");
    hero.id = "smmHero"; hero.innerHTML = HERO;
    view.parentNode.insertBefore(hero, view);
    var sync = function () { hero.classList.toggle("on", isHome()); };
    sync();
    window.addEventListener("hashchange", sync);
    var dec = function () {
      view.querySelectorAll(".empty:not(.has-art)").forEach(function (el) {
        if (el.textContent.trim() === "…") return;
        el.classList.add("has-art");
        el.insertAdjacentHTML("afterbegin", EMPTY);
      });
    };
    new MutationObserver(function () { window.requestAnimationFrame(dec); }).observe(view, { childList: true, subtree: true });
    dec();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
