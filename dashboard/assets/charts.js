/* ============================================================================
 * charts.js — Lightweight, dependency-free SVG chart library
 * Built for the mohidev-tech analytics dashboards.
 * No external libraries, no CDN. Fully self-contained & portable.
 * API: Charts.kpi / line / bars / groupedBars / stackedBars / donut / table
 * ==========================================================================*/
(function (global) {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  const fmtInt = (n) => Math.round(n).toLocaleString("en-US");
  const fmtNum = (n, d = 1) => Number(n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  const fmtPct = (n, d = 1) => fmtNum(n, d) + "%";
  const fmtMoney = (n) => {
    const a = Math.abs(n);
    if (a >= 1e9) return "$" + fmtNum(n / 1e9, 2) + "B";
    if (a >= 1e6) return "$" + fmtNum(n / 1e6, 2) + "M";
    if (a >= 1e3) return "$" + fmtNum(n / 1e3, 1) + "K";
    return "$" + fmtInt(n);
  };

  function el(tag, attrs, children) {
    const e = document.createElementNS(NS, tag);
    if (attrs) for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (children) (Array.isArray(children) ? children : [children]).forEach((c) => {
      if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return e;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function svgRoot(w, h) {
    return el("svg", { viewBox: `0 0 ${w} ${h}`, width: "100%", height: "100%", preserveAspectRatio: "xMidYMid meet", class: "chart-svg" });
  }
  function niceMax(v) {
    if (v <= 0) return 1;
    const pow = Math.pow(10, Math.floor(Math.log10(v)));
    const n = v / pow;
    let step;
    if (n <= 1) step = 1; else if (n <= 2) step = 2; else if (n <= 2.5) step = 2.5; else if (n <= 5) step = 5; else step = 10;
    return step * pow;
  }

  // ---- shared tooltip -------------------------------------------------------
  let tip;
  function ensureTip() {
    if (tip) return tip;
    tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.style.cssText = "position:fixed;pointer-events:none;z-index:9999;opacity:0;transition:opacity .08s;background:var(--tip-bg,#111827);color:#fff;font:600 12px/1.4 system-ui,sans-serif;padding:6px 9px;border-radius:6px;box-shadow:0 4px 14px rgba(0,0,0,.25);white-space:nowrap";
    document.body.appendChild(tip);
    return tip;
  }
  function showTip(html, evt) {
    const t = ensureTip();
    t.innerHTML = html;
    t.style.opacity = "1";
    const x = evt.clientX + 14, y = evt.clientY + 14;
    t.style.left = Math.min(x, window.innerWidth - t.offsetWidth - 8) + "px";
    t.style.top = Math.min(y, window.innerHeight - t.offsetHeight - 8) + "px";
  }
  function hideTip() { if (tip) tip.style.opacity = "0"; }
  function hoverable(node, html) {
    node.style.cursor = "default";
    node.addEventListener("mousemove", (e) => showTip(html, e));
    node.addEventListener("mouseleave", hideTip);
  }

  // ---- KPI card -------------------------------------------------------------
  function kpi(node, o) {
    node.classList.add("kpi");
    node.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.className = "kpi-inner";
    const deltaHtml = (o.delta != null && o.delta !== "")
      ? `<div class="kpi-delta ${o.deltaGood === false ? "bad" : o.deltaGood === true ? "good" : "neutral"}">${o.delta}</div>` : "";
    wrap.innerHTML = `
      <div class="kpi-label">${o.label}</div>
      <div class="kpi-value">${o.value}</div>
      ${deltaHtml}
      ${o.sub ? `<div class="kpi-sub">${o.sub}</div>` : ""}`;
    node.appendChild(wrap);
  }

  // ---- axes helper ----------------------------------------------------------
  function drawAxes(svg, x0, y0, w, h, maxY, yFmt, ticks = 5, minY = 0) {
    for (let i = 0; i <= ticks; i++) {
      const val = minY + ((maxY - minY) * i) / ticks;
      const y = y0 - (h * i) / ticks;
      svg.appendChild(el("line", { x1: x0, y1: y, x2: x0 + w, y2: y, class: "grid" }));
      svg.appendChild(el("text", { x: x0 - 8, y: y + 4, class: "axis-lbl", "text-anchor": "end" }, yFmt ? yFmt(val) : fmtInt(val)));
    }
  }

  // ---- line / multi-line ----------------------------------------------------
  function line(node, o) {
    clear(node);
    const W = 720, H = 300, m = { t: 20, r: 24, b: 46, l: 60 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const svg = svgRoot(W, H);
    const labels = o.xLabels;
    const allY = o.series.flatMap((s) => s.points);
    const rawMax = Math.max(...allY, 0);
    const rawMin = Math.min(...allY, 0);
    const minY = o.yMin != null ? o.yMin : 0;
    const maxY = o.yMax != null ? o.yMax : niceMax(rawMax * 1.1);
    const span = maxY - minY || 1;
    const yFmt = o.yFmt || fmtInt;
    drawAxes(svg, m.l, m.t + ih, iw, ih, maxY, yFmt, 5, minY);
    const xStep = labels.length > 1 ? iw / (labels.length - 1) : iw;
    labels.forEach((lb, i) => {
      const x = m.l + xStep * i;
      if (labels.length <= 14 || i % Math.ceil(labels.length / 12) === 0)
        svg.appendChild(el("text", { x, y: m.t + ih + 22, class: "axis-lbl", "text-anchor": "middle" }, lb));
    });
    o.series.forEach((s) => {
      const pts = s.points.map((v, i) => [m.l + xStep * i, m.t + ih - (ih * (v - minY)) / span]);
      const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
      if (o.area) {
        const area = d + ` L ${pts[pts.length - 1][0].toFixed(1)} ${(m.t + ih)} L ${pts[0][0].toFixed(1)} ${(m.t + ih)} Z`;
        svg.appendChild(el("path", { d: area, fill: s.color, opacity: 0.12 }));
      }
      svg.appendChild(el("path", { d, fill: "none", stroke: s.color, "stroke-width": 2.5, "stroke-linejoin": "round", "stroke-linecap": "round" }));
      pts.forEach((p, i) => {
        const c = el("circle", { cx: p[0], cy: p[1], r: 3.5, fill: "#fff", stroke: s.color, "stroke-width": 2 });
        hoverable(c, `<span style="color:${s.color}">●</span> ${s.name}<br>${labels[i]}: <b>${yFmt(s.points[i])}</b>`);
        svg.appendChild(c);
      });
    });
    node.appendChild(svg);
    if (o.series.length > 1 || o.legend) legend(node, o.series.map((s) => ({ label: s.name, color: s.color })));
  }

  // ---- vertical/horizontal bars --------------------------------------------
  function bars(node, o) {
    clear(node);
    const horizontal = !!o.horizontal;
    const yFmt = o.yFmt || fmtInt;
    const W = 720, H = 300, m = { t: 20, r: 24, b: 54, l: horizontal ? 120 : 60 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const svg = svgRoot(W, H);
    const maxV = niceMax(Math.max(...o.values, 0) * 1.1);
    if (!horizontal) {
      drawAxes(svg, m.l, m.t + ih, iw, ih, maxV, yFmt);
      const bw = (iw / o.labels.length) * 0.62;
      const step = iw / o.labels.length;
      o.labels.forEach((lb, i) => {
        const x = m.l + step * i + step / 2;
        const bh = (ih * o.values[i]) / maxV;
        const color = Array.isArray(o.color) ? o.color[i % o.color.length] : (o.color || "var(--c1)");
        const r = el("rect", { x: x - bw / 2, y: m.t + ih - bh, width: bw, height: bh, rx: 3, fill: color });
        hoverable(r, `${lb}: <b>${yFmt(o.values[i])}</b>`);
        svg.appendChild(r);
        svg.appendChild(el("text", { x, y: m.t + ih + 20, class: "axis-lbl", "text-anchor": "middle" }, lb.length > 12 ? lb.slice(0, 11) + "…" : lb));
      });
    } else {
      const bh = (ih / o.labels.length) * 0.62;
      const step = ih / o.labels.length;
      for (let i = 0; i <= 5; i++) {
        const x = m.l + (iw * i) / 5;
        svg.appendChild(el("line", { x1: x, y1: m.t, x2: x, y2: m.t + ih, class: "grid" }));
        svg.appendChild(el("text", { x, y: m.t + ih + 20, class: "axis-lbl", "text-anchor": "middle" }, yFmt((maxV * i) / 5)));
      }
      o.labels.forEach((lb, i) => {
        const y = m.t + step * i + step / 2;
        const bw = (iw * o.values[i]) / maxV;
        const color = Array.isArray(o.color) ? o.color[i % o.color.length] : (o.color || "var(--c1)");
        const r = el("rect", { x: m.l, y: y - bh / 2, width: Math.max(bw, 0), height: bh, rx: 3, fill: color });
        hoverable(r, `${lb}: <b>${yFmt(o.values[i])}</b>`);
        svg.appendChild(r);
        svg.appendChild(el("text", { x: m.l - 10, y: y + 4, class: "axis-lbl", "text-anchor": "end" }, lb.length > 16 ? lb.slice(0, 15) + "…" : lb));
      });
    }
    node.appendChild(svg);
  }

  // ---- grouped bars ---------------------------------------------------------
  function groupedBars(node, o) {
    clear(node);
    const yFmt = o.yFmt || fmtInt;
    const W = 720, H = 300, m = { t: 20, r: 24, b: 54, l: 60 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const svg = svgRoot(W, H);
    const maxV = niceMax(Math.max(...o.groups.flatMap((g) => g.values), 0) * 1.1);
    drawAxes(svg, m.l, m.t + ih, iw, ih, maxV, yFmt);
    const step = iw / o.labels.length;
    const gband = step * 0.72, bw = gband / o.groups.length;
    o.labels.forEach((lb, i) => {
      const gx = m.l + step * i + (step - gband) / 2;
      o.groups.forEach((g, j) => {
        const bh = (ih * g.values[i]) / maxV;
        const r = el("rect", { x: gx + bw * j, y: m.t + ih - bh, width: bw * 0.86, height: bh, rx: 2, fill: g.color });
        hoverable(r, `${lb} — <span style="color:${g.color}">${g.name}</span>: <b>${yFmt(g.values[i])}</b>`);
        svg.appendChild(r);
      });
      svg.appendChild(el("text", { x: m.l + step * i + step / 2, y: m.t + ih + 20, class: "axis-lbl", "text-anchor": "middle" }, lb));
    });
    node.appendChild(svg);
    legend(node, o.groups.map((g) => ({ label: g.name, color: g.color })));
  }

  // ---- stacked bars ---------------------------------------------------------
  function stackedBars(node, o) {
    clear(node);
    const yFmt = o.yFmt || fmtInt;
    const W = 720, H = 300, m = { t: 20, r: 24, b: 54, l: 60 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const svg = svgRoot(W, H);
    const totals = o.labels.map((_, i) => o.groups.reduce((s, g) => s + g.values[i], 0));
    const maxV = niceMax(Math.max(...totals, 0) * 1.1);
    drawAxes(svg, m.l, m.t + ih, iw, ih, maxV, yFmt);
    const step = iw / o.labels.length, bw = step * 0.6;
    o.labels.forEach((lb, i) => {
      const x = m.l + step * i + step / 2 - bw / 2;
      let acc = 0;
      o.groups.forEach((g) => {
        const bh = (ih * g.values[i]) / maxV;
        const y = m.t + ih - acc - bh;
        const r = el("rect", { x, y, width: bw, height: bh, fill: g.color });
        hoverable(r, `${lb} — <span style="color:${g.color}">${g.name}</span>: <b>${yFmt(g.values[i])}</b>`);
        svg.appendChild(r);
        acc += bh;
      });
      svg.appendChild(el("text", { x: x + bw / 2, y: m.t + ih + 20, class: "axis-lbl", "text-anchor": "middle" }, lb));
    });
    node.appendChild(svg);
    legend(node, o.groups.map((g) => ({ label: g.name, color: g.color })));
  }

  // ---- donut ----------------------------------------------------------------
  function donut(node, o) {
    clear(node);
    const W = 340, H = 300, cx = 150, cy = 150, R = 110, r = 66;
    const svg = svgRoot(W, H);
    const total = o.items.reduce((s, it) => s + it.value, 0) || 1;
    let a0 = -Math.PI / 2;
    o.items.forEach((it) => {
      const frac = it.value / total, a1 = a0 + frac * 2 * Math.PI;
      const large = a1 - a0 > Math.PI ? 1 : 0;
      const p = (ang, rad) => [cx + rad * Math.cos(ang), cy + rad * Math.sin(ang)];
      const [x0, y0] = p(a0, R), [x1, y1] = p(a1, R), [x2, y2] = p(a1, r), [x3, y3] = p(a0, r);
      const d = `M ${x0} ${y0} A ${R} ${R} 0 ${large} 1 ${x1} ${y1} L ${x2} ${y2} A ${r} ${r} 0 ${large} 0 ${x3} ${y3} Z`;
      const path = el("path", { d, fill: it.color });
      hoverable(path, `<span style="color:${it.color}">●</span> ${it.label}: <b>${fmtInt(it.value)}</b> (${fmtPct(frac * 100)})`);
      svg.appendChild(path);
      a0 = a1;
    });
    svg.appendChild(el("text", { x: cx, y: cy - 4, "text-anchor": "middle", class: "donut-total" }, o.centerValue || fmtInt(total)));
    svg.appendChild(el("text", { x: cx, y: cy + 16, "text-anchor": "middle", class: "donut-sub" }, o.centerLabel || "Total"));
    node.appendChild(svg);
    legend(node, o.items.map((it) => ({ label: `${it.label} — ${fmtPct((it.value / total) * 100)}`, color: it.color })));
  }

  // ---- legend ---------------------------------------------------------------
  function legend(node, items) {
    const lg = document.createElement("div");
    lg.className = "chart-legend";
    lg.innerHTML = items.map((it) => `<span class="lg-item"><span class="lg-dot" style="background:${it.color}"></span>${it.label}</span>`).join("");
    node.appendChild(lg);
  }

  // ---- data table -----------------------------------------------------------
  function table(node, o) {
    clear(node);
    const t = document.createElement("table");
    t.className = "data-table";
    const thead = document.createElement("thead");
    thead.innerHTML = "<tr>" + o.columns.map((c) => `<th class="${c.align || "left"}">${c.label}</th>`).join("") + "</tr>";
    const tbody = document.createElement("tbody");
    o.rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = o.columns.map((c) => {
        let v = row[c.key];
        if (c.fmt) v = c.fmt(v, row);
        const badge = c.badge ? c.badge(row[c.key], row) : "";
        return `<td class="${c.align || "left"}">${badge || v}</td>`;
      }).join("");
      tbody.appendChild(tr);
    });
    t.appendChild(thead); t.appendChild(tbody);
    node.appendChild(t);
  }

  // ---- forecast: history + projected line with confidence band ------------
  function forecast(node, o) {
    clear(node);
    const W = 720, H = 300, m = { t: 20, r: 24, b: 46, l: 60 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const svg = svgRoot(W, H);
    const hist = o.histValues, pt = o.point, lo = o.lower, up = o.upper;
    const labels = o.histLabels.concat(o.futureLabels);
    const nH = hist.length, nAll = labels.length;
    const yFmt = o.yFmt || fmtInt;
    const all = hist.concat(pt, up, lo);
    const maxY = niceMax(Math.max(...all) * 1.08);
    const minY = Math.min(0, Math.min(...all));
    const span = maxY - minY || 1;
    drawAxes(svg, m.l, m.t + ih, iw, ih, maxY, yFmt, 5, minY);
    const xStep = nAll > 1 ? iw / (nAll - 1) : iw;
    const X = (i) => m.l + xStep * i;
    const Y = (v) => m.t + ih - (ih * (v - minY)) / span;
    labels.forEach((lb, i) => {
      if (nAll <= 16 || i % Math.ceil(nAll / 12) === 0)
        svg.appendChild(el("text", { x: X(i), y: m.t + ih + 22, class: "axis-lbl", "text-anchor": "middle" }, lb));
    });
    const color = o.color || "var(--c1)";
    // forecast region shading + CI band
    svg.appendChild(el("rect", { x: X(nH - 1), y: m.t, width: iw - (X(nH - 1) - m.l), height: ih, fill: color, opacity: 0.05 }));
    const bandTop = pt.map((v, i) => [X(nH + i), Y(up[i])]);
    const bandBot = pt.map((v, i) => [X(nH + i), Y(lo[i])]);
    const startTop = [X(nH - 1), Y(hist[nH - 1])];
    const bandPath = "M " + startTop[0] + " " + startTop[1] + " " +
      bandTop.map(p => "L " + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ") + " " +
      bandBot.reverse().map(p => "L " + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ") + " Z";
    svg.appendChild(el("path", { d: bandPath, fill: color, opacity: 0.15 }));
    // history line
    const hp = hist.map((v, i) => [X(i), Y(v)]);
    svg.appendChild(el("path", { d: hp.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" "), fill: "none", stroke: color, "stroke-width": 2.5 }));
    // forecast line (dashed), connected to last history point
    const fp = [[X(nH - 1), Y(hist[nH - 1])]].concat(pt.map((v, i) => [X(nH + i), Y(v)]));
    svg.appendChild(el("path", { d: fp.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" "), fill: "none", stroke: color, "stroke-width": 2.5, "stroke-dasharray": "6 4" }));
    hist.forEach((v, i) => { const c = el("circle", { cx: X(i), cy: Y(v), r: 3, fill: "#fff", stroke: color, "stroke-width": 2 }); hoverable(c, `${o.histLabels[i]}: <b>${yFmt(v)}</b>`); svg.appendChild(c); });
    pt.forEach((v, i) => { const c = el("circle", { cx: X(nH + i), cy: Y(v), r: 3, fill: color, stroke: "#fff", "stroke-width": 1.5 }); hoverable(c, `${o.futureLabels[i]} (forecast): <b>${yFmt(v)}</b><br>range ${yFmt(lo[i])} – ${yFmt(up[i])}`); svg.appendChild(c); });
    node.appendChild(svg);
    legend(node, [{ label: "Actual", color }, { label: "Forecast (95% band)", color }]);
  }

  // ---- ROC curve (numeric 0..1 axes) --------------------------------------
  function roc(node, o) {
    clear(node);
    const S = 300, m = 40, iw = S - m - 14, ih = S - m - 14;
    const svg = svgRoot(S, S);
    const X = (v) => m + iw * v, Y = (v) => (S - m) - ih * v;
    for (let i = 0; i <= 5; i++) {
      const g = i / 5;
      svg.appendChild(el("line", { x1: X(g), y1: Y(0), x2: X(g), y2: Y(1), class: "grid" }));
      svg.appendChild(el("line", { x1: X(0), y1: Y(g), x2: X(1), y2: Y(g), class: "grid" }));
      svg.appendChild(el("text", { x: X(g), y: S - m + 16, class: "axis-lbl", "text-anchor": "middle" }, g.toFixed(1)));
      svg.appendChild(el("text", { x: m - 8, y: Y(g) + 4, class: "axis-lbl", "text-anchor": "end" }, g.toFixed(1)));
    }
    svg.appendChild(el("line", { x1: X(0), y1: Y(0), x2: X(1), y2: Y(1), stroke: "#9ca3af", "stroke-width": 1.2, "stroke-dasharray": "5 4" }));
    const color = o.color || "var(--c1)";
    const d = o.points.map((p, i) => (i ? "L" : "M") + X(p[0]).toFixed(1) + " " + Y(p[1]).toFixed(1)).join(" ");
    svg.appendChild(el("path", { d, fill: "none", stroke: color, "stroke-width": 2.6, "stroke-linejoin": "round" }));
    svg.appendChild(el("text", { x: X(0.55), y: Y(0.22), fill: color, "font-size": 15, "font-weight": 800 }, "AUC " + o.auc));
    svg.appendChild(el("text", { x: X(0.5), y: S - 4, class: "axis-lbl", "text-anchor": "middle" }, "False positive rate"));
    node.appendChild(svg);
  }

  global.Charts = { kpi, line, bars, groupedBars, stackedBars, donut, table, forecast, roc, legend, fmt: { int: fmtInt, num: fmtNum, pct: fmtPct, money: fmtMoney } };
})(window);
