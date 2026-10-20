export function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = value ?? "";
  return node.innerHTML;
}

export function verdictChip(verdict) {
  const value = verdict || "Uncertain";
  const cls = value === "Likely Synthetic" ? "synthetic" : value === "Likely Real" ? "real" : "uncertain";
  const icon = value === "Likely Synthetic" ? "✕" : value === "Likely Real" ? "✓" : "!";
  return '<span class="chip ' + cls + '"><span aria-hidden="true">' + icon + "</span> " + escapeHtml(value) + "</span>";
}

export function scoreGauge(score, threshold, band) {
  if (score == null) return '<div class="empty">No speech windows were available for scoring.</div>';
  const marker = Math.max(0, Math.min(100, Number(threshold) * 100));
  const radius = Math.max(0, Math.min(100, Number(band) * 100));
  return '<div class="prob">' + Number(score).toFixed(3) + '</div>' +
    '<div class="muted">Estimated fake score (not a calibrated real-world probability)</div>' +
    '<div class="gauge" role="img" aria-label="Score ' + Number(score).toFixed(3) + '; threshold ' + Number(threshold).toFixed(3) + '">' +
    '<span class="score-fill" style="width:' + Math.max(0, Math.min(100, Number(score) * 100)) + '%"></span>' +
    '<span class="uncertain-range" style="left:' + Math.max(0, marker - radius) + '%;width:' + Math.min(100, radius * 2) + '%"></span>' +
    '<span class="marker" style="left:' + marker + '%"></span></div>' +
    '<div class="muted">0 = real · threshold ' + Number(threshold).toFixed(3) + ' · 1 = synthetic · uncertain band ±' + Number(band).toFixed(3) + '</div>';
}

export function timeline(windows = []) {
  if (!windows.length) return '<div class="empty">No timeline data available.</div>';
  return '<div class="timeline" role="img" aria-label="Score timeline">' + windows.map((window) => {
    const score = window.prob == null ? 0 : Number(window.prob);
    const start = Number(window.t_start ?? window.t ?? 0);
    const end = Number(window.t_end ?? start);
    const speech = window.speech !== false;
    const title = start.toFixed(2) + '–' + end.toFixed(2) + ' s · ' +
      (speech && window.prob != null ? score.toFixed(3) : 'No speech');
    return '<span class="bar ' + (speech ? '' : 'silent') + '" title="' + title +
      '" style="height:' + Math.max(3, score * 100) + '%"></span>';
  }).join('') + '</div>';
}

export function number(value, digits = 2) {
  return value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toFixed(digits);
}
