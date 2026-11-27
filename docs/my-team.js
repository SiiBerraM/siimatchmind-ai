/* SiiMatchMind — صفحة «فريقي المفضل» (#/my-team) + تحديات المستخدمين وحساب المالك Berra وقائمة المشتركين أونلاين + دعم hlpara و Sii-Football®. */
(function () {
  "use strict";
  var OWNER_NAME = "Berra";
  var PAYPAL_DONATE_URL = "https://www.paypal.com/donate";
  var SII_FOOTBALL_URL = "https://siiberram.github.io/Sii-Football/";
  var PLATFORM_FEE_RATE = 0.10;
  var SUPABASE_URL = "https://gbvcmlfgoeptaqetsbwg.supabase.co";
  var SUPABASE_KEY = "Sb_publishable_tnRZW4FwUATCGCg0mX0I-Q_2w0h_S8Y";
  var CHALLENGES_ENDPOINT = SUPABASE_URL + "/rest/v1/challenges";
  
  function getSbCfg() {
    var cfg = window.SMM_SUPABASE || {};
    if (!cfg.url || !cfg.key) return null;
    return {
      url: String(cfg.url).replace(/\/+$/, ""),
      key: String(cfg.key),
      table: String(cfg.table || "challenges")
    };
  }
  function sbHeaders(cfg, extra) {
    var h = Object.assign({
      "apikey": cfg.key,
      "Authorization": "Bearer " + cfg.key,
      "Content-Type": "application/json"
    }, extra || {});
    return h;
  }
  function mapRowToChallenge(row) {
    if (!row) return null;
    if (row.payload && typeof row.payload === "object") {
      return Object.assign({}, row.payload, { id: row.payload.id || row.id });
    }
    return {
      id: row.id,
      match_label: row.match_label || "",
      status: row.status || "pending"
    };
  }
  function mapChallengeToRow(ch) {
    var label = ch.match_label || [ch.homeName, ch.awayName].filter(Boolean).join(" vs ") || ch.matchId || ch.id;
    return {
      id: String(ch.id),
      match_label: String(label).slice(0, 200),
      status: String(ch.status || (ch.opponentMatched ? "matched" : "pending")),
      payload: ch
    };
  }
  function sbUpsertChallenge(ch) {
    var cfg = getSbCfg();
    if (!cfg || !ch || !ch.id) return Promise.resolve(false);
    var endpoint = cfg.url + "/rest/v1/" + encodeURIComponent(cfg.table) + "?on_conflict=id";
    return fetch(endpoint, {
      method: "POST",
      headers: sbHeaders(cfg, { "Prefer": "resolution=merge-duplicates,return=minimal" }),
      body: JSON.stringify([mapChallengeToRow(ch)])
    }).then(function (r) { return r.ok; }).catch(function () { return false; });
  }
  function normalizeChallenge(raw) {
    if (!raw || typeof raw !== "object") return null;
    var id = String(raw.id || "").trim();
    if (!id) return null;
    var matchLabel = String(raw.matchLabel || raw.match_label || [raw.homeName, raw.awayName].filter(Boolean).join(" vs ") || raw.matchId || id).trim();
    var stakeNum = Number(raw.stake);
    return Object.assign({}, raw, {
      id: id,
      matchId: raw.matchId || raw.match_id || "",
      matchLabel: matchLabel,
      homeName: String(raw.homeName || raw.home_name || ""),
      awayName: String(raw.awayName || raw.away_name || ""),
      creatorName: String(raw.creatorName || raw.creator_name || "عضو"),
      creatorSide: raw.creatorSide === "away" ? "away" : "home",
      stake: Number.isFinite(stakeNum) && stakeNum > 0 ? stakeNum : 0,
      status: String(raw.status || (raw.opponentMatched ? "matched" : "pending")),
      opponentName: raw.opponentName || raw.opponent_name || "",
      opponentMatched: Boolean(raw.opponentMatched || raw.opponent_matched)
    });
  }
  function mergeChallenges(localList, remoteList) {
    var map = Object.create(null);
    var order = [];
    var lists = [Array.isArray(remoteList) ? remoteList : [], Array.isArray(localList) ? localList : []];
    for (var l = 0; l < lists.length; l++) {
      for (var i = 0; i < lists[l].length; i++) {
        var item = normalizeChallenge(lists[l][i]);
        if (!item) continue;
        if (!map[item.id]) {
          map[item.id] = item;
          order.push(item.id);
        } else {
          map[item.id] = normalizeChallenge(Object.assign({}, map[item.id], item));
        }
      }
    }
    return order.map(function (id) { return map[id]; });
  }
  function sbPullChallenges() {
    var cfg = getSbCfg();
    if (!cfg) return Promise.resolve(null);
    var endpoint = cfg.url + "/rest/v1/" + encodeURIComponent(cfg.table) + "?select=id,match_label,status,payload&limit=100";
    return fetch(endpoint, {
      method: "GET",
      headers: sbHeaders(cfg)
    }).then(function (r) {
      if (!r.ok) return null;
      return r.json();
    }).then(function (rows) {
      if (!Array.isArray(rows)) return null;
      return rows.map(mapRowToChallenge).map(normalizeChallenge).filter(Boolean);
    }).catch(function () { return null; });
  }
  var STORAGE_KEYS = {
    favTeam: "smm.favTeam",
    favLeague: "smm.favLeague",
    sub: "smm.challengeSub",
    onlineMembers: "smm.onlineSubscribers",
    challenges: "smm.userChallenges",
    ownerMode: "smm.ownerMode"
  };
  function getLang() {
    try {
      return (localStorage.getItem("smm.lang") || document.documentElement.lang || "ar").slice(0, 2);
    } catch (e) {
      return "ar";
    }
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
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function readJson(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      if (!raw) return fallback;
      var parsed = JSON.parse(raw);
      return parsed != null ? parsed : fallback;
    } catch (e) {
      return fallback;
    }
  }
  function writeJson(key, val) {
    try {
      localStorage.setItem(key, JSON.stringify(val));
    } catch (e) {}
  }
  function emitState(extra) {
    try {
      window.dispatchEvent(new CustomEvent("smm:state-change", {
        detail: Object.assign({ league: getSelectedLeague(), source: "my-team" }, extra || {})
      }));
    } catch (e) {}
  }
  function sbHeaders(extra) {
    return Object.assign({
      "apikey": SUPABASE_KEY,
      "Authorization": "Bearer " + SUPABASE_KEY,
      "Content-Type": "application/json"
    }, extra || {});
  }
  function serializeChallengeRow(ch) {
    return {
      id: String(ch.id),
      creator_name: String(ch.creatorName || "User"),
      creator_payout: String((ch.creatorMethod || "PayPal") + (ch.creatorAccount ? (": " + ch.creatorAccount) : "")),
      match_label: String(ch.matchLabel || ""),
      team_pick: String(ch.creatorSide === "away" ? (ch.awayName || "Away") : (ch.homeName || "Home")),
      amount: String(ch.stake != null ? ch.stake : 1),
      opponent_name: ch.opponentName ? String(ch.opponentName) : null,
      opponent_payout: ch.opponentAccount
        ? String((ch.opponentMethod || "PayPal") + ": " + ch.opponentAccount)
        : (ch.opponentMethod || null),
      status: ch.opponentMatched ? "matched" : "open",
      updated_at: new Date().toISOString()
    };
  }
  function mergeRowIntoChallenge(row, existingList) {
    var prev = (existingList || []).find(function (item) { return String(item.id) === String(row.id); }) || {};
    var parts = String(row.match_label || "").split(" vs ");
    var homeName = prev.homeName || (parts[0] ? parts[0].trim() : "Home");
    var awayName = prev.awayName || (parts[1] ? parts[1].trim() : "Away");
    var creatorSide = prev.creatorSide || (row.team_pick === awayName ? "away" : "home");
    var stakeNum = Number(row.amount);
    var stake = Number.isFinite(stakeNum) && stakeNum > 0 ? stakeNum : (prev.stake || 1);
    var merged = Object.assign({}, prev, {
      id: String(row.id),
      matchId: prev.matchId || "",
      matchLabel: row.match_label || prev.matchLabel || (homeName + " vs " + awayName),
      homeName: homeName,
      awayName: awayName,
      creatorName: row.creator_name || prev.creatorName || "User",
      creatorMethod: prev.creatorMethod || "PayPal",
      creatorAccount: prev.creatorAccount || "",
      opponentName: row.opponent_name || prev.opponentName || "",
      opponentMethod: prev.opponentMethod || "PayPal",
      opponentAccount: prev.opponentAccount || "",
      opponentMatched: row.status === "matched" || !!prev.opponentMatched,
      creatorSide: creatorSide,
      stake: stake,
      feeRate: prev.feeRate != null ? prev.feeRate : PLATFORM_FEE_RATE,
      createdAt: row.created_at || prev.createdAt || new Date().toISOString()
    });
    if (!merged.inviteCode) {
      merged.inviteCode = makeChallengeCode(merged);
    }
    return merged;
  }
  function fetchChallengesFromSupabase() {
    return fetch(CHALLENGES_ENDPOINT + "?select=*&order=created_at.desc", {
      method: "GET",
      headers: sbHeaders(),
      cache: "no-store"
    })
      .then(function (res) {
        if (!res.ok) throw new Error("Supabase fetch failed: " + res.status);
        return res.json();
      })
      .then(function (rows) {
        if (!Array.isArray(rows)) return null;
        var localList = readJson(STORAGE_KEYS.challenges, []);
        var mapped = rows.map(function (r) { return mergeRowIntoChallenge(r, localList); });
        writeJson(STORAGE_KEYS.challenges, mapped);
        return mapped;
      })
      .catch(function () {
        return null;
      });
  }
  function upsertChallengeToSupabase(ch) {
    var payload = serializeChallengeRow(ch);
    return fetch(CHALLENGES_ENDPOINT + "?on_conflict=id", {
      method: "POST",
      headers: sbHeaders({ "Prefer": "resolution=merge-duplicates,return=representation" }),
      body: JSON.stringify(payload)
    }).catch(function () {
      return null;
    });
  }
  function upsertOnlineMember(subObj) {
    if (!subObj || !subObj.active) return;
    var members = readJson(STORAGE_KEYS.onlineMembers, []);
    var name = (subObj.memberName || "مشترك").trim();
    var method = subObj.payoutMethod || "PayPal";
    var account = (subObj.payoutAccount || "").trim();
    var key = (name + "|" + account).toLowerCase();
    var filtered = members.filter(function (m) {
      return ((String(m.name || "") + "|" + String(m.account || "")).toLowerCase()) !== key;
    });
    filtered.unshift({
      id: "SUB-" + key.replace(/[^a-z0-9\u0600-\u06ff]+/gi, "-").slice(0, 18),
      name: name,
      method: method,
      account: account,
      online: true,
      lastSeen: new Date().toISOString()
    });
    writeJson(STORAGE_KEYS.onlineMembers, filtered.slice(0, 50));
  }
  function buildTeamsMap(data) {
    var map = Object.create(null);
    var teams = data && data.teams;
    if (!teams) return map;
    function add(id, obj) {
      if (!id) return;
      var k = String(id).trim();
      if (!k) return;
      var name = typeof obj === "string" ? obj : (obj && (obj.name || obj.team_name || obj.title || obj.shortName)) || k;
      var logo = typeof obj === "object" && obj ? (obj.logo || obj.crest || obj.image || "") : "";
      map[k] = { id: k, name: name, logo: logo };
      var bare = k.replace(/^[ht]/i, "");
      if (bare && !map[bare]) map[bare] = { id: k, name: name, logo: logo };
    }
    if (Array.isArray(teams)) {
      teams.forEach(function (t) {
        if (t && typeof t === "object") add(t.id || t.team_id || t.code, t);
      });
    } else if (typeof teams === "object") {
      Object.keys(teams).forEach(function (k) { add(k, teams[k]); });
    }
    return map;
  }
  function resolveTeamName(rawId, fallback, teamsMap) {
    var k = rawId != null ? String(rawId).trim() : "";
    var fb = fallback != null ? String(fallback).trim() : "";
    var entry = (k && teamsMap[k]) || (fb && teamsMap[fb]) || null;
    if (entry && entry.name) return entry.name;
    return fb || k || "Team";
  }
  function collectMatches(data, teamsMap, leagueFilter) {
    var list = [];
    var seen = Object.create(null);
    function push(m, lg) {
      if (!m || typeof m !== "object") return;
      var leagueCode = String(lg || m.league || m.league_id || m.comp || "").trim();
      if (leagueFilter && leagueCode !== leagueFilter) return;
      var homeId = String(m.home_id || m.homeTeamId || m.home || "").trim();
      var awayId = String(m.away_id || m.awayTeamId || m.away || "").trim();
      var homeName = resolveTeamName(homeId, m.home_name || m.home, teamsMap);
      var awayName = resolveTeamName(awayId, m.away_name || m.away, teamsMap);
      var matchId = String(m.id || m.match_id || m.fixture_id || (homeId + "_vs_" + awayId + "_" + (m.date || "")));
      if (seen[matchId]) return;
      seen[matchId] = 1;
      var hg = (m.hg != null && m.hg !== "") ? Number(m.hg) : (m.home_goals != null ? Number(m.home_goals) : null);
      var ag = (m.ag != null && m.ag !== "") ? Number(m.ag) : (m.away_goals != null ? Number(m.away_goals) : null);
      list.push({
        id: matchId,
        league: leagueCode,
        date: String(m.date || m.utcDate || "").slice(0, 10),
        time: String(m.time || ""),
        homeId: homeId || homeName,
        awayId: awayId || awayName,
        homeName: homeName,
        awayName: awayName,
        hg: Number.isFinite(hg) ? hg : null,
        ag: Number.isFinite(ag) ? ag : null
      });
    }
    var mbl = (data && data.matches_by_league) || {};
    Object.keys(mbl).forEach(function (code) {
      var bucket = mbl[code];
      if (Array.isArray(bucket)) {
        bucket.forEach(function (m) { push(m, code); });
      } else if (bucket && typeof bucket === "object") {
        ["yesterday", "today", "tomorrow", "day_after", "upcoming", "results", "matches", "fixtures"].forEach(function (k) {
          if (Array.isArray(bucket[k])) bucket[k].forEach(function (m) { push(m, code); });
        });
      }
    });
    if (Array.isArray(data && data.matches)) {
      data.matches.forEach(function (m) { push(m, m.league || m.league_id || ""); });
    }
    return list.slice(0, 120);
  }
  function calcSettlement(stakeAmount, feeRate) {
    var stake = Math.max(0, Number(stakeAmount) || 0);
    var rate = Math.min(0.95, Math.max(0, Number(feeRate != null ? feeRate : PLATFORM_FEE_RATE) || 0));
    var totalPool = +(stake * 2).toFixed(2);
    var feeAmount = +(totalPool * rate).toFixed(2);
    var winnerPayout = +(totalPool - feeAmount).toFixed(2);
    var drawRefundEach = +((stake * (1 - rate))).toFixed(2);
    return {
      stake: stake,
      ratePercent: +(rate * 100).toFixed(1),
      totalPool: totalPool,
      feeAmount: feeAmount,
      winnerPayout: winnerPayout,
      drawRefundEach: drawRefundEach
    };
  }
  function evaluateChallenge(ch, matchObj) {
    if (!matchObj || matchObj.hg == null || matchObj.ag == null) {
      return { status: "pending", outcome: "pending", winnerSide: null };
    }
    var s = calcSettlement(ch.stake, ch.feeRate);
    if (matchObj.hg > matchObj.ag) {
      return {
        status: "settled",
        outcome: "home_win",
        winnerSide: "home",
        winnerName: ch.creatorSide === "home" ? ch.creatorName : (ch.opponentName || "الطرف الثاني"),
        payout: s.winnerPayout,
        fee: s.feeAmount
      };
    }
    if (matchObj.ag > matchObj.hg) {
      return {
        status: "settled",
        outcome: "away_win",
        winnerSide: "away",
        winnerName: ch.creatorSide === "away" ? ch.creatorName : (ch.opponentName || "الطرف الثاني"),
        payout: s.winnerPayout,
        fee: s.feeAmount
      };
    }
    return {
      status: "settled",
      outcome: "draw",
      winnerSide: null,
      refundEach: s.drawRefundEach,
      fee: s.feeAmount
    };
  }
  function makeChallengeCode(ch) {
    var payload = {
      id: ch.id,
      matchId: ch.matchId,
      matchLabel: ch.matchLabel,
      homeName: ch.homeName,
      awayName: ch.awayName,
      creatorSide: ch.creatorSide,
      stake: ch.stake,
      opponentName: ch.opponentName || "",
      owner: OWNER_NAME
    };
    try {
      return "SMM-" + btoa(unescape(encodeURIComponent(JSON.stringify(payload)))).slice(0, 32);
    } catch (e) {
      return ch.id + "-" + ch.stake;
    }
  }
  function render(view) {
    if (!view) return;
    var isAr = getLang() === "ar";
    var leagueCode = getSelectedLeague();
    var favTeam = readJson(STORAGE_KEYS.favTeam, null);
    var sub = readJson(STORAGE_KEYS.sub, { active: false, memberName: "", payoutMethod: "PayPal", payoutAccount: "", plan: "monthly_symbolic" });
    if (sub && sub.active) upsertOnlineMember(sub);
    var onlineMembers = readJson(STORAGE_KEYS.onlineMembers, []);
    var challenges = readJson(STORAGE_KEYS.challenges, []);
    var ownerMode = !!readJson(STORAGE_KEYS.ownerMode, false);
    var isParaSelected = leagueCode.toLowerCase().indexOf("para") !== -1 || leagueCode === "hlpara" ||
      (favTeam && String(favTeam.league || "").toLowerCase().indexOf("para") !== -1);
    view.innerHTML = [
      '<div class="wrap">',
        '<div class="card" style="margin-bottom:12px;padding:14px">',
          '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">',
            '<b>⭐ ' + esc(isAr ? "فريقي المفضل" : "My Favorite Team") + '</b>',
            '<span style="font-size:12px;opacity:.85">' + esc(isAr ? ("المالك الرئيسي: " + OWNER_NAME) : ("Owner Account: " + OWNER_NAME)) + '</span>',
          '</div>',
          '<div id="favTeamBox" style="margin-top:8px">',
            (favTeam
              ? ('<div><b>' + esc(favTeam.name) + '</b>' + (favTeam.league ? (' <small style="opacity:.75">[' + esc(favTeam.league) + ']</small>') : '') + '</div>')
              : ('<p class="note" style="margin:4px 0 0">' + esc(isAr ? "لم تحدد فريقاً مفضلاً بعد. اختر فريقاً من قائمة الفرق أدناه." : "No favorite team selected yet. Pick one below.") + '</p>')
            ),
          '</div>',
          '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">',
            '<select id="favTeamSelect" style="flex:1;min-width:180px;padding:8px;border-radius:8px">',
              '<option value="">' + esc(isAr ? "اختر فريقك المفضل..." : "Select favorite team...") + '</option>',
            '</select>',
            '<button type="button" id="saveFavTeamBtn" class="btn">' + esc(isAr ? "حفظ الفريق" : "Save Team") + '</button>',
            '<button type="button" id="toggleOwnerBtn" class="btn" style="opacity:.85">' +
              esc(ownerMode ? (isAr ? "إخفاء لوحة المالك (Berra)" : "Hide Owner Panel") : (isAr ? "لوحة المالك (Berra)" : "Owner Panel (Berra)")) +
            '</button>',
          '</div>',
        '</div>',
        (isParaSelected
          ? (
              '<div class="card" style="margin-bottom:12px;padding:12px;border-color:rgba(250,204,21,.45)">' +
                '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">' +
                  '<b>♿ ' + esc(isAr ? "بطولات ذوي الهمم (Para Football)" : "Para Football Competitions") + '</b>' +
                  '<a class="btn" href="#/para" style="padding:6px 10px;font-size:12px">' +
                    esc(isAr ? "فتح بيانات وتفاصيل دوريات ذوي الهمم عبر Sii-Football®" : "Open Para Football data on Sii-Football®") +
                  '</a>' +
                '</div>' +
              '</div>'
            )
          : ''
        ),
        '<div class="card" style="margin-bottom:12px;padding:14px">',
          '<b>🎟️ ' + esc(isAr ? "الاشتراك الشهري الرمزي (بدون ربط بريد إلكتروني)" : "Symbolic Monthly Membership (No Email Required)") + '</b>',
          '<p class="note" style="margin:6px 0 10px">' +
            esc(isAr
              ? ("يُحفظ اشتراكك وبياناتك على هاتفك فقط. بعد التفعيل يظهر زر «تحدي المستخدمين» وقائمة المشتركين أونلاين؛ وتُوجَّه المدفوعات إلى حساب المالك (" + OWNER_NAME + ") عبر PayPal.")
              : ("Saved locally on your phone. Once active, User Challenges and the Online Subscribers list appear; payments go to owner " + OWNER_NAME + " via PayPal.")) +
          '</p>',
          '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px">',
            '<input type="text" id="subMemberName" value="' + esc(sub.memberName || "") + '" placeholder="' + esc(isAr ? "اسمك أو لقبك في التحدي" : "Your display name / tag") + '" style="padding:8px;border-radius:8px">',
            '<select id="subPayoutMethod" style="padding:8px;border-radius:8px">',
              '<option value="PayPal"' + (sub.payoutMethod === "PayPal" ? " selected" : "") + '>PayPal</option>',
              '<option value="Bank Card"' + (sub.payoutMethod === "Bank Card" ? " selected" : "") + '>' + esc(isAr ? "بطاقة بنكية (Bank Card)" : "Bank Card") + '</option>',
            '</select>',
            '<input type="text" id="subPayoutAccount" value="' + esc(sub.payoutAccount || "") + '" placeholder="' + esc(isAr ? "حساب PayPal أو رقم/مرجع البطاقة" : "PayPal handle or card ref") + '" style="padding:8px;border-radius:8px">',
          '</div>',
          '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">',
            '<a class="btn" href="#/pay" style="padding:8px 12px">' +
              esc(isAr ? ("دفع الاشتراك الرمزي عبر PayPal (" + OWNER_NAME + ")") : ("Pay Symbolic Fee via PayPal (" + OWNER_NAME + ")")) +
            '</a>',
            '<button type="button" id="activateSubBtn" class="btn">' +
              esc(sub.active ? (isAr ? "تحديث بيانات الاشتراك النشط" : "Update Active Subscription") : (isAr ? "تفعيل الاشتراك الشهري الرمزي" : "Activate Symbolic Monthly Sub")) +
            '</button>',
            (sub.active
              ? ('<button type="button" id="deactivateSubBtn" class="btn" style="opacity:.75">' + esc(isAr ? "إلغاء التفعيل المحلي" : "Deactivate Local") + '</button>')
              : ''
            ),
          '</div>',
          '<p id="subStatusNote" class="note" style="margin:8px 0 0">' +
            (sub.active
              ? ('✅ ' + esc(isAr ? ("الاشتراك مفعل على هذا الهاتف باسم: " + (sub.memberName || "مستخدم") + " | الاستلام عبر: " + (sub.payoutMethod || "PayPal") + " (" + (sub.payoutAccount || "غير محدد") + ")") : ("Active locally for: " + (sub.memberName || "Member"))))
              : ('🔒 ' + esc(isAr ? "زر «تحدي المستخدمين» وقائمة المشتركين أونلاين مخفية حالياً حتى تفعيل الاشتراك الشهري الرمزي." : "User Challenges button and Online Subscribers list are hidden until subscription is activated."))) +
          '</p>',
        '</div>',
        '<div id="challengeGateArea">',
          (sub.active
            ? (
                '<div style="margin-bottom:12px">' +
                  '<button type="button" id="openChallengePanelBtn" class="btn" style="width:100%;padding:12px;font-weight:700;background:#16a34a;color:#fff">' +
                    '⚔️ ' + esc(isAr ? "تحدي المستخدمين (قائمة الأونلاين + مباراة + فريق + مطابقة المبلغ)" : "User Challenges (Online List + Match + Team + Equal Stake)") +
                  '</button>' +
                '</div>' +
                '<div id="challengePanel" class="card" style="margin-bottom:12px;padding:14px">' +
                  '<div style="margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,.12)">' +
                    '<b>🟢 ' + esc(isAr ? "المشتركون أونلاين (اختر شخصاً بالضغط على مؤشر/زر الاختيار)" : "Online Subscribers (Tap indicator/button to pick challenger)") + '</b>' +
                    '<div id="onlineMembersList" style="margin-top:8px;display:grid;gap:6px">' +
                      (onlineMembers.length
                        ? onlineMembers.map(function (m, idx) {
                            return (
                              '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;background:rgba(255,255,255,.04);font-size:12px">' +
                                '<span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#22c55e;margin-inline-end:6px" title="Online"></span><b>' + esc(m.name || (isAr ? "مشترك" : "Member")) + '</b> <small style="opacity:.75">(' + esc(m.method || "PayPal") + ')</small></span>' +
                                '<button type="button" class="btn pickOnlineBtn" data-idx="' + idx + '" style="padding:5px 10px;font-size:11px">' +
                                  '📍 ' + esc(isAr ? "اختيار للتحدي" : "Select") +
                                '</button>' +
                              '</div>'
                            );
                          }).join("")
                        : ('<p class="note" style="margin:4px 0 0">' + esc(isAr ? "لا يوجد مشتركون أونلاين مسجلون بعد." : "No online subscribers yet.") + '</p>')
                      ) +
                    '</div>' +
                  '</div>' +
                  '<b>⚔️ ' + esc(isAr ? "إنشاء أو إرسال تحدٍ بالقيمة" : "Create & Send Challenge With Stake") + '</b>' +
                  '<p class="note" style="margin:6px 0 10px">' +
                    esc(isAr
                      ? ("اختر مباراة وفريقك، واكتب مبلغ التحدي (مثلاً 1). يجب أن يدخل الطرف الثاني نفس المبلغ بالضبط. نسبة التطبيق (" + (PLATFORM_FEE_RATE * 100) + "%) تُخصم آلياً من الفائز أو عند التعادل.")
                      : ("Pick a match and your team, then enter stake amount (e.g. 1). Opponent must match the exact same amount. App fee (" + (PLATFORM_FEE_RATE * 100) + "%) applies on win or draw.")) +
                  '</p>' +
                  '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px">' +
                    '<select id="chMatchSelect" style="padding:8px;border-radius:8px">' +
                      '<option value="">' + esc(isAr ? "جاري تحميل المباريات..." : "Loading matches...") + '</option>' +
                    '</select>' +
                    '<select id="chSideSelect" style="padding:8px;border-radius:8px">' +
                      '<option value="home">' + esc(isAr ? "أختار الفريق الأول (Home)" : "Pick Home Team") + '</option>' +
                      '<option value="away">' + esc(isAr ? "أختار الفريق الثاني (Away)" : "Pick Away Team") + '</option>' +
                    '</select>' +
                    '<input type="number" id="chStakeInput" min="0.5" step="0.5" value="1" placeholder="' + esc(isAr ? "قيمة التحدي ($)" : "Stake amount ($)") + '" style="padding:8px;border-radius:8px">' +
                    '<input type="text" id="chOpponentName" placeholder="' + esc(isAr ? "اسم المتحدَّى من القائمة أو يدوياً" : "Selected or typed opponent") + '" style="padding:8px;border-radius:8px">' +
                  '</div>' +
                  '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">' +
                    '<button type="button" id="createChallengeBtn" class="btn">' + esc(isAr ? "إرسال/إنشاء التحدي وتوليد كود الدعوة" : "Send/Create Challenge & Code") + '</button>' +
                    '<a class="btn" href="#/pay" style="padding:8px 12px">' +
                      esc(isAr ? ("إرسال مبلغ التحدي إلى PayPal (" + OWNER_NAME + ")") : ("Send Stake to PayPal (" + OWNER_NAME + ")")) +
                    '</a>' +
                  '</div>' +
                  '<div id="challengeInviteBox" style="margin-top:10px"></div>' +
                  '<div style="margin-top:12px;padding-top:10px;border-top:1px solid rgba(255,255,255,.12)">' +
                    '<div style="font-size:12px;font-weight:700;margin-bottom:6px">' + esc(isAr ? "قبول تحدٍ من صديق (إلزام مطابقة المبلغ)" : "Accept Friend Challenge (Exact Stake Match Required)") + '</div>' +
                    '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
                      '<input type="text" id="acceptChallengeId" placeholder="' + esc(isAr ? "معرّف التحدي (مثال: CH-...)" : "Challenge ID (e.g. CH-...)") + '" style="flex:1;min-width:150px;padding:8px;border-radius:8px">' +
                      '<input type="number" id="acceptStakeInput" min="0.5" step="0.5" placeholder="' + esc(isAr ? "أدخل نفس المبلغ بالضبط" : "Enter exact same amount") + '" style="width:170px;padding:8px;border-radius:8px">' +
                      '<input type="text" id="acceptOpponentName" placeholder="' + esc(isAr ? "اسمك كمتحدٍ ثانٍ" : "Your opponent name") + '" style="width:160px;padding:8px;border-radius:8px">' +
                      '<button type="button" id="acceptChallengeBtn" class="btn">' + esc(isAr ? "تأكيد ومطابقة المبلغ" : "Match & Join") + '</button>' +
                    '</div>' +
                  '</div>' +
                '</div>'
              )
            : ''
          ),
        '</div>',
        (ownerMode
          ? (
              '<div id="ownerSettlementPanel" class="card" style="margin-bottom:12px;padding:14px;border-color:rgba(56,189,248,.5)">' +
                '<b>👑 ' + esc(isAr ? ("لوحة المالك الرئيسية — " + OWNER_NAME) : ("Owner Settlement Console — " + OWNER_NAME)) + '</b>' +
                '<p class="note" style="margin:6px 0 10px">' +
                  esc(isAr
                    ? "تُعرض هنا التحديات المسجلة على الجهاز مع احتساب صافي المستحق للإرسال للفائز أو لكل طرف عند التعادل بعد خصم عمولة التطبيق."
                    : "Displays recorded challenges with net payout to winner or refund per side on draw after app fee deduction.") +
                '</p>' +
                '<div id="ownerSettlementList"></div>' +
              '</div>'
            )
          : ''
        ),
        '<div class="card" style="padding:14px">',
          '<b>🏆 ' + esc(isAr ? "سجل التحديات الحالية والنتائج" : "Active & Settled Challenges") + '</b>',
          '<div id="challengesList" style="margin-top:8px"></div>',
        '</div>',
      '</div>'
    ].join("");
    var saveFavBtn = view.querySelector("#saveFavTeamBtn");
    var favSel = view.querySelector("#favTeamSelect");
    var toggleOwnerBtn = view.querySelector("#toggleOwnerBtn");
    var activateSubBtn = view.querySelector("#activateSubBtn");
    var deactivateSubBtn = view.querySelector("#deactivateSubBtn");
    if (saveFavBtn && favSel) {
      saveFavBtn.addEventListener("click", function () {
        var opt = favSel.options[favSel.selectedIndex];
        var val = favSel.value;
        if (!val) {
          localStorage.removeItem(STORAGE_KEYS.favTeam);
        } else {
          writeJson(STORAGE_KEYS.favTeam, {
            id: val,
            name: opt ? opt.getAttribute("data-name") || opt.textContent : val,
            league: opt ? opt.getAttribute("data-league") || "" : ""
          });
        }
        emitState({ favTeamId: val });
        render(view);
      });
    }
    if (toggleOwnerBtn) {
      toggleOwnerBtn.addEventListener("click", function () {
        writeJson(STORAGE_KEYS.ownerMode, !ownerMode);
        render(view);
      });
    }
    if (activateSubBtn) {
      activateSubBtn.addEventListener("click", function () {
        var mName = (view.querySelector("#subMemberName") && view.querySelector("#subMemberName").value.trim()) || (isAr ? "مشترك" : "Member");
        var pMethod = (view.querySelector("#subPayoutMethod") && view.querySelector("#subPayoutMethod").value) || "PayPal";
        var pAcc = (view.querySelector("#subPayoutAccount") && view.querySelector("#subPayoutAccount").value.trim()) || "";
        var nextSub = {
          active: true,
          memberName: mName,
          payoutMethod: pMethod,
          payoutAccount: pAcc,
          plan: "monthly_symbolic",
          activatedAt: new Date().toISOString()
        };
        writeJson(STORAGE_KEYS.sub, nextSub);
        upsertOnlineMember(nextSub);
        emitState({ subscriptionActive: true });
        render(view);
      });
    }
    if (deactivateSubBtn) {
      deactivateSubBtn.addEventListener("click", function () {
        writeJson(STORAGE_KEYS.sub, {
          active: false,
          memberName: (view.querySelector("#subMemberName") && view.querySelector("#subMemberName").value.trim()) || "",
          payoutMethod: (view.querySelector("#subPayoutMethod") && view.querySelector("#subPayoutMethod").value) || "PayPal",
          payoutAccount: (view.querySelector("#subPayoutAccount") && view.querySelector("#subPayoutAccount").value.trim()) || "",
          plan: "monthly_symbolic"
        });
        emitState({ subscriptionActive: false });
        render(view);
      });
    }
    view.querySelectorAll(".pickOnlineBtn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var idx = Number(btn.getAttribute("data-idx"));
        var chosen = onlineMembers[idx];
        var oppInput = view.querySelector("#chOpponentName");
        if (chosen && oppInput) {
          oppInput.value = chosen.name || "";
          oppInput.setAttribute("data-payout-method", chosen.method || "PayPal");
          oppInput.setAttribute("data-payout-account", chosen.account || "");
          oppInput.focus();
        }
      });
    });
    fetch("data/static.json", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (data) {
        var teamsMap = buildTeamsMap(data || {});
        var matches = collectMatches(data || {}, teamsMap, leagueCode);
        if (!matches.length && leagueCode) {
          matches = collectMatches(data || {}, teamsMap, "");
        }
        if (favSel) {
          var currentFavId = favTeam && favTeam.id ? String(favTeam.id) : "";
          var teamEntries = [];
          Object.keys(teamsMap).forEach(function (k) {
            var item = teamsMap[k];
            if (item && item.id === k) teamEntries.push(item);
          });
          teamEntries.sort(function (a, b) { return String(a.name).localeCompare(String(b.name)); });
          favSel.innerHTML =
            '<option value="">' + esc(isAr ? "اختر فريقك المفضل..." : "Select favorite team...") + '</option>' +
            teamEntries.slice(0, 400).map(function (t) {
              var selAttr = t.id === currentFavId ? " selected" : "";
              return '<option value="' + esc(t.id) + '" data-name="' + esc(t.name) + '" data-league="' + esc(t.league || "") + '"' + selAttr + '>' +
                esc(t.name) + (t.league ? (' [' + esc(t.league) + ']') : '') +
              '</option>';
            }).join("");
        }
        var matchSel = view.querySelector("#chMatchSelect");
        var sideSel = view.querySelector("#chSideSelect");
        var stakeInp = view.querySelector("#chStakeInput");
        var calcBox = view.querySelector("#chCalcPreview");
        var createBtn = view.querySelector("#createChallengeBtn");
        var openPanelBtn = view.querySelector("#openChallengePanelBtn");
        var panelEl = view.querySelector("#challengePanel");
        if (openPanelBtn && panelEl) {
          openPanelBtn.addEventListener("click", function () {
            var hidden = panelEl.style.display === "none";
            panelEl.style.display = hidden ? "" : "none";
          });
        }
        if (matchSel) {
          matchSel.innerHTML = matches.length
            ? matches.map(function (m) {
                return '<option value="' + esc(m.id) + '">' +
                  esc(m.homeName + " vs " + m.awayName + (m.date ? (" (" + m.date + ")") : "")) +
                '</option>';
              }).join("")
            : ('<option value="">' + esc(isAr ? "لا توجد مباريات متاحة حالياً" : "No matches available") + '</option>');
        }
        function refreshSideLabelsAndCalc() {
          var selectedMatch = matches.find(function (m) { return m.id === (matchSel && matchSel.value); }) || matches[0];
          if (sideSel && selectedMatch) {
            var prevVal = sideSel.value || "home";
            sideSel.innerHTML =
              '<option value="home"' + (prevVal === "home" ? " selected" : "") + '>' + esc((isAr ? "الفريق الأول: " : "Home: ") + selectedMatch.homeName) + '</option>' +
              '<option value="away"' + (prevVal === "away" ? " selected" : "") + '>' + esc((isAr ? "الفريق الثاني: " : "Away: ") + selectedMatch.awayName) + '</option>';
          }
          if (calcBox) {
            var s = calcSettlement(stakeInp ? stakeInp.value : 1, PLATFORM_FEE_RATE);
            calcBox.innerHTML = isAr
              ? ('قيمة كل طرف: <b>$' + s.stake + '</b> (يجب أن يدفع الطرف الثاني نفس القيمة <b>$' + s.stake + '</b>) | ' +
                 'إجمالي الرهان: <b>$' + s.totalPool + '</b> | عمولة التطبيق (' + s.ratePercent + '%): <b>$' + s.feeAmount + '</b><br>' +
                 '🏆 عند الفوز يستلم الفائز: <b>$' + s.winnerPayout + '</b> | 🤝 عند التعادل يسترد كل طرف: <b>$' + s.drawRefundEach + '</b>')
              : ('Each side stake: <b>$' + s.stake + '</b> (exact match required) | Pool: <b>$' + s.totalPool + '</b> | Fee (' + s.ratePercent + '%): <b>$' + s.feeAmount + '</b><br>' +
                 '🏆 Winner net payout: <b>$' + s.winnerPayout + '</b> | 🤝 Draw refund each: <b>$' + s.drawRefundEach + '</b>');
          }
        }
        refreshSideLabelsAndCalc();
        if (matchSel) matchSel.addEventListener("change", refreshSideLabelsAndCalc);
        if (stakeInp) stakeInp.addEventListener("input", refreshSideLabelsAndCalc);
        if (createBtn) {
          createBtn.addEventListener("click", function () {
            var mObj = matches.find(function (m) { return m.id === (matchSel && matchSel.value); }) || matches[0];
            var stakeVal = Number(stakeInp && stakeInp.value);
            if (!mObj || !Number.isFinite(stakeVal) || stakeVal <= 0) return;
            var sideVal = (sideSel && sideSel.value) || "home";
            var oppInput = view.querySelector("#chOpponentName");
            var oppName = (oppInput && oppInput.value.trim()) || "";
            var oppMethod = (oppInput && oppInput.getAttribute("data-payout-method")) || "PayPal";
            var oppAccount = (oppInput && oppInput.getAttribute("data-payout-account")) || "";
            var newCh = {
              id: "CH-" + Date.now().toString(36).toUpperCase(),
              matchId: mObj.id,
              matchLabel: mObj.homeName + " vs " + mObj.awayName,
              homeName: mObj.homeName,
              awayName: mObj.awayName,
              creatorName: sub.memberName || (isAr ? "مستخدم" : "User"),
              creatorMethod: sub.payoutMethod || "PayPal",
              creatorAccount: sub.payoutAccount || "",
              opponentName: oppName,
              opponentMethod: oppMethod,
              opponentAccount: oppAccount,
              opponentMatched: false,
              creatorSide: sideVal,
              stake: stakeVal,
              feeRate: PLATFORM_FEE_RATE,
              createdAt: new Date().toISOString()
            };
            newCh.inviteCode = makeChallengeCode(newCh);
            var updated = [newCh].concat(readJson(STORAGE_KEYS.challenges, []));
            writeJson(STORAGE_KEYS.challenges, updated);
          sbUpsertChallenge(newCh);
            emitState({ challengeCreated: newCh.id });
            render(view);
          });
        }
        var acceptBtn = view.querySelector("#acceptChallengeBtn");
        if (acceptBtn) {
          acceptBtn.addEventListener("click", function () {
            var cid = (view.querySelector("#acceptChallengeId") && view.querySelector("#acceptChallengeId").value.trim()) || "";
            var enteredStake = Number(view.querySelector("#acceptStakeInput") && view.querySelector("#acceptStakeInput").value);
            var oppName = (view.querySelector("#acceptOpponentName") && view.querySelector("#acceptOpponentName").value.trim()) || (sub.memberName || (isAr ? "المتحدي الثاني" : "Opponent"));
            var msgEl = view.querySelector("#acceptMsg");
            var list = readJson(STORAGE_KEYS.challenges, []);
            var target = list.find(function (item) {
              return item.id.toLowerCase() === cid.toLowerCase() || (item.inviteCode && item.inviteCode.toLowerCase() === cid.toLowerCase());
            });
            if (!target) {
              if (msgEl) msgEl.innerHTML = '<span style="color:#f87171">' + esc(isAr ? "لم يتم العثور على التحدي بهذا المعرّف." : "Challenge ID not found.") + '</span>';
              return;
            }
            if (!Number.isFinite(enteredStake) || Math.abs(enteredStake - Number(target.stake)) > 0.0001) {
              if (msgEl) {
                msgEl.innerHTML = '<span style="color:#f87171">' + esc(
                  isAr
                    ? ("يجب إدخال نفس قيمة التحدي بالضبط ($" + target.stake + ") لقبول التحدي.")
                    : ("You must enter the exact same stake amount ($" + target.stake + ").")
                ) + '</span>';
              }
              return;
            }
            target.opponentMatched = true;
            target.opponentName = oppName;
            target.opponentMethod = sub.payoutMethod || "PayPal";
            target.opponentAccount = sub.payoutAccount || "";
            writeJson(STORAGE_KEYS.challenges, list);
          sbUpsertChallenge(target);
            emitState({ challengeAccepted: target.id });
            render(view);
          });
        }
        var matchById = Object.create(null);
        matches.forEach(function (m) { matchById[m.id] = m; });
        var currentChallenges = mergeChallenges(readJson(STORAGE_KEYS.challenges, []), []);
        writeJson(STORAGE_KEYS.challenges, currentChallenges);
        if (!view.__sbPulled) {
          view.__sbPulled = true;
          sbPullChallenges().then(function (remoteList) {
            if (!Array.isArray(remoteList)) return;
            var merged = mergeChallenges(readJson(STORAGE_KEYS.challenges, []), remoteList);
            writeJson(STORAGE_KEYS.challenges, merged);
            if (view && view.isConnected) render(view);
          });
        }
        var listBox = view.querySelector("#challengesList");
        if (listBox) {
          if (!currentChallenges.length) {
            listBox.innerHTML = '<p class="empty">' + esc(isAr ? "لا توجد تحديات مسجلة بعد." : "No challenges recorded yet.") + '</p>';
          } else {
            listBox.innerHTML = currentChallenges.map(function (rawCh) {
              var ch = normalizeChallenge(rawCh);
              if (!ch) return "";
              var mObj = matchById[ch.matchId] || null;
              var ev;
              try {
                ev = evaluateChallenge(ch, mObj) || { status: "pending" };
              } catch (e) {
                ev = { status: "pending" };
              }
              var pickedTeam = ch.creatorSide === "home" ? ch.homeName : ch.awayName;
              var oppTeam = ch.creatorSide === "home" ? ch.awayName : ch.homeName;
              var statusBadge = "";
              if (ev.status === "pending") {
                statusBadge = isAr ? "⏳ بانتظار نتيجة المباراة" : "⏳ Awaiting match result";
              } else if (ev.outcome === "draw") {
                statusBadge = isAr ? ("🤝 تعادل — استرداد $" + ev.refundEach + " لكل طرف (بعد خصم $" + ev.fee + ")") : ("🤝 Draw — $" + ev.refundEach + " refund each");
              } else {
                statusBadge = isAr ? ("🏆 الفائز: " + ev.winnerName + " — صافي المستحق: $" + ev.payout + " (عمولة $" + ev.fee + ")") : ("🏆 Winner: " + ev.winnerName + " — Net: $" + ev.payout);
              }
              return (
                '<div class="card" style="margin-bottom:10px;padding:12px">' +
                  '<div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap">' +
                    '<b>' + esc(ch.matchLabel) + '</b>' +
                    '<span style="font-size:12px;opacity:.85">' + esc(ch.id) + ' | $' + esc(ch.stake) + ' × 2</span>' +
                  '</div>' +
                  '<div style="font-size:12px;margin-top:6px">' +
                    esc(isAr
                      ? (ch.creatorName + " اختار: " + pickedTeam + " | الطرف المنافس (" + (ch.opponentName || "بانتظار الانضمام") + "): " + oppTeam + (ch.opponentMatched ? " [مطابق للمبلغ ✅]" : " [بانتظار مطابقة المبلغ]"))
                      : (ch.creatorName + " picked: " + pickedTeam + " vs " + oppTeam)) +
                  '</div>' +
                  '<div style="font-size:12px;margin-top:4px;font-weight:700">' + esc(statusBadge) + '</div>' +
                  '<div style="font-size:11px;margin-top:6px;opacity:.8;word-break:break-all">' +
                    esc(isAr ? "كود الدعوة: " : "Invite Code: ") + '<code>' + esc(ch.inviteCode || ch.id) + '</code>' +
                  '</div>' +
                '</div>'
              );
            }).join("");
          }
        }
        var paidInp = view.querySelector("#ownerPaidAmountInput");
        var modeSel = view.querySelector("#ownerTxModeSelect");
        var calcRes = view.querySelector("#ownerAutoCalcResult");
        function updateOwnerAutoCalc() {
          if (!calcRes) return;
          var amt = Math.max(0, Number(paidInp && paidInp.value) || 0);
          var mode = (modeSel && modeSel.value) || "refund";
          var rate = PLATFORM_FEE_RATE;
          if (mode === "win_pool") {
            var pool = +(amt * 2).toFixed(2);
            var fee = +(pool * rate).toFixed(2);
            var net = +(pool - fee).toFixed(2);
            calcRes.innerHTML = "المقتطع للتطبيق: $" + fee + " | الواجب إرساله للفائز: $" + net;
          } else if (mode === "draw_pool") {
            var feeEach = +(amt * rate).toFixed(2);
            var refundEach = +(amt - feeEach).toFixed(2);
            calcRes.innerHTML = "المقتطع لكل طرف: $" + feeEach + " | الواجب رده لكل طرف: $" + refundEach;
          } else {
            var feeOne = +(amt * rate).toFixed(2);
            var refundOne = +(amt - feeOne).toFixed(2);
            calcRes.innerHTML = "المقتطع للتطبيق: $" + feeOne + " | الواجب رده للمستخدم: $" + refundOne;
          }
        }
        updateOwnerAutoCalc();
        if (paidInp) paidInp.addEventListener("input", updateOwnerAutoCalc);
        if (modeSel) modeSel.addEventListener("change", updateOwnerAutoCalc);
        var ownerBox = view.querySelector("#ownerSettlementList");
        if (ownerBox) {
          if (!currentChallenges.length) {
            ownerBox.innerHTML = '<p class="empty">' + esc(isAr ? "لا توجد تحديات لتسويتها حالياً." : "No challenges to settle yet.") + '</p>';
          } else {
            ownerBox.innerHTML = currentChallenges.map(function (ch) {
              var mObj = matchById[ch.matchId] || null;
              var ev = evaluateChallenge(ch, mObj);
              var winnerSide = ev.winnerSide;
              var recipientName = "";
              var recipientMethod = "";
              var recipientAcc = "";
              if (winnerSide && winnerSide === ch.creatorSide) {
                recipientName = ch.creatorName;
                recipientMethod = ch.creatorMethod || "PayPal";
                recipientAcc = ch.creatorAccount || (isAr ? "غير مسجل" : "N/A");
              } else if (winnerSide && winnerSide !== ch.creatorSide) {
                recipientName = ch.opponentName || (isAr ? "الطرف الثاني" : "Opponent");
                recipientMethod = ch.opponentMethod || "PayPal";
                recipientAcc = ch.opponentAccount || (isAr ? "غير مسجل" : "N/A");
              }
              var settlementLine = "";
              if (ev.status === "pending") {
                settlementLine = isAr ? "المباراة لم تُحسم بعد في static.json." : "Match result not available yet.";
              } else if (ev.outcome === "draw") {
                settlementLine = isAr
                  ? ("إرجاع $" + ev.refundEach + " إلى " + ch.creatorName + " (" + (ch.creatorMethod || "PayPal") + ": " + (ch.creatorAccount || "-") + ") وإرجاع $" + ev.refundEach + " إلى " + (ch.opponentName || "الطرف الثاني") + " (" + (ch.opponentMethod || "PayPal") + ": " + (ch.opponentAccount || "-") + ") | عمولة المالك (" + OWNER_NAME + "): $" + ev.fee)
                  : ("Refund $" + ev.refundEach + " to each side | Owner fee: $" + ev.fee);
              } else {
                settlementLine = isAr
                  ? ("إرسال $" + ev.payout + " إلى الفائز " + recipientName + " عبر " + recipientMethod + " (" + recipientAcc + ") | عمولة المالك (" + OWNER_NAME + "): $" + ev.fee)
                  : ("Send $" + ev.payout + " to " + recipientName + " via " + recipientMethod + " (" + recipientAcc + ") | Owner fee: $" + ev.fee);
              }
              return (
                '<div style="padding:8px 10px;margin-bottom:8px;border-radius:8px;background:rgba(255,255,255,.04);font-size:12px">' +
                  '<div><b>' + esc(ch.id) + ' — ' + esc(ch.matchLabel) + '</b></div>' +
                  '<div style="margin-top:4px">' + esc(settlementLine) + '</div>' +
                '</div>'
              );
            }).join("");
          }
        }
      })
      .catch(function () {
        var listBox = view.querySelector("#challengesList");
        if (listBox) listBox.innerHTML = '<p class="empty">' + esc(isAr ? "تعذر تحميل بيانات المباريات والفرق." : "Failed to load matches/teams data.") + '</p>';
      });
  }
  view.addEventListener("click", function (ev) {
  var btn = ev.target && ev.target.closest && ev.target.closest("#copyChallengeCodeBtn");
  if (!btn) return;
  var codeEl = view.querySelector("#challengeInviteCode");
  var statusEl = view.querySelector("#copyChallengeCodeStatus");
  var text = (codeEl && (codeEl.value || codeEl.textContent) || "").trim();
  if (!text) return;
  var done = function () { if (statusEl) statusEl.textContent = "تم النسخ ✓"; };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(function () { done(); });
  } else {
    done();
  }
});
window.smmMyTeam = function (view) {
    render(view);
  };
  window.addEventListener("smm:state-change", function (ev) {
    var detail = (ev && ev.detail) || {};
    if (detail.source === "my-team") return;
    if ((location.hash || "#/") === "#/my-team") {
      render(document.getElementById("view"));
    }
  });
  if (location.hash === "#/my-team") window.dispatchEvent(new Event("hashchange"));
})();
