// Section lens: the profile drawn EXACTLY from Form IR segments (lines and
// arcs) — no mesh, no tolerance fuzz. For profile-driven parts this is the
// primary truth, not the STL.
const TAG_COLORS = {
  cavity_inner: "#4dc3d6", cable_contact: "#4dc3d6", mouth_face: "#f0a832",
  mouth_upper: "#f0a832", mouth_lower: "#f0a832", upper_lip: "#46c07a",
  lower_lip: "#46c07a", mount_face: "#d9b544", tongue_bottom: "#d9b544",
  neck: "#8a93a3", hook_outer: "#8a93a3", external: "#8a93a3",
};

function segColor(tags) {
  for (const t of tags) if (TAG_COLORS[t]) return TAG_COLORS[t];
  return "#8a93a3";
}

function arcPath(seg) {
  const [ax, ay] = seg.a, [bx, by] = seg.b, [cx, cy] = seg.center;
  const r = Math.hypot(ax - cx, ay - cy);
  // sweep angle to pick large-arc flag
  let a0 = Math.atan2(ay - cy, ax - cx), a1 = Math.atan2(by - cy, bx - cx);
  let sweep = seg.ccw ? a1 - a0 : a0 - a1;
  while (sweep < 0) sweep += Math.PI * 2;
  const large = sweep > Math.PI ? 1 : 0;
  // SVG y-axis is flipped (we scale y by -1 in the group), so ccw stays ccw
  const sweepFlag = seg.ccw ? 1 : 0;
  return `M ${ax} ${ay} A ${r} ${r} 0 ${large} ${sweepFlag} ${bx} ${by}`;
}

export function renderSection(container, form) {
  if (!form || !form.section || !form.section.segments.length) {
    container.innerHTML = `<div class="dim" style="padding:40px">no section IR</div>`;
    return;
  }
  const segs = form.section.segments;
  let minU = 1e9, minV = 1e9, maxU = -1e9, maxV = -1e9;
  const upd = ([u, v]) => {
    minU = Math.min(minU, u); maxU = Math.max(maxU, u);
    minV = Math.min(minV, v); maxV = Math.max(maxV, v);
  };
  for (const s of segs) {
    upd(s.a); upd(s.b);
    if (s.type === "arc") {
      const r = Math.hypot(s.a[0] - s.center[0], s.a[1] - s.center[1]);
      upd([s.center[0] - r, s.center[1] - r]);
      upd([s.center[0] + r, s.center[1] + r]);
    }
  }
  const pad = Math.max((maxU - minU), (maxV - minV)) * 0.12 + 6;
  const w = maxU - minU + 2 * pad, h = maxV - minV + 2 * pad;
  const parts = [];
  for (const s of segs) {
    const d = s.type === "arc"
      ? arcPath(s)
      : `M ${s.a[0]} ${s.a[1]} L ${s.b[0]} ${s.b[1]}`;
    parts.push(
      `<path d="${d}" fill="none" stroke="${segColor(s.tags)}" ` +
      `stroke-width="0.8" vector-effect="non-scaling-stroke">` +
      `<title>${s.tags.join(", ") || "segment"}</title></path>`
    );
  }
  // Frame annotations live in HTML BESIDE the drawing, never inside the
  // viewBox — a tiny profile (a ring's 2x8mm half-section) must not fight
  // its own labels for space.
  const f = form.frame || {};
  const noteKeys = [
    ["mouth_gap", "mouth_gap"], ["r_cavity", "r_cavity"],
    ["wall", "wall"], ["snap_arc_deg", "arc_deg"],
    ["inner_w", "inner_w"], ["tongue_t", "tongue_t"],
    ["sweep_span", "span"], ["sweep_rise", "rise"],
    ["inner_d_effective", "bore ⌀ eff"], ["band_h", "band_h"],
    ["cyl_r_mid", "r_mid"],
  ];
  const notes = noteKeys
    .filter(([k]) => f[k] !== undefined)
    .map(([k, label]) =>
      `<div><span>${label}</span><b>${Number(f[k]).toFixed(2)}</b></div>`)
    .join("");
  const cellPx = Math.max(w, h) / 20;
  container.innerHTML = `
    <div class="section-wrap">
      <div class="section-box">
        <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet">
          <defs><pattern id="bgrid" width="${cellPx}" height="${cellPx}" patternUnits="userSpaceOnUse">
            <path d="M ${cellPx} 0 L 0 0 0 ${cellPx}" fill="none" stroke="#1b2027" stroke-width="${cellPx / 40}"/>
          </pattern></defs>
          <rect width="${w}" height="${h}" fill="url(#bgrid)"/>
          <g transform="translate(${pad - minU}, ${h - pad + minV}) scale(1,-1)">
            ${parts.join("\n")}
          </g>
        </svg>
      </div>
      <div class="section-meta">
        ${notes || '<div class="faint">no headline frame values</div>'}
        <div class="section-caption">section: ${form.section.name}<br>plane ${form.section.plane} · exact IR, no mesh</div>
      </div>
    </div>`;
}
