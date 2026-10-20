import { api } from "./api.js";
import { state, setProfile } from "./state.js";
import { escapeHtml as esc, number, scoreGauge, timeline, verdictChip } from "./render.js";

const pages = [
  ["Dashboard", "dashboard"], ["Analyze File", "analyze-file"], ["Live Check", "live-check"],
  ["Call Monitor", "call-monitor"], ["History", "history"],
  ["Model & Evaluation", "model-and-evaluation"], ["Settings", "settings"],
];
const nav = document.querySelector("#nav");
const content = document.querySelector("#content");
const title = document.querySelector("#page-title");
const status = document.querySelector("#status");
const profileSelect = document.querySelector("#model-profile");
const modelStatus = document.querySelector("#model-status");

function navMarkup() {
  nav.innerHTML = pages.map(([name, slug]) =>
    '<button class="nav-link" type="button" data-page="' + slug + '">' + esc(name) + "</button>"
  ).join("");
  nav.querySelectorAll("[data-page]").forEach((button) =>
    button.addEventListener("click", () => navigate(button.dataset.page))
  );
}

function setPage(html) {
  content.innerHTML = html;
  status.innerHTML = "";
  nav.querySelectorAll(".nav-link").forEach((button) =>
    button.classList.toggle("active", button.dataset.page === location.hash.slice(1))
  );
}

function reportError(error) {
  status.innerHTML = '<div class="error" role="alert">' + esc(error?.message || error) + "</div>";
}

function navTo(page) { location.hash = page; }

function navigate(page) {
  if (!pages.some(([, slug]) => slug === page)) page = "dashboard";
  if (location.hash.slice(1) !== page) { location.hash = page; return; }
  renderPage(page);
}

function detailList(entries) {
  return '<dl class="detail-list">' + entries.map(([label, value]) =>
    "<div><dt>" + esc(label) + "</dt><dd>" + esc(value) + "</dd></div>"
  ).join("") + "</dl>";
}

function table(headers, rows) {
  if (!rows.length) return '<div class="empty">No records are available.</div>';
  return '<div class="table-scroll"><table><thead><tr>' +
    headers.map((header) => "<th>" + esc(header) + "</th>").join("") +
    "</tr></thead><tbody>" + rows.join("") + "</tbody></table></div>";
}

function metricTable(metrics) {
  const keys = ["accuracy", "precision", "recall", "f1", "fpr", "fnr", "eer", "roc_auc"];
  return table(["Metric", "Measured value"], keys.map((key) =>
    "<tr><th>" + key.toUpperCase() + "</th><td>" + number(metrics[key], 4) + "</td></tr>"
  ));
}

async function refreshHeader() {
  profileSelect.value = state.profile;
  try {
    const [health, model] = await Promise.all([api.health(), api.model(state.profile)]);
    modelStatus.textContent = health.profiles?.[state.profile] ? model.name + " ready" : "Model unavailable";
    modelStatus.classList.toggle("offline", !health.profiles?.[state.profile]);
  } catch (error) {
    modelStatus.textContent = "Backend unavailable";
    modelStatus.classList.add("offline");
    if (content.children.length) reportError(error);
  }
}

async function renderDashboard() {
  setPage('<div class="card loading">Loading saved analysis data…</div>');
  try {
    const [data, model] = await Promise.all([api.dashboard(), api.model(state.profile)]);
    const recent = data.recent || [];
    const rows = recent.map((row) => "<tr><td>" + esc(new Date(row.created_at).toLocaleString()) +
      "</td><td>" + esc(row.source) + "</td><td>" + esc(row.name) + "</td><td>" +
      verdictChip(row.verdict) + "</td><td>" + number(row.mean_prob, 3) + "</td></tr>");
    const bars = (data.series || []).map((row) => {
      const value = row.mean_prob == null ? 0 : Number(row.mean_prob);
      return '<span class="bar" title="' + esc(new Date(row.created_at).toLocaleString()) +
        " · score " + number(row.mean_prob, 3) + '" style="height:' + Math.max(3, value * 100) + '%"></span>';
    }).join("");
    setPage(
      '<div class="grid kpis">' +
      '<div class="card"><div class="metric-label">Saved analyses</div><div class="metric">' + data.total + "</div></div>" +
      '<div class="card"><div class="metric-label">Likely synthetic</div><div class="metric">' + data.flagged +
      '</div><div class="metric-sub">' + number(Number(data.flagged_pct) * 100, 1) + "% of saved analyses</div></div>" +
      '<div class="card"><div class="metric-label">Uncertain</div><div class="metric">' + data.uncertain + "</div></div>" +
      '<div class="card"><div class="metric-label">Mean processing time</div><div class="metric">' +
      (data.avg_latency_ms == null ? "—" : number(data.avg_latency_ms, 1) + " ms") + "</div></div></div>" +
      '<div class="grid two section-gap"><div class="card"><h2>Recent analyses</h2>' +
      table(["Time", "Source", "Name", "Verdict", "Fake score"], rows) +
      '</div><div class="card"><h2>Recent fake scores</h2>' +
      (bars ? '<div class="bar-chart" role="img" aria-label="Scores from recent saved analyses">' + bars + "</div>" :
        '<div class="empty">No saved analysis scores yet.</div>') + "</div></div>" +
      '<div class="card section-gap"><h2>Selected model</h2>' +
      detailList([["Model", model.name], ["Training dataset", model.training_dataset],
        ["Profile", model.profile || state.profile], ["Threshold", number(model.threshold, 4)],
        ["Model version", model.model_version]]) +
      '<div class="actions"><button class="btn primary" data-go="analyze-file">Analyze a file</button>' +
      '<button class="btn" data-go="history">Open history</button></div></div>'
    );
    content.querySelectorAll("[data-go]").forEach((button) =>
      button.addEventListener("click", () => navTo(button.dataset.go))
    );
  } catch (error) { setPage('<div class="error" role="alert">' + esc(error.message) + "</div>"); }
}

function analysisResult(result) {
  const speechWindows = (result.windows || []).filter((window) => window.speech).length;
  return '<div class="grid two section-gap"><div class="card"><h2>Result ' + verdictChip(result.verdict) + "</h2>" +
    scoreGauge(result.mean_prob, result.threshold, result.band ?? result.uncertain_band) + "</div>" +
    '<div class="card"><h2>Analysis details</h2>' + detailList([
      ["File", result.name], ["Duration", number(result.duration_s, 3) + " s"],
      ["Input sample rate", result.sample_rate + " Hz"], ["Speech windows", speechWindows],
      ["Speech ratio", number(Number(result.speech_ratio) * 100, 1) + "%"],
      ["Processing time", number(result.latency_ms, 1) + " ms"],
      ["Model version", result.model_version], ["Decision threshold", number(result.threshold, 4)],
    ]) + "</div></div><div class=\"card section-gap\"><h2>Timeline</h2>" +
    timeline(result.windows || []) + '<div class="muted">Bars follow the analysis window timestamps; silent windows are marked separately.</div></div>' +
    '<div class="actions section-gap"><button class="btn" id="export-result">Download this result as JSON</button></div>';
}

function downloadJson(name, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

function renderAnalyze() {
  setPage('<div class="card"><h2>Analyze File</h2><p class="muted">Select a supported audio file up to 10 MB. The selected model is shown in the page header.</p>' +
    '<div class="drop"><label for="audio-file">Audio file</label><input id="audio-file" type="file" accept=".wav,.flac,.ogg,.mp3,audio/wav,audio/flac,audio/ogg,audio/mpeg">' +
    '<button class="btn primary" id="analyze-file" type="button">Analyze file</button></div><div id="analysis-output"></div></div>' +
    '<p class="footer-note">This research model provides an additional verification signal, not proof. Scores may be wrong or uncertain.</p>');
  document.querySelector("#analyze-file").addEventListener("click", async () => {
    const file = document.querySelector("#audio-file").files[0];
    const output = document.querySelector("#analysis-output");
    if (!file) { output.innerHTML = '<div class="error">Choose an audio file first.</div>'; return; }
    output.innerHTML = '<div class="loading" role="status">Analyzing audio with the selected model…</div>';
    try {
      const result = await api.upload(file, state.profile);
      output.innerHTML = analysisResult(result);
      document.querySelector("#export-result").addEventListener("click", () =>
        downloadJson("voiceguard-analysis-" + result.id + ".json", result));
      await refreshHeader();
    } catch (error) { output.innerHTML = '<div class="error" role="alert">' + esc(error.message) + "</div>"; }
  });
}

async function renderHistory() {
  setPage('<div class="card"><h2>History</h2><form id="history-filter" class="filters">' +
    '<label>Source<select id="source-filter"><option value="">All sources</option><option value="Upload">Upload</option>' +
    '<option value="mic">Microphone</option><option value="system">System audio</option><option value="replay">Demo replay stream</option><option value="Demo">Demo clip analysis</option></select></label>' +
    '<label>Verdict<select id="verdict-filter"><option value="">All verdicts</option><option>Likely Real</option><option>Uncertain</option><option>Likely Synthetic</option></select></label>' +
    '<button class="btn" type="submit">Apply filters</button><a class="btn" download="voiceguard-history.csv" href="/api/history/export.csv">Export all history as CSV</a></form>' +
    '<div id="history-output" class="loading">Loading history…</div></div>');
  const output = document.querySelector("#history-output");
  async function load() {
    output.innerHTML = '<div class="loading">Loading matching records…</div>';
    try {
      const rows = await api.history({
        source: document.querySelector("#source-filter").value,
        verdict: document.querySelector("#verdict-filter").value,
      });
      const tableRows = rows.map((row) => '<tr><td>' + row.id + "</td><td>" +
        esc(new Date(row.created_at).toLocaleString()) + "</td><td>" + esc(row.source) + "</td><td>" +
        esc(row.name) + "</td><td>" + number(row.duration_s, 2) + " s</td><td>" +
        verdictChip(row.verdict) + "</td><td>" + number(row.mean_prob, 3) + "</td><td>" +
        esc(row.model_version) + '</td><td><button class="btn small" data-detail="' + row.id + '">Details</button></td></tr>' +
        '<tr class="detail-row" id="detail-' + row.id + '" hidden><td colspan="9"></td></tr>');
      output.innerHTML = table(["ID", "Date/time", "Source", "Name", "Duration", "Verdict", "Score", "Model", ""], tableRows);
      output.querySelectorAll("[data-detail]").forEach((button) => button.addEventListener("click", async () => {
        const target = document.querySelector("#detail-" + button.dataset.detail);
        if (!target.hidden) { target.hidden = true; return; }
        target.hidden = false;
        const cell = target.querySelector("td");
        cell.innerHTML = '<div class="loading">Loading stored detail…</div>';
        try {
          const detail = await api.historyDetail(button.dataset.detail);
          cell.innerHTML = detailList([["Model version", detail.model_version],
            ["Threshold used", number(detail.threshold, 4)], ["Uncertain band", number(detail.band, 4)],
            ["Maximum fake score", number(detail.max_prob, 4)], ["Latency", number(detail.latency_ms, 2) + " ms"]]) +
            timeline(detail.windows || []);
        } catch (error) { cell.innerHTML = '<div class="error">' + esc(error.message) + "</div>"; }
      }));
    } catch (error) { output.innerHTML = '<div class="error">' + esc(error.message) + "</div>"; }
  }
  document.querySelector("#history-filter").addEventListener("submit", (event) => { event.preventDefault(); load(); });
  await load();
}

async function renderModel() {
  setPage('<div class="card loading">Loading model metadata and evaluation files…</div>');
  try {
    const [model, metrics] = await Promise.all([api.model(state.profile), api.metrics(state.profile)]);
    if (!metrics.available) {
      setPage('<div class="empty">No evaluation results file is available for this model profile.</div>');
      return;
    }
    const report = metrics.results;
    const validation = report.models?.svm?.validation || report.validation;
    const test = report.models?.svm?.test || report.test;
    const confusion = test.confusion_matrix || [];
    const splitData = model.data_split || {};
    const subsetNote = report.max_files_per_class
      ? "Balanced subset report: up to " + (report.max_files_per_class * 2) + " files per split. Do not interpret as full natural-distribution performance."
      : "Metrics are from the saved evaluation report; held-out test performance is substantially weaker than validation.";
    setPage('<div class="grid two"><div class="card"><h2>Model card</h2>' + detailList([
      ["Model", model.name], ["Model version", model.model_version], ["Training dataset", model.training_dataset],
      ["Features", model.features], ["Feature details", model.feature_details],
      ["Inference contract", model.inference_kind || "Windowed"], ["Sample rate", model.sample_rate + " Hz"],
      ["Window / clip", (model.window_s == null ? "Complete clip" : number(model.window_s, 2) + " s")],
      ["Current decision threshold", number(model.threshold, 6)], ["Training files in report", splitData.training],
      ["Validation files in report", splitData.validation], ["Test files in report", splitData.testing],
      ["Score definition", model.score_definition],
    ]) + "</div><div class=\"card\"><h2>Held-out test metrics</h2><p class=\"muted\">" + esc(subsetNote) +
      "</p>" + metricTable(test) + '<h3>Confusion matrix (actual rows, predicted columns)</h3>' +
      table(["", "Predicted real", "Predicted synthetic"], confusion.map((row, index) =>
        "<tr><th>" + (index === 0 ? "Actual real" : "Actual synthetic") + "</th><td>" +
        esc(row[0]) + "</td><td>" + esc(row[1]) + "</td></tr>")) + "</div></div>" +
      '<div class="card section-gap"><h2>Validation metrics</h2>' + metricTable(validation) +
      '<p class="muted">The saved artifact threshold came from validation EER. Runtime threshold changes are saved with each analysis and do not change the model artifact.</p></div>' +
      '<div class="card section-gap"><h2>Known limitations</h2><ul>' +
      "<li>The FoR model has weak held-out test performance and a high false-negative rate.</li>" +
      "<li>The ASVspoof artifact was trained and evaluated on balanced subsets, not the full natural class distribution.</li>" +
      "<li>The ASVspoof model scores complete clips; live streaming currently uses the legacy FoR windowed model.</li>" +
      "<li>Live microphone and call audio can differ from training audio; results may be wrong or uncertain.</li></ul></div>");
  } catch (error) { setPage('<div class="error">' + esc(error.message) + "</div>"); }
}

async function renderSettings() {
  setPage('<div class="card loading">Loading saved settings…</div>');
  try {
    const settings = await api.settings(state.profile);
    setPage('<div class="card"><h2>Decision and streaming settings</h2>' +
      '<p class="muted">These settings apply to subsequent analyses. Each saved analysis keeps its own threshold and band.</p>' +
      '<div class="field"><label for="threshold">Decision threshold: <output id="threshold-value">' + number(settings.threshold, 4) + '</output></label>' +
      '<input id="threshold" type="range" min="0" max="1" step="0.001" value="' + settings.threshold + '"></div>' +
      '<div class="field"><label for="band">Uncertain band width: <output id="band-value">' + number(settings.uncertain_band, 3) + '</output></label>' +
      '<input id="band" type="range" min="0" max="0.3" step="0.005" value="' + settings.uncertain_band + '"></div>' +
      '<div class="field"><label for="hop">Streaming hop (seconds)</label><input id="hop" type="number" min="0.1" max="2" step="0.1" value="' + settings.hop_seconds + '"></div>' +
      '<div class="field"><label for="vad">Silence gate (RMS threshold)</label><input id="vad" type="number" min="0" max="1" step="0.001" value="' + settings.vad_threshold + '"></div>' +
      '<div class="field"><label for="smoothing">Smoothing strength: <output id="smoothing-value">' + number(settings.smoothing_alpha, 2) + '</output></label>' +
      '<input id="smoothing" type="range" min="0.05" max="1" step="0.05" value="' + settings.smoothing_alpha + '"></div>' +
      '<div class="field"><label for="alerts">Consecutive windows before alert</label><input id="alerts" type="number" min="1" max="100" step="1" value="' + settings.alert_consecutive_windows + '"></div>' +
      '<div class="actions"><button class="btn primary" id="save-settings" type="button">Save settings</button>' +
      '<button class="btn danger" id="clear-history" type="button">Clear history</button></div><div id="settings-message" role="status"></div></div>' +
      '<p class="footer-note">Raw audio is not stored. The application saves analysis scores and window metadata in local SQLite history.</p>');
    for (const [input, output] of [["threshold", "threshold-value"], ["band", "band-value"], ["smoothing", "smoothing-value"]]) {
      document.querySelector("#" + input).addEventListener("input", (event) => {
        document.querySelector("#" + output).value = event.target.value;
      });
    }
    document.querySelector("#save-settings").addEventListener("click", async () => {
      const message = document.querySelector("#settings-message");
      message.innerHTML = '<div class="loading">Saving settings…</div>';
      try {
        await api.saveSettings({
          threshold: Number(document.querySelector("#threshold").value),
          uncertain_band: Number(document.querySelector("#band").value),
          hop_seconds: Number(document.querySelector("#hop").value),
          vad_threshold: Number(document.querySelector("#vad").value),
          smoothing_alpha: Number(document.querySelector("#smoothing").value),
          alert_consecutive_windows: Number(document.querySelector("#alerts").value),
        }, state.profile);
        message.innerHTML = '<div class="success">Settings saved. They apply to the next analysis or stream.</div>';
        await refreshHeader();
      } catch (error) { message.innerHTML = '<div class="error">' + esc(error.message) + "</div>"; }
    });
    document.querySelector("#clear-history").addEventListener("click", async () => {
      if (!window.confirm("Delete all saved analysis history from this local application?")) return;
      try {
        await api.clearHistory();
        document.querySelector("#settings-message").innerHTML = '<div class="success">Saved analysis history cleared.</div>';
      } catch (error) {
        document.querySelector("#settings-message").innerHTML = '<div class="error">' + esc(error.message) + "</div>";
      }
    });
  } catch (error) { setPage('<div class="error">' + esc(error.message) + "</div>"); }
}

async function listAudioDevices() {
  const select = document.querySelector("#input-device");
  if (!select || !navigator.mediaDevices?.enumerateDevices) return;
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const microphones = devices.filter((device) => device.kind === "audioinput");
    select.innerHTML = '<option value="">Default microphone</option>' + microphones.map((device, index) =>
      '<option value="' + esc(device.deviceId) + '">' +
      esc(device.label || ("Microphone " + (index + 1))) + "</option>"
    ).join("");
  } catch (error) { reportError(error); }
}

function renderLive(mode) {
  const isCall = mode === "call";
  setPage('<div class="grid two"><div class="card"><h2>' + (isCall ? "Call Monitor" : "Live Check") + "</h2>" +
    '<p class="notice">Audio is analyzed on this device. Call Monitor is not connected to a phone network. Live windows use the legacy FoR model. Raw audio is not stored.</p>' +
    '<div class="field"><label for="source">Audio source</label><select id="source">' +
    '<option value="mic">Microphone</option><option value="system">System or tab audio</option>' +
    '<option value="replay">Locked demo replay</option></select></div>' +
    '<div class="field" id="device-field"><label for="input-device">Microphone device</label><select id="input-device"><option value="">Default microphone</option></select></div>' +
    '<div class="field" id="demo-field" hidden><label for="demo-sample">Demo sample (label hidden until after analysis)</label>' +
    '<select id="demo-sample"><option value="">Loading demo samples…</option></select></div>' +
    '<label class="consent"><input id="live-consent" type="checkbox"> I understand audio is processed locally by this application and is not saved as raw audio.</label>' +
    '<div class="actions"><button class="btn primary" id="start-live" type="button" disabled>Start ' + (isCall ? "monitoring" : "listening") +
    '</button><button class="btn" id="stop-live" type="button" disabled>Stop</button></div>' +
    '<div id="live-status" class="muted" role="status">Waiting for consent and source selection.</div>' +
    '<div id="live-result"></div><div id="demo-truth"></div></div>' +
    '<div class="card"><h2>Rolling score timeline</h2><div id="live-timeline" class="empty">Scores appear after speech windows are processed.</div></div></div>' +
    '<p class="footer-note">Research output is an additional verification signal. A live reading may be wrong or uncertain.</p>');
  const source = document.querySelector("#source");
  const consent = document.querySelector("#live-consent");
  const startButton = document.querySelector("#start-live");
  const stopButton = document.querySelector("#stop-live");
  const sourceChange = () => {
    document.querySelector("#demo-field").hidden = source.value !== "replay";
    document.querySelector("#device-field").hidden = source.value !== "mic";
  };
  source.addEventListener("change", sourceChange);
  consent.addEventListener("change", () => { startButton.disabled = !consent.checked; });
  stopButton.addEventListener("click", () => stopLive(false));
  startButton.addEventListener("click", () => startLive(mode));
  sourceChange();
  listAudioDevices();
  navigator.mediaDevices?.addEventListener?.("devicechange", listAudioDevices);
  api.demoSamples().then((samples) => {
    const demoSelect = document.querySelector("#demo-sample");
    if (!demoSelect) return;
    demoSelect.innerHTML = samples.map((sample) =>
      '<option value="' + esc(sample.id) + '">' + esc(sample.name) + " · " +
      number(sample.duration_s, 2) + " s</option>"
    ).join("");
    if (!samples.length) demoSelect.innerHTML = '<option value="">No demo samples available</option>';
  }).catch((error) => {
    const demoSelect = document.querySelector("#demo-sample");
    if (demoSelect) demoSelect.innerHTML = '<option value="">Demo samples unavailable</option>';
    document.querySelector("#live-status").textContent = error.message;
  });
}

function liveMessage(session, message) {
  const output = document.querySelector("#live-result");
  if (!output) return;
  if (message.type === "status") {
    document.querySelector("#live-status").textContent =
      message.state === "no_speech" ? "No speech detected in the latest window." :
      message.state === "lagging" ? "Processing is behind the incoming audio." : "Listening to audio.";
  } else if (message.type === "window") {
    session.windows.push({ t: message.t, prob: message.smoothed, speech: message.speech, verdict: message.verdict });
    output.innerHTML = "<h3>" + verdictChip(message.verdict) + "</h3>" +
      scoreGauge(message.smoothed, session.model.threshold, session.model.uncertain_band) +
      '<p class="muted">Processed windows: ' + session.windows.length +
      " · latest inference: " + number(message.latency_ms, 1) + " ms</p>";
    document.querySelector("#live-timeline").innerHTML = timeline(session.windows);
    document.querySelector("#live-status").textContent = message.speech ? "Speech window analyzed." : "No speech detected.";
  } else if (message.type === "alert") {
    output.innerHTML += '<div class="banner" role="alert">' + esc(message.message) + "</div>";
  } else if (message.type === "error") {
    document.querySelector("#live-status").innerHTML = '<span class="error">' + esc(message.message) + "</span>";
  } else if (message.type === "summary") {
    session.stopping = true;
    output.innerHTML += '<div class="card"><h3>Saved session summary</h3><p>' +
      verdictChip(message.verdict) + " · " + number(message.duration_s, 2) + " s · speech ratio " +
      number(Number(message.speech_ratio) * 100, 1) + "% · " + session.windows.length +
      " received windows</p><p class=\"muted\">Saved in local history as record " + esc(message.session_id) + ".</p></div>";
    document.querySelector("#live-status").textContent = "Session saved.";
    void cleanupCapture(session);
    if (session.demoId) revealDemoTruth(session);
  }
}

async function connectSocket(session) {
  return new Promise((resolve, reject) => {
    const socket = api.socket();
    session.socket = socket;
    let opened = false;
    socket.onopen = () => {
      opened = true;
      socket.send(JSON.stringify({ mode: session.mode, source: session.source, sample_rate: session.sampleRate }));
      resolve();
    };
    socket.onmessage = (event) => {
      try { liveMessage(session, JSON.parse(event.data)); }
      catch (error) { document.querySelector("#live-status").textContent = error.message; }
    };
    socket.onerror = () => { if (!opened) reject(new Error("Live analysis connection could not be opened.")); };
    socket.onclose = () => {
      if (session.stopping || !session.active) return;
      if (session.reconnects === 0) {
        session.reconnects += 1;
        document.querySelector("#live-status").textContent = "Connection dropped; reconnecting once. The next summary covers the remaining segment.";
        connectSocket(session).catch(() => finishPartial(session));
      } else finishPartial(session);
    };
  });
}

async function startLive(mode) {
  const startButton = document.querySelector("#start-live");
  const sourceName = document.querySelector("#source").value;
  const statusText = document.querySelector("#live-status");
  if (!document.querySelector("#live-consent").checked) return;
  startButton.disabled = true;
  statusText.textContent = "Requesting audio access…";
  const session = {
    mode, source: sourceName, sampleRate: null, profile: "legacy_for2sec",
    model: null, windows: [], reconnects: 0, active: true, stopping: false, tracks: [],
  };
  try {
    session.model = await api.model(session.profile);
    session.context = new AudioContext();
    await session.context.resume();
    await session.context.audioWorklet.addModule("/static/audio-worklet.js");
    if (sourceName === "mic") {
      const selectedDevice = document.querySelector("#input-device").value;
      session.stream = await navigator.mediaDevices.getUserMedia({
        audio: selectedDevice ? { deviceId: { exact: selectedDevice } } : true,
      });
      session.input = session.context.createMediaStreamSource(session.stream);
    } else if (sourceName === "system") {
      if (!navigator.mediaDevices.getDisplayMedia) throw new Error("This browser does not support system or tab audio capture.");
      session.stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
      if (!session.stream.getAudioTracks().length) {
        session.stream.getTracks().forEach((track) => track.stop());
        throw new Error("No audio was shared. Select a tab or screen and enable its audio, then try again.");
      }
      session.input = session.context.createMediaStreamSource(session.stream);
    } else {
      session.demoId = document.querySelector("#demo-sample").value;
      if (!session.demoId) throw new Error("No locked demo sample is available.");
      const blob = await api.demoAudio(session.demoId);
      const buffer = await session.context.decodeAudioData(await blob.arrayBuffer());
      const destination = session.context.createMediaStreamDestination();
      session.stream = destination.stream;
      session.input = session.context.createMediaStreamSource(session.stream);
      session.player = session.context.createBufferSource();
      session.player.buffer = buffer;
      session.player.connect(session.context.destination);
      session.player.connect(destination);
    }
    session.tracks = session.stream.getTracks();
    session.tracks.forEach((track) => {
      track.onended = () => { if (session.active && !session.stopping) stopLive(true); };
    });
    session.sampleRate = session.context.sampleRate;
    session.worklet = new AudioWorkletNode(session.context, "pcm16-capture", {
      numberOfInputs: 1, numberOfOutputs: 1, channelCount: 1, channelCountMode: "explicit",
    });
    session.sink = session.context.createGain();
    session.sink.gain.value = 0;
    session.worklet.connect(session.sink);
    session.sink.connect(session.context.destination);
    session.worklet.port.onmessage = (event) => {
      if (session.socket?.readyState === WebSocket.OPEN) session.socket.send(event.data);
    };
    session.input.connect(session.worklet);
    state.live = session;
    await connectSocket(session);
    if (session.player) {
      session.player.onended = () => stopLive(true);
      session.player.start();
    }
    document.querySelector("#stop-live").disabled = false;
    statusText.textContent = "Audio capture active. Scores arrive after a full model window is available.";
  } catch (error) {
    session.active = false;
    await cleanupCapture(session);
    startButton.disabled = false;
    statusText.innerHTML = '<span class="error" role="alert">' + esc(error.message || "Audio capture failed.") + "</span>";
  }
}

async function cleanupCapture(session) {
  if (!session) return;
  session.active = false;
  try { session.worklet?.disconnect(); } catch {}
  try { session.sink?.disconnect(); } catch {}
  try { session.input?.disconnect(); } catch {}
  session.tracks?.forEach((track) => track.stop());
  try { session.player?.stop(); } catch {}
  if (session.context && session.context.state !== "closed") {
    try { await session.context.close(); } catch {}
  }
  const stopButton = document.querySelector("#stop-live");
  if (stopButton) stopButton.disabled = true;
  const startButton = document.querySelector("#start-live");
  if (startButton) startButton.disabled = !document.querySelector("#live-consent")?.checked;
  if (state.live === session) state.live = null;
}

function stopLive(partial) {
  const session = state.live;
  if (!session) return;
  session.stopping = true;
  if (session.socket?.readyState === WebSocket.OPEN) session.socket.send(JSON.stringify({ type: "stop" }));
  void cleanupCapture(session);
  if (partial) document.querySelector("#live-status").textContent = "Audio source ended; requesting a partial session summary.";
}

function finishPartial(session) {
  if (!session.active) return;
  session.stopping = true;
  void cleanupCapture(session);
  const last = session.windows.at(-1);
  const output = document.querySelector("#live-result");
  if (output) output.innerHTML += '<div class="banner">Connection ended after one reconnect. The display below is a partial client summary; the server may have saved only its last connected segment.</div>' +
    '<div class="card"><h3>Partial summary</h3><p>Processed windows: ' + session.windows.length +
    " · last score: " + number(last?.prob, 3) + " · last verdict: " + verdictChip(last ? last.verdict : "Uncertain") + "</p></div>";
  const liveStatus = document.querySelector("#live-status");
  if (liveStatus) liveStatus.textContent = "Connection ended. Partial summary shown.";
}

async function revealDemoTruth(session) {
  const target = document.querySelector("#demo-truth");
  if (!target) return;
  target.innerHTML = '<div class="loading">Analyzing the same demo with the ASVspoof complete-clip model to reveal its label…</div>';
  try {
    const result = await api.demoAnalyze(session.demoId);
    target.innerHTML = '<div class="card"><h3>Demo ground truth revealed after replay</h3>' +
      detailList([["Actual label", result.ground_truth], ["Attack ID", result.attack_id],
        ["ASVspoof complete-clip model", result.model_version], ["Clip-model verdict", result.verdict],
        ["Clip-model score", number(result.mean_prob, 4)]]) +
      '<p class="notice">The live replay above uses the FoR windowed model. Its cross-dataset stream score is shown for demonstration only and is not a valid ASVspoof evaluation.</p></div>';
  } catch (error) { target.innerHTML = '<div class="error">' + esc(error.message) + "</div>"; }
}

function renderPage(page) {
  const pair = pages.find(([, slug]) => slug === page);
  title.textContent = pair ? pair[0] : "Dashboard";
  refreshHeader();
  if (page === "analyze-file") renderAnalyze();
  else if (page === "live-check") renderLive("mic");
  else if (page === "call-monitor") renderLive("call");
  else if (page === "history") renderHistory();
  else if (page === "model-and-evaluation") renderModel();
  else if (page === "settings") renderSettings();
  else renderDashboard();
}

navMarkup();
profileSelect.addEventListener("change", () => {
  setProfile(profileSelect.value);
  refreshHeader();
  if (location.hash === "#model-and-evaluation") renderModel();
});
window.addEventListener("hashchange", () => {
  const page = location.hash.slice(1);
  renderPage(pages.some(([, slug]) => slug === page) ? page : "dashboard");
});
if (!location.hash) history.replaceState(null, "", "#dashboard");
renderPage(pages.some(([, slug]) => slug === location.hash.slice(1)) ? location.hash.slice(1) : "dashboard");
