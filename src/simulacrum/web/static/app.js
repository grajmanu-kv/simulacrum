"use strict";
const $ = (s, r = document) => r.querySelector(s);
const state = { sid: null, snap: null, catalog: [], playing: false, busy: false, layer: "terrain", group: "counts",
  pick: null, hover: null, chartT: null, table: false, ecos: [], timer: null };
const css = () => getComputedStyle(document.documentElement);
const cv = (n) => css().getPropertyValue(n).trim();
const human = (k) => { const t = String(k).replace(/:/g, ", ").replace(/_/g, " "); return t.charAt(0).toUpperCase() + t.slice(1); };
const fmt = (v) => (Number.isInteger(v) || Math.abs(v) >= 10) ? String(Math.round(v * 10) / 10) : v.toFixed(2);

/* ---------- api ---------- */
function errText(body, status) {
  if (!body) return "Request failed (" + status + ")";
  const d = body.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.slice(0, 3).map((e) => (e.loc || []).join(".") + ": " + e.msg).join("; ");
  return JSON.stringify(d || body).slice(0, 300);
}
async function api(path, opts) {
  const r = await fetch(path, Object.assign({ headers: { "content-type": "application/json" } }, opts));
  let body = null;
  try { body = await r.json(); } catch (e) { /* non-JSON body */ }
  if (!r.ok) throw new Error(errText(body, r.status));
  return body;
}
function status(msg, isErr) { const s = $("#status"); s.textContent = msg || ""; s.className = isErr ? "err" : ""; }

/* ---------- world lifecycle ---------- */
async function newWorld(inlineSpec) {
  pause();
  status("Generating world...");
  const body = inlineSpec ? { spec: inlineSpec, llm: $("#llm").value } :
    { ecosystem: $("#eco").value, seed: $("#seed").value === "" ? null : Number($("#seed").value), llm: $("#llm").value };
  if (inlineSpec && $("#seed").value !== "") body.seed = Number($("#seed").value);
  try {
    const r = await api("/api/sessions", { method: "POST", body: JSON.stringify(body) });
    Object.assign(state, { sid: r.session, snap: r.snapshot, catalog: r.catalog, pick: null, chartT: null, group: "counts", layer: "terrain" });
    $("#world-title").textContent = r.spec_name === undefined ? "Simulacrum" : (state.ecos.find((e) => e.id === r.spec_name) || { name: r.spec_name }).name;
    $("#world-desc").textContent = r.description || "";
    for (const id of ["play", "step1", "step10", "verify", "download", "p-apply"]) $("#" + id).disabled = false;
    buildLayers(); buildForm(); renderAll();
    status("World ready. Press Play, or Step to advance one tick.");
    return true;
  } catch (e) { status(e.message, true); return false; }
}
function apply(snap) { state.snap = snap; renderAll(); }
async function advance(n) {
  if (state.busy || !state.sid) return;
  state.busy = true;
  try { apply(await api("/api/sessions/" + state.sid + "/step", { method: "POST", body: JSON.stringify({ n }) })); }
  catch (e) { pause(); status(e.message, true); }
  state.busy = false;
}
function play() { state.playing = true; $("#play").textContent = "Pause"; loop(); }
function pause() { state.playing = false; $("#play").textContent = "Play"; clearTimeout(state.timer); }
async function loop() {
  if (!state.playing) return;
  const rate = Number($("#speed").value), t0 = performance.now();
  await advance(rate >= 30 ? 4 : 1);
  if (!state.playing) return;
  const wait = rate >= 30 ? 0 : Math.max(0, 1000 / rate - (performance.now() - t0));
  state.timer = setTimeout(loop, wait);
}

/* ---------- map ---------- */
function typeIndex(name) { return Object.keys(state.snap.types).indexOf(name); }
function typeColor(name) { const i = typeIndex(name); return i < 8 ? cv("--s" + (i + 1)) : cv("--muted"); }
function buildLayers() {
  const box = $("#layers"); box.textContent = "";
  const layers = [["terrain", "Terrain"], ...Object.keys(state.snap.fields).map((f) => ["field:" + f, human(f)]), ["text", "Text"]];
  for (const [id, label] of layers) {
    const b = document.createElement("button"); b.textContent = label; b.setAttribute("aria-pressed", String(state.layer === id));
    b.onclick = () => { state.layer = id; for (const x of box.children) x.setAttribute("aria-pressed", String(x === b)); drawMap(); };
    box.appendChild(b);
  }
}
function shape(g, kind, cx, cy, r, fill, ring, dir) {
  g.beginPath();
  if (dir) {
    const ang = { N: 0, E: Math.PI / 2, S: Math.PI, W: -Math.PI / 2 }[dir] || 0;
    [[0, -r * 1.15], [r * 0.9, r * 0.9], [-r * 0.9, r * 0.9]].forEach(([px, py], i) => {
      const x = cx + px * Math.cos(ang) - py * Math.sin(ang), y = cy + px * Math.sin(ang) + py * Math.cos(ang);
      i ? g.lineTo(x, y) : g.moveTo(x, y);
    });
    g.closePath();
  } else if (kind === 0) g.arc(cx, cy, r, 0, Math.PI * 2);
  else if (kind === 1) { g.moveTo(cx, cy - r * 1.15); g.lineTo(cx + r, cy + r * 0.85); g.lineTo(cx - r, cy + r * 0.85); g.closePath(); }
  else if (kind === 2) g.rect(cx - r * 0.9, cy - r * 0.9, r * 1.8, r * 1.8);
  else if (kind === 3) { g.moveTo(cx, cy - r * 1.2); g.lineTo(cx + r * 1.2, cy); g.lineTo(cx, cy + r * 1.2); g.lineTo(cx - r * 1.2, cy); g.closePath(); }
  else { const w = r * 0.6; [[-w, -r], [w, -r], [w, -w], [r, -w], [r, w], [w, w], [w, r], [-w, r], [-w, w], [-r, w], [-r, -w], [-w, -w]].forEach(([px, py], i) => i ? g.lineTo(cx + px, cy + py) : g.moveTo(cx + px, cy + py)); g.closePath(); }
  g.lineWidth = 2; g.strokeStyle = ring; g.stroke(); g.fillStyle = fill; g.fill();
}
function cellSize() { const s = state.snap; return Math.max(6, Math.min(24, Math.floor(($(".stage").clientWidth || 640) / s.w))); }
function drawMap() {
  const s = state.snap; if (!s) return;
  const text = state.layer === "text";
  $("#map").hidden = text; $("#ascii").hidden = !text;
  if (text) { $("#ascii").textContent = asciiOf(s); return; }
  const cell = cellSize(), dpr = window.devicePixelRatio || 1, W = s.w * cell, H = s.h * cell, c = $("#map");
  if (c.width !== Math.round(W * dpr) || c.height !== Math.round(H * dpr)) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); c.style.width = W + "px"; c.style.height = H + "px"; }
  const g = c.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const isField = state.layer.startsWith("field:");
  const fname = isField ? state.layer.slice(6) : Object.keys(s.fields)[0];
  const farr = fname ? s.fields[fname] : null, finfo = fname ? s.field_info[fname] : null;
  const colors = s.terrain_names.map((n) => s.terrains[n].color), bg = cv("--field");
  for (let y = 0; y < s.h; y++) for (let x = 0; x < s.w; x++) {
    const i = y * s.w + x;
    g.fillStyle = isField ? bg : colors[s.terrain[i]]; g.fillRect(x * cell, y * cell, cell, cell);
    if (farr) { const v = Math.min(1, farr[i] / (finfo.max || 1)); if (v > 0) { g.globalAlpha = (isField ? 1 : 0.55) * v; g.fillStyle = finfo.color; g.fillRect(x * cell, y * cell, cell, cell); g.globalAlpha = 1; } }
  }
  const flag = cv("--flag"), ring = cv("--plate"), ink = cv("--ink");
  g.font = "600 11px system-ui, sans-serif"; g.textBaseline = "alphabetic";
  const seen = new Set(), globalFx = [];
  for (const e of s.effects) {
    const key = e.label + e.x + e.y + e.radius; if (seen.has(key)) continue; seen.add(key);
    if (e.radius < 0 || e.x == null) { globalFx.push(e.label); continue; }
    const cx = e.x * cell + cell / 2, cy = e.y * cell + cell / 2;
    g.setLineDash([5, 4]); g.lineWidth = 2; g.strokeStyle = flag; g.beginPath(); g.arc(cx, cy, Math.max(cell / 2, e.radius * cell + cell / 2), 0, Math.PI * 2); g.stroke(); g.setLineDash([]);
    flagMark(g, cx, cy, flag, cell); haloText(g, e.label, cx + cell * 0.5, cy - cell * 0.9, flag, ring);
  }
  globalFx.forEach((l, i) => haloText(g, "worldwide: " + l, 8, 16 + i * 15, flag, ring));
  const names = Object.keys(s.types);
  for (const a of s.agents) {
    const ti = names.indexOf(a.type), big = s.types[a.type].tier === "llm";
    const r = Math.max(2.5, cell * (big ? 0.46 : 0.32)), cx = a.x * cell + cell / 2, cy = a.y * cell + cell / 2;
    shape(g, ti % 5, cx, cy, r, typeColor(a.type), ring, a.attrs.dir);
  }
  if (cell >= 10) for (const a of s.agents) if (s.types[a.type].tier === "llm" && a.attrs.name) haloText(g, a.attrs.name, a.x * cell + cell / 2 - 14, a.y * cell + cell * 1.9, ink, ring);
  if (state.pick) {
    const cx = state.pick.x * cell + cell / 2, cy = state.pick.y * cell + cell / 2, rad = Number(($("#p-radius") || {}).value);
    if (rad >= 0) { g.setLineDash([3, 4]); g.lineWidth = 1.5; g.strokeStyle = flag; g.beginPath(); g.arc(cx, cy, Math.max(cell / 2, rad * cell + cell / 2), 0, Math.PI * 2); g.stroke(); g.setLineDash([]); }
    flagMark(g, cx, cy, flag, cell, true);
  }
  if (state.hover) { g.lineWidth = 1.5; g.strokeStyle = ink; g.strokeRect(state.hover.x * cell + 0.75, state.hover.y * cell + 0.75, cell - 1.5, cell - 1.5); }
}
function haloText(g, t, x, y, fill, halo) { g.lineWidth = 3; g.strokeStyle = halo; g.strokeText(t, x, y); g.fillStyle = fill; g.fillText(t, x, y); }
function flagMark(g, cx, cy, color, cell, solid) {
  const h = Math.max(12, cell * 1.3);
  g.lineWidth = 2; g.strokeStyle = color; g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx, cy - h); g.stroke();
  g.fillStyle = color; g.beginPath(); g.moveTo(cx, cy - h); g.lineTo(cx + h * 0.6, cy - h * 0.75); g.lineTo(cx, cy - h * 0.5); g.closePath(); g.fill();
  if (solid) { g.beginPath(); g.arc(cx, cy, 2.5, 0, Math.PI * 2); g.fill(); }
}
function asciiOf(s) {
  const grid = [];
  for (let y = 0; y < s.h; y++) { const row = []; for (let x = 0; x < s.w; x++) row.push((s.terrains[s.terrain_names[s.terrain[y * s.w + x]]].glyph || ".")[0]); grid.push(row); }
  for (const a of s.agents) grid[a.y][a.x] = String(a.attrs.glyph || s.types[a.type].glyph || "?")[0];
  const legend = Object.entries(s.types).map(([n, t]) => t.glyph + " = " + n).join("   ");
  return "tick " + s.tick + "\n" + grid.map((r) => r.join("")).join("\n") + "\n" + legend;
}
function cellAt(e) {
  const r = $("#map").getBoundingClientRect(), s = state.snap, cell = r.width / s.w;
  const x = Math.floor((e.clientX - r.left) / cell), y = Math.floor((e.clientY - r.top) / cell);
  return x >= 0 && y >= 0 && x < s.w && y < s.h ? { x, y } : null;
}
function mapTip(e, c) {
  const tip = $("#maptip"), s = state.snap;
  if (!c) { tip.hidden = true; return; }
  tip.textContent = "";
  const add = (cls, txt) => { const d = document.createElement("div"); if (cls) d.className = cls; d.textContent = txt; tip.appendChild(d); return d; };
  const i = c.y * s.w + c.x;
  add("", s.terrain_names[s.terrain[i]] + " at " + c.x + ", " + c.y).style.fontWeight = "650";
  for (const [f, arr] of Object.entries(s.fields)) add("dim", human(f) + ": " + fmt(arr[i]));
  const here = s.agents.filter((a) => a.x === c.x && a.y === c.y);
  for (const a of here.slice(0, 5)) {
    const bits = [a.type]; if (a.attrs.name) bits[0] = a.attrs.name + " (" + a.type + ")";
    for (const k of ["pop", "food", "stance", "trait"]) if (a.attrs[k] !== undefined) bits.push(k + " " + (typeof a.attrs[k] === "number" ? fmt(a.attrs[k]) : a.attrs[k]));
    bits.push("energy " + fmt(a.energy));
    add("", bits.join(", "));
  }
  if (here.length > 5) add("dim", "and " + (here.length - 5) + " more");
  tip.hidden = false;
  const w = $("#mapwrap").getBoundingClientRect();
  let x = e.clientX - w.left + 14, y = e.clientY - w.top + 14;
  if (x + tip.offsetWidth > w.width) x = e.clientX - w.left - tip.offsetWidth - 14;
  if (y + tip.offsetHeight > w.height) y = Math.max(0, w.height - tip.offsetHeight - 4);
  tip.style.left = Math.max(0, x) + "px"; tip.style.top = y + "px";
}
$("#map").addEventListener("pointermove", (e) => { const c = cellAt(e); state.hover = c; mapTip(e, c); drawMap(); });
$("#map").addEventListener("pointerleave", () => { state.hover = null; $("#maptip").hidden = true; drawMap(); });
$("#map").addEventListener("click", (e) => {
  const c = cellAt(e); if (!c) return;
  state.pick = c;
  if ($("#p-x")) $("#p-x").value = c.x; if ($("#p-y")) $("#p-y").value = c.y;
  drawMap();
});

/* ---------- readout, feed, relations, tallies ---------- */
function renderReadout() {
  const s = state.snap, box = $("#readout"); box.textContent = "";
  const t = document.createElement("span"); t.className = "tick"; t.textContent = "Tick " + s.tick; box.appendChild(t);
  for (const [k, v] of Object.entries(s.globals)) { if (k.endsWith("_growth")) continue; const sp = document.createElement("span"); sp.textContent = human(k) + " " + (typeof v === "number" ? fmt(v) : v); box.appendChild(sp); }
}
function renderFeed() {
  const ol = $("#feed"); ol.textContent = "";
  for (const e of state.snap.events.slice().reverse()) {
    const li = document.createElement("li"); li.className = e.kind + " " + e.level;
    const t = document.createElement("span"); t.className = "t"; t.textContent = e.t;
    const x = document.createElement("span"); x.className = "x"; x.textContent = e.text;
    li.append(t, x); ol.appendChild(li);
  }
  if (!ol.children.length) { const li = document.createElement("li"); li.className = "empty"; li.textContent = "Nothing has happened yet. Step the world forward."; ol.appendChild(li); }
}
function renderRelations() {
  const rels = state.snap.relations.slice(0, 8), box = $("#rels"); box.textContent = "";
  $("#relsec").hidden = rels.length === 0;
  for (const r of rels) {
    const row = document.createElement("div"); row.className = "rel";
    const name = document.createElement("span"); name.textContent = r.a_name + " toward " + r.b_name;
    const bar = document.createElement("div"); bar.className = "bar2";
    const fill = document.createElement("div"); fill.className = "fill";
    fill.style.background = r.value < 0 ? "var(--neg)" : "var(--pos)";
    fill.style.left = (r.value < 0 ? 50 + r.value * 50 : 50) + "%"; fill.style.width = Math.abs(r.value) * 50 + "%";
    bar.appendChild(fill);
    const num = document.createElement("span"); num.className = "num"; num.textContent = (r.value > 0 ? "+" : "") + r.value.toFixed(2);
    row.append(name, bar, num); box.appendChild(row);
  }
}
function renderTally() {
  const box = $("#tally"); box.textContent = "";
  const entries = Object.entries(state.snap.counters);
  if (!entries.length) { box.textContent = "No events counted yet."; return; }
  for (const [k, v] of entries) { const d = document.createElement("div"); const a = document.createElement("span"); a.textContent = human(k); const b = document.createElement("b"); b.textContent = v; d.append(a, b); box.appendChild(d); }
}

/* ---------- interventions ---------- */
function buildForm() {
  const sel = $("#p-name"); sel.textContent = "";
  for (const c of state.catalog) { const o = document.createElement("option"); o.value = c.name; o.textContent = c.label; sel.appendChild(o); }
  sel.onchange = renderParams; renderParams();
}
function renderParams() {
  const def = state.catalog.find((c) => c.name === $("#p-name").value), box = $("#p-params"); box.textContent = "";
  if (!def) { $("#p-desc").textContent = "This world accepts no outside input."; $("#p-apply").disabled = true; return; }
  $("#p-desc").textContent = def.description || "";
  $("#p-apply").disabled = !state.sid;
  for (const [k, p] of Object.entries(def.params)) {
    const wrap = document.createElement("label"); wrap.className = "field" + (p.type === "choice" ? " wide" : ""); wrap.textContent = p.label || human(k);
    let inp;
    if (p.type === "choice") { inp = document.createElement("select"); for (const ch of p.choices) { const o = document.createElement("option"); o.value = ch; o.textContent = ch; inp.appendChild(o); } inp.value = p.default; }
    else { inp = document.createElement("input"); inp.type = "number"; inp.step = p.type === "int" ? "1" : "0.05"; if (p.min !== undefined) inp.min = p.min; if (p.max !== undefined) inp.max = p.max; inp.value = p.default; }
    inp.id = p.role === "x" ? "p-x" : p.role === "y" ? "p-y" : k === "radius" ? "p-radius" : "p-" + k; inp.dataset.key = k; inp.dataset.type = p.type;
    inp.addEventListener("input", drawMap);
    wrap.appendChild(inp); box.appendChild(wrap);
  }
  if (state.pick) { if ($("#p-x")) $("#p-x").value = state.pick.x; if ($("#p-y")) $("#p-y").value = state.pick.y; }
}
$("#pform").addEventListener("submit", async (e) => {
  e.preventDefault(); if (!state.sid) return;
  const params = {};
  for (const inp of $("#p-params").querySelectorAll("[data-key]")) params[inp.dataset.key] = inp.dataset.type === "choice" ? inp.value : Number(inp.value);
  try {
    const r = await api("/api/sessions/" + state.sid + "/perturb", { method: "POST", body: JSON.stringify({ name: $("#p-name").value, params }) });
    state.snap = r.snapshot; renderAll();
    status("Queued for tick " + r.queued.tick + (state.playing ? "." : ". Press Step or Play to apply it."));
  } catch (err) { status(err.message, true); }
});
function renderPending() {
  const p = state.snap.pending; $("#pending").textContent = p.length ? "Waiting: " + p.map((x) => x.name.replace(/_/g, " ") + " at tick " + x.tick).join(", ") : "";
}

/* ---------- chart ---------- */
function groups() {
  const s = state.snap, out = {};
  out.counts = { label: "Populations", series: Object.keys(s.types).map((k, i) => ({ key: k, label: k, color: i < 8 ? "--s" + (i + 1) : "--muted", get: (r) => r.counts[k] })) };
  if (Object.keys(s.fields).length) out.fields = { label: "Resources", series: Object.keys(s.fields).map((k, i) => ({ key: k, label: k, color: "--s" + (i + 1), get: (r) => r.fields[k] })) };
  const mk = new Set(); s.history.forEach((r) => Object.keys(r.metrics || {}).forEach((k) => mk.add(k)));
  if (mk.size) out.metrics = { label: "Measures", series: [...mk].map((k, i) => ({ key: k, label: human(k), color: "--s" + (i + 1), get: (r) => (r.metrics || {})[k] })) };
  return out;
}
function niceMax(v) { if (v <= 1) return 1; const p = Math.pow(10, Math.floor(Math.log10(v))), m = v / p; return ([1, 2, 4, 8, 10].find((x) => m <= x)) * p; }
const NS = "http://www.w3.org/2000/svg";
function sv(tag, attrs, parent) { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v); if (parent) parent.appendChild(n); return n; }
function renderChart() {
  const s = state.snap, G = groups(); if (!G[state.group]) state.group = "counts";
  const tabs = $("#tabs"); tabs.textContent = "";
  for (const [id, g] of Object.entries(G)) { const b = document.createElement("button"); b.textContent = g.label; b.setAttribute("aria-pressed", String(id === state.group)); b.onclick = () => { state.group = id; renderChart(); }; tabs.appendChild(b); }
  $("#tabs").hidden = Object.keys(G).length < 2;
  const grp = G[state.group], hist = s.history, series = grp.series;
  const lg = $("#legend"); lg.textContent = "";
  if (series.length >= 2) for (const se of series) { const d = document.createElement("span"); const i = document.createElement("i"); i.style.background = "var(" + se.color + ")"; d.append(i, document.createTextNode(se.label)); lg.appendChild(d); }
  const box = $("#chart"); box.textContent = "";
  if (state.table) return renderTable(box, grp, hist);
  const n = hist.length, W = Math.max(320, box.clientWidth || 600);
  const maxes = series.map((se) => { let mx = 0; for (const r of hist) { const v = se.get(r); if (v != null && v > mx) mx = v; } return mx; });
  const hi = Math.max(0, ...maxes), lo = Math.min(...maxes);
  /* one axis only: when magnitudes differ a lot, give each series its own panel instead of a second scale */
  const multiples = series.length >= 2 && series.length <= 4 && hi > 4 * Math.max(lo, 1);
  const m = { l: 42, r: (!multiples && series.length <= 4) ? 104 : 14, t: 12, b: 26 }, ph = 64, gap = 20;
  const panels = multiples
    ? series.map((se, k) => ({ list: [se], top: m.t + k * (ph + gap), h: ph, max: niceMax(maxes[k] * 1.08 || 1), ticks: 2 }))
    : [{ list: series, top: m.t, h: 200, max: niceMax(hi * 1.08 || 1), ticks: 4 }];
  const lastP = panels[panels.length - 1], H = lastP.top + lastP.h + m.b, bottom = lastP.top + lastP.h;
  const svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": grp.label + " over time. Use the table view for exact values." }, box);
  const pw = W - m.l - m.r, xs = (i) => m.l + (n <= 1 ? 0 : pw * i / (n - 1));
  const ysOf = (p, v) => p.top + p.h * (1 - v / p.max), panelOf = (se) => panels.find((p) => p.list.includes(se));
  for (const p of panels) for (let k = 0; k <= p.ticks; k++) {
    const v = p.max * k / p.ticks, y = ysOf(p, v);
    sv("line", { x1: m.l, x2: W - m.r, y1: y, y2: y, stroke: k ? "var(--grid)" : "var(--axis)", "stroke-width": 1 }, svg);
    sv("text", { x: m.l - 8, y: y + 4, "text-anchor": "end" }, svg).textContent = fmt(v);
  }
  for (let k = 0; k <= 4; k++) { const i = Math.round((n - 1) * k / 4); if (n < 2 && k) break; sv("text", { x: xs(i), y: H - 6, "text-anchor": k === 0 ? "start" : k === 4 ? "end" : "middle" }, svg).textContent = hist[i].t; }
  const ends = [];
  for (const p of panels) for (const se of p.list) {
    let d = "", pen = false, last = null;
    hist.forEach((r, i) => { const v = se.get(r); if (v == null) { pen = false; return; } d += (pen ? "L" : "M") + xs(i).toFixed(1) + " " + ysOf(p, v).toFixed(1); pen = true; last = v; });
    sv("path", { d, fill: "none", stroke: "var(" + se.color + ")", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
    if (last != null) ends.push({ se, y: ysOf(p, last) });
  }
  if (multiples) for (const p of panels) sv("text", { x: m.l + 6, y: p.top + 13, class: "lbl" }, svg).textContent = p.list[0].label;
  else if (series.length <= 4) { ends.sort((a, b) => a.y - b.y); let prev = -99; for (const e of ends) { e.ly = Math.max(e.y, prev + 14); prev = e.ly; const t = sv("text", { x: W - m.r + 8, y: e.ly + 4, class: "lbl" }, svg); t.textContent = e.se.label.length > 14 ? e.se.label.slice(0, 13) + "…" : e.se.label; } }
  const cross = sv("g", { visibility: "hidden" }, svg), vline = sv("line", { y1: m.t, y2: bottom, stroke: "var(--ink2)", "stroke-width": 1 }, cross);
  const dots = series.map((se) => sv("circle", { r: 4, fill: "var(" + se.color + ")", stroke: "var(--plate)", "stroke-width": 2 }, cross));
  const tip = document.createElement("div"); tip.className = "tip"; tip.hidden = true; box.appendChild(tip);
  const show = (i) => {
    i = Math.max(0, Math.min(n - 1, i)); const r = hist[i]; state.chartT = r.t;
    cross.setAttribute("visibility", "visible"); vline.setAttribute("x1", xs(i)); vline.setAttribute("x2", xs(i));
    tip.textContent = ""; const head = document.createElement("div"); head.className = "dim"; head.textContent = "Tick " + r.t; tip.appendChild(head);
    series.forEach((se, k) => {
      const v = se.get(r); if (v == null) { dots[k].setAttribute("visibility", "hidden"); return; }
      dots[k].setAttribute("visibility", "visible"); dots[k].setAttribute("cx", xs(i)); dots[k].setAttribute("cy", ysOf(panelOf(se), v));
      const row = document.createElement("div"); row.className = "row"; const key = document.createElement("span"); key.className = "key"; key.style.background = "var(" + se.color + ")";
      const val = document.createElement("b"); val.textContent = fmt(v); const nm = document.createElement("span"); nm.className = "dim"; nm.textContent = se.label; row.append(key, val, nm); tip.appendChild(row);
    });
    tip.hidden = false; const px = xs(i); tip.style.left = (px + 14 + 170 > W ? px - 14 - tip.offsetWidth : px + 14) + "px"; tip.style.top = "8px";
  };
  const hide = () => { cross.setAttribute("visibility", "hidden"); tip.hidden = true; state.chartT = null; };
  const hit = sv("rect", { x: m.l, y: m.t, width: pw, height: bottom - m.t, fill: "transparent", tabindex: 0, "aria-label": "Chart values. Use left and right arrow keys to read each tick." }, svg);
  hit.addEventListener("pointermove", (e) => { const rc = svg.getBoundingClientRect(), px = (e.clientX - rc.left) * (W / rc.width) - m.l; show(Math.round(px / pw * (n - 1))); });
  hit.addEventListener("pointerleave", hide); hit.addEventListener("blur", hide);
  hit.addEventListener("keydown", (e) => { if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return; e.preventDefault(); let i = hist.findIndex((r) => r.t === state.chartT); if (i < 0) i = n - 1; const step = e.shiftKey ? 10 : 1; show(e.key === "Home" ? 0 : e.key === "End" ? n - 1 : i + (e.key === "ArrowLeft" ? -step : step)); });
  if (state.chartT != null) { const i = hist.findIndex((r) => r.t === state.chartT); if (i >= 0) show(i); }
}
function renderTable(box, grp, hist) {
  const t = document.createElement("table"); t.className = "data";
  const cap = document.createElement("caption"); cap.textContent = grp.label + ", most recent ticks first"; t.appendChild(cap);
  const hr = document.createElement("tr"); for (const h of ["Tick", ...grp.series.map((s) => s.label)]) { const th = document.createElement("th"); th.textContent = h; hr.appendChild(th); } t.appendChild(hr);
  for (const r of hist.slice(-16).reverse()) { const tr = document.createElement("tr"); for (const c of [r.t, ...grp.series.map((s) => s.get(r))]) { const td = document.createElement("td"); td.textContent = c == null ? "" : fmt(c); tr.appendChild(td); } t.appendChild(tr); }
  box.appendChild(t);
}
$("#tableToggle").onclick = () => { state.table = !state.table; $("#tableToggle").setAttribute("aria-pressed", String(state.table)); $("#tableToggle").textContent = state.table ? "View as chart" : "View as table"; renderChart(); };

/* ---------- wiring ---------- */
function renderAll() { renderReadout(); drawMap(); renderChart(); renderFeed(); renderRelations(); renderTally(); renderPending(); }
$("#play").onclick = () => (state.playing ? pause() : play());
$("#step1").onclick = () => { pause(); advance(1); };
$("#step10").onclick = () => { pause(); advance(10); };
$("#new-world").addEventListener("submit", (e) => { e.preventDefault(); newWorld(); });
$("#reseed").onclick = () => { $("#seed").value = 1 + Math.floor(Math.random() * 999999); };
$("#eco").onchange = () => { const e = state.ecos.find((x) => x.id === $("#eco").value); if (e) { $("#seed").value = e.seed; $("#world-desc").textContent = e.description; } };
$("#verify").onclick = async () => {
  const out = $("#verify-out"); out.textContent = "Replaying from the recorded log...";
  try { const r = await api("/api/sessions/" + state.sid + "/verify", { method: "POST" }); out.textContent = r.ok ? "Replay matches: " + r.ticks + " ticks reproduced exactly (state " + r.got + ")." : "Replay differs from the live run" + (r.error ? ": " + r.error : " (expected " + r.expected + ", got " + r.got + ")") + "."; }
  catch (e) { out.textContent = e.message; }
};
$("#download").onclick = async () => {
  try { const lg = await api("/api/sessions/" + state.sid + "/log"); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(lg)], { type: "application/json" })); a.download = "simulacrum-run-tick" + lg.ticks + ".json"; a.click(); URL.revokeObjectURL(a.href); }
  catch (e) { status(e.message, true); }
};
const dlg = $("#spec-dialog");
$("#custom").onclick = async () => { if (state.sid && !$("#spec-text").value) await loadSpec(); $("#spec-err").textContent = ""; dlg.showModal(); };
$("#spec-close").onclick = () => dlg.close();
async function loadSpec() { if (!state.sid) return; try { $("#spec-text").value = JSON.stringify(await api("/api/sessions/" + state.sid + "/spec"), null, 2); } catch (e) { $("#spec-err").textContent = e.message; } }
$("#spec-load").onclick = loadSpec;
$("#spec-run").onclick = async () => {
  let spec; try { spec = JSON.parse($("#spec-text").value); } catch (e) { $("#spec-err").textContent = "That is not valid JSON: " + e.message; return; }
  delete spec.plugins; $("#spec-err").textContent = "";
  if (await newWorld(spec)) dlg.close(); else $("#spec-err").textContent = $("#status").textContent;
};
window.addEventListener("resize", () => { if (state.snap) { drawMap(); renderChart(); } });
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (state.snap) { drawMap(); renderChart(); } });

(async function init() {
  try {
    state.ecos = await api("/api/ecosystems");
    const sel = $("#eco"); for (const e of state.ecos) { const o = document.createElement("option"); o.value = e.id; o.textContent = e.name; sel.appendChild(o); }
    if (!state.ecos.length) { status("No ecosystems found. Add a .json spec to the server's ecosystems folder.", true); return; }
    $("#eco").onchange(); await newWorld();
  } catch (e) { status(e.message, true); }
})();
