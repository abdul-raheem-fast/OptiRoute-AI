/* OptiRoute AI dashboard logic — vanilla JS, no dependencies. */
"use strict";

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtUSD = (v, digits = 0) =>
  "$" + v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

let META = null;          // /api/models payload
let RESULTS = null;       // /api/results payload
let MODES = null;         // /api/modes payload
let SCEN = null;          // /api/scenarios payload (real benchmark queries)
let LAST_DECISION = null; // last routed decision (playground echo)

/* ------------------------------------------------------------ boot */
async function boot() {
  initTheme();
  const [meta, results, modes, scen] = await Promise.all([
    fetch("/api/models").then((r) => r.json()),
    fetch("/api/results").then((r) => r.json()),
    fetch("/api/modes").then((r) => r.json()),
    fetch("/api/scenarios").then((r) => r.json()),
  ]);
  META = meta;
  RESULTS = results;
  MODES = modes.modes;
  SCEN = scen;

  initSimulator();
  renderModes();
  renderPolicyTable();
  renderPareto();
  renderGuardrail();
  renderEvidence();
  initCalculator();
  renderModelsTable();
  initPlayground();
  initReveal();
  refreshSessionStats();
  setInterval(refreshSessionStats, 4000);
}

/* ----------------------------------------------------------- theme */
function initTheme() {
  const btn = $("#theme-toggle");
  const apply = (t) => {
    document.documentElement.dataset.theme = t;
    btn.textContent = t === "dark" ? "Light" : "Dark";
  };
  apply(localStorage.getItem("af-theme") || "light");
  btn.addEventListener("click", () => {
    const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    localStorage.setItem("af-theme", t);
    apply(t);
  });
}

/* -------------------------------------------------- reveal on scroll */
function initReveal() {
  const els = document.querySelectorAll(".panel, .hero .wrap");
  if (!("IntersectionObserver" in window)) {
    els.forEach((e) => e.classList.add("is-visible"));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    for (const en of entries) {
      if (en.isIntersecting) {
        en.target.classList.add("is-visible");
        io.unobserve(en.target);
      }
    }
  }, { threshold: 0.08 });
  els.forEach((e) => io.observe(e));
}

/* ------------------------------------------------------- simulator */
function initSimulator() {
  const sel = $("#sim-class");
  for (const c of META.classes) {
    const o = document.createElement("option");
    o.value = c;
    o.textContent = c;
    sel.appendChild(o);
  }
  const slider = $("#sim-threshold");
  slider.value = META.t_star.toFixed(2);
  $("#sim-threshold-val").textContent = "t = " + Number(slider.value).toFixed(2);
  slider.addEventListener("input", () => {
    $("#sim-threshold-val").textContent = "t = " + Number(slider.value).toFixed(2);
  });

  // Real benchmark scenario chips (curated from the frozen test split).
  const scenBox = $("#sim-scenarios");
  const dotClass = { easy: "dot-easy", medium: "dot-med", hard: "dot-hard" };
  const applyQuery = (query, cls) => {
    $("#sim-query").value = query;
    if (cls) $("#sim-class").value = cls;
    runRoute();
  };
  ((SCEN && SCEN.scenarios) || []).forEach((s) => {
    const b = document.createElement("button");
    b.className = "chip";
    b.title = s.query_class + " — expected: " +
      (s.expected_route === "cheap" ? "cheap route" : "escalate to strongest");
    b.innerHTML = '<i class="dot ' + (dotClass[s.dot] || "dot-med") + '"></i>' + esc(s.label);
    b.addEventListener("click", () => applyQuery(s.query, s.query_class));
    scenBox.appendChild(b);
  });

  $("#sim-run").addEventListener("click", runRoute);
  $("#sim-challenge").addEventListener("click", () => {
    const pool = (SCEN && SCEN.challenges) || [];
    if (!pool.length) return;
    const cur = $("#sim-query").value;
    let pick = pool[Math.floor(Math.random() * pool.length)];
    for (let g = 0; pick.query === cur && g < 12; g++)
      pick = pool[Math.floor(Math.random() * pool.length)];
    applyQuery(pick.query, pick.query_class);
  });
  $("#sim-query").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) runRoute();
  });

  // Open with a real, compelling decision already routed (cheap win + savings).
  const first = (SCEN && SCEN.scenarios && SCEN.scenarios[0]) || null;
  if (first) applyQuery(first.query, first.query_class);
}

async function runRoute() {
  const query = $("#sim-query").value.trim();
  if (!query) return;
  const btn = $("#sim-run");
  btn.disabled = true;
  try {
    const res = await fetch("/api/route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        query_class: $("#sim-class").value || null,
        threshold: Number($("#sim-threshold").value),
      }),
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    renderDecision(await res.json());
  } catch (err) {
    $("#sim-output").innerHTML =
      `<div class="sim-empty"><p>Routing failed: ${esc(err.message)}</p></div>`;
  } finally {
    btn.disabled = false;
  }
}

function renderDecision(d) {
  const perQuery = d.est_cost_per_query;
  const gpt5 = d.strongest_cost_per_query;
  const bars = META.models
    .map((m) => {
      const p = d.p_correct[m.model];
      const chosen = m.model === d.chosen_model;
      return `<div class="probbar ${chosen ? "chosen" : ""}">
        <span class="probbar-name">${esc(m.model)}</span>
        <span class="probbar-track"><span class="probbar-fill" data-w="${(p * 100).toFixed(1)}" style="width:0"></span></span>
        <span class="probbar-val">${(p * 100).toFixed(1)}%</span>
      </div>`;
    })
    .join("");

  const cxBars = d.tier_probs ? ["easy", "medium", "hard"].map((t) => `
      <div class="probbar">
        <span class="probbar-name">${t}</span>
        <span class="probbar-track"><span class="probbar-fill" data-w="${(d.tier_probs[t] * 100).toFixed(1)}" style="width:0"></span></span>
        <span class="probbar-val">${(d.tier_probs[t] * 100).toFixed(0)}%</span>
      </div>`).join("") : "";
  const why = (d.reasons || []).map((r) =>
    `<li class="${d.is_fallback && (r.startsWith("no model") || r.startsWith("escalated")) ? "risk" : ""}">${esc(r)}</li>`).join("");
  const wns = d.why_not_strongest || {};

  $("#sim-output").innerHTML = `
    <span class="decision-label">Routed to</span>
    <div class="decision-model pop">${esc(d.chosen_model)}</div>
    <div class="decision-meta">
      class: <strong>${esc(d.query_class)}</strong><span class="sep">|</span>
      est. cost ${fmtUSD(perQuery, 6)}/query vs GPT-5 ${fmtUSD(gpt5, 6)}
      <span class="sep">|</span> <strong>${d.est_saving_pct}% cheaper</strong>
      ${d.is_fallback ? '<span class="sep">|</span><em>no model met the threshold &mdash; safety fallback to strongest</em>' : ""}
    </div>
    ${cxBars ? `<span class="decision-label">Query complexity</span>
    <div class="probbars cx-block">${cxBars}</div>` : ""}
    <span class="decision-label">P(correct) per model &mdash; cheapest to strongest</span>
    <div class="probbars">${bars}</div>
    <span class="decision-label">Why this route</span>
    <ul class="why-list">${why}</ul>
    <div class="alt-box">Alternative: always-GPT-5 at ${fmtUSD(gpt5, 6)}/query.
      This route ${fmtUSD(perQuery, 6)} &mdash; <strong>you save ${d.est_saving_pct}%</strong> on this query.
      <br><span class="fineprint">${esc(wns.verdict || "")}
      (+${wns.delta_accuracy_pts} pts expected quality for +${fmtUSD(wns.delta_cost_per_query, 5)}).</span></div>
    <p class="thresh-note">Cost and latency shown for arbitrary queries are benchmark
    averages of the chosen model, not a live meter. Headline savings come from the
    measured test split below.</p>`;

  const steps = [];
  for (const s of d.cascade_trace) {
    steps.push(`<span class="cstep ${s.passes ? "accepted" : "rejected"}">
      ${esc(s.model)}<span class="p">p=${(s.p_correct * 100).toFixed(1)}% ${s.passes ? "&#10003; take" : "&#10007; below t"}</span>
    </span>`);
  }
  const joined = steps.join('<span class="cstep-arrow">&rarr;</span>');
  const fallback = d.is_fallback
    ? '<span class="cstep-arrow">&rarr;</span><span class="cstep accepted">' +
      esc(d.chosen_model) + '<span class="p">fallback: strongest</span></span>'
    : "";
  $("#sim-cascade").innerHTML =
    `<div class="cascade-title">Cascade walk (threshold t = ${d.threshold.toFixed(2)})</div>
     <div class="cascade">${joined}${fallback}</div>`;

  // Animate: bars fill left-to-right, cascade steps walk in one by one.
  requestAnimationFrame(() => requestAnimationFrame(() => {
    document.querySelectorAll("#sim-output .probbar-fill").forEach((f) => {
      f.style.width = f.dataset.w + "%";
    });
    document.querySelectorAll("#sim-cascade .cstep, #sim-cascade .cstep-arrow").forEach((el, i) => {
      el.style.animation = "rise 0.3s ease forwards";
      el.style.animationDelay = (i * 70) + "ms";
    });
  }));
  refreshSessionStats();
  LAST_DECISION = d;
  const pgRes = $("#pg-res");
  if (pgRes) pgRes.textContent = JSON.stringify(d, null, 2);
  updatePgReq();
}

/* ------------------------------------------------- session stats */
async function refreshSessionStats() {
  try {
    const s = await fetch("/api/stats").then((r) => r.json());
    renderOps(s);
    if (!s.session_queries) return;
    const colors = ["#0e5a4a", "#4aa88e", "#b8860b", "#8d897a",
                    "#5b7c99", "#a06a4c", "#7a5b99", "#c05b5b"];
    $("#sim-stats").hidden = false;
    $("#sim-stats-total").textContent = s.session_queries;
    $("#sim-stats-bar").innerHTML = META.models
      .map((m, idx) => {
        const n = s.distribution[m.model] || 0;
        if (!n) return "";
        return `<span style="width:${((n / s.session_queries) * 100).toFixed(1)}%;
          background:${colors[idx % colors.length]}" title="${esc(m.model)}: ${n}"></span>`;
      })
      .join("");
  } catch (e) { /* stats panel is decorative — never break routing on it */ }
}

/* ---------------------------------------------------- policy table */
function renderPolicyTable() {
  const rows = RESULTS.baselines_report;
  if (!rows) return;
  const html = rows
    .map((r) => {
      const name = r.policy;
      const hl = name.startsWith("learned") ? "highlight" : name === "oracle" ? "" : "";
      const dim = name === "always-cheapest" || name === "random" ? "dim" : "";
      const floor = String(r.meets_quality_floor) === "True" || r.meets_quality_floor === true;
      return `<tr class="${hl} ${dim}">
        <td>${esc(name)}</td>
        <td>${Number(r.accuracy_pct).toFixed(2)}%</td>
        <td>${Number(r.quality_vs_strongest_pct).toFixed(1)}%</td>
        <td>${Number(r.cost_reduction_vs_strongest_pct).toFixed(1)}%</td>
        <td>${floor ? '<span class="tick-yes">&#10003;</span>' : '<span class="tick-no">&#10007;</span>'}</td>
      </tr>`;
    })
    .join("");
  $("#policy-table").innerHTML = `<table>
    <thead><tr><th>Policy</th><th>Accuracy</th><th>Quality vs GPT-5</th><th>Cost cut</th><th>Floor</th></tr></thead>
    <tbody>${html}</tbody></table>`;
}

/* -------------------------------------------------- pareto (SVG) */
function renderPareto() {
  const rows = RESULTS.baselines_report;
  if (!rows) return;
  const W = 520, H = 400, m = { t: 24, r: 20, b: 46, l: 56 };
  const pts = rows.map((r) => ({
    name: r.policy.replace(/ \(t=.*\)/, ""),
    cost: Number(r.avg_cost_per_query),
    acc: Number(r.accuracy_pct),
    learned: r.policy.startsWith("learned"),
    oracle: r.policy === "oracle",
  }));
  const maxC = Math.max(...pts.map((p) => p.cost)) * 1.15;
  const minA = Math.min(...pts.map((p) => p.acc)) - 4;
  const maxA = Math.max(...pts.map((p) => p.acc)) + 3;
  const X = (c) => m.l + (c / maxC) * (W - m.l - m.r);
  const Y = (a) => H - m.b - ((a - minA) / (maxA - minA)) * (H - m.t - m.b);

  const floorRow = rows.find((r) => r.policy === "always-strongest");
  const floorAcc = Number(floorRow.accuracy_pct) * 0.9;

  let g = "";
  // gridlines + y labels
  for (let a = Math.ceil(minA / 10) * 10; a <= maxA; a += 10) {
    g += `<line class="gridline" x1="${m.l}" y1="${Y(a)}" x2="${W - m.r}" y2="${Y(a)}"/>`;
    g += `<text class="axis-label" x="${m.l - 8}" y="${Y(a) + 3}" text-anchor="end">${a}%</text>`;
  }
  // x labels
  for (let i = 0; i <= 4; i++) {
    const c = (maxC / 4) * i;
    g += `<text class="axis-label" x="${X(c)}" y="${H - m.b + 18}" text-anchor="middle">$${c.toFixed(3)}</text>`;
  }
  // quality-floor band
  g += `<rect x="${m.l}" y="${Y(floorAcc)}" width="${W - m.l - m.r}" height="${H - m.b - Y(floorAcc)}"
        fill="#8a3324" opacity="0.05"/>`;
  g += `<line x1="${m.l}" y1="${Y(floorAcc)}" x2="${W - m.r}" y2="${Y(floorAcc)}"
        stroke="#8a3324" stroke-dasharray="5 4" stroke-width="1" opacity="0.5"/>`;
  g += `<text class="axis-label" x="${W - m.r - 4}" y="${Y(floorAcc) - 5}" text-anchor="end" fill="#8a3324">quality floor</text>`;

  // Fixed dataset: per-policy label placement avoids collisions at all sizes.
  const LABEL_POS = {
    "always-strongest": { anchor: "end", dx: -10, dy: 16 },
    "knn-cascade": { anchor: "end", dx: -10, dy: -10 },
    "learned-cascade": { anchor: "end", dx: -10, dy: -14 },
    "prior-cascade": { anchor: "end", dx: -10, dy: -10 },
    "class-based": { anchor: "end", dx: -10, dy: 14 },
    "oracle": { anchor: "start", dx: 10, dy: 4 },
    "random": { anchor: "end", dx: -10, dy: 4 },
    "always-cheapest": { anchor: "start", dx: 10, dy: 4 },
  };
  for (const p of pts) {
    const cls = p.learned ? "pt-learned" : p.oracle ? "pt-oracle" : "pt-default";
    const rr = p.learned || p.oracle ? 7 : 5;
    g += `<circle class="pareto-dot ${cls}" cx="${X(p.cost)}" cy="${Y(p.acc)}" r="${rr}"
          stroke="var(--panel)" stroke-width="1.5"
          data-name="${esc(p.name)}" data-acc="${p.acc.toFixed(2)}" data-cost="${p.cost.toFixed(6)}"/>`;
    const pos = LABEL_POS[p.name] || { anchor: "start", dx: 10, dy: 4 };
    g += `<text class="pt-label ${p.learned ? "learned-lbl" : ""}" x="${X(p.cost) + pos.dx}" y="${Y(p.acc) + pos.dy}"
          text-anchor="${pos.anchor}">${esc(p.name)}</text>`;
  }
  // axes titles
  g += `<text class="axis-label" x="${(W + m.l - m.r) / 2}" y="${H - 8}" text-anchor="middle">avg cost per query (USD)</text>`;
  g += `<text class="axis-label" x="14" y="${(H + m.t - m.b) / 2}" text-anchor="middle"
        transform="rotate(-90 14 ${(H + m.t - m.b) / 2})">accuracy (test split)</text>`;

  $("#pareto-chart").innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Cost vs accuracy per routing policy">${g}</svg>`;

  // Hover tooltips with exact numbers per policy dot.
  const holder = $("#pareto-chart");
  const tip = document.createElement("div");
  tip.id = "chart-tip";
  holder.appendChild(tip);
  holder.querySelectorAll(".pareto-dot").forEach((c) => {
    c.addEventListener("mouseenter", () => {
      tip.innerHTML = `<strong>${esc(c.dataset.name)}</strong><br>
        ${c.dataset.acc}% accuracy<br>${fmtUSD(Number(c.dataset.cost), 5)} / query`;
      const box = holder.getBoundingClientRect();
      const r = c.getBoundingClientRect();
      tip.style.display = "block";
      tip.style.left = (r.left - box.left + r.width / 2 + 12) + "px";
      tip.style.top = (r.top - box.top - 14) + "px";
    });
    c.addEventListener("mouseleave", () => { tip.style.display = "none"; });
  });
}

/* -------------------------------------------------- calculator */
function initCalculator() {
  const rows = RESULTS.baselines_report;
  const learned = rows.find((r) => r.policy.startsWith("learned"));
  const cRouted = Number(learned.avg_cost_per_query);
  const sel = $("#calc-strategy");
  rows
    .filter((r) => !r.policy.startsWith("learned") && r.policy !== "oracle")
    .forEach((r) => {
      const o = document.createElement("option");
      o.value = r.policy;
      o.textContent = r.policy;
      sel.appendChild(o);
    });
  sel.value = "always-strongest";

  const volume = $("#calc-volume");
  const slider = $("#calc-slider");

  const update = () => {
    const n = Math.max(1, Number(volume.value) || 0);
    const base = Number(rows.find((r) => r.policy === sel.value).avg_cost_per_query);
    const strong = Number(rows.find((r) => r.policy === "always-strongest").avg_cost_per_query);
    const yB = base * n * 365;
    const yR = cRouted * n * 365;
    $("#calc-base-d").textContent = fmtUSD(base * n) + " / day";
    $("#calc-base-m").textContent = fmtUSD((yB / 365) * 30.44);
    $("#calc-base-y").textContent = fmtUSD(yB);
    $("#calc-routed-d").textContent = fmtUSD(cRouted * n) + " / day";
    $("#calc-routed-m").textContent = fmtUSD((yR / 365) * 30.44);
    $("#calc-routed-y").textContent = fmtUSD(yR);
    const saved = yB - yR;
    $("#calc-saved").textContent = fmtUSD(saved);
    const cut = (1 - cRouted / base) * 100;
    $("#calc-reinvest").innerHTML = `
      <h4>What the savings buy</h4>
      <ul>
        <li>${(saved / cRouted / 1e6).toFixed(1)}M additional routed queries per year</li>
        <li>${Math.round(saved / strong).toLocaleString("en-US")} extra GPT-5 queries for genuinely hard work</li>
        <li>${cut.toFixed(1)}% lower inference spend on this workload</li>
        <li>fewer unnecessary high-compute calls &mdash; quality floor held at 90% of flagship</li>
      </ul>`;
  };
  volume.addEventListener("input", () => {
    slider.value = Math.log10(Math.max(1, Number(volume.value) || 1));
    update();
  });
  slider.addEventListener("input", () => {
    volume.value = Math.round(Math.pow(10, Number(slider.value)));
    update();
  });
  sel.addEventListener("change", update);
  update();
}

/* ------------------------------------------------- models table */
function renderModelsTable() {
  const classes = META.classes;
  const head = classes.map((c) => `<th>${esc(c.replace("Questionnaire", "Q.").replace("Reasoning", "Reas."))}</th>`).join("");
  const body = META.models
    .map((m) => {
      const cells = classes.map((c) => `<td>${m.class_accuracy[c].toFixed(1)}%</td>`).join("");
      const price = m.price_in != null && m.price_in > 0
        ? `${m.price_in.toFixed(2)} / ${m.price_out.toFixed(2)}`
        : "self-hosted";
      return `<tr>
        <td>${esc(m.model)}</td>
        <td>${esc(m.provider.split("/")[0].trim())}</td>
        <td class="mono">${price}</td>
        <td>${fmtUSD(m.avg_cost_per_query, 6)}</td>
        ${cells}
      </tr>`;
    })
    .join("");
  $("#models-table").innerHTML = `<table>
    <thead><tr><th>Model</th><th>Provider</th><th>$/1M in / out</th><th>Avg $/query</th>${head}</tr></thead>
    <tbody>${body}</tbody></table>`;
}

/* ------------------------------------------------------ modes */
let CURRENT_MODE = "balanced";

function renderModes() {
  const wrap = $("#mode-switch");
  wrap.innerHTML = MODES.map((m) =>
    `<button data-mode="${m.key}" class="${m.key === CURRENT_MODE ? "active" : ""}">${esc(m.label)}</button>`).join("");
  wrap.querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      CURRENT_MODE = b.dataset.mode;
      wrap.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
      const m = MODES.find((x) => x.key === CURRENT_MODE);
      $("#sim-threshold").value = m.t.toFixed(2);
      $("#sim-threshold-val").textContent = "t = " + m.t.toFixed(2);
      noteMode();
      updatePgReq();
      if ($("#sim-query").value.trim()) runRoute();  // show the mode's effect
    }));
  noteMode();
}

function noteMode() {
  const m = MODES.find((x) => x.key === CURRENT_MODE);
  $("#mode-note").textContent =
    `${m.label} (t = ${m.t.toFixed(2)}): ${m.description}. ` +
    `Measured on the ${m.measured_on}: ${m.val_accuracy_pct.toFixed(1)}% accuracy at ` +
    `${fmtUSD(m.val_avg_cost_per_query, 4)}/query. Headline test-split numbers are for Balanced.`;
}

/* -------------------------------------------------- guardrail */
function renderGuardrail() {
  const rows = RESULTS.baselines_report;
  const strong = rows.find((r) => r.policy === "always-strongest");
  const learned = rows.find((r) => r.policy.startsWith("learned"));
  const floor = Number(strong.accuracy_pct) * 0.9;
  const acc = Number(learned.accuracy_pct);
  const margin = acc - floor;
  $("#guardrail").innerHTML = `
    <div class="g-item"><span class="stat-num">${floor.toFixed(1)}<small>%</small></span>
      <span class="stat-label">target quality floor</span></div>
    <div class="g-item"><span class="stat-num">${acc.toFixed(2)}<small>%</small></span>
      <span class="stat-label">current policy (test)</span></div>
    <div class="g-item"><span class="stat-num">+${margin.toFixed(2)}<small> pts</small></span>
      <span class="stat-label">margin</span></div>
    <div class="g-item"><span class="g-safe">${margin >= 0 ? "&#10003; SAFE" : "&#10007; AT RISK"}</span>
      <span class="stat-label">guardrail status</span></div>
    <p class="g-line">Cost is the objective; quality is the constraint. OptiRoute optimizes
    spend subject to a measured quality floor &mdash; it is not &ldquo;send everything to
    the cheapest model&rdquo;.</p>`;
}

/* --------------------------------------------------- evidence */
function renderEvidence() {
  const mf = RESULTS.splits_manifest;
  const rows = RESULTS.baselines_report;
  const get = (p) => p === "us"
    ? rows.find((r) => r.policy.startsWith("learned"))
    : rows.find((r) => r.policy === p);
  $("#ev-manifest").innerHTML = mf ? `
    <span class="ev-chip">split <b>test</b></span>
    <span class="ev-chip">queries <b>${mf.split_counts.test}</b></span>
    <span class="ev-chip">seed <b>${mf.seed}</b></span>
    <span class="ev-chip">strata <b>${Object.keys(mf.strata).length}</b> class&times;tier</span>
    <span class="ev-chip">leakage audit <b>${mf.duplicate_ids_in_val_or_test.length === 0 ? "passed" : "FAILED"}</b></span>
    <span class="ev-chip">aligned_7 dups excluded <b>${mf.aligned7_duplicate_ids}</b></span>` : "";
  const card = (title, r, cls, extra) => `
    <div class="ev-card ${cls}">
      <h4>${title}</h4>
      <span class="mono">accuracy ${Number(r.accuracy_pct).toFixed(2)}%</span>
      <span class="mono">cost ${fmtUSD(Number(r.avg_cost_per_query), 6)}/query</span>
      ${extra || ""}
    </div>`;
  const us = get("us");
  $("#ev-cards").innerHTML =
    card("Always strongest", get("always-strongest"), "") +
    card("OptiRoute AI", us, "us",
      `<span class="mono"><b>${Number(us.cost_reduction_vs_strongest_pct).toFixed(1)}% cheaper</b> at ${Number(us.quality_vs_strongest_pct).toFixed(1)}% of flagship quality</span>`) +
    card("Oracle ceiling", get("oracle"), "",
      `<span class="mono tip" data-tip="Oracle has hindsight: it knows which model would perform best after seeing outcomes. OptiRoute must decide before inference, so Oracle is a theoretical upper bound, not a deployable baseline.">what does oracle mean?</span>`);
}

/* ------------------------------------------------- operations */
function renderOps(s) {
  const cards = [
    ["Total queries", s.session_queries],
    ["Efficient routes", s.efficient_routes],
    ["Escalations", s.escalations],
    ["Escalation rate", s.escalation_rate_pct + "%"],
    ["Est. savings", fmtUSD(s.est_savings_total, 2)],
  ];
  $("#ops-cards").innerHTML = cards.map(([l, v]) =>
    `<div class="stat"><span class="stat-num">${v}</span><span class="stat-label">${l}</span></div>`).join("");
  const colors = ["#0e5a4a", "#4aa88e", "#b8860b", "#8d897a",
                  "#5b7c99", "#a06a4c", "#7a5b99", "#c05b5b"];
  const bar = (entries, total) => entries.map(([label, n, c]) =>
    n ? `<span style="width:${((n / total) * 100).toFixed(1)}%;background:${c}" title="${esc(label)}: ${n}"></span>` : "").join("");
  $("#ops-model-bar").innerHTML =
    bar(META.models.map((m, i) => [m.model, s.distribution[m.model] || 0, colors[i % 8]]),
        Math.max(1, s.session_queries));
  const tTot = Math.max(1, Object.values(s.tier_distribution).reduce((a, b) => a + b, 0));
  $("#ops-tier-bar").innerHTML =
    bar(Object.entries(s.tier_distribution).map(([t, n], i) =>
        [t, n, ["#3f8f5f", "#b8860b", "#8a3324"][i]]), tTot);

  let cum = 0;
  const pts = (s.route_log || []).map((r, i) => { cum += r.saved; return [i, cum]; });
  const W = 520, H = 110, mg = { t: 10, r: 10, b: 18, l: 46 };
  if (pts.length > 1) {
    const maxX = pts[pts.length - 1][0];
    const maxY = Math.max(...pts.map((p) => p[1])) * 1.1 || 1;
    const X = (i) => mg.l + (i / maxX) * (W - mg.l - mg.r);
    const Y = (v) => H - mg.b - (v / maxY) * (H - mg.t - mg.b);
    const line = pts.map(([i, v]) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
    $("#ops-spark").innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Cumulative session savings">
      <polyline points="${line}" fill="none" stroke="var(--accent)" stroke-width="2"/>
      <text class="axis-label" x="${mg.l}" y="${Y(maxY / 1.1) + 10}">${fmtUSD(maxY / 1.1, 2)}</text>
      <text class="axis-label" x="${W - mg.r}" y="${H - 4}" text-anchor="end">${pts.length} routes</text></svg>`;
  } else {
    $("#ops-spark").innerHTML =
      `<p class="fineprint">Route queries in the arena to draw the savings curve.</p>`;
  }
}

/* -------------------------------------------------- playground */
function initPlayground() {
  updatePgReq();
  $("#pg-copy").addEventListener("click", () => {
    const q = $("#sim-query").value.trim() || "Explain blockchain simply";
    const cmd = `curl -X POST http://127.0.0.1:8317/api/route -H "Content-Type: application/json" -d '{"query": "${q.replace(/'/g, "")}", "mode": "${CURRENT_MODE}"}'`;
    navigator.clipboard.writeText(cmd);
    $("#pg-copy").textContent = "copied";
    setTimeout(() => { $("#pg-copy").textContent = "copy curl"; }, 1200);
  });
}

function updatePgReq() {
  const el = $("#pg-req");
  if (!el) return;
  const q = ($("#sim-query").value.trim() || "Explain blockchain simply").slice(0, 80);
  el.textContent = `POST /api/route\n{\n  "query": "${q}",\n  "mode": "${CURRENT_MODE}"\n}`;
}

boot().catch((err) => {
  document.querySelectorAll(".panel, .hero .wrap").forEach((e) => e.classList.add("is-visible"));
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div style="position:fixed;bottom:16px;left:16px;background:#8a3324;color:#fff;
     padding:10px 16px;border-radius:4px;font-size:13px">Failed to load data: ${esc(err.message)}</div>`
  );
});
