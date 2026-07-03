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
  // frame annotations: the headline numbers, straight from the frame dict.
  // font size lives in viewBox units — scale it to the drawing, not the px.
  const fs = Math.max(h, w) * 0.028;
  const f = form.frame || {};
  const notes = [];
  const noteKeys = [
    ["mouth_gap", "mouth_gap"], ["r_cavity", "r_cavity"],
    ["wall", "wall"], ["snap_arc_deg", "arc_deg"],
    ["inner_w", "inner_w"], ["tongue_t", "tongue_t"],
    ["sweep_span", "span"], ["sweep_rise", "rise"],
  ];
  let ny = fs * 1.4;
  for (const [k, label] of noteKeys) {
    if (f[k] !== undefined) {
      notes.push(`<text x="${fs * 0.5}" y="${ny}" font-size="${fs}" fill="#8a93a3" font-family="monospace">${label}: ${Number(f[k]).toFixed(2)}</text>`);
      ny += fs * 1.35;
    }
  }
  container.innerHTML = `
    <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet">
      <defs><pattern id="bgrid" width="${w / 24}" height="${w / 24}" patternUnits="userSpaceOnUse">
        <path d="M ${w / 24} 0 L 0 0 0 ${w / 24}" fill="none" stroke="#1b2027" stroke-width="${w / 900}"/>
      </pattern></defs>
      <rect width="${w}" height="${h}" fill="url(#bgrid)"/>
      <g transform="translate(${pad - minU}, ${h - pad + minV}) scale(1,-1)">
        ${parts.join("\n")}
      </g>
      ${notes.join("\n")}
      <text x="${fs * 0.5}" y="${h - fs * 0.5}" font-size="${fs * 0.8}" fill="#565e6c" font-family="monospace">section: ${form.section.name} · plane ${form.section.plane} · exact IR, no mesh</text>
    </svg>`;
}
