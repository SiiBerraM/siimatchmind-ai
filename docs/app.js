(function () {
  "use strict";
  const view = document.getElementById("view");
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ---------- الترجمة ----------
  // لإضافة لغة: انسخ locales/en.json إلى locales/xx.json وترجمه، ثم أضف اللغة إلى locales/languages.json
  let LANGS = [], DICT = {}, EN = {}, lang = "ar";
  const jget = async p => (await fetch(p)).json();
  async function loadLocale(code) {
    if (window.SMM_LOCALES && window.SMM_LOCALES[code]) return window.SMM_LOCALES[code];
    return jget("locales/" + code + ".json");
  }
  function t(key, params) {
    let s = DICT[key] != null ? DICT[key] : (EN[key] != null ? EN[key] : key);
    if (params) s = s.replace(/\{(\w+)\}/g, (m, k) => params[k] != null ? params[k] : m);
    return s;
  }
  const loc = () => lang === "ar" ? "ar-u-nu-latn" : lang;
  const pct = x => (x * 100).toFixed(1).replace(/\.0$/, "") + "%";
  const fmtDate = s => new Date(s + "T12:00:00").toLocaleDateString(loc(), { weekday: "short", day: "numeric", month: "short" });
  const errText = e => e && e.code ? t("err." + e.code, e.params) : (e && e.message) || t("err.generic");

  // ---------- الشعارات: صورة، وإن فشلت أو غابت فحرف بديل ----------
  const initials = n => (String(n || "?").trim().split(/\s+/).slice(0, 2).map(w => w[0]).join("") || "?").toUpperCase();
  window.__smmPh = el => {
    const s = document.createElement("span");
    s.className = "crest ph"; s.style.cssText = el.style.cssText; s.textContent = initials(el.dataset.n);
    el.replaceWith(s);
  };
  function crest(name, logo, size) {
    const st = size ? ` style="width:${size}px;height:${size}px;font-size:${Math.round(size * 0.38)}px"` : "";
    if (!logo) return `<span class="crest ph"${st}>${esc(initials(name))}</span>`;
    return `<img class="crest"${st} src="${esc(logo)}" alt="" loading="lazy" referrerpolicy="no-referrer" data-n="${esc(name)}" onerror="__smmPh(this)">`;
  }

  // ---------- المظهر ----------
  function applyTheme(th) {
    document.documentElement.dataset.theme = th;
    const m = document.querySelector('meta[name="theme-color"]'); if (m) m.content = th === "light" ? "#f2f6fb" : "#071a33";
    try { localStorage.setItem("smm.theme", th); } catch (e) { }
  }
  function initTheme() {
    let th = null; try { th = localStorage.getItem("smm.theme"); } catch (e) { }
    if (!th) th = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    applyTheme(th);
    document.getElementById("themeBtn").onclick = () => applyTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light");
  }

  // ---------- البيانات: خادم إن وُجد وإلا الملف الثابت ----------
  let mode = "static", ST = null, TEAMS = [], META = null, TOKEN = null, USER = null, LEAGUES = [], LEAGUE = null;
  try { TOKEN = localStorage.getItem("smm.token"); } catch (e) { }

  async function detect() {
    if (location.protocol.indexOf("http") === 0 && !window.SMM_STATIC && !location.hostname.endsWith("github.io")) {
      try {
        const c = new AbortController(), tm = setTimeout(() => c.abort(), 2000);
        const r = await fetch("/api/health", { signal: c.signal });
        clearTimeout(tm);
        if (r.ok) { mode = "api"; return; }
      } catch (e) { /* وضع ثابت */ }
    }
    ST = window.SMM_STATIC || await jget("data/static.json");
  }

  async function call(method, path, body) {
    const h = {};
    if (body) h["Content-Type"] = "application/json";
    if (TOKEN) h["Authorization"] = "Bearer " + TOKEN;
    const r = await fetch(path, { method, headers: h, body: body ? JSON.stringify(body) : undefined });
    let data = null;
    try { data = await r.json(); } catch (e) { }
    if (!r.ok) throw (data && data.error) ? data.error : { code: "generic" };
    return data;
  }
  const get = p => call("GET", p);
  const lq = () => LEAGUE ? "league=" + encodeURIComponent(LEAGUE) : "";

  const api = {
    meta: async () => mode === "api" ? get("/api/meta") : ST.meta,
    leagues: async () => mode === "api" ? get("/api/leagues") : (ST.leagues || []),
    teams: async () => mode === "api" ? get("/api/teams") : ST.teams,
    matches: async k => mode === "api" ? get("/api/matches?kind=" + k + (LEAGUE ? "&" + lq() : "")) : (ST.matches_by_league && LEAGUE ? ((ST.matches_by_league[LEAGUE] || {})[k] || []) : ST.matches[k]),
    team: async id => mode === "api" ? get("/api/teams/" + encodeURIComponent(id)) : (ST.team_detail[id] || Promise.reject({ code: "not_found" })),
    quality: async () => mode === "api" ? get("/api/quality" + (LEAGUE ? "?" + lq() : "")) : ST.quality,
    standings: async () => mode === "api" ? get("/api/standings" + (LEAGUE ? "?" + lq() : "")) : ((ST.standings || {})[LEAGUE] || Object.values(ST.standings || {})[0] || { rows: [] }),
    analyze: async (h, a, mid) => {
      if (mode === "api") return get("/api/analyze?home=" + encodeURIComponent(h) + "&away=" + encodeURIComponent(a) + "&n=10" + (mid ? "&match_id=" + encodeURIComponent(mid) : ""));
      const k = h + "|" + a;
      if (ST.analyses[k]) return ST.analyses[k];
      if (h === a) throw { code: "same_team" };
      const th = (ST.teams || []).find(x => x.id === h), ta = (ST.teams || []).find(x => x.id === a);
      if (!th || !ta) throw { code: "not_found" };
      if (th.league !== ta.league) throw { code: "different_leagues" };
      window.SMM_PACKS = window.SMM_PACKS || {};
      if (!window.SMM_PACKS[th.league]) window.SMM_PACKS[th.league] = await jget("data/analyses/" + th.league + ".json");
      const r = window.SMM_PACKS[th.league][k];
      if (!r) throw { code: "not_found" };
      return r;
    }
  };

  // ---------- المفضلة والسجل والفرق المتابَعة: على الخادم إن سُجّل الدخول وإلا على الجهاز ----------
  const store = {
    read(k) { try { return JSON.parse(localStorage.getItem(k)) || []; } catch (e) { return []; } },
    write(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { } }
  };
  const logged = () => mode === "api" && !!USER;
  const favs = {
    async list() { return logged() ? get("/api/favorites") : store.read("smm.fav"); },
    async toggle(h, a) {
      const cur = await favs.list();
      const has = cur.some(x => x.home === h && x.away === a);
      if (logged()) return has ? call("DELETE", `/api/favorites?home=${h}&away=${a}`) : call("POST", "/api/favorites", { home: h, away: a });
      store.write("smm.fav", has ? cur.filter(x => !(x.home === h && x.away === a)) : [{ home: h, away: a }].concat(cur));
    }
  };
  const follows = {
    async list() { return logged() ? get("/api/fav-teams") : store.read("smm.follow"); },
    async toggle(id) {
      const cur = await follows.list(), has = cur.includes(id);
      if (logged()) return has ? call("DELETE", "/api/fav-teams?team=" + encodeURIComponent(id)) : call("POST", "/api/fav-teams", { team: id });
      store.write("smm.follow", has ? cur.filter(x => x !== id) : [id].concat(cur));
    }
  };
  const hist = {
    async list() { return logged() ? get("/api/history") : store.read("smm.hist"); },
    push(r) {
      if (logged()) return;           // الخادم يسجّل السجل تلقائيًا للمستخدم المسجَّل
      const p = r.prediction.percent;
      const h = store.read("smm.hist").filter(x => !(x.home === r.home.id && x.away === r.away.id));
      h.unshift({ home: r.home.id, away: r.away.id, t: new Date().toISOString().slice(0, 10), p: [p.home, p.draw, p.away] });
      store.write("smm.hist", h.slice(0, 30));
    },
    clear() { store.write("smm.hist", []); }
  };
  const tinfo = id => TEAMS.find(x => x.id === id) || { name: id, logo: null };
  const tname = id => tinfo(id).name;
  const teamsOf = () => LEAGUE ? TEAMS.filter(x => x.league === LEAGUE) : TEAMS;

  // ---------- البطولات: أسماء مترجمة ومرتبة أبجديًا ----------
  const lname = l => DICT["league." + l.code] || EN["league." + l.code] || l.name;
  function fillLeagueSel() {
    const ls = document.getElementById("leagueSel");
    if (!ls) return;
    LEAGUES.sort((a, b) => lname(a).localeCompare(lname(b), lang));
    ls.innerHTML = LEAGUES.map(l => `<option value="${esc(l.code)}">${esc(lname(l))}</option>`).join("");
    ls.value = LEAGUE || ""; ls.hidden = LEAGUES.length < 2;
    ls.setAttribute("aria-label", t("league.label"));
  }

  async function setLang(code) {
    if (!LANGS.some(l => l.code === code)) code = "ar";
    const info = LANGS.find(l => l.code === code);
    DICT = await loadLocale(code);
    lang = code;
    document.documentElement.lang = code;
    document.documentElement.dir = info.dir || "ltr";
    try { localStorage.setItem("smm.lang", code); } catch (e) { }
    document.title = t("app.title");
    document.querySelectorAll(".bar a").forEach(a => a.querySelector("span").textContent = t("nav." + a.dataset.tab));
    document.getElementById("langSel").setAttribute("aria-label", t("lang.label"));
    document.getElementById("themeBtn").setAttribute("aria-label", t("theme.label"));
    fillLeagueSel();
    paintBanner();
  }

  // ---------- مكوّنات العرض ----------
  function paintBanner() {
    const badge = document.getElementById("demoBadge"), note = document.getElementById("demoNote");
    if (!META) return;
    if (META.kind === "demo") {
      badge.hidden = false; badge.textContent = t("badge.demo");
      note.hidden = false; note.textContent = t("note.demo") + (mode === "api" ? "" : " • " + t("note.static"));
      return;
    }
    badge.hidden = true;
    const cur = LEAGUES.find(l => l.code === LEAGUE);
    const arch = cur && cur.source === "api-football" && !cur.current;       // أرشيف: لا مباريات حالية في الخطة المجانية
    let txt = t(arch ? "note.archive" : "note.real", { league: cur ? lname(cur) : (META.league || ""), season: (cur && cur.season) || META.season || "" });
    if (META.updated_at) {
      const d = new Date(META.updated_at);
      if (!isNaN(d)) txt += " • " + t("updated", { when: d.toLocaleString(loc(), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) });
    }
    note.hidden = false; note.textContent = txt;
  }

  function matchCard(m) {
    const played = m.status === "played";
    const mid = played ? `${m.hg} - ${m.ag}` : (m.status === "today" ? (m.time || t("match.today")) : t("match.vs"));
    const tag = m.status === "today" ? t("match.today") : fmtDate(m.date);
    return `<a class="match" href="#/analyze/${esc(m.home)}/${esc(m.away)}/${esc(m.id)}">
      <div class="meta"><span>${tag}${m.status === "scheduled" && m.time ? " • " + esc(m.time) : ""}</span><span>${m.round ? t("match.round", { n: m.round }) : ""}</span></div>
      <div class="row"><div class="tn">${crest(m.home_name, m.home_logo || tinfo(m.home).logo)}<span>${esc(m.home_name)}</span></div><div class="vs ${played ? "" : "pending"}">${mid}</div><div class="tn">${crest(m.away_name, m.away_logo || tinfo(m.away).logo)}<span>${esc(m.away_name)}</span></div></div></a>`;
  }
  const formRow = list => `<div class="form">${list.map(r => `<i class="${r.result}" title="${esc(tname(r.opponent))} ${r.gf}-${r.ga}">${t("res." + r.result)}</i>`).join("")}</div>`;
  const resultsList = list => list.map(r => `<div class="res"><span class="muted">${fmtDate(r.date)}</span><span>${r.venue === "home" ? t("res.home_vs") : t("res.away_at")} ${crest(r.opponent_name || tname(r.opponent), r.opponent_logo || tinfo(r.opponent).logo, 20)}${esc(r.opponent_name || tname(r.opponent))}</span><b>${r.gf} - ${r.ga}</b></div>`).join("");
  const cell = v => v === null || v === undefined ? "—" : v;
  const list = items => `<ul class="plain">${items.map(x => `<li>${x}</li>`).join("")}</ul>`;
  const reasonText = (prefix, r) => t(prefix + r.k, r);
  const skel = () => '<div class="sk"></div>'.repeat(4);

  // ---------- الصفحات ----------
  async function myTeamsBlock() {
    const ids = (await follows.list()).slice(0, 8);
    if (!ids.length) return "";
    const found = [];
    for (const id of ids) { try { const d = await api.team(id); if (d.upcoming && d.upcoming[0]) found.push(d.upcoming[0]); } catch (e) { } }
    const seen = new Set(), uniq = found.filter(m => !seen.has(m.id) && seen.add(m.id));
    uniq.sort((a, b) => (a.date + (a.time || "")).localeCompare(b.date + (b.time || "")));
    return uniq.length ? `<h2>${t("follow.my_matches")}</h2>${uniq.slice(0, 5).map(matchCard).join("")}<h2>${t("home.title")}</h2>` : "";
  }

  async function pageHome(kind) {
    let items;
    if (!kind) {                       // الافتراضي: أول قسم فيه مباريات (اليوم ثم القادمة ثم النتائج)
      for (const k of ["today", "upcoming", "results"]) { items = await api.matches(k); if (items.length) { kind = k; break; } }
      if (!kind) { kind = "today"; items = []; }
    } else items = await api.matches(kind);
    const mine = await myTeamsBlock();
    view.innerHTML = `${mine || `<h1>${t("home.title")}</h1>`}
      <div class="seg" role="tablist">${["today", "upcoming", "results"].map(k => `<button data-k="${k}" class="${k === kind ? "on" : ""}">${t("home." + k)}</button>`).join("")}</div>
      ${items.length ? items.map(matchCard).join("") : `<p class="empty">${t("home.empty")}</p>`}
      <p class="muted">${t("home.hint")}</p>`;
    view.querySelectorAll(".seg button").forEach(b => b.onclick = () => pageHome(b.dataset.k));
  }

  async function pageStandings() {
    const s = await api.standings();
    const rows = s.rows || [];
    const cur = LEAGUES.find(l => l.code === LEAGUE);
    view.innerHTML = `<h1>${t("stand.title")}</h1><p class="muted">${cur ? esc(lname(cur)) : ""}</p>` + (rows.length ? `
      <div class="tblw"><table class="std"><tr><th>#</th><th>${t("stand.team")}</th><th>${t("stand.p")}</th><th>${t("stand.w")}</th><th>${t("stand.d")}</th><th>${t("stand.l")}</th><th>${t("stand.gd")}</th><th>${t("stand.pts")}</th></tr>
      ${rows.map(r => `<tr data-id="${esc(r.team)}"><td class="pos">${r.pos}</td><td class="tm"><div class="tmc">${crest(r.name, r.logo, 24)}<div style="min-width:0"><b>${esc(r.name)}</b><div class="dots">${r.form.map(f => `<i class="${f}"></i>`).join("")}</div></div></div></td>
        <td>${r.p}</td><td>${r.w}</td><td>${r.d}</td><td>${r.l}</td><td dir="ltr">${r.gd > 0 ? "+" + r.gd : r.gd}</td><td class="pts">${r.pts}</td></tr>`).join("")}</table></div>
      <p class="cap">${t("stand.note")}</p>` : `<p class="empty">${t("stand.empty")}</p>`);
    view.querySelectorAll("tr[data-id]").forEach(tr => tr.onclick = () => { location.hash = "#/team/" + tr.dataset.id; });
  }

  const teamOptions = sel => `<option value="">${t("analyze.pick")}</option>` + teamsOf().slice().sort((a, b) => a.name.localeCompare(b.name, lang))
    .map(x => `<option value="${esc(x.id)}" ${x.id === sel ? "selected" : ""}>${esc(x.name)}</option>`).join("");

  function pageAnalyzeForm(h, a, msg) {
    view.innerHTML = `<h1>${t("analyze.title")}</h1>
      <div class="pick">
        <div><label for="selH">${t("analyze.home_label")}</label><select id="selH">${teamOptions(h)}</select></div>
        <div><label for="selA">${t("analyze.away_label")}</label><select id="selA">${teamOptions(a)}</select></div>
        <button class="btn" id="go">${t("analyze.go")}</button>
        ${msg ? `<p class="err">${esc(msg)}</p>` : ""}
      </div>`;
    document.getElementById("go").onclick = () => {
      const hv = document.getElementById("selH").value, av = document.getElementById("selA").value;
      if (!hv || !av) return pageAnalyzeForm(hv, av, t("analyze.err_pick"));
      if (hv === av) return pageAnalyzeForm(hv, av, t("err.same_team"));
      location.hash = `#/analyze/${hv}/${av}`;
    };
  }

  function matrixTable(r) {
    const m = r.prediction.score_matrix, best = r.prediction.most_likely_score;
    let max = 0; m.forEach(row => row.forEach(v => { if (v > max) max = v; }));
    let h = `<table class="mx" aria-label="${t("an.matrix")}"><tr><th></th>${[0, 1, 2, 3, 4, 5].map(j => `<th>${j}</th>`).join("")}</tr>`;
    m.forEach((row, i) => {
      h += `<tr><th>${i}</th>` + row.map((v, j) => `<td class="${i === best.home && j === best.away ? "best" : ""}" style="background:rgba(30,212,138,${(0.08 + 0.8 * v / max).toFixed(2)})">${(v * 100).toFixed(0)}</td>`).join("") + "</tr>";
    });
    return h + `</table><p class="cap">${t("an.matrix_cap", { home: esc(r.home.name), away: esc(r.away.name) })}</p>`;
  }

  function statsTable(r) {
    const s = r.stats;
    const row = (label, k, suf) => `<tr><td>${label}</td><td>${s.home ? cell(s.home[k]) + (s.home[k] != null ? suf : "") : "—"}</td><td>${s.away ? cell(s.away[k]) + (s.away[k] != null ? suf : "") : "—"}</td></tr>`;
    return `<table class="cmp"><tr><th></th><th>${esc(r.home.name)}</th><th>${esc(r.away.name)}</th></tr>
      ${row(t("stat.possession"), "possession", "%")}${row(t("stat.shots"), "shots", "")}${row(t("stat.shots_on"), "shots_on", "")}${row(t("stat.corners"), "corners", "")}</table>
      <p class="cap">${t("stat.cap")}</p>`;
  }

  function contextBlock(r) {
    const c = r.context; if (!c) return "";
    const inj = (c.injuries || []).map(i => `<li>${esc(tname(i.team))}: ${esc(i.player || "?")}${i.reason ? " — " + esc(i.reason) : ""}</li>`).join("");
    const lu = Object.keys(c.lineups || {}).map(id => `<li>${esc(tname(id))} ${c.lineups[id].formation ? "(" + esc(c.lineups[id].formation) + ")" : ""}: ${esc((c.lineups[id].start || []).join("، "))}</li>`).join("");
    return `<h2>${t("an.availability")}</h2>
      ${inj ? `<p class="muted">${t("an.injuries")}</p><ul class="plain">${inj}</ul>` : ""}
      ${lu ? `<p class="muted">${t("an.lineups")}</p><ul class="plain">${lu}</ul>` : ""}
      <p class="cap">${t("an.availability_cap")}</p>`;
  }

  async function shareAnalysis(r) {
    const p = r.prediction.percent;
    const text = t("share.text", { home: r.home.name, away: r.away.name, h: p.home, d: p.draw, a: p.away });
    try { if (navigator.share) { await navigator.share({ title: "SiiMatchMind AI", text, url: location.href }); return; } }
    catch (e) { if (e && e.name === "AbortError") return; }
    try { await navigator.clipboard.writeText(text + " " + location.href); alert(t("share.copied")); }
    catch (e) { prompt("", text + " " + location.href); }
  }

  async function pageAnalysis(h, a, mid) {
    let r;
    try { r = await api.analyze(h, a, mid); } catch (e) { return pageAnalyzeForm(h, a, errText(e)); }
    hist.push(r);
    const isF = (await favs.list()).some(x => x.home === h && x.away === a);
    const p = r.prediction, pc = p.percent, c = r.confidence, ms = p.most_likely_score;
    const fs = r.form_summary, vs = r.venue_split, hh = r.head_to_head, mt = r.match;
    const lvl = { low: 0, mid: 1, good: 2 }[c.level];
    const hl = r.home.logo || tinfo(h).logo, al = r.away.logo || tinfo(a).logo;
    const info = mt ? (mt.status === "played"
      ? `<div class="score-big">${mt.hg} - ${mt.ag}</div><div style="text-align:center"><span class="pill">${t("an.actual")}</span></div>`
      : `<div style="text-align:center"><span class="pill">${t("an.kickoff", { t: esc(fmtDate(mt.date) + (mt.time ? " " + mt.time : "")) })}</span></div>`) : "";
    view.innerHTML = `
      <div class="hero">
        <div class="names"><div class="side">${crest(r.home.name, hl, 48)}<b>${esc(r.home.name)}</b><small>${t("an.host")}</small></div><div class="side">${crest(r.away.name, al, 48)}<b>${esc(r.away.name)}</b><small>${t("an.guest")}</small></div></div>
        ${info}
        <div class="strip" role="img" aria-label="${esc(r.home.name)} ${pc.home}% / ${t("an.draw")} ${pc.draw}% / ${esc(r.away.name)} ${pc.away}%">
          <div class="h" style="flex-basis:${pc.home}%">${pc.home}%</div>
          <div class="d" style="flex-basis:${pc.draw}%">${pc.draw}%</div>
          <div class="a" style="flex-basis:${pc.away}%">${pc.away}%</div></div>
        <div class="legend"><span>${t("an.win", { team: esc(r.home.name) })}</span><span>${t("an.draw")}</span><span>${t("an.win", { team: esc(r.away.name) })}</span></div>
        <div class="kpis">
          <div class="kpi"><b>${ms.home} - ${ms.away}</b><span>${t("an.likely", { p: pct(ms.p) })}</span></div>
          <div class="kpi"><b>${p.expected_goals.home} - ${p.expected_goals.away}</b><span>${t("an.xg")}</span></div>
          <div class="kpi"><b>${pct(p.p_over25)}</b><span>${t("an.over25")}</span></div>
          <div class="kpi"><b>${pct(p.p_btts)}</b><span>${t("an.btts")}</span></div>
        </div>
      </div>
      <div class="row3" style="margin-top:12px">
        <button class="btn ghost" id="fav">${isF ? t("an.unfav") : t("an.fav")}</button>
        <button class="btn ghost" id="share">${t("share.btn")}</button>
        <a class="btn ghost" href="#/analyze">${t("an.another")}</a></div>

      <h2>${t("an.confidence")} <span class="chip c${lvl}">${t("level." + c.level)}</span></h2>
      ${c.reasons.length ? list(c.reasons.map(x => esc(reasonText("conf.", x)))) : `<p class="muted">${t("conf.none")}</p>`}

      <h2>${t("an.why")}</h2>${list(r.reasons.map(x => esc(reasonText("reason.", x))))}
      <h2>${t("an.matrix")}</h2>${matrixTable(r)}

      <h2>${t("an.form", { n: r.form.home.length })}</h2>
      <div>${esc(r.home.name)}${formRow(r.form.home)}</div>
      <div style="margin-top:8px">${esc(r.away.name)}${formRow(r.form.away)}</div>
      <p class="cap">${t("an.form_cap")}</p>

      <h2>${t("an.attdef")}</h2>
      <table class="cmp"><tr><th></th><th>${esc(r.home.name)}</th><th>${esc(r.away.name)}</th></tr>
        <tr><td>${t("an.gf")}</td><td>${cell(fs.home.avg_gf)}</td><td>${cell(fs.away.avg_gf)}</td></tr>
        <tr><td>${t("an.ga")}</td><td>${cell(fs.home.avg_ga)}</td><td>${cell(fs.away.avg_ga)}</td></tr>
        <tr><td>${t("an.cs")}</td><td>${fs.home.clean_sheets}</td><td>${fs.away.clean_sheets}</td></tr>
        <tr><td>${t("an.fts")}</td><td>${fs.home.failed_to_score}</td><td>${fs.away.failed_to_score}</td></tr>
        <tr><td>${t("an.at_home")}</td><td>${vs.home_at_home.w}-${vs.home_at_home.d}-${vs.home_at_home.l}</td><td>—</td></tr>
        <tr><td>${t("an.away_away")}</td><td>—</td><td>${vs.away_away.w}-${vs.away_away.d}-${vs.away_away.l}</td></tr></table>

      ${r.stats ? `<h2>${t("stat.title")}</h2>${statsTable(r)}` : ""}

      <h2>${t("an.h2h")}</h2>
      ${hh.count ? `<p class="muted">${t("an.h2h_sum", { n: hh.count, a: esc(r.home.name), wa: hh.wins_a, d: hh.draws, b: esc(r.away.name), wb: hh.wins_b })}</p>` +
        hh.matches.map(m => `<div class="res"><span class="muted">${fmtDate(m.date)}</span><span>${esc(tname(m.home))} ${t("res.home_vs")} ${esc(tname(m.away))}</span><b>${m.hg} - ${m.ag}</b></div>`).join("")
        : `<p class="muted">${t("an.h2h_none")}</p>`}
      <p class="cap">${t("an.h2h_cap")}</p>
      ${contextBlock(r)}
      <h2>${t("an.missing")}</h2>${list(r.missing_data.map(x => esc(reasonText("missing.", x))))}
      <p class="disc">${t("disclaimer")}${r.data_kind === "demo" ? " " + t("disclaimer.demo") : ""}</p>`;
    document.getElementById("fav").onclick = async () => { await favs.toggle(h, a); pageAnalysis(h, a, mid); };
    document.getElementById("share").onclick = () => shareAnalysis(r);
  }

  async function pageTeams(q) {
    q = (q || "").trim();
    const items = q ? teamsOf().filter(x => x.name.toLowerCase().indexOf(q.toLowerCase()) >= 0) : teamsOf();
    view.innerHTML = `<h1>${t("teams.title")}</h1><input type="search" id="q" placeholder="${t("teams.search")}" value="${esc(q)}" aria-label="${t("teams.search")}">
      <div id="tl">${items.length ? items.map(x => `<a class="tl" href="#/team/${esc(x.id)}"><span class="nm">${crest(x.name, x.logo)}<span>${esc(x.name)}</span></span><span class="muted">${t("teams.view")}</span></a>`).join("") : `<p class="empty">${t("teams.none")}</p>`}</div>`;
    const inp = document.getElementById("q");
    inp.oninput = () => { const v = inp.value; pageTeams(v).then(() => { const n = document.getElementById("q"); n.focus(); n.setSelectionRange(v.length, v.length); }); };
  }

  async function pageTeam(id) {
    let d;
    try { d = await api.team(id); } catch (e) { view.innerHTML = `<p class="err">${esc(errText(e))}</p>`; return; }
    const s = d.summary, st = d.strength, on = (await follows.list()).includes(id);
    const sr = d.stats ? `<h2>${t("stat.title")}</h2><table class="cmp"><tr><td>${t("stat.possession")}</td><td>${cell(d.stats.possession)}%</td></tr><tr><td>${t("stat.shots")}</td><td>${cell(d.stats.shots)}</td></tr><tr><td>${t("stat.shots_on")}</td><td>${cell(d.stats.shots_on)}</td></tr><tr><td>${t("stat.corners")}</td><td>${cell(d.stats.corners)}</td></tr></table><p class="cap">${t("stat.cap")}</p>` : `<p class="cap">${t("stat.none")}</p>`;
    view.innerHTML = `<div class="team-head">${crest(d.team.name, d.team.logo || tinfo(id).logo, 52)}<h1>${esc(d.team.name)}</h1><button class="star ${on ? "on" : ""}" id="fol">${on ? "★ " + t("follow.unfollow") : "☆ " + t("follow.follow")}</button></div>
      <table class="cmp"><tr><th></th><th>${t("team.last10")}</th><th>${t("team.home")}</th><th>${t("team.away")}</th></tr>
        <tr><td>${t("team.wdl")}</td><td>${s.w}-${s.d}-${s.l}</td><td>${d.home.w}-${d.home.d}-${d.home.l}</td><td>${d.away.w}-${d.away.d}-${d.away.l}</td></tr>
        <tr><td>${t("an.gf")}</td><td>${cell(s.avg_gf)}</td><td>${cell(d.home.avg_gf)}</td><td>${cell(d.away.avg_gf)}</td></tr>
        <tr><td>${t("an.ga")}</td><td>${cell(s.avg_ga)}</td><td>${cell(d.home.avg_ga)}</td><td>${cell(d.away.avg_ga)}</td></tr></table>
      <p class="cap">${t("team.strength", { att: st.attack.toFixed(2), def: st.defense.toFixed(2) })}</p>
      <h2>${t("team.results")}</h2>${formRow(d.last_results)}${resultsList(d.last_results)}
      <h2>${t("team.upcoming")}</h2>${d.upcoming.length ? d.upcoming.map(matchCard).join("") : `<p class="muted">${t("team.no_upcoming")}</p>`}
      ${sr}`;
    document.getElementById("fol").onclick = async () => { await follows.toggle(id); pageTeam(id); };
  }

  async function accountBlock() {
    if (mode !== "api") return `<p class="cap">${t("acct.needs_server")}</p>`;
    if (USER) return `<div class="tl"><span>${esc(USER.email)}</span><button class="btn ghost" id="logout" style="width:auto;padding:6px 14px">${t("acct.logout")}</button></div>
      <button class="btn ghost" id="delacct" style="margin-top:10px;color:var(--red)">${t("acct.delete")}</button>`;
    return `<div class="pick"><p class="muted">${t("acct.intro")}</p>
      <input type="email" id="em" placeholder="${t("acct.email")}" autocomplete="email" aria-label="${t("acct.email")}">
      <input type="password" id="pw" placeholder="${t("acct.password")}" autocomplete="current-password" aria-label="${t("acct.password")}">
      <div class="row2"><button class="btn" id="login">${t("acct.login")}</button><button class="btn ghost" id="register">${t("acct.register")}</button></div>
      <p class="err" id="acctErr"></p></div>`;
  }

  async function authDo(kind) {
    const email = document.getElementById("em").value, password = document.getElementById("pw").value;
    try {
      const r = await call("POST", "/api/auth/" + kind, { email, password });
      TOKEN = r.token; USER = r.user;
      try { localStorage.setItem("smm.token", TOKEN); } catch (e) { }
      await call("POST", "/api/sync", { favorites: store.read("smm.fav"), history: store.read("smm.hist"), teams: store.read("smm.follow") });   // ينقل ما حُفظ على الجهاز
      pageSaved();
    } catch (e) { document.getElementById("acctErr").textContent = errText(e); }
  }

  async function pageSaved() {
    const f = await favs.list(), h = await hist.list(), fl = await follows.list();
    const link = x => `<a class="tl" href="#/analyze/${esc(x.home)}/${esc(x.away)}"><span class="nm">${crest(tname(x.home), tinfo(x.home).logo, 22)}${crest(tname(x.away), tinfo(x.away).logo, 22)}<span>${esc(tname(x.home))} ${t("res.home_vs")} ${esc(tname(x.away))}</span></span><span class="muted">${x.p ? x.p.join("/") + "% • " + x.t : t("saved.analysis")}</span></a>`;
    const tl = id => `<a class="tl" href="#/team/${esc(id)}"><span class="nm">${crest(tname(id), tinfo(id).logo, 24)}<span>${esc(tname(id))}</span></span><span class="muted">★</span></a>`;
    view.innerHTML = `<h1>${t("saved.title")}</h1>
      <h2>${t("acct.title")}</h2>${await accountBlock()}
      ${fl.length ? `<h2>${t("follow.unfollow")}</h2>${fl.map(tl).join("")}` : ""}
      <h2>${t("saved.fav")}</h2>${f.length ? f.map(link).join("") : `<p class="muted">${t("saved.fav_empty")}</p>`}
      <h2>${t("saved.hist")}</h2>
      ${h.length ? h.map(link).join("") + (logged() ? "" : `<button class="btn ghost" id="clr" style="margin-top:12px">${t("saved.clear")}</button>`) : `<p class="muted">${t("saved.hist_empty")}</p>`}
      <p class="cap">${logged() ? t("saved.cap_server") : t("saved.cap_local")}</p>
      <a class="tl" href="#/quality" style="margin-top:14px"><span>${t("saved.quality")}</span><span class="muted">›</span></a>
      <p class="cap"><a href="/privacy.html" target="_blank" rel="noopener">${t("legal.privacy")}</a> • <a href="/terms.html" target="_blank" rel="noopener">${t("legal.terms")}</a></p>`;
    const g = id => document.getElementById(id);
    if (g("delacct")) g("delacct").onclick = async () => {
      const pw = prompt(t("acct.delete_prompt"));
      if (!pw) return;
      try {
        await call("POST", "/api/auth/delete", { password: pw });
        TOKEN = null; USER = null; try { localStorage.removeItem("smm.token"); } catch (e) { }
        alert(t("acct.deleted")); pageSaved();
      } catch (e) { alert(errText(e)); }
    };
    if (g("clr")) g("clr").onclick = () => { hist.clear(); pageSaved(); };
    if (g("login")) { g("login").onclick = () => authDo("login"); g("register").onclick = () => authDo("register"); }
    if (g("logout")) g("logout").onclick = async () => {
      try { await call("POST", "/api/auth/logout", {}); } catch (e) { }
      TOKEN = null; USER = null; try { localStorage.removeItem("smm.token"); } catch (e) { }
      pageSaved();
    };
  }

  async function pageQuality() {
    const q = await api.quality();
    if (!q.available) { view.innerHTML = `<h1>${t("q.title")}</h1><p class="empty">${t("q.unavailable")}</p>`; return; }
    const better = q.model.brier < q.baseline.brier;
    view.innerHTML = `<h1>${t("q.title")}</h1>
      <p class="muted">${q.data_kind === "demo" ? t("q.note_demo") : t("q.note_real")}</p>
      <h2>${t("q.tested", { n: q.tested_matches })}</h2>
      <table class="cmp"><tr><th></th><th>${t("q.model")}</th><th>${t("q.baseline")}</th></tr>
        <tr><td>${t("q.brier")}</td><td>${q.model.brier}</td><td>${q.baseline.brier}</td></tr>
        <tr><td>${t("q.logloss")}</td><td>${q.model.log_loss}</td><td>${q.baseline.log_loss}</td></tr>
        <tr><td>${t("q.acc")}</td><td>${pct(q.model.accuracy)}</td><td>${pct(q.baseline.accuracy)}</td></tr></table>
      <p class="cap">${t("q.explain", { u: q.uniform_brier })} ${better ? t("q.better") : t("q.notbetter")}</p>
      <h2>${t("q.calib")}</h2>
      <table class="cmp"><tr><th>${t("q.range")}</th><th>${t("q.count")}</th><th>${t("q.pred")}</th><th>${t("q.obs")}</th></tr>
        ${q.calibration.map(b => `<tr><td>${b.range}</td><td>${b.count}</td><td>${pct(b.predicted)}</td><td>${pct(b.observed)}</td></tr>`).join("")}</table>
      <p class="cap">${t("q.calib_cap", { e: pct(q.calibration_error) })}</p>`;
  }

  // ---------- التوجيه ----------
  const routes = [
    [/^#\/analyze\/([\w-]+)\/([\w-]+)(?:\/([\w-]+))?$/, "analyze", m => pageAnalysis(m[1], m[2], m[3])],
    [/^#\/analyze$/, "analyze", () => pageAnalyzeForm()],
    [/^#\/team\/([\w-]+)$/, "teams", m => pageTeam(m[1])],
    [/^#\/teams$/, "teams", () => pageTeams()],
    [/^#\/standings$/, "standings", () => pageStandings()],
    [/^#\/saved$/, "saved", () => pageSaved()],
    [/^#\/quality$/, "saved", () => pageQuality()],
    [/^#?\/?$/, "home", () => pageHome()]
  ];

  async function route() {
    const hash = location.hash || "#/";
    for (const [re, tab, fn] of routes) {
      const m = hash.match(re);
      if (m) {
        document.querySelectorAll(".bar a").forEach(a => a.classList.toggle("on", a.dataset.tab === tab));
        view.innerHTML = skel();
        try { await fn(m); } catch (e) { view.innerHTML = `<p class="err">${esc(errText(e))}</p>`; }
        window.scrollTo(0, 0);
        return;
      }
    }
    location.hash = "#/";
  }

  function pickLang() {
    let saved = null; try { saved = localStorage.getItem("smm.lang"); } catch (e) { }
    if (saved && LANGS.some(l => l.code === saved)) return saved;
    const nav = (navigator.language || "ar").slice(0, 2).toLowerCase();
    return LANGS.some(l => l.code === nav) ? nav : "ar";
  }

  async function init() {
    try {
      initTheme();
      LANGS = window.SMM_LANGS || await jget("locales/languages.json");
      EN = window.SMM_LOCALES ? window.SMM_LOCALES.en : await jget("locales/en.json");
      const sel = document.getElementById("langSel");
      sel.innerHTML = LANGS.map(l => `<option value="${l.code}">${esc(l.name)}</option>`).join("");
      lang = pickLang(); sel.value = lang;
      await setLang(lang);
      sel.onchange = async () => { await setLang(sel.value); route(); };
      await detect();
      TEAMS = await api.teams();
      META = await api.meta();
      LEAGUES = await api.leagues();
      let savedL = null; try { savedL = localStorage.getItem("smm.league"); } catch (e) { }
      LEAGUE = LEAGUES.some(l => l.code === savedL) ? savedL : null;
      fillLeagueSel();
      if (!LEAGUE && LEAGUES[0]) LEAGUE = LEAGUES[0].code;       // أول بطولة بعد الترتيب الأبجدي
      const ls = document.getElementById("leagueSel"); ls.value = LEAGUE || "";
      ls.onchange = () => { LEAGUE = ls.value; try { localStorage.setItem("smm.league", LEAGUE); } catch (e) { } paintBanner(); if (location.hash && location.hash !== "#/") location.hash = "#/"; else route(); };
      if (mode === "api" && TOKEN) {
        try { USER = (await get("/api/me")).user; } catch (e) { TOKEN = null; try { localStorage.removeItem("smm.token"); } catch (x) { } }
      }
      paintBanner();
      window.addEventListener("hashchange", route);
      await route();
      if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => { });
    } catch (e) {
      view.innerHTML = `<p class="err">${esc(DICT["err.load"] || "تعذّر تحميل البيانات / Could not load data")}<br><small>${esc(e && (e.message || e.code) || "")}</small></p>`;
    }
  }
  init();
})();
