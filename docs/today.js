/* SiiMatchMind — صفحة «مباريات اليوم» (#/today) لكل البطولات مع مزامنة كاملة وأسماء الفرق الحقيقية + دعم hlpara و Sii-Football®. */
(function () {
  "use strict";

  var DAYS_AR = ["الأحد", "الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];
  var SII_FOOTBALL_URL = "https://siiberram.github.io/Sii-Football/";

  function getLang() {
    try { return (localStorage.getItem("smm.lang") || document.documentElement.lang || "ar").slice(0, 2); }
    catch (e) { return "ar"; }
  }

  function getSelectedLeague() {
    try {
      var sel = document.getElementById("leagueSel");
      var v = (sel && sel.value) || localStorage.getItem("smm.league") || window.SMM_LEAGUE || "";
      v = String(v || "").trim();
      if (!v || v === "all" || v === "ALL" || v === "*") return "";
      return v;
    } catch (e) {
      return "";
    }
  }

  function syncLeagueAcrossControls(leagueVal) {
    var clean = String(leagueVal || "").trim();
    try {
      if (clean) localStorage.setItem("smm.league", clean);
      else localStorage.removeItem("smm.league");
    } catch (e) {}
    window.SMM_LEAGUE = clean;

    var sel = document.getElementById("leagueSel");
    if (sel && sel.value !== clean) {
      sel.value = clean;
    }

    try {
      window.dispatchEvent(new CustomEvent("smm:state-change", {
        detail: { league: clean, source: "today" }
      }));
    } catch (e) {}
  }

  function matchMatchesLeague(m, leagueCode) {
    if (!leagueCode) return true;
    var candidates = [
      m && m.league,
      m && m.league_id,
      m && m.leagueId,
      m && m._league,
      m && m.comp,
      m && m.competition,
      m && m.competition_id,
      m && m.code,
      m && m.hl
    ];
    for (var i = 0; i < candidates.length; i++) {
      if (candidates[i] != null && String(candidates[i]).trim() === leagueCode) {
        return true;
      }
    }
    return false;
  }

  function isoDay(offset) {
    var d = new Date();
    d.setDate(d.getDate() + offset);
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, "0");
    var day = String(d.getDate()).padStart(2, "0");
    return y + "-" + m + "-" + day;
  }

  function dayLabel(offset, isAr) {
    if (offset === -1) return isAr ? "أمس" : "Yesterday";
    if (offset === 0) return isAr ? "اليوم" : "Today";
    if (offset === 1) return isAr ? "غدًا" : "Tomorrow";
    if (offset === 2) return isAr ? "بعد غد" : "Day after";
    var d = new Date();
    d.setDate(d.getDate() + offset);
    return DAYS_AR[d.getDay()];
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function extractDatePart(val) {
    var s = String(val || "").trim();
    if (!s) return "";
    return s.slice(0, 10);
  }

  function buildTeamsIndex(data) {
    var map = Object.create(null);
    var teams = data && data.teams;
    if (!teams) return map;

    function addEntry(key, obj) {
      if (!key) return;
      var k = String(key).trim();
      if (!k) return;
      var name = "";
      var logo = "";
      if (typeof obj === "string") {
        name = obj;
      } else if (obj && typeof obj === "object") {
        name = obj.name || obj.team_name || obj.title || obj.shortName || obj.short_name || "";
        logo = obj.logo || obj.crest || obj.image || obj.img || "";
      }
      if (name || logo) {
        map[k] = { name: name || k, logo: logo || "" };
        var bare = k.replace(/^[ht]/i, "");
        if (bare && !map[bare]) map[bare] = { name: name || k, logo: logo || "" };
      }
    }

    if (Array.isArray(teams)) {
      teams.forEach(function (t) {
        if (!t || typeof t !== "object") return;
        addEntry(t.id || t.team_id || t.code, t);
      });
    } else if (typeof teams === "object") {
      Object.keys(teams).forEach(function (k) {
        addEntry(k, teams[k]);
      });
    }
    return map;
  }

  function resolveTeam(rawVal, fallbackName, teamsMap) {
    var raw = rawVal != null ? String(rawVal).trim() : "";
    var fb = fallbackName != null ? String(fallbackName).trim() : "";
    var entry = (raw && teamsMap[raw]) || (fb && teamsMap[fb]) || null;
    if (entry && entry.name) {
      return { name: entry.name, logo: entry.logo || "" };
    }
    return { name: fb || raw || "Team", logo: "" };
  }

  function collectMatchesForDay(data, day, leagueCode) {
    var seen = Object.create(null);
    var list = [];

    function pushMatch(m, code) {
      if (!m || typeof m !== "object") return;
      var mDay = extractDatePart(m.date || m.utcDate || m.kickoff || m.start_time || "");
      if (mDay && mDay !== day) return;
      var id = String(m.id || m.match_id || m.fixture_id || ((m.home || "") + "_" + (m.away || "") + "_" + mDay));
      if (seen[id]) return;
      var effectiveLeague = String(code || m.league || m.league_id || m.comp || "");
      if (leagueCode && effectiveLeague.trim() !== leagueCode && !matchMatchesLeague(m, leagueCode)) {
        return;
      }
      seen[id] = 1;
      list.push(Object.assign({ _league: effectiveLeague }, m));
    }

    var mbl = (data && data.matches_by_league) || {};
    Object.keys(mbl).forEach(function (code) {
      var bucket = mbl[code];
      if (Array.isArray(bucket)) {
        bucket.forEach(function (m) { pushMatch(m, code); });
      } else if (bucket && typeof bucket === "object") {
        ["yesterday", "today", "tomorrow", "day_after", "upcoming", "results", "matches", "fixtures"].forEach(function (k) {
          if (Array.isArray(bucket[k])) {
            bucket[k].forEach(function (m) { pushMatch(m, code); });
          }
        });
      }
    });

    if (Array.isArray(data && data.matches)) {
      data.matches.forEach(function (m) { pushMatch(m, m.league || m.league_id || ""); });
    }

    return list;
  }

  function render(view) {
    if (!view) return;
    var isAr = getLang() === "ar";
    var leagueCode = getSelectedLeague();
    var offsets = [-1, 0, 1, 2];
    var activeOffset = Number(view.getAttribute("data-today-offset") || "0");
    if (offsets.indexOf(activeOffset) === -1) activeOffset = 0;

    var tabsHtml = offsets.map(function (off) {
      var cls = off === activeOffset ? ' class="on"' : "";
      return '<button type="button" data-off="' + off + '"' + cls + '>' + esc(dayLabel(off, isAr)) + '</button>';
    }).join("");

    var isParaSelected = leagueCode.toLowerCase().indexOf("para") !== -1 || leagueCode === "hlpara";

    view.innerHTML =
      '<div class="wrap">' +
        '<div class="seg" role="tablist">' + tabsHtml + '</div>' +
        (leagueCode
          ? '<p class="note">' + esc(isAr ? ("عرض مباريات الدوري المحدد فقط: " + leagueCode) : ("Filtered by selected league: " + leagueCode)) + '</p>'
          : '') +
        (isParaSelected
          ? '<div class="card" style="margin-bottom:10px;padding:12px;border-color:rgba(250,204,21,.45)">' +
              '<b>♿ ' + esc(isAr ? "بطولات ذوي الهمم (Para Football)" : "Para Football Competitions") + '</b>' +
              '<div style="font-size:12px;margin-top:4px">' +
                '<a href="' + esc(SII_FOOTBALL_URL) + '" target="_blank" rel="noopener noreferrer" style="color:#facc15;font-weight:700">' +
                  esc(isAr ? "فتح بيانات وتفاصيل دوريات المعاقين عبر Sii-Football®" : "Open Para Football data on Sii-Football®") +
                '</a>' +
              '</div>' +
            '</div>'
          : '') +
        '<div id="todayList"><p class="empty">…</p></div>' +
      '</div>';

    view.querySelectorAll(".seg button").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var nextOff = btn.getAttribute("data-off") || "0";
        view.setAttribute("data-today-offset", nextOff);
        try {
          window.dispatchEvent(new CustomEvent("smm:state-change", {
            detail: { dayOffset: Number(nextOff), league: getSelectedLeague(), source: "today" }
          }));
        } catch (e) {}
        render(view);
      });
    });

    fetch("data/static.json", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (data) {
        var box = view.querySelector("#todayList");
        if (!box) return;
        var teamsMap = buildTeamsIndex(data || {});
        var dayStr = isoDay(activeOffset);
        var items = collectMatchesForDay(data || {}, dayStr, leagueCode);

        if (!items.length) {
          var paraHint = isParaSelected
            ? (' <a href="' + esc(SII_FOOTBALL_URL) + '" target="_blank" rel="noopener noreferrer" style="color:#facc15">Sii-Football®</a>')
            : '';
          box.innerHTML = '<p class="empty">' + esc(
            isAr
              ? ("لا توجد مباريات في هذا اليوم" + (leagueCode ? (" للدوري المحدد (" + leagueCode + ").") : "."))
              : ("No matches for this day" + (leagueCode ? (" in selected league (" + leagueCode + ").") : "."))
          ) + paraHint + '</p>';
          return;
        }

        box.innerHTML = items.map(function (m) {
          var homeInfo = resolveTeam(m.home_id || m.homeTeamId || m.home, m.home_name || m.home, teamsMap);
          var awayInfo = resolveTeam(m.away_id || m.awayTeamId || m.away, m.away_name || m.away, teamsMap);
          var hLogo = homeInfo.logo
            ? '<img src="' + esc(homeInfo.logo) + '" alt="" style="width:20px;height:20px;object-fit:contain;vertical-align:middle;margin-inline-end:6px">'
            : '';
          var aLogo = awayInfo.logo
            ? '<img src="' + esc(awayInfo.logo) + '" alt="" style="width:20px;height:20px;object-fit:contain;vertical-align:middle;margin-inline-start:6px">'
            : '';
          var score = (m.hg != null && m.ag != null) ? (esc(m.hg) + " - " + esc(m.ag)) : esc(m.time || m.date || "");
          var lgTag = m._league ? (' <small style="opacity:.7">[' + esc(m._league) + ']</small>') : '';

          return (
            '<div class="card" style="margin-bottom:10px;padding:12px;display:flex;justify-content:space-between;align-items:center;gap:8px">' +
              '<span style="flex:1;text-align:start">' + hLogo + '<b>' + esc(homeInfo.name) + '</b></span>' +
              '<span style="white-space:nowrap;font-weight:700">' + score + lgTag + '</span>' +
              '<span style="flex:1;text-align:end"><b>' + esc(awayInfo.name) + '</b>' + aLogo + '</span>' +
            '</div>'
          );
        }).join("");
      })
      .catch(function () {
        var box = view.querySelector("#todayList");
        if (box) box.innerHTML = '<p class="empty">' + esc(isAr ? "تعذر تحميل المباريات." : "Failed to load matches.") + '</p>';
      });
  }

  window.smmToday = function (view) {
    render(view);
  };

  document.addEventListener("change", function (ev) {
    if (ev && ev.target && ev.target.id === "leagueSel") {
      syncLeagueAcrossControls(ev.target.value || "");
      if ((location.hash || "#/") === "#/today") {
        render(document.getElementById("view"));
      }
    }
  });

  window.addEventListener("smm:state-change", function (ev) {
    var detail = (ev && ev.detail) || {};
    if (detail.source === "today") return;
    if (typeof detail.league === "string") {
      var sel = document.getElementById("leagueSel");
      if (sel && sel.value !== detail.league) sel.value = detail.league;
    }
    if ((location.hash || "#/") === "#/today") {
      render(document.getElementById("view"));
    }
  });

  if (location.hash === "#/today") window.dispatchEvent(new Event("hashchange"));
})();
