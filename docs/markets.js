/* SiiMatchMind — قسم «احتمالات إضافية» في صفحة المباراة، محسوب من مصفوفة النتائج الحالية (بلا بيانات جديدة). */
(function () {
  "use strict";
  var D = {
    ar: { h: "احتمالات إضافية", hnl: "المضيف لا يخسر", anl: "الضيف لا يخسر", nd: "مباراة بفائز (لا تعادل)", o15: "أكثر من 1.5 هدف", o35: "أكثر من 3.5 هدف", csh: "شباك المضيف نظيفة", csa: "شباك الضيف نظيفة", wnh: "المضيف يفوز بشباك نظيفة", wna: "الضيف يفوز بشباك نظيفة", cap: "محسوبة من مصفوفة النتائج (حتى 5 أهداف لكل فريق). هي احتمالات تقديرية، وليست يقينًا." },
    en: { h: "Extra probabilities", hnl: "Home does not lose", anl: "Away does not lose", nd: "Match has a winner (no draw)", o15: "Over 1.5 goals", o35: "Over 3.5 goals", csh: "Home clean sheet", csa: "Away clean sheet", wnh: "Home wins without conceding", wna: "Away wins without conceding", cap: "Computed from the score matrix (up to 5 goals per team). These are estimated probabilities, not certainty." },
    fr: { h: "Probabilités supplémentaires", hnl: "L’équipe à domicile ne perd pas", anl: "L’équipe à l’extérieur ne perd pas", nd: "Match avec un vainqueur (pas de nul)", o15: "Plus de 1,5 but", o35: "Plus de 3,5 buts", csh: "Domicile : clean sheet", csa: "Extérieur : clean sheet", wnh: "Domicile gagne sans encaisser", wna: "Extérieur gagne sans encaisser", cap: "Calculées à partir de la matrice des scores (jusqu’à 5 buts par équipe). Ce sont des probabilités estimées, pas des certitudes." },
    es: { h: "Probabilidades adicionales", hnl: "El local no pierde", anl: "El visitante no pierde", nd: "Partido con ganador (sin empate)", o15: "Más de 1,5 goles", o35: "Más de 3,5 goles", csh: "Portería a cero del local", csa: "Portería a cero del visitante", wnh: "El local gana sin recibir gol", wna: "El visitante gana sin recibir gol", cap: "Calculadas con la matriz de resultados (hasta 5 goles por equipo). Son probabilidades estimadas, no certezas." },
    tr: { h: "Ek olasılıklar", hnl: "Ev sahibi yenilmez", anl: "Deplasman yenilmez", nd: "Kazananlı maç (beraberlik yok)", o15: "1,5 gol üstü", o35: "3,5 gol üstü", csh: "Ev sahibi kalesini gole kapatır", csa: "Deplasman kalesini gole kapatır", wnh: "Ev sahibi gol yemeden kazanır", wna: "Deplasman gol yemeden kazanır", cap: "Skor matrisinden hesaplanır (takım başına 5 gole kadar). Tahmini olasılıklardır, kesinlik değildir." }
  };
  var CSS = ".mk-r{display:flex;align-items:center;gap:10px;margin:7px 0}.mk-r span{flex:1;font-size:14px}.mk-r b{min-width:44px;text-align:end;color:var(--green)}.mk-t{flex:0 0 38%;height:7px;border-radius:99px;background:var(--panel);overflow:hidden}.mk-t i{display:block;height:100%;background:var(--green)}";
  var injected = false;
  function lang() { var l = "ar"; try { l = localStorage.getItem("smm.lang") || document.documentElement.lang || "ar"; } catch (e) { } return D[l] ? l : "ar"; }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  // يحدّد هل الصفوف = أهداف المضيف (الافتراضي) أم العكس، اعتمادًا على أرجح نتيجة ثم الأهداف المتوقعة
  function rowsAreHome(m, p) {
    var best = -1, bi = 0, bj = 0, i, j;
    for (i = 0; i < m.length; i++) for (j = 0; j < m[i].length; j++) if (m[i][j] > best) { best = m[i][j]; bi = i; bj = j; }
    var s = p.most_likely_score;
    if (s && s.home !== s.away) {
      if (bi === s.home && bj === s.away) return true;
      if (bi === s.away && bj === s.home) return false;
    }
    var xg = p.expected_goals, tot = 0, mi = 0, mj = 0;
    for (i = 0; i < m.length; i++) for (j = 0; j < m[i].length; j++) { tot += m[i][j]; mi += i * m[i][j]; mj += j * m[i][j]; }
    if (!tot || !xg) return true;
    return Math.abs(mi / tot - xg.home) + Math.abs(mj / tot - xg.away) <= Math.abs(mj / tot - xg.home) + Math.abs(mi / tot - xg.away);
  }

  function compute(r) {
    var p = r.prediction, m = p && p.score_matrix, pc = p && p.percent;
    if (!m || !m.length || !pc) return null;
    var rows = rowsAreHome(m, p), tot = 0, o15 = 0, o35 = 0, hcs = 0, acs = 0, hwn = 0, awn = 0, i, j, hg, ag, v;
    for (i = 0; i < m.length; i++) for (j = 0; j < m[i].length; j++) {
      v = m[i][j]; if (typeof v !== "number") return null;
      hg = rows ? i : j; ag = rows ? j : i;
      tot += v;
      if (hg + ag >= 2) o15 += v;
      if (hg + ag >= 4) o35 += v;
      if (ag === 0) hcs += v;
      if (hg === 0) acs += v;
      if (ag === 0 && hg > 0) hwn += v;
      if (hg === 0 && ag > 0) awn += v;
    }
    if (!tot) return null;
    return { hnl: pc.home + pc.draw, anl: pc.away + pc.draw, nd: pc.home + pc.away, o15: 100 * o15 / tot, o35: 100 * o35 / tot, csh: 100 * hcs / tot, csa: 100 * acs / tot, wnh: 100 * hwn / tot, wna: 100 * awn / tot };
  }

  window.smmMarkets = function (r) {
    try {
      var c = compute(r); if (!c) return "";
      var T = D[lang()];
      if (!injected) { var s = document.createElement("style"); s.textContent = CSS; document.head.appendChild(s); injected = true; }
      var keys = ["hnl", "anl", "nd", "o15", "o35", "csh", "csa", "wnh", "wna"];
      return "<h2>" + T.h + "</h2>" + keys.map(function (k) {
        var v = Math.max(0, Math.min(100, Math.round(c[k])));
        return '<div class="mk-r"><span>' + esc(T[k]) + "</span><div class=\"mk-t\"><i style=\"width:" + v + '%"></i></div><b>' + v + "%</b></div>";
      }).join("") + '<p class="cap">' + T.cap + "</p>";
    } catch (e) { return ""; }
  };
  window.smmMarketsCompute = compute;
})();
