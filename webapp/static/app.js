/* AetherFlow dashboard logic — vanilla JS, no dependencies. */
"use strict";

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtUSD = (v, digits = 0) =>
  "$" + v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

let META = null;          // /api/models payload
let RESULTS = null;       // /api/results payload

/* ------------------------------------------------------------ boot */
async function boot() {
  initTheme();
  const [meta, results] = await Promise.all([
    fetch("/api/models").then((r) => r.json()),
    fetch("/api/results").then((r) => r.json()),
  ]);
  META = meta;
  RESULTS = results;

  initSimulator();
  renderPolicyTable();
  renderPareto();
  initCalculator();
  renderModelsTable();
  initReveal();
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

  document.querySelectorAll(".chip").forEach((chip) =>
    chip.addEventListener("click", () => {
      $("#sim-query").value = chip.dataset.q;
      runRoute();
    })
  );
  $("#sim-run").addEventListener("click", runRoute);
  $("#sim-query").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) runRoute();
  });
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

  $("#sim-output").innerHTML = `
    <span class="decision-label">Routed to</span>
    <div class="decision-model pop">${esc(d.chosen_model)}</div>
    <div class="decision-meta">
      class: <strong>${esc(d.query_class)}</strong><span class="sep">|</span>
      est. cost ${fmtUSD(perQuery, 6)}/query vs GPT-5 ${fmtUSD(gpt5, 6)}
      <span class="sep">|</span> <strong>${d.est_saving_pct}% cheaper</strong>
      ${d.is_fallback ? '<span class="sep">|</span><em>no model met the threshold — safety fallback to strongest</em>' : ""}
    </div>
    <span class="decision-label">P(correct) per model — cheapest to strongest</span>
    <div class="probbars">${bars}</div>
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
}

/* ------------------------------------------------- session stats */
async function refreshSessionStats() {
  try {
    const s = await fetch("/api/stats").then((r) => r.json());
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
  const strongest = rows.find((r) => r.policy === "always-strongest");
  const learned = rows.find((r) => r.policy.startsWith("learned"));
  const cBase = Number(strongest.avg_cost_per_query);
  const cRouted = Number(learned.avg_cost_per_query);

  const volume = $("#calc-volume");
  const slider = $("#calc-slider");

  const update = () => {
    const n = Math.max(1, Number(volume.value) || 0);
    const yearBase = cBase * n * 365;
    const yearRouted = cRouted * n * 365;
    $("#calc-baseline").textContent = fmtUSD(yearBase) + " / yr";
    $("#calc-routed").textContent = fmtUSD(yearRouted) + " / yr";
    $("#calc-saved").textContent = fmtUSD(yearBase - yearRouted);
  };
  volume.addEventListener("input", () => {
    slider.value = Math.log10(Math.max(1, Number(volume.value) || 1));
    update();
  });
  slider.addEventListener("input", () => {
    volume.value = Math.round(Math.pow(10, Number(slider.value)));
    update();
  });
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

boot().catch((err) => {
  document.querySelectorAll(".panel, .hero .wrap").forEach((e) => e.classList.add("is-visible"));
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div style="position:fixed;bottom:16px;left:16px;background:#8a3324;color:#fff;
     padding:10px 16px;border-radius:4px;font-size:13px">Failed to load data: ${esc(err.message)}</div>`
  );
});
