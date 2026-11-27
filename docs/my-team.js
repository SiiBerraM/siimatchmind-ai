(function () {
  "use strict";

  var ROUTE_HASH = "#/my-team";
  var STORAGE_KEY = "smm.my_team.v1";

  /* =========================================================
     طبقة الجاهزية المستقبلية للاشتراك والخطط المدفوعة
     حاليًا mode = "free" (كل شيء متاح للمستخدمين).
     مستقبلًا يمكن التبديل إلى "subscription" أو قفل ميزات معينة.
     ========================================================= */
  window.SMM_ACCESS_CONFIG = window.SMM_ACCESS_CONFIG || {
    mode: "free", // "free" | "freemium" | "subscription"
    defaultPlan: "free",
    plans: {
      free: { labelAr: "مجاني", labelEn: "Free", maxPredictionsPerWeek: 999 },
      vip: { labelAr: "اشتراك VIP", labelEn: "VIP Pass", maxPredictionsPerWeek: 999 }
    },
    gatedFeatures: {
      trophyCabinet: false,
      starBadges: false,
      unlimitedPredictions: false,
      transfersIntel: false
    },
    checkoutUrl: "https://www.paypal.com/ncp/payment/LSC7692XCDRK6",
    checkAccess: function (featureKey, userPlan) {
      var cfg = window.SMM_ACCESS_CONFIG;
      if (!cfg || cfg.mode === "free") return { allowed: true, reason: null };
      var plan = userPlan || cfg.defaultPlan || "free";
      if (plan === "vip" || plan === "paid" || plan === "pro") {
        return { allowed: true, reason: null };
      }
      if (cfg.mode === "subscription") {
        return { allowed: false, reason: "subscription_required" };
      }
      if (cfg.gatedFeatures && cfg.gatedFeatures[featureKey]) {
        return { allowed: false, reason: "feature_gated" };
      }
      return { allowed: true, reason: null };
    }
  };

  var cache = { staticData: null, ledgerData: null, newsData: null, promise: null };

  function getLang() {
    try {
      return (localStorage.getItem("smm.lang") || document.documentElement.lang || "ar").slice(0, 2).toLowerCase();
    } catch (e) {
      return "ar";
    }
  }

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function getView() {
    return document.getElementById("view") || document.querySelector("main");
  }

  function fetchJsonSafe(url) {
    return fetch(url, { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  function loadAllData() {
    if (cache.promise) return cache.promise;
    cache.promise = Promise.all([
      fetchJsonSafe("data/static.json"),
      fetchJsonSafe("data/ledger.json"),
      fetchJsonSafe("data/news.json")
    ]).then(function (res) {
      cache.staticData = res[0] || cache.staticData || {};
      cache.ledgerData = res[1] || cache.ledgerData || {};
      cache.newsData = res[2] || cache.newsData || {};
      cache.promise = null;
      return cache;
    });
    return cache.promise;
  }

  function defaultState() {
    var anonId = "Fan#" + String(Math.floor(1000 + Math.random() * 9000));
    return {
      userId: anonId,
      nickname: anonId,
      plan: window.SMM_ACCESS_CONFIG.defaultPlan || "free",
      teamId: "",
      founderPhoto: "icons/founder-my-team.jpg",
      predictions: {},
      leaderboard: [
        { id: "seed_1", name: "Yassine_AI", points: 24, streak: 3, isSelf: false },
        { id: "seed_2", name: "Casa_Ultra", points: 18, streak: 2, isSelf: false },
        { id: "seed_3", name: "Atlas_Scout", points: 12, streak: 1, isSelf: false }
      ]
    };
  }

  function loadState() {
    var base = defaultState();
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return base;
      var parsed = JSON.parse(raw);
      return {
        userId: parsed.userId || base.userId,
        nickname: parsed.nickname || parsed.userId || base.nickname,
        plan: parsed.plan || base.plan,
        teamId: parsed.teamId || "",
        founderPhoto: parsed.founderPhoto || "icons/founder-my-team.jpg",
        predictions: parsed.predictions && typeof parsed.predictions === "object" ? parsed.predictions : {},
        leaderboard: Array.isArray(parsed.leaderboard) && parsed.leaderboard.length ? parsed.leaderboard : base.leaderboard
      };
    } catch (e) {
      return base;
    }
  }

  function saveState(st) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(st));
    } catch (e) {}
  }

  function extractTeams(staticData) {
    if (!staticData) return [];
    if (Array.isArray(staticData.teams) && staticData.teams.length) {
      return staticData.teams.map(function (t, idx) {
        return {
          id: String(t.id || t.code || t.team_id || idx),
          name: String(t.name || t.title || t.team || ("Team " + (idx + 1))),
          league: String(t.league || t.competition || ""),
          logo: String(t.logo || t.crest || ""),
          trophies: Array.isArray(t.trophies) ? t.trophies : (Array.isArray(t.honours) ? t.honours : [])
        };
      });
    }
    if (staticData.teams && typeof staticData.teams === "object") {
      return Object.keys(staticData.teams).map(function (k) {
        var t = staticData.teams[k] || {};
        return {
          id: String(t.id || k),
          name: String(t.name || k),
          league: String(t.league || ""),
          logo: String(t.logo || ""),
          trophies: Array.isArray(t.trophies) ? t.trophies : []
        };
      });
    }
    return [];
  }

  function extractMatches(staticData, ledgerData, teamId) {
    var pools = [];
    [staticData, ledgerData].forEach(function (src) {
      if (!src) return;
      ["matches", "fixtures", "upcoming", "events"].forEach(function (key) {
        if (Array.isArray(src[key])) pools = pools.concat(src[key]);
      });
      if (src.predictions && typeof src.predictions === "object") {
        Object.keys(src.predictions).forEach(function (k) {
          var item = src.predictions[k];
          if (item && typeof item === "object") {
            pools.push(Object.assign({ id: k }, item));
          }
        });
      }
    });

    var seen = Object.create(null);
    var list = [];
    pools.forEach(function (m, i) {
      var id = String(m.id || m.match_id || m.fixture_id || ("m_" + i));
      if (seen[id]) return;
      var hId = String(m.home_id || m.homeTeamId || (m.home && m.home.id) || "");
      var aId = String(m.away_id || m.awayTeamId || (m.away && m.away.id) || "");
      var hName = String(m.home_name || m.homeTeam || (m.home && m.home.name) || m.home || "Home");
      var aName = String(m.away_name || m.awayTeam || (m.away && m.away.name) || m.away || "Away");
      var matchesTeam = !teamId || hId === teamId || aId === teamId || hName === teamId || aName === teamId;
      if (!matchesTeam) return;
      seen[id] = true;
      var actualOutcome = null;
      if (typeof m.home_goals === "number" && typeof m.away_goals === "number") {
        actualOutcome = m.home_goals > m.away_goals ? "H" : (m.home_goals < m.away_goals ? "A" : "D");
      } else if (m.result || m.outcome) {
        actualOutcome = String(m.result || m.outcome).toUpperCase();
      }
      list.push({
        id: id,
        home: hName,
        away: aName,
        date: String(m.date || m.utcDate || m.kickoff || ""),
        actualOutcome: actualOutcome
      });
    });
    return list.slice(0, 12);
  }

  function computePointsAndStars(st, matches) {
    var points = 0;
    var correctCount = 0;
    var streak = 0;
    var bestStreak = 0;

    matches.forEach(function (m) {
      var pick = st.predictions[m.id];
      if (!pick || !m.actualOutcome) return;
      if (pick === m.actualOutcome) {
        points += 3;
        correctCount += 1;
        streak += 1;
        if (streak > bestStreak) bestStreak = streak;
      } else {
        points += 0;
        streak = 0;
      }
    });

    var stars = Math.min(5, Math.floor(points / 6) + (bestStreak >= 2 ? 1 : 0));
    return { points: points, correctCount: correctCount, stars: stars };
  }

  function extractNewsBuckets(newsData, team) {
    var rawItems = [];
    if (Array.isArray(newsData)) rawItems = newsData;
    else if (newsData && Array.isArray(newsData.items)) rawItems = newsData.items;
    else if (newsData && Array.isArray(newsData.news)) rawItems = newsData.news;

    var teamName = team ? team.name.toLowerCase() : "";
    var teamNews = [], playerNews = [], transferNews = [];

    rawItems.forEach(function (item) {
      var title = String(item.title || item.headline || item.text || "");
      var cat = String(item.category || item.type || item.tag || "").toLowerCase();
      var hay = (title + " " + cat).toLowerCase();
      if (teamName && rawItems.length > 6 && hay.indexOf(teamName) === -1 && cat.indexOf("transfer") === -1) {
        return;
      }
      if (cat.indexOf("transfer") !== -1 || hay.indexOf("انتقال") !== -1 || hay.indexOf("transfer") !== -1 || hay.indexOf("mercato") !== -1) {
        transferNews.push(title);
      } else if (cat.indexOf("player") !== -1 || hay.indexOf("لاعب") !== -1 || hay.indexOf("player") !== -1 || hay.indexOf("إصابة") !== -1) {
        playerNews.push(title);
      } else {
        teamNews.push(title);
      }
    });

    return {
      teamNews: teamNews.slice(0, 5),
      playerNews: playerNews.slice(0, 5),
      transferNews: transferNews.slice(0, 5)
    };
  }

  function buildLeaderboard(st, stats) {
    var others = (st.leaderboard || []).filter(function (u) { return !u.isSelf; });
    var selfRow = {
      id: st.userId,
      name: st.nickname || st.userId,
      points: stats.points,
      stars: stats.stars,
      isSelf: true
    };
    return others.concat([selfRow]).sort(function (a, b) {
      return (b.points || 0) - (a.points || 0);
    });
  }

  function injectStyles() {
    if (document.getElementById("smm-my-team-css")) return;
    var s = document.createElement("style");
    s.id = "smm-my-team-css";
    s.textContent = [
      ".mt-wrap{display:flex;flex-direction:column;gap:14px;padding-bottom:24px}",
      ".mt-cabinet{background:linear-gradient(135deg,#0c2240,#13355e);border:1px solid rgba(250,204,21,.45);border-radius:14px;padding:12px 14px}",
      ".mt-cabinet-hd{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px;font-weight:700;color:#facc15}",
      ".mt-trophies{display:flex;flex-wrap:wrap;gap:8px}",
      ".mt-trophy-pill{background:rgba(250,204,21,.12);border:1px solid rgba(250,204,21,.4);color:#fef08a;padding:5px 10px;border-radius:999px;font-size:12px}",
      ".mt-card{background:rgba(15,23,42,.82);border:1px solid rgba(148,163,184,.22);border-radius:14px;padding:14px}",
      ".mt-head-row{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:10px}",
      ".mt-stars{color:#facc15;font-size:18px;letter-spacing:2px}",
      ".mt-form{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}",
      ".mt-form select,.mt-form input{background:#0b1526;color:#f8fafc;border:1px solid rgba(148,163,184,.35);border-radius:10px;padding:8px 10px;font-size:13px}",
      ".mt-match{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px;padding:10px 0;border-bottom:1px solid rgba(148,163,184,.14)}",
      ".mt-match:last-child{border-bottom:none}",
      ".mt-picks{display:flex;gap:6px}",
      ".mt-pick-btn{padding:6px 10px;border-radius:8px;border:1px solid rgba(148,163,184,.3);background:#0b1526;color:#e2e8f0;cursor:pointer;font-size:12px;font-weight:700}",
      ".mt-pick-btn.on{background:#1ed48a;color:#062015;border-color:#1ed48a}",
      ".mt-grid-3{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}",
      ".mt-table{width:100%;border-collapse:collapse;font-size:13px}",
      ".mt-table th,.mt-table td{padding:8px 6px;border-bottom:1px solid rgba(148,163,184,.14);text-align:start}",
      ".mt-self{background:rgba(30,212,138,.12);font-weight:700}",
      ".mt-founder{display:flex;flex-wrap:wrap;gap:14px;align-items:center;background:linear-gradient(135deg,rgba(15,23,42,.95),rgba(20,45,82,.88));border:1px solid rgba(250,204,21,.35);border-radius:14px;padding:14px}",
      ".mt-founder-img{width:84px;height:104px;object-fit:cover;border-radius:12px;border:1.5px solid rgba(250,204,21,.6);flex:none;background:#091324}",
      ".mt-founder-body{flex:1;min-width:220px}",
      ".mt-founder-quote{margin:6px 0 8px;font-size:13.5px;line-height:1.75;color:#f1f5f9}",
      ".mt-founder-sign{font-size:12px;color:#facc15;font-weight:700}"
    ].join("\n");
    document.head.appendChild(s);
  }

  function renderPage(targetView) {
    if (!targetView) return;
    if ((location.hash || "#/") !== ROUTE_HASH) return;
    injectStyles();

    var lang = getLang();
    var isAr = lang === "ar";
    var st = loadState();
    var teams = extractTeams(cache.staticData);
    var selectedTeam = null;
    for (var i = 0; i < teams.length; i++) {
      if (teams[i].id === st.teamId) {
        selectedTeam = teams[i];
        break;
      }
    }
    if (!selectedTeam && teams.length) {
      selectedTeam = teams[0];
      st.teamId = selectedTeam.id;
      saveState(st);
    }

    var matches = extractMatches(cache.staticData, cache.ledgerData, selectedTeam ? selectedTeam.id : "");
    var stats = computePointsAndStars(st, matches);
    var board = buildLeaderboard(st, stats);
    var news = extractNewsBuckets(cache.newsData, selectedTeam);

    var trophies = (selectedTeam && selectedTeam.trophies && selectedTeam.trophies.length)
      ? selectedTeam.trophies
      : (selectedTeam ? [isAr ? ("خزانة ألقاب " + selectedTeam.name) : (selectedTeam.name + " Trophy Cabinet")] : []);

    var starsVisual = stats.stars > 0
      ? Array(stats.stars + 1).join("★") + Array(5 - stats.stars + 1).join("☆")
      : "☆☆☆☆☆";

    var teamOptionsHtml = teams.map(function (t) {
      var sel = selectedTeam && t.id === selectedTeam.id ? " selected" : "";
      return '<option value="' + esc(t.id) + '"' + sel + '>' + esc(t.name) + '</option>';
    }).join("");

    var matchesHtml = matches.length ? matches.map(function (m) {
      var curPick = st.predictions[m.id] || "";
      var statusBadge = "";
      if (m.actualOutcome && curPick) {
        statusBadge = curPick === m.actualOutcome
          ? '<span style="color:#1ed48a;font-weight:700"> (+3 ' + (isAr ? "نقاط" : "pts") + ')</span>'
          : '<span style="color:#f87171"> (0 ' + (isAr ? "نقاط" : "pts") + ')</span>';
      }
      return (
        '<div class="mt-match" data-mid="' + esc(m.id) + '">' +
          '<div><b>' + esc(m.home) + '</b> vs <b>' + esc(m.away) + '</b>' + statusBadge +
            (m.date ? '<div style="font-size:11px;opacity:.75">' + esc(m.date) + '</div>' : '') +
          '</div>' +
          '<div class="mt-picks">' +
            '<button type="button" class="mt-pick-btn' + (curPick === "H" ? " on" : "") + '" data-pick="H">1</button>' +
            '<button type="button" class="mt-pick-btn' + (curPick === "D" ? " on" : "") + '" data-pick="D">X</button>' +
            '<button type="button" class="mt-pick-btn' + (curPick === "A" ? " on" : "") + '" data-pick="A">2</button>' +
          '</div>' +
        '</div>'
      );
    }).join("") : ('<p style="opacity:.75">' + (isAr ? "لا توجد مباريات قادمة مسجلة حاليًا." : "No upcoming matches found.") + '</p>');

    var boardHtml = board.map(function (row, idx) {
      var rowStars = typeof row.stars === "number" ? ("★".repeat(row.stars)) : "";
      return (
        '<tr class="' + (row.isSelf ? "mt-self" : "") + '">' +
          '<td>#' + (idx + 1) + '</td>' +
          '<td>' + esc(row.name) + (row.isSelf ? (isAr ? " (أنت)" : " (You)") : "") + '</td>' +
          '<td>' + esc(row.points) + '</td>' +
          '<td style="color:#facc15">' + esc(rowStars || "-") + '</td>' +
        '</tr>'
      );
    }).join("");

    function renderList(arr, fallback) {
      if (!arr || !arr.length) return '<p style="opacity:.75;font-size:13px">' + esc(fallback) + '</p>';
      return '<ul style="margin:6px 0 0;padding-inline-start:18px;font-size:13px">' +
        arr.map(function (x) { return '<li style="margin-bottom:6px">' + esc(x) + '</li>'; }).join("") +
      '</ul>';
    }

    targetView.innerHTML =
      '<div class="mt-wrap">' +
        '<div class="mt-cabinet">' +
          '<div class="mt-cabinet-hd">' +
            '<span>🏆 ' + (isAr ? "خزانة ألقاب الفريق وكؤوسه" : "Team Trophy Cabinet") + '</span>' +
            '<span style="font-size:12px;opacity:.9">' + (isAr ? "الوضع الحالي: مجاني (جاهز للاشتراكات مستقبلًا)" : "Current Tier: Free (Subscription-Ready)") + '</span>' +
          '</div>' +
          '<div class="mt-trophies">' +
            trophies.map(function (tr) {
              return '<span class="mt-trophy-pill">🏆 ' + esc(typeof tr === "string" ? tr : (tr.title || tr.name || "Cup")) + '</span>';
            }).join("") +
          '</div>' +
        '</div>' +

        '<div class="mt-card">' +
          '<div class="mt-head-row">' +
            '<div>' +
              '<h1 style="margin:0;font-size:20px">' + (isAr ? "فريقي المفضل" : "My Favorite Team") + (selectedTeam ? (" — " + esc(selectedTeam.name)) : "") + '</h1>' +
              '<div style="font-size:12px;opacity:.8;margin-top:4px">' +
                (isAr ? "المعرّف:" : "ID:") + ' <b>' + esc(st.userId) + '</b> • ' +
                (isAr ? "النقاط:" : "Points:") + ' <b>' + stats.points + '</b> • ' +
                (isAr ? "توقعات صحيحة:" : "Correct:") + ' <b>' + stats.correctCount + '</b>' +
              '</div>' +
            '</div>' +
            '<div title="' + (isAr ? "نجوم الإنجاز المعلقة" : "Earned Achievement Stars") + '">' +
              '<div style="font-size:11px;opacity:.8;text-align:center">' + (isAr ? "نجوم الفريق" : "Team Stars") + '</div>' +
              '<div class="mt-stars">' + starsVisual + '</div>' +
            '</div>' +
          '</div>' +

          '<div class="mt-form">' +
            '<input id="mtNickInput" type="text" value="' + esc(st.nickname) + '" placeholder="' + (isAr ? "اسمك / لقبك" : "Your nickname") + '">' +
            '<select id="mtTeamSelect">' + teamOptionsHtml + '</select>' +
            '<button id="mtSaveProfileBtn" type="button" class="mt-pick-btn on">' + (isAr ? "حفظ الفريق والهوية" : "Save Team & ID") + '</button>' +
          '</div>' +
        '</div>' +

        '<div class="mt-card">' +
          '<h2 style="margin:0 0 6px;font-size:16px">' + (isAr ? "توقعات المباريات القادمة" : "Upcoming Match Predictions") + '</h2>' +
          '<div style="font-size:12px;opacity:.75;margin-bottom:8px">' +
            (isAr ? "اختر 1 (فوز المضيف) أو X (تعادل) أو 2 (فوز الضيف): التوقع الصحيح يضيف نقاطًا، والخطأ لا يضيف أي نقاط." : "Pick 1 / X / 2: accurate picks earn points; wrong picks earn 0.") +
          '</div>' +
          matchesHtml +
        '</div>' +

        '<div class="mt-card">' +
          '<h2 style="margin:0 0 8px;font-size:16px">' + (isAr ? "ترتيب المستخدمين" : "Users Leaderboard") + '</h2>' +
          '<table class="mt-table"><thead><tr>' +
            '<th>#</th><th>' + (isAr ? "المستخدم" : "User") + '</th><th>' + (isAr ? "النقاط" : "Points") + '</th><th>' + (isAr ? "النجوم" : "Stars") + '</th>' +
          '</tr></thead><tbody>' + boardHtml + '</tbody></table>' +
        '</div>' +

        '<div class="mt-founder">' +
          '<img id="mtFounderImg" class="mt-founder-img" src="' + esc(st.founderPhoto || "icons/founder-my-team.jpg") + '" alt="Berra" onerror="this.src=\'icons/about.jpg\';this.onerror=null;">' +
          '<div class="mt-founder-body">' +
            '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">' +
              '<b style="color:#facc15;font-size:14px">' + (isAr ? "كلمة لك من مؤسس المنصة" : "A Message From The Founder") + '</b>' +
              '<label style="font-size:11px;cursor:pointer;padding:4px 8px;border-radius:8px;border:1px solid rgba(148,163,184,.35);background:#0b1526;color:#e2e8f0">' +
                (isAr ? "تغيير الصورة محليًا" : "Change Photo") +
                '<input id="mtFounderFile" type="file" accept="image/*" style="display:none">' +
              '</label>' +
            '</div>' +
            '<p class="mt-founder-quote">' +
              (isAr
                ? "«أهلاً بكم في مساحة شغفكم الحقيقي بكرة القدم. اختر فريقك بقلبٍ ينبض بالانتماء، وتوقّع بروح المحلل، واجمع النقاط والنجوم خطوةً بخطوة لتصنع مجدك الخاص داخل التطبيق. نحن هنا لنمنح شغفكم منصة تليق بكم، والقادم أجمل وأرقى بكم ومعكم دائماً.»"
                : "“Welcome to the home of your true football passion. Choose your club with heart, predict like an analyst, and earn points and stars step by step to build your own legacy inside the app.”") +
            '</p>' +
            '<div class="mt-founder-sign">Berra • SiiMatchMind®</div>' +
          '</div>' +
        '</div>' +

        '<div class="mt-card" style="border-color:rgba(250,204,21,.4)">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">' +
          '<b style="color:#facc15;font-size:14px">' +
            (isAr ? '♿ دوريات ذوي الهمم (hlpara) وبيانات Sii-Football®' : '♿ Para Football (hlpara) & Sii-Football®') +
          '</b>' +
          '<a href="https://siiberram.github.io/Sii-Football/" target="_blank" rel="noopener noreferrer" style="color:#1ed48a;font-size:12px;font-weight:700">' +
            (isAr ? 'فتح منصة Sii-Football® ↗' : 'Open Sii-Football® ↗') +
          '</a>' +
        '</div>' +
        '<p style="margin:6px 0 0;font-size:12.5px;opacity:.85">' +
          (isAr ? 'بطولات ذوي الهمم مفعّلة ومدعومة ضمن النظام (hlpara)، ويمكنك متابعة تفاصيلها عبر Sii-Football® وصفحة المباريات حسب اليوم.' : 'Para football competitions (hlpara) are supported here; view full details via Sii-Football®.') +
        '</p>' +
        '</div>' +
        '<div class="mt-grid-3">' +
          '<div class="mt-card"><h3 style="margin:0;font-size:14px">' + (isAr ? "أخبار الفريق" : "Team News") + '</h3>' +
            renderList(news.teamNews, isAr ? "لا توجد أخبار فريق حديثة." : "No recent team news.") + '</div>' +
          '<div class="mt-card"><h3 style="margin:0;font-size:14px">' + (isAr ? "أخبار اللاعبين" : "Players News") + '</h3>' +
            renderList(news.playerNews, isAr ? "لا توجد أخبار لاعبين حديثة." : "No recent player news.") + '</div>' +
          '<div class="mt-card"><h3 style="margin:0;font-size:14px">' + (isAr ? "الانتقالات" : "Transfers") + '</h3>' +
            renderList(news.transferNews, isAr ? "لا توجد أخبار انتقالات حديثة." : "No recent transfer news.") + '</div>' +
        '</div>' +
      '</div>';

    var fileInput = targetView.querySelector("#mtFounderFile");
    if (fileInput) {
      fileInput.onchange = function () {
        var f = fileInput.files && fileInput.files[0];
        if (!f || !window.FileReader) return;
        var reader = new FileReader();
        reader.onload = function (ev) {
          var nextSt = loadState();
          nextSt.founderPhoto = String(ev.target && ev.target.result || "");
          saveState(nextSt);
          renderPage(targetView);
        };
        reader.readAsDataURL(f);
      };
    }

    var saveBtn = targetView.querySelector("#mtSaveProfileBtn");
    if (saveBtn) {
      saveBtn.onclick = function () {
        var nickEl = targetView.querySelector("#mtNickInput");
        var teamEl = targetView.querySelector("#mtTeamSelect");
        var nextSt = loadState();
        nextSt.nickname = (nickEl && nickEl.value.trim()) || nextSt.userId;
        nextSt.teamId = teamEl ? teamEl.value : nextSt.teamId;
        saveState(nextSt);
        renderPage(targetView);
      };
    }

    targetView.querySelectorAll(".mt-match").forEach(function (rowEl) {
      var mid = rowEl.getAttribute("data-mid");
      rowEl.querySelectorAll(".mt-pick-btn").forEach(function (btnEl) {
        btnEl.onclick = function () {
          var pick = btnEl.getAttribute("data-pick");
          var nextSt = loadState();
          if (nextSt.predictions[mid] === pick) delete nextSt.predictions[mid];
          else nextSt.predictions[mid] = pick;
          saveState(nextSt);
          renderPage(targetView);
        };
      });
    });
  }

  window.smmMyTeam = function (customView) {
    var target = customView || getView();
    renderPage(target);
    loadAllData().then(function () {
      renderPage(target);
    });
  };

  window.addEventListener("hashchange", function () {
    if ((location.hash || "#/") === ROUTE_HASH) {
      window.smmMyTeam(getView());
    }
  });
})();
