/* SiiMatchMind — بطاقة «الدقة المباشرة» في صفحة الجودة (#/quality)، من سجل التوقعات data/ledger.json */
(function () {
  "use strict";
  var NEED = 30;
  var D = {
    ar: { title: "الدقة المباشرة", intro: "توقعات سُجّلت قبل المباريات ولا تُعدَّل، ثم قورنت بالنتائج الفعلية.", logged: "توقعات مسجّلة", settled: "مباريات انتهت", need: "نحتاج {n} مباراة منتهية على الأقل قبل عرض أرقام موثوقة.", of: "من", metric: "المقياس", model: "توقعاتنا", rand: "تخمين عشوائي", brier: "Brier (الأقل أفضل)", ll: "Log Loss (الأقل أفضل)", acc: "نسبة الإصابة", since: "منذ", note: "نسبة الإصابة مقياس خشن: التطبيق يعطي احتمالات وليس يقينًا." },
    en: { title: "Live accuracy", intro: "Predictions logged before the matches and never edited, then compared with real results.", logged: "predictions logged", settled: "matches finished", need: "We need at least {n} finished matches before showing reliable numbers.", of: "of", metric: "Metric", model: "Our predictions", rand: "Random guess", brier: "Brier (lower is better)", ll: "Log Loss (lower is better)", acc: "Hit rate", since: "since", note: "Hit rate is a rough measure: the app gives probabilities, not certainty." },
    fr: { title: "Précision en direct", intro: "Prédictions enregistrées avant les matchs et jamais modifiées, puis comparées aux résultats réels.", logged: "prédictions enregistrées", settled: "matchs terminés", need: "Il faut au moins {n} matchs terminés avant d’afficher des chiffres fiables.", of: "sur", metric: "Mesure", model: "Nos prédictions", rand: "Au hasard", brier: "Brier (plus bas = mieux)", ll: "Log Loss (plus bas = mieux)", acc: "Taux de réussite", since: "depuis", note: "Le taux de réussite est une mesure grossière : l’app donne des probabilités, pas des certitudes." },
    es: { title: "Precisión en directo", intro: "Pronósticos registrados antes de los partidos y nunca editados, comparados con los resultados reales.", logged: "pronósticos registrados", settled: "partidos terminados", need: "Necesitamos al menos {n} partidos terminados antes de mostrar cifras fiables.", of: "de", metric: "Medida", model: "Nuestros pronósticos", rand: "Al azar", brier: "Brier (menos es mejor)", ll: "Log Loss (menos es mejor)", acc: "Aciertos", since: "desde", note: "El porcentaje de aciertos es una medida burda: la app da probabilidades, no certezas." },
    tr: { title: "Canlı doğruluk", intro: "Maçlardan önce kaydedilen ve hiç değiştirilmeyen tahminler, gerçek sonuçlarla karşılaştırıldı.", logged: "tahmin kaydedildi", settled: "maç bitti", need: "Güvenilir rakamlar göstermeden önce en az {n} biten maç gerekiyor.", of: "/", metric: "Ölçüt", model: "Tahminlerimiz", rand: "Rastgele tahmin", brier: "Brier (düşük iyidir)", ll: "Log Loss (düşük iyidir)", acc: "İsabet oranı", since: "başlangıç", note: "İsabet oranı kaba bir ölçüdür: uygulama olasılık verir, kesinlik değil." }
  };
  var CSS = [
    ".lv-c{margin-top:22px;padding:14px;border:1px solid var(--line);border-radius:var(--r-md);background:var(--deep)}",
    ".lv-c h2{margin-top:0}",
    ".lv-n{display:flex;gap:18px;margin:10px 0}",
    ".lv-n div{flex:1;text-align:center}",
    ".lv-n b{display:block;font-size:24px;color:var(--green)}",
    ".lv-n span{font-size:12px;color:var(--mute)}",
    ".lv-bar{height:8px;border-radius:99px;background:var(--panel);overflow:hidden;margin:8px 0 4px}",
    ".lv-bar i{display:block;height:100%;background:var(--green)}"
  ].join("\n");
  var cache, loading, injected = false;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function lang() { var l = "ar"; try { l = localStorage.getItem("smm.lang") || document.documentElement.lang || "ar"; } catch (e) { } return D[l] ? l : "ar"; }
  function pct(x) { return Math.round(x * 1000) / 10 + "%"; }

  function card(led) {
    var T = D[lang()], s = (led && led.summary) || {};
    var logged = s.logged || 0, settled = s.settled || 0;
    var first = "";
    var ps = (led && led.predictions) || {};
    Object.keys(ps).forEach(function (k) { var t = (ps[k].logged_at || "").slice(0, 10); if (t && (!first || t < first)) first = t; });
    var h = '<div class="lv-c" data-live="1"><h2>' + T.title + "</h2><p class=\"muted\">" + T.intro + "</p>" +
      '<div class="lv-n"><div><b>' + logged + "</b><span>" + T.logged + (first ? " · " + T.since + " <bdi dir=\"ltr\" style=\"white-space:nowrap\">" + esc(first) + "</bdi>" : "") + "</span></div><div><b>" + settled + "</b><span>" + T.settled + "</span></div></div>";
    if (settled < NEED || !s.final_all) {
      h += '<div class="lv-bar"><i style="width:' + Math.min(100, Math.round(settled * 100 / NEED)) + '%"></i></div><p class="cap">' + T.need.replace("{n}", NEED) + " <bdi dir=\"ltr\" style=\"white-space:nowrap\">" + settled + " / " + NEED + "</bdi></p>";
    } else {
      var f = s.final_all, u = s.baseline_uniform || { brier: 0.6667, log_loss: 1.0986 };
      h += '<table class="cmp"><tr><th>' + T.metric + "</th><th>" + T.model + "</th><th>" + T.rand + "</th></tr>" +
        "<tr><td>" + T.brier + "</td><td>" + f.brier + "</td><td>" + u.brier + "</td></tr>" +
        "<tr><td>" + T.ll + "</td><td>" + f.log_loss + "</td><td>" + u.log_loss + "</td></tr>" +
        "<tr><td>" + T.acc + "</td><td>" + pct(f.accuracy) + "</td><td>33.3%</td></tr></table>" +
        '<p class="cap">' + T.note + "</p>";
    }
    return h + "</div>";
  }

  function start() {
    var view = document.getElementById("view");
    if (!view) return;
    var st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
    var go = function () {
      if (location.hash !== "#/quality" || view.querySelector("[data-live]")) return;
      if (view.textContent.trim() === "…") return;
      var put = function () { if (location.hash === "#/quality" && !view.querySelector("[data-live]")) view.insertAdjacentHTML("beforeend", card(cache)); };
      if (cache !== undefined) { put(); return; }
      if (loading) return;
      loading = true;
      fetch("data/ledger.json", { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }).then(function (d) { cache = d || null; loading = false; put(); });
    };
    new MutationObserver(function () { window.requestAnimationFrame(go); }).observe(view, { childList: true });
    window.addEventListener("hashchange", function () { window.requestAnimationFrame(go); });
    go();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
