(() => {
  const livePage = ["/live-check", "/call-monitor"].includes(location.pathname);
  let activeProfile = livePage ? "legacy_for2sec" : (localStorage.getItem("voiceguard.profile") || "legacy_for2sec");
  const routes = {
    dashboard: "/dashboard",
    "analyze-file": "/analyze-file",
    "live-check": "/live-check",
    "call-monitor": "/call-monitor",
    history: "/history",
    "model-and-evaluation": "/model-and-evaluation",
    settings: "/settings",
  };

  function bindNavigation() {
    document.querySelectorAll("[data-path]").forEach((link) => {
      link.addEventListener("click", (event) => {
        const destination = routes[link.dataset.path];
        if (destination) {
          event.preventDefault();
          window.location.assign(destination);
        }
      });
    });
  }

  function downloadFile(filename, contents, type) {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([contents], { type }));
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function bindPageActions() {
    document.querySelectorAll('button[onclick*="alert("], a[onclick*="alert("]').forEach((control) => control.remove());
    document.querySelector("#reeval-suite-btn")?.remove();
    const report = document.querySelector("#export-report-btn");
    if (report) {
      const label = report.querySelector("[data-report-label]");
      if (label) label.textContent = "Download evaluation JSON";
      report.onclick = async () => {
        report.disabled = true;
        try {
          const response = await fetch(`/api/model/metrics?profile=${encodeURIComponent(activeProfile)}`);
          const payload = await response.json();
          if (!response.ok || !payload.available) throw new Error(payload.detail || "Evaluation report is unavailable.");
          downloadFile(`${activeProfile}-evaluation.json`, JSON.stringify(payload, null, 2), "application/json");
        } catch (error) {
          window.alert(error.message || "Evaluation report could not be downloaded.");
        } finally {
          report.disabled = false;
        }
      };
    }
    document.querySelectorAll("button").forEach((button) => {
      if (button.textContent.includes("Export CSV")) button.onclick = async () => {
        const csv = await fetch("/api/history/export.csv").then((response) => response.text());
        downloadFile("voiceguard-history.csv", csv, "text/csv");
      };
      else if (button.textContent.includes("Batch Telemetry Export")) button.onclick = async () => {
        const rows = await fetch("/api/history").then((response) => response.json());
        downloadFile("voiceguard-history.json", JSON.stringify(rows, null, 2), "application/json");
      };
    });
    window.downloadTelemetryJSON = () => {
      if (window.voiceguardLastAnalysis) downloadFile("voiceguard-analysis.json", JSON.stringify(window.voiceguardLastAnalysis, null, 2), "application/json");
    };
    document.querySelectorAll("a[data-path]").forEach((link) => {
      const destination = routes[link.dataset.path];
      if (destination) link.href = destination;
    });
    document.querySelectorAll("button").forEach((button) => {
      if (button.textContent.includes("Start live check")) button.onclick = () => { location.href = routes["live-check"]; };
      if (button.textContent.includes("Monitor a call")) button.onclick = () => { location.href = routes["call-monitor"]; };
      if (button.textContent.includes("Analyze file")) button.onclick = () => { location.href = routes["analyze-file"]; };
    });
  }

  function applyResponsiveShell() {
    const style = document.createElement("style");
    style.textContent = `
      #voiceguard-mobile-nav{display:none}
      @media(max-width:767px){
        html,body{width:100%;max-width:100vw;overflow-x:hidden}
        aside{display:none!important}
        .pl-\\[240px\\]{box-sizing:border-box;width:100%;max-width:100%;min-width:0;padding-left:0!important}
        header.fixed{left:0!important;right:0!important;width:100%;box-sizing:border-box;padding-left:1rem!important;padding-right:1rem!important}
        header .flex.items-center.gap-4>span{display:none!important}
        header .flex.items-center.gap-6{gap:.5rem!important}
        header .flex.items-center.gap-6>div{display:none!important}
        header .flex.items-center.gap-6>.rounded-full.bg-primary{display:inline-flex!important}
        header .flex.items-center.gap-6 select{max-width:8rem}
        main,main>div,main .grid,main section,main article,main form{box-sizing:border-box;width:100%;max-width:100%;min-width:0}
        main *{min-width:0;box-sizing:border-box}
        main .grid>*{grid-column:1/-1!important}
        main .flex{flex-wrap:wrap}
        main .px-8,main .px-6{padding-left:1rem!important;padding-right:1rem!important}
        main .grid{grid-template-columns:minmax(0,1fr)!important}
        main img,main canvas,main svg{max-width:100%}
        main pre,main table{max-width:100%;overflow:auto}
        #voiceguard-mobile-nav{display:block}
        #voiceguard-call-source-buttons{box-sizing:border-box;width:100%;max-width:100%;flex-wrap:wrap!important}
        #voiceguard-call-source-buttons>button{box-sizing:border-box;flex:1 1 8rem!important;justify-content:center!important;min-width:0}
      }`;
    document.head.append(style);
    const header = document.querySelector("header .flex.items-center.gap-4");
    if (!header || document.querySelector("#voiceguard-mobile-nav")) return;
    const navigation = document.createElement("select");
    navigation.id = "voiceguard-mobile-nav";
    navigation.className = "rounded-md border border-border-subtle bg-surface-panel px-2 py-1 text-xs";
    navigation.setAttribute("aria-label", "Navigate to page");
    navigation.innerHTML = Object.entries(routes).map(([page, path]) => `<option value="${path}" ${location.pathname === path ? "selected" : ""}>${page.replaceAll("-", " ")}</option>`).join("");
    navigation.addEventListener("change", () => { location.assign(navigation.value); });
    header.prepend(navigation);
  }

  function bindProfile() {
    const header = document.querySelector("header .flex.items-center.gap-6");
    if (!header || document.querySelector("#voiceguard-profile")) return;
    const select = document.createElement("select");
    select.id = "voiceguard-profile";
    select.className = "rounded-lg border border-border-subtle bg-surface-canvas px-3 py-2 text-sm text-on-surface";
    select.setAttribute("aria-label", "Model profile");
    select.innerHTML = '<option value="legacy_for2sec">FoR model</option><option value="asvspoof_la_balanced2500">ASVspoof model</option>';
    select.value = activeProfile;
    if (livePage) select.hidden = true;
    select.addEventListener("change", () => {
      activeProfile = select.value;
      localStorage.setItem("voiceguard.profile", activeProfile);
      location.reload();
    });
    header.prepend(select);
  }

  async function bindModelStatus() {
    try {
      const response = await fetch("/api/health");
      if (!response.ok) return;
      const health = await response.json();
      replaceText("Model loaded", health.profiles?.[activeProfile] ? "Model loaded" : "Model unavailable");
      document.querySelectorAll("[data-model-status]").forEach((element) => {
        element.textContent = health.model_loaded ? "Model loaded" : "Model unavailable";
      });
    } catch {
      replaceText("Model loaded", "Backend unavailable");
    }
  }

  function textNodes() {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let node;
    while ((node = walker.nextNode())) {
      if (!["SCRIPT", "STYLE"].includes(node.parentElement?.tagName)) nodes.push(node);
    }
    return nodes;
  }

  function replaceText(from, to) {
    textNodes().forEach((node) => {
      if (node.nodeValue.includes(from)) node.nodeValue = node.nodeValue.split(from).join(String(to));
    });
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
  }

  function setValueNear(label, value) {
    const labelNode = [...document.querySelectorAll("span,div,p")].find(
      (element) => element.children.length === 0 && element.textContent.trim().toLowerCase() === label.toLowerCase()
    );
    if (!labelNode) return;
    let container = labelNode.parentElement;
    for (let level = 0; level < 4 && container; level += 1) {
      const candidate = [...container.querySelectorAll("span")].find(
        (element) => element !== labelNode && /font-label-numeric|headline/.test(element.className)
      );
      if (candidate) {
        candidate.textContent = value;
        return;
      }
      container = container.parentElement;
    }
  }

  function hideStaticCard(label) {
    const leaf = [...document.querySelectorAll("h1,h2,h3,span,p,div")].find((element) => element.children.length === 0 && element.textContent.trim().toLowerCase().includes(label.toLowerCase()));
    let card = leaf;
    while (card && card !== document.querySelector("main") && !card.classList.contains("bg-surface-panel")) card = card.parentElement;
    if (card && card !== document.querySelector("main")) card.classList.add("hidden");
  }

  function addLiveResultPanel() {
    if (!document.querySelector("#audio-input") || document.querySelector("#live-result-panel")) return;
    const panel = document.createElement("div");
    panel.id = "live-result-panel";
    panel.className = "mt-4 p-5 rounded-xl bg-surface-panel border border-border-subtle shadow-sm";
    panel.innerHTML = '<div class="font-headline-sm text-headline-sm">No analysis loaded</div><div class="font-body-sm text-body-sm text-on-surface-variant mt-1">Choose an audio file to see scores produced by the selected model.</div><svg class="mt-5 w-full" viewBox="0 0 1000 240" role="img" aria-label="Measured speech window scores"></svg>';
    const input = document.querySelector("#audio-input");
    input.closest("div").after(panel);
    const sampleBanner = [...document.querySelectorAll("main *")].find((element) => element.children.length === 0 && element.textContent.trim() === "Analysis complete");
    sampleBanner?.closest(".bg-surface-panel")?.remove();
    const sampleVerdict = [...document.querySelectorAll("main *")].find((element) => element.children.length === 0 && element.textContent.trim() === "Analysis Verdict");
    let sampleGrid = sampleVerdict;
    while (sampleGrid && sampleGrid !== document.querySelector("main") && !sampleGrid.className?.includes("grid-cols-1")) sampleGrid = sampleGrid.parentElement;
    sampleGrid?.remove();
    const sampleTimeline = [...document.querySelectorAll("main h2,main h3")].find((element) => element.textContent.includes("Per-Window Temporal Anomaly Timeline"));
    let timelineCard = sampleTimeline;
    while (timelineCard && timelineCard !== document.querySelector("main") && !timelineCard.className?.includes("bg-surface-panel")) timelineCard = timelineCard.parentElement;
    timelineCard?.remove();
    drawAnalysisGraph([], Number(window.voiceguardThreshold ?? 0.5), Number(window.voiceguardBand ?? 0.1));
    const analyzeFile = async (file) => {
      if (!file) return;
      panel.innerHTML = '<div class="font-headline-sm text-headline-sm">Analyzing file…</div><p class="mt-1 text-sm text-secondary">Waiting for the selected model response.</p>';
      const form = new FormData();
      form.append("file", file);
      try {
        const response = await fetch(`/api/analyze/upload?profile=${encodeURIComponent(activeProfile)}`, { method: "POST", body: form });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Analysis failed");
        window.voiceguardLastAnalysis = result;
        drawAnalysisGraph(result.windows || [], Number(result.threshold), Number(result.uncertain_band), true);
        panel.innerHTML = `<div class="flex flex-wrap items-center justify-between gap-3"><div class="font-headline-sm text-headline-sm">${escapeHtml(result.verdict)}</div><div class="font-label-numeric text-label-numeric">${result.mean_prob == null ? "No speech windows scored" : `Fake score: ${Number(result.mean_prob).toFixed(3)}`} · Threshold: ${Number(result.threshold).toFixed(3)}</div></div><div class="font-body-sm text-on-surface-variant mt-2">${escapeHtml(file.name)} · ${Number(result.duration_s).toFixed(2)} s · ${result.windows.filter((window) => window.speech).length} speech windows · ${Number(result.latency_ms).toFixed(1)} ms inference</div><svg class="mt-5 w-full" viewBox="0 0 1000 240" role="img" aria-label="Measured speech window scores"></svg>`;
        drawAnalysisGraph(result.windows || [], Number(result.threshold), Number(result.uncertain_band), true);
      } catch (error) {
        panel.innerHTML = `<div class="text-verdict-synthetic-base">${escapeHtml(error.message || error)}</div>`;
      }
    };
    input.addEventListener("change", (event) => { void analyzeFile(event.target.files[0]); });
    const dropZone = input.parentElement;
    if (dropZone) {
      dropZone.addEventListener("dragover", (event) => { event.preventDefault(); dropZone.classList.add("ring-2", "ring-primary"); });
      dropZone.addEventListener("dragleave", () => dropZone.classList.remove("ring-2", "ring-primary"));
      dropZone.addEventListener("drop", (event) => {
        event.preventDefault();
        dropZone.classList.remove("ring-2", "ring-primary");
        void analyzeFile(event.dataTransfer?.files?.[0]);
      });
    }
  }

  function audioSocketUrl() {
    return `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/live`;
  }

  function drawLiveGraph(entries, threshold, band) {
    const svg = [...document.querySelectorAll("svg")].find((element) => ["0 0 600 240", "0 0 900 200"].includes(element.getAttribute("viewBox") || element.getAttribute("viewbox")));
    if (!svg) return;
    const wide = (svg.getAttribute("viewBox") || svg.getAttribute("viewbox")) === "0 0 900 200";
    const left = wide ? 50 : 50;
    const right = wide ? 875 : 585;
    const top = 12;
    const bottom = wide ? 180 : 215;
    const usableHeight = bottom - top;
    const values = entries.filter((entry) => entry.speech && Number.isFinite(entry.smoothed));
    const firstTime = values[0]?.t ?? 0;
    const latestTime = entries.at(-1)?.t ?? firstTime;
    const points = values.map((entry) => ({
      x: right - (right - left) * Math.max(0, Math.min(60, latestTime - entry.t)) / 60,
      y: bottom - Math.max(0, Math.min(1, entry.smoothed)) * usableHeight,
      score: Math.max(0, Math.min(1, entry.smoothed)),
    }));
    const line = points.map((point, index) => `${index ? "L" : "M"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");
    const area = points.length ? `${line} L ${right} ${bottom} L ${left} ${bottom} Z` : "";
    const yFor = (score) => bottom - Math.max(0, Math.min(1, score)) * usableHeight;
    const bandTop = yFor(threshold + band);
    const bandBottom = yFor(threshold - band);
    const graphCanvas = svg.closest("div.relative.bg-surface-canvas") || svg.parentElement;
    if (graphCanvas) {
      [...graphCanvas.children].filter((element) => element.tagName === "DIV" && element.classList.contains("absolute")).forEach((element) => element.remove());
      const xAxis = [...graphCanvas.querySelectorAll("div")].find((element) => element.children.length >= 5 && [...element.children].every((child) => /^-?\d+s/.test(child.textContent.trim())));
      if (xAxis) xAxis.innerHTML = '<span>-60s</span><span>-45s</span><span>-30s</span><span>-15s</span><span class="text-waveform-active font-semibold">0s (Now)</span>';
    }
    svg.innerHTML = `<defs><linearGradient id="voiceguardLiveFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#2563EB" stop-opacity=".2"/><stop offset="100%" stop-color="#2563EB" stop-opacity="0"/></linearGradient></defs>
      <rect x="${left}" y="${bandTop}" width="${right-left}" height="${Math.max(0, bandBottom-bandTop)}" fill="#FEF3C7" opacity=".65"/>
      <line x1="${left}" y1="${yFor(threshold)}" x2="${right}" y2="${yFor(threshold)}" stroke="#0F172A" stroke-dasharray="6 5"/>
      <line x1="${left}" y1="${top}" x2="${left}" y2="${bottom}" stroke="#CBD5E1"/><line x1="${left}" y1="${bottom}" x2="${right}" y2="${bottom}" stroke="#CBD5E1"/>
      ${[0, .25, .5, .75, 1].map((value) => `<line x1="${left}" y1="${yFor(value)}" x2="${right}" y2="${yFor(value)}" stroke="#CBD5E1" stroke-dasharray="2 5" opacity=".6"/>`).join("")}
      ${area ? `<path d="${area}" fill="url(#voiceguardLiveFill)"/>` : ""}
      ${line ? `<path d="${line}" fill="none" stroke="#2563EB" stroke-width="2.4" stroke-linejoin="round"/>` : ""}
      ${points.map((point) => `<circle cx="${point.x}" cy="${point.y}" r="4" fill="${point.score >= threshold + band ? "#DC2626" : point.score >= threshold - band ? "#D97706" : "#059669"}" stroke="white" stroke-width="1.5"/>`).join("")}
      <text x="${left}" y="${wide ? 198 : 235}" fill="#64748B" font-size="10">${values.length} scored speech windows · latest at ${Number(latestTime).toFixed(1)} s</text>`;
  }

  function drawDashboardGraph(series, threshold, band) {
    const svg = [...document.querySelectorAll("svg")].find((element) => (element.getAttribute("viewBox") || element.getAttribute("viewbox")) === "0 0 320 180");
    if (!svg) return;
    const rows = [...series].reverse().filter((row) => row.mean_prob != null && Number.isFinite(Number(row.mean_prob)));
    const left = 22, right = 310, top = 12, bottom = 158;
    const yFor = (value) => bottom - Math.max(0, Math.min(1, value)) * (bottom - top);
    const points = rows.map((row, index) => ({
      x: rows.length <= 1 ? right : left + (right - left) * index / (rows.length - 1),
      y: yFor(Number(row.mean_prob)), score: Number(row.mean_prob),
    }));
    const path = points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
    svg.innerHTML = `<rect x="${left}" y="${yFor(threshold + band)}" width="${right-left}" height="${Math.max(0, yFor(threshold-band)-yFor(threshold+band))}" fill="#FEF3C7" opacity=".7"/>${[0,.25,.5,.75,1].map((v)=>`<line x1="${left}" y1="${yFor(v)}" x2="${right}" y2="${yFor(v)}" stroke="#CBD5E1" stroke-dasharray="3 4"/>`).join("")}<line x1="${left}" y1="${yFor(threshold)}" x2="${right}" y2="${yFor(threshold)}" stroke="#0F172A" stroke-dasharray="5 4"/>${path?`<path d="${path}" fill="none" stroke="#2563EB" stroke-width="2"/>`:""}${points.map((point)=>`<circle cx="${point.x}" cy="${point.y}" r="3.5" fill="${point.score>=threshold+band?"#DC2626":point.score>=threshold-band?"#D97706":"#059669"}"/>`).join("")}<text x="${left}" y="174" fill="#64748B" font-size="9">${rows.length} saved analyses · fake score</text>`;
    if (!rows.length) svg.insertAdjacentHTML("beforeend", '<text x="160" y="90" text-anchor="middle" fill="#64748B" font-size="12">No analyzed audio yet</text>');
  }

  function drawAnalysisGraph(windows, threshold, band, analyzed = false) {
    const svg = [...document.querySelectorAll("svg")].find((element) => (element.getAttribute("viewBox") || element.getAttribute("viewbox")) === "0 0 1000 240");
    if (!svg) return;
    const values = windows.filter((item) => item.speech && Number.isFinite(Number(item.prob)));
    const left = 34, right = 990, top = 12, bottom = 210;
    const y = (value) => bottom - Math.max(0, Math.min(1, value)) * (bottom - top);
    const points = values.map((item, index) => ({ x: values.length < 2 ? right : left + (right-left)*index/(values.length-1), y: y(Number(item.prob)), score: Number(item.prob) }));
    const path = points.map((point, index) => `${index ? "L" : "M"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");
    svg.innerHTML = `<defs><linearGradient id="voiceguardAnalysisFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#2563EB" stop-opacity=".18"/><stop offset="100%" stop-color="#2563EB" stop-opacity="0"/></linearGradient></defs><rect x="${left}" y="${y(threshold+band)}" width="${right-left}" height="${Math.max(0,y(threshold-band)-y(threshold+band))}" fill="#FEF3C7" opacity=".7"/><line x1="${left}" y1="${y(threshold)}" x2="${right}" y2="${y(threshold)}" stroke="#0F172A" stroke-dasharray="6 5"/>${path ? `<path d="${path} L ${right} ${bottom} L ${left} ${bottom} Z" fill="url(#voiceguardAnalysisFill)"/><path d="${path}" fill="none" stroke="#2563EB" stroke-width="2.2"/>` : ""}${points.map((point) => `<circle cx="${point.x}" cy="${point.y}" r="3.6" fill="${point.score >= threshold+band ? "#DC2626" : point.score >= threshold-band ? "#D97706" : "#059669"}" stroke="white" stroke-width="1.2"/>`).join("")}<text x="${left}" y="232" fill="#64748B" font-size="11">${values.length} measured speech windows</text>`;
    if (!values.length) svg.insertAdjacentHTML("beforeend", `<text x="500" y="120" text-anchor="middle" fill="#64748B" font-size="14">${analyzed ? "No speech windows were scored" : "Upload audio to display measured window scores"}</text>`);
  }

  function updateLiveCounters(entries) {
    const scored = entries.filter((entry) => entry.speech && Number.isFinite(entry.smoothed));
    const meanLatency = scored.length ? scored.reduce((sum, entry) => sum + Number(entry.latency_ms || 0), 0) / scored.length : null;
    const host = document.querySelector("#voiceguard-live-result");
    if (!host) return;
    const line = host.querySelector(".voiceguard-live-counts");
    if (line) line.textContent = `${scored.length} speech windows · ${meanLatency == null ? "—" : meanLatency.toFixed(1) + " ms"} average inference`;
    else host.insertAdjacentHTML("beforeend", `<p class="voiceguard-live-counts mt-2 font-label-code text-label-code text-secondary">${scored.length} speech windows · ${meanLatency == null ? "—" : meanLatency.toFixed(1) + " ms"} average inference</p>`);
  }

  function liveWaitingMarkup() {
    const seconds = Number(window.voiceguardWindow);
    const duration = Number.isFinite(seconds) && seconds > 0 ? `${seconds.toFixed(1)} seconds` : "a full model window";
    return `<h2 class="font-headline-md text-headline-md">Waiting for speech</h2><p class="mt-2 text-secondary">The saved FoR model scores each speech window after ${duration} of audio. No result is shown before a model window is ready.</p>`;
  }

  function attachMicrophoneSelector(host) {
    if (!host || document.querySelector("#voiceguard-mic-device")) return;
    const label = document.createElement("label");
    label.id = "voiceguard-mic-device-wrap";
    label.className = "flex flex-col gap-1 text-sm text-secondary";
    label.innerHTML = '<span>Microphone input device</span><select id="voiceguard-mic-device" class="rounded-lg border border-border-subtle bg-surface-panel px-3 py-2 text-on-surface" aria-label="Microphone input device"><option value="">System default microphone</option></select>';
    host.append(label);
    const select = label.querySelector("select");
    const refresh = async () => {
      if (!navigator.mediaDevices?.enumerateDevices) {
        select.disabled = true;
        return;
      }
      try {
        const previous = select.value;
        const devices = (await navigator.mediaDevices.enumerateDevices()).filter((device) => device.kind === "audioinput");
        select.replaceChildren(new Option("System default microphone", ""));
        devices.forEach((device, index) => {
          if (device.deviceId) select.add(new Option(device.label || `Microphone ${index + 1}`, device.deviceId));
        });
        if ([...select.options].some((option) => option.value === previous)) select.value = previous;
      } catch {
        select.replaceChildren(new Option("System default microphone", ""));
      }
    };
    void refresh();
    navigator.mediaDevices?.addEventListener?.("devicechange", refresh);
  }

  function bindAudioStream(button, mode) {
    if (!button || button.dataset.voiceguardBound === "true") return;
    button.dataset.voiceguardBound = "true";
    let socket;
    let stream;
    let context;
    let worklet;
    let sink;
    let windows = [];
    let stopping = false;
    let starting = false;
    let activeSession = false;
    let receivedSummary = false;
    let sourceName = "mic";
    let demoId = null;
    let player = null;

    const setButton = (active) => {
      const label = active ? (mode === "call" ? "Stop Monitoring" : "Stop Check") : (mode === "call" ? "Start Monitoring" : "Start Live Check");
      const textNode = [...button.childNodes].find((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
      if (textNode) textNode.textContent = `\n          ${label}\n        `;
      button.setAttribute("aria-pressed", String(active));
      if (mode === "call") setCallMonitorBadge(active ? "MONITORING LIVE" : "Ready", active);
    };

    const cleanup = () => {
      try { worklet?.disconnect(); } catch {}
      try { sink?.disconnect(); } catch {}
      stream?.getTracks().forEach((track) => track.stop());
      if (context && context.state !== "closed") void context.close();
      socket = null;
      stream = null;
      context = null;
      worklet = null;
      sink = null;
      player = null;
      activeSession = false;
      starting = false;
      stopping = false;
      const listeningBadge = document.querySelector("#voiceguard-listening-status");
      if (listeningBadge) listeningBadge.textContent = "Ready";
      const bufferStatus = document.querySelector("#voiceguard-live-buffer-status");
      if (bufferStatus) bufferStatus.textContent = "WAITING FOR STREAM";
      updateVadStatus(null);
      const deviceSelect = document.querySelector("#voiceguard-mic-device");
      if (deviceSelect) deviceSelect.disabled = false;
      const consentControl = document.querySelector("#voiceguard-live-consent");
      if (consentControl) consentControl.disabled = false;
      document.querySelectorAll("#voiceguard-call-source-buttons button").forEach((sourceButton) => { sourceButton.disabled = false; });
      setButton(false);
      button.disabled = !consentControl?.checked;
    };
    const updateLiveMeter = (level) => {
      const title = [...document.querySelectorAll("h2,h3")].find((element) => element.textContent.trim() === "Live Audio Input Level");
      let card = title;
      while (card && !card.classList.contains("bg-surface-panel")) card = card.parentElement;
      const bar = card?.querySelector(".h-6.bg-surface-canvas");
      if (!Number.isFinite(level)) return;
      const db = level > 0 ? 20 * Math.log10(level) : -60;
      const rmsValue = document.querySelector("#voiceguard-rms-value");
      const rmsState = document.querySelector("#voiceguard-rms-state");
      const configuredGate = Number(window.voiceguardVadThreshold);
      const gateDb = configuredGate > 0 ? 20 * Math.log10(configuredGate) : null;
      if (rmsValue) rmsValue.textContent = `${db.toFixed(1)} dBFS`;
      if (rmsState) rmsState.textContent = gateDb == null ? "Waiting for saved speech gate" : db >= gateDb ? "Above saved energy gate" : "Below saved energy gate";
      if (bar) {
        const lit = Math.max(0, Math.min(bar.children.length, Math.round(((db + 60) / 60) * bar.children.length)));
        [...bar.children].forEach((segment, index) => {
          segment.classList.toggle("bg-border-subtle/70", index >= lit);
          segment.classList.toggle("bg-verdict-real-base", index < lit && db < -18);
          segment.classList.toggle("bg-verdict-uncertain-base", index < lit && db >= -18 && db < -6);
          segment.classList.toggle("bg-error", index < lit && db >= -6);
        });
        bar.setAttribute("aria-label", `Live audio level ${db.toFixed(1)} dBFS`);
      }
      const fill = document.querySelector("#voiceguard-live-level-fill");
      const label = document.querySelector("#voiceguard-live-level-label");
      const percent = Math.max(0, Math.min(100, ((db + 60) / 60) * 100));
      if (fill) fill.style.width = `${percent}%`;
      const meter = document.querySelector('[role="meter"]');
      if (meter) meter.setAttribute("aria-valuenow", String(Math.round(percent)));
      if (label) label.textContent = `${db.toFixed(1)} dBFS`;
    };
    const updateVadStatus = (speech) => {
      const label = document.querySelector("#voiceguard-vad-status");
      if (!label) return;
      label.textContent = speech === true ? "VAD: Speech detected" : speech === false ? "VAD: No speech" : "VAD: Waiting";
      label.classList.toggle("text-verdict-real-base", speech === true);
      label.classList.toggle("text-secondary", speech !== true);
      const badge = document.querySelector("#voiceguard-vad-badge");
      if (badge) badge.textContent = `VAD: ${speech === true ? "Speech" : speech === false ? "No speech" : "Waiting"}`;
      const listening = document.querySelector("#voiceguard-listening-status");
      if (listening) listening.textContent = speech === null ? "Listening" : speech ? "Speech" : "Silence";
      const bufferStatus = document.querySelector("#voiceguard-live-buffer-status");
      if (bufferStatus) bufferStatus.textContent = speech === null ? "LIVE STREAM" : "LIVE STREAM · WINDOW RECEIVED";
    };
    const currentPanel = () => {
      if (document.querySelector("#voiceguard-live-result")) return document.querySelector("#voiceguard-live-result");
      const panel = document.createElement("section");
      panel.id = "voiceguard-live-result";
      panel.className = "bg-surface-panel rounded-xl border border-border-subtle p-5 shadow-sm my-4";
      panel.setAttribute("aria-live", "polite");
      const heading = [...document.querySelectorAll("h2,h3,span")].find((element) => /Current Window Verdict|Call Risk Assessment/.test(element.textContent));
      (heading?.closest("section") || document.querySelector("main"))?.prepend(panel);
      return panel;
    };
    const statusLine = () => document.querySelector("#voiceguard-live-status");
    const renderWindow = (message) => {
      windows.push(message);
      const latestWindowTime = windows.at(-1)?.t ?? message.t;
      windows = windows.filter((entry) => latestWindowTime - entry.t <= 60);
      updateVadStatus(Boolean(message.speech));
      const panel = currentPanel();
      if (statusLine()) statusLine().textContent = message.speech ? "Speech detected · model window analyzed." : "No speech in this window · waiting for speech.";
      const score = message.speech && Number.isFinite(message.smoothed) ? message.smoothed : null;
      const verdict = message.speech ? (message.verdict || "Uncertain") : "No speech";
      const displayScore = score == null ? "No score" : score.toFixed(3);
      panel.innerHTML = `<div class="flex flex-wrap items-center justify-between gap-3"><div><p class="font-label-code text-label-code text-secondary uppercase">Latest model window</p><h2 class="font-headline-md text-headline-md mt-1">${escapeHtml(verdict)}</h2></div><div class="font-label-numeric text-[32px] font-semibold">${displayScore}</div></div><p class="font-body-sm text-body-sm text-secondary mt-2">${message.speech ? "Saved FoR model fake score (not a calibrated real-world probability)." : "No speech detected in this window; no fake score was produced."} · Threshold ${Number(message.threshold).toFixed(3)} · Window ${windows.length} · ${Number(message.latency_ms).toFixed(1)} ms inference</p>`;
      drawLiveGraph(windows, Number(message.threshold ?? window.voiceguardThreshold ?? 0.5), Number(message.uncertain_band ?? window.voiceguardBand ?? 0.1));
      updateLiveCounters(windows);
    };
    const stop = () => {
      if (stopping) return;
      stopping = true;
      if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "stop" }));
      else cleanup();
    };

    button.addEventListener("click", async (event) => {
      event.preventDefault();
      if (socket && socket.readyState === WebSocket.OPEN) {
        stop();
        return;
      }
      try {
        stopping = false;
        starting = true;
        activeSession = false;
        windows = [];
        receivedSummary = false;
        demoId = null;
        player = null;
        currentPanel().innerHTML = liveWaitingMarkup();
        button.disabled = true;
        const consentControl = document.querySelector("#voiceguard-live-consent");
        if (consentControl) consentControl.disabled = true;
        const deviceSelect = document.querySelector("#voiceguard-mic-device");
        if (deviceSelect) deviceSelect.disabled = true;
        document.querySelectorAll("#voiceguard-call-source-buttons button").forEach((sourceButton) => { sourceButton.disabled = true; });
        if (statusLine()) statusLine().textContent = sourceName === "mic"
          ? "Starting microphone capture · allow microphone access if your browser asks."
          : sourceName === "system"
            ? "Starting shared audio capture · choose a tab and enable its audio."
            : "Loading the selected demo audio…";
        context = new AudioContext();
        await context.resume();
        await context.audioWorklet.addModule("/static/audio-worklet.js");
        if (sourceName === "system") {
          if (!navigator.mediaDevices.getDisplayMedia) throw new Error("This browser cannot capture shared tab or system audio.");
          stream = await navigator.mediaDevices.getDisplayMedia({ audio: true, video: true });
          if (!stream.getAudioTracks().length) throw new Error("No audio was shared. Choose a tab and enable its audio.");
        } else if (sourceName === "replay") {
          demoId = document.querySelector("#voiceguard-demo-sample")?.value;
          if (!demoId) throw new Error("Select a demo audio sample first.");
          const audioResponse = await fetch(`/api/demo/audio/${encodeURIComponent(demoId)}`);
          if (!audioResponse.ok) throw new Error("Selected demo audio could not be loaded.");
          const buffer = await context.decodeAudioData(await audioResponse.arrayBuffer());
          const destination = context.createMediaStreamDestination();
          stream = destination.stream;
          player = context.createBufferSource();
          player.buffer = buffer;
          player.connect(context.destination);
          player.connect(destination);
        } else {
          const deviceId = document.querySelector("#voiceguard-mic-device")?.value;
          stream = await navigator.mediaDevices.getUserMedia({ audio: deviceId ? { deviceId: { exact: deviceId } } : true });
          const deviceSelect = document.querySelector("#voiceguard-mic-device");
          if (deviceSelect && navigator.mediaDevices?.enumerateDevices) {
            try {
              const previousDevice = deviceSelect.value;
              const devices = (await navigator.mediaDevices.enumerateDevices()).filter((device) => device.kind === "audioinput");
              deviceSelect.replaceChildren(new Option("System default microphone", ""));
              devices.forEach((device, index) => { if (device.deviceId) deviceSelect.add(new Option(device.label || `Microphone ${index + 1}`, device.deviceId)); });
              deviceSelect.value = previousDevice;
            } catch {}
          }
        }
        stream.getTracks().forEach((track) => { track.onended = () => stop(); });
        const source = context.createMediaStreamSource(stream);
        worklet = new AudioWorkletNode(context, "pcm16-capture", { numberOfInputs: 1, numberOfOutputs: 1, channelCount: 1, channelCountMode: "explicit" });
        sink = context.createGain();
        sink.gain.value = 0;
        worklet.connect(sink);
        sink.connect(context.destination);
        socket = new WebSocket(audioSocketUrl());
        socket.binaryType = "arraybuffer";
        socket.onopen = async () => {
          try {
            const ticketResponse = await fetch("/api/auth/ws-ticket", {
              method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
            });
            if (!ticketResponse.ok) throw new Error(ticketResponse.status === 401 ? "Sign in before starting a live check." : "Could not authorize the live audio connection.");
            const { ticket } = await ticketResponse.json();
            socket.send(JSON.stringify({ type: "auth", ticket }));
          } catch (error) {
            if (statusLine()) statusLine().textContent = error.message;
            cleanup();
          }
        };
        const startAuthorizedStream = () => {
          socket.send(JSON.stringify({ mode, source: sourceName, sample_rate: context.sampleRate }));
          worklet.port.onmessage = (event) => {
            updateLiveMeter(event.data.level);
            if (socket?.readyState === WebSocket.OPEN) socket.send(event.data.frame);
          };
          source.connect(worklet);
          activeSession = true;
          starting = false;
          const listeningBadge = document.querySelector("#voiceguard-listening-status");
          if (listeningBadge) listeningBadge.textContent = "Listening";
          const bufferStatus = document.querySelector("#voiceguard-live-buffer-status");
          if (bufferStatus) bufferStatus.textContent = "LIVE STREAM";
          setButton(true);
          button.disabled = false;
          if (statusLine()) statusLine().textContent = sourceName === "mic" ? "Microphone active · analyzing incoming speech windows." : sourceName === "system" ? "Shared tab audio active · analyzing incoming speech windows." : "Demo replay active · analyzing its audio windows.";
          if (player) { player.onended = () => stop(); player.start(); }
        };
        socket.onmessage = async (event) => {
          const message = JSON.parse(event.data);
          if (message.type === "authenticated") { startAuthorizedStream(); return; }
          if (message.type === "status" && statusLine()) {
            statusLine().textContent = message.state === "no_speech" ? "Listening · no speech detected in the latest window." : message.state === "lagging" ? "Processing is behind incoming audio." : `${sourceName === "mic" ? "Microphone" : sourceName === "system" ? "Shared tab audio" : "Demo replay"} active · listening.`;
            if (message.state === "no_speech") updateVadStatus(false);
            else if (message.state === "listening") updateVadStatus(null);
          }
          if (message.type === "window") renderWindow(message);
          if (message.type === "alert") {
            const panel = currentPanel();
            panel.insertAdjacentHTML("beforeend", `<p class="mt-3 rounded-lg bg-verdict-synthetic-surface p-3 text-verdict-synthetic-base">${escapeHtml(message.message)}</p>`);
          }
          if (message.type === "summary") {
            receivedSummary = true;
            if (statusLine()) statusLine().textContent = "Monitoring stopped · final summary saved to history.";
            currentPanel().insertAdjacentHTML("beforeend", `<p class="mt-3 text-secondary">Session ended · ${Number(message.duration_s).toFixed(1)} s · ${windows.length} windows · ${message.speech_ratio == null ? "0" : (Number(message.speech_ratio) * 100).toFixed(1)}% speech. Saved to local history as #${message.session_id}.</p>`);
            if (demoId) {
              try {
                const response = await fetch(`/api/demo/analyze/${encodeURIComponent(demoId)}`, { method: "POST" });
                if (!response.ok) throw new Error("Demo ground truth is unavailable.");
                const truth = await response.json();
                currentPanel().insertAdjacentHTML("beforeend", `<p class="mt-3 rounded-lg bg-surface-canvas p-3">Demo label revealed after replay: ${escapeHtml(truth.ground_truth)} · ASVspoof complete-clip score ${Number(truth.mean_prob).toFixed(3)}. The live timeline above is the FoR model reading on an ASVspoof clip and is not valid cross-dataset evaluation.</p>`);
              } catch (error) {
                currentPanel().insertAdjacentHTML("beforeend", `<p class="mt-3 text-secondary">${escapeHtml(error.message)}</p>`);
              }
            }
            cleanup();
          }
          if (message.type === "error") {
            if (statusLine()) statusLine().textContent = message.message;
            currentPanel().insertAdjacentHTML("beforeend", `<p class="mt-3 text-verdict-synthetic-base">${escapeHtml(message.message)}</p>`);
          }
        };
        socket.onclose = () => {
          if (receivedSummary) return;
          if (statusLine()) statusLine().textContent = "Connection ended before a final summary arrived.";
          currentPanel().insertAdjacentHTML("beforeend", '<p class="mt-3 text-secondary">The server may have saved a partial session if audio reached it. Check local history for the saved record.</p>');
          cleanup();
        };
        socket.onerror = () => { currentPanel().insertAdjacentHTML("beforeend", '<p class="mt-3 text-verdict-synthetic-base">Live analysis connection failed.</p>'); stop(); };
      } catch (error) {
        cleanup();
        const sourceLabel = sourceName === "mic" ? "Microphone" : sourceName === "system" ? "System or tab audio" : "Demo replay";
        if (statusLine()) statusLine().textContent = `${sourceLabel} could not be started.`;
        currentPanel().innerHTML = `<p class="text-verdict-synthetic-base">${sourceLabel} could not be started: ${escapeHtml(String(error.message || error))}</p>`;
      }
    });
    if (mode === "call") {
      const sourceButtons = [...document.querySelectorAll("button")].filter((item) => /Microphone \(speakerphone\)|System \/ tab audio|Demo replay/.test(item.textContent));
      sourceButtons[0]?.parentElement?.setAttribute("id", "voiceguard-call-source-buttons");
      const demoSelect = document.createElement("select");
      demoSelect.id = "voiceguard-demo-sample";
      demoSelect.className = "mt-2 rounded-lg border border-border-subtle bg-surface-panel p-2 text-sm";
      demoSelect.hidden = true;
      demoSelect.innerHTML = '<option value="">Loading locked demo clips…</option>';
      sourceButtons[0]?.parentElement?.after(demoSelect);
      fetch("/api/demo/samples").then((response) => response.json()).then((samples) => {
        demoSelect.innerHTML = samples.map((sample) => `<option value="${escapeHtml(sample.id)}">${escapeHtml(sample.name)} · ${Number(sample.duration_s).toFixed(2)} s</option>`).join("");
        if (!samples.length) demoSelect.innerHTML = '<option value="">No demo clips available</option>';
      }).catch(() => { demoSelect.innerHTML = '<option value="">Demo clips unavailable</option>'; });
      sourceButtons.forEach((item, index) => item.addEventListener("click", () => {
        if (activeSession || starting) return;
        sourceName = ["mic", "system", "replay"][index] || "mic";
        const deviceWrap = document.querySelector("#voiceguard-mic-device-wrap");
        if (deviceWrap) deviceWrap.hidden = sourceName !== "mic";
        demoSelect.hidden = sourceName !== "replay";
        sourceButtons.forEach((candidate, candidateIndex) => {
          candidate.classList.toggle("bg-surface-panel", candidateIndex === index);
          candidate.classList.toggle("text-primary", candidateIndex === index);
          candidate.classList.toggle("font-semibold", candidateIndex === index);
        });
      }));
    }
  }

  function bindLiveControls() {
    if (location.pathname === "/live-check") {
      const button = document.querySelector("#toggle-record-btn");
      if (button) button.innerHTML = button.innerHTML.replace(/Stop Check/g, "Start Live Check");
      prepareLivePage();
      bindAudioStream(button, "mic");
    }
    if (location.pathname === "/call-monitor") {
      const original = document.querySelector("#btn-stop-monitoring");
      const button = original?.cloneNode(true);
      if (original && button) original.replaceWith(button);
      if (button) button.innerHTML = button.innerHTML.replace(/Stop Monitoring/g, "Start Monitoring");
      prepareLivePage();
      bindAudioStream(button, "call");
    }
  }

  function prepareLivePage() {
    document.querySelector("#alert-banner")?.classList.add("hidden");
    if (location.pathname === "/call-monitor") setCallMonitorBadge("Ready", false);
    ["Windows Analyzed", "Latency / Window", "Speech Ratio", "FLAGGED WINDOWS", "SILENCE GATED", "41ms", "04:18 active", "Session Summary", "Mic Check #104", "Consent Notice Acknowledged", "Timestamped signature recorded"].forEach(hideStaticCard);
    const fakeHardware = [...document.querySelectorAll("span")].find((element) => element.textContent.trim() === "MacBook Pro Microphone (CoreAudio Built-in)");
    if (fakeHardware) {
      const deviceCard = fakeHardware.parentElement?.parentElement;
      const controlRow = deviceCard?.parentElement;
      deviceCard?.remove();
      attachMicrophoneSelector(controlRow);
    } else {
      const sourceButton = [...document.querySelectorAll("button")].find((element) => /Microphone \(speakerphone\)/.test(element.textContent));
      attachMicrophoneSelector(sourceButton?.parentElement?.parentElement);
    }
    const engine = [...document.querySelectorAll("span")].find((element) => element.textContent.trim().startsWith("AUDIO ENGINE:"));
    if (engine) engine.textContent = `Audio path: browser capture → ${window.voiceguardSampleRate || "model"} Hz FoR model`;
    const privacy = [...document.querySelectorAll("span")].find((element) => element.textContent.includes("Audio is analyzed on this device's server"));
    if (privacy) privacy.textContent = "Raw audio is not saved; live model scores are stored in local history.";
    const listening = [...document.querySelectorAll("span")].find((element) => element.textContent.trim() === "Listening");
    if (listening) {
      listening.id = "voiceguard-listening-status";
      listening.textContent = "Ready";
      listening.closest("div")?.querySelector(".animate-ping")?.classList.remove("animate-ping");
    }
    const vadBadge = [...document.querySelectorAll("span")].find((element) => element.textContent.trim() === "VAD: Speech detected");
    if (vadBadge) { vadBadge.id = "voiceguard-vad-badge"; vadBadge.textContent = "VAD: Waiting"; }
    const rtt = [...document.querySelectorAll("span")].find((element) => element.textContent.trim() === "RTT:");
    rtt?.parentElement?.remove();
    const timerIcon = [...document.querySelectorAll("span.material-symbols-outlined")].find((element) => element.textContent.trim() === "timer");
    timerIcon?.parentElement?.remove();
    const monitorBadge = [...document.querySelectorAll("span")].find((element) => element.textContent.trim() === "READY TO MONITOR");
    if (monitorBadge) { monitorBadge.id = "voiceguard-monitor-status"; monitorBadge.textContent = "Ready"; }
    const buffer = [...document.querySelectorAll("span")].find((element) => element.textContent.trim() === "LIVE BUFFER");
    if (buffer) { buffer.id = "voiceguard-live-buffer-status"; buffer.textContent = "WAITING FOR STREAM"; buffer.parentElement?.querySelector(".animate-pulse")?.classList.remove("animate-pulse"); }
    const callTimeline = [...document.querySelectorAll("span,h2,h3")].find((element) => element.textContent.includes("Live Call Rolling Timeline (Last 90s)"));
    if (callTimeline) callTimeline.textContent = callTimeline.textContent.replace("Last 90s", "Last 60s");
    const rmsValueLabel = [...document.querySelectorAll("span")].find((element) => element.textContent.trim() === "RMS Value");
    if (rmsValueLabel) {
      const card = rmsValueLabel.closest("div.flex.flex-col");
      if (card?.children[1]) { card.children[1].id = "voiceguard-rms-value"; card.children[1].textContent = "Waiting for audio"; }
      if (card?.children[2]) { card.children[2].id = "voiceguard-rms-state"; card.children[2].textContent = "No audio received"; }
    }
    const gateLabel = [...document.querySelectorAll("span")].find((element) => element.textContent.trim() === "Silence Gate");
    if (gateLabel) {
      const card = gateLabel.closest("div.flex.flex-col");
      if (card?.children[1]) { card.children[1].id = "voiceguard-gate-value"; card.children[1].textContent = "Loading saved gate"; }
      if (card?.children[2]) { card.children[2].id = "voiceguard-gate-state"; card.children[2].textContent = "Waiting for audio"; }
    }
    void fetch("/api/settings?profile=legacy_for2sec").then((response) => response.ok ? response.json() : Promise.reject()).then((settings) => {
      window.voiceguardVadThreshold = Number(settings.vad_threshold);
      const value = document.querySelector("#voiceguard-gate-value");
      if (value) value.textContent = `${(20 * Math.log10(settings.vad_threshold)).toFixed(1)} dBFS`;
      const state = document.querySelector("#voiceguard-gate-state");
      if (state) state.textContent = "Saved speech gate";
      replaceText("1-SECOND HOP RESOLUTION", `${Number(settings.hop_seconds).toFixed(2)}s HOP RESOLUTION`);
      replaceText("Score: ≥ 0.50", `Alert score: ≥ ${Number(settings.threshold).toFixed(3)}`);
      replaceText("Window: 2.0s (1.0s hop)", `Window: ${Number(window.voiceguardWindow || 2).toFixed(1)}s (${Number(settings.hop_seconds).toFixed(2)}s hop)`);
      replaceText("Trigger: N=3 consecutive", `Trigger: N=${settings.alert_consecutive_windows} consecutive speech windows`);
      replaceText("Policy #DEF-02", "Saved stream settings");
    }).catch(() => {
      const value = document.querySelector("#voiceguard-gate-value");
      if (value) value.textContent = "Unavailable";
    });
    const heading = [...document.querySelectorAll("h2,h3,span")].find((element) => /Current Window Verdict|Call Risk Assessment/.test(element.textContent));
    let card = heading;
    while (card && !card.classList.contains("bg-surface-panel")) card = card.parentElement;
    if (card) card.classList.add("hidden");
    const meterHeading = [...document.querySelectorAll("h2,h3")].find((element) => element.textContent.trim() === "Live Audio Input Level");
    let meter = meterHeading;
    while (meter && !meter.classList.contains("bg-surface-panel")) meter = meter.parentElement;
    if (meter) {
      meter.classList.remove("hidden");
      const bars = meter.querySelector(".h-6.bg-surface-canvas");
      bars && [...bars.children].forEach((segment) => {
        segment.classList.remove("bg-verdict-real-base", "bg-verdict-uncertain-base", "bg-error");
        segment.classList.add("bg-border-subtle/70");
      });
    }
    const startButton = document.querySelector("#btn-stop-monitoring, #toggle-record-btn");
    if (startButton) {
      startButton.classList.add("voiceguard-live-start");
      if (!document.querySelector("#voiceguard-live-start-style")) {
        const style = document.createElement("style");
        style.id = "voiceguard-live-start-style";
        style.textContent = ".voiceguard-live-start:disabled{opacity:.5!important;cursor:not-allowed!important;filter:saturate(.7)}";
        document.head.append(style);
      }
    }
    let consentLabel = document.querySelector("#voiceguard-live-consent")?.closest("label") || null;
    if (startButton && !document.querySelector("#voiceguard-live-consent")) {
      consentLabel = document.createElement("label");
      consentLabel.id = "voiceguard-live-consent-label";
      consentLabel.className = "flex items-start gap-2 text-sm text-secondary";
      consentLabel.innerHTML = '<input id="voiceguard-live-consent" type="checkbox" class="mt-1"><span>I agree to send the selected audio source to this local app for live analysis. Raw audio is not saved.</span>';
      const consentCheckbox = consentLabel.querySelector("#voiceguard-live-consent");
      startButton.disabled = !consentCheckbox.checked;
      consentCheckbox.addEventListener("change", (event) => { startButton.disabled = !event.target.checked; });
    }
    const status = document.createElement("p");
    status.id = "voiceguard-live-status";
    status.className = "font-label-code text-label-code text-secondary";
    status.textContent = "Ready. Start monitoring and speak; the first result appears after a full model window.";
    const livePanel = document.createElement("section");
    livePanel.id = "voiceguard-live-result";
    livePanel.className = "bg-surface-canvas rounded-lg border border-border-subtle p-4";
    livePanel.setAttribute("aria-live", "polite");
    livePanel.innerHTML = liveWaitingMarkup();
    const feedback = document.createElement("section");
    feedback.id = "voiceguard-live-feedback";
    feedback.className = "bg-surface-panel rounded-xl border border-border-subtle p-4 shadow-sm my-4 flex flex-col gap-3";
    if (consentLabel) feedback.append(consentLabel);
    const level = document.createElement("div");
    level.className = "flex flex-wrap items-center gap-3 text-sm text-secondary";
    level.innerHTML = '<span>Input level</span><div class="h-2 w-40 overflow-hidden rounded-full bg-surface-canvas" role="meter" aria-label="Live audio input level" aria-valuemin="0" aria-valuemax="100"><div id="voiceguard-live-level-fill" class="h-full w-0 bg-primary transition-[width]"></div></div><span id="voiceguard-live-level-label">Waiting for audio</span>';
    const vadLock = [...document.querySelectorAll("span")].find((element) => element.textContent.trim() === "VAD LOCK");
    if (vadLock) {
      vadLock.id = "voiceguard-vad-status";
      vadLock.textContent = "VAD: Waiting";
      vadLock.className = "font-label-numeric text-label-numeric text-secondary font-semibold";
      vadLock.previousElementSibling?.classList.add("hidden");
      level.append(vadLock);
    } else level.insertAdjacentHTML("beforeend", '<span id="voiceguard-vad-status">VAD: Waiting</span>');
    feedback.append(level, status, livePanel);
    const chart = [...document.querySelectorAll("svg")].find((element) => ["0 0 600 240", "0 0 900 200"].includes(element.getAttribute("viewBox") || element.getAttribute("viewbox")));
    let graphCard = chart;
    while (graphCard && graphCard !== document.querySelector("main") && !graphCard.classList.contains("bg-surface-panel")) graphCard = graphCard.parentElement;
    if (graphCard && graphCard !== document.querySelector("main")) {
      let liveGrid = graphCard.parentElement;
      while (liveGrid && liveGrid !== document.querySelector("main") && !liveGrid.classList.contains("grid")) liveGrid = liveGrid.parentElement;
      if (liveGrid && liveGrid !== document.querySelector("main")) {
        liveGrid.style.gridTemplateColumns = "minmax(0, 1fr)";
        [...liveGrid.children].forEach((child) => { child.style.gridColumn = "1 / -1"; });
      }
      graphCard.before(feedback);
    }
    else startButton?.parentElement?.after(feedback);
  }

  function setCallMonitorBadge(label, active) {
    const badge = document.querySelector("#voiceguard-monitor-status") || [...document.querySelectorAll("div")].find((element) => element.textContent.trim() === "MONITORING ACTIVE" || element.textContent.trim() === "MONITORING READY" || element.textContent.trim() === "MONITORING LIVE");
    if (!badge) return;
    const textNode = [...badge.childNodes].find((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
    if (textNode) textNode.textContent = `\n          ${label}\n        `;
    badge.classList.toggle("bg-verdict-real-surface", active);
    badge.classList.toggle("text-verdict-real-base", active);
    badge.classList.toggle("bg-surface-canvas", !active);
    badge.classList.toggle("text-secondary", !active);
  }

  async function bindSettings(model, history = []) {
    if (location.pathname !== "/settings") return;
    try {
      const response = await fetch(`/api/settings?profile=${encodeURIComponent(activeProfile)}`);
      if (!response.ok) throw new Error("Settings could not be loaded");
      const settings = await response.json();
      const band = document.querySelector("#bandwidth-slider");
      const bandValue = document.querySelector("#bandwidth-val");
      const ema = document.querySelector("#ema-slider");
      const emaValue = document.querySelector("#ema-val");
      const consecutive = document.querySelector("#consecutive-windows");
      const threshold = document.querySelector("#threshold-slider");
      const vadRadios = [...document.querySelectorAll('input[name="vad_level"]')];
      const vadChoices = [10 ** (-38 / 20), 10 ** (-45 / 20), 10 ** (-52 / 20)];
      const selectedVad = vadChoices.reduce((best, value, index) => Math.abs(value - settings.vad_threshold) < Math.abs(vadChoices[best] - settings.vad_threshold) ? index : best, 0);
      let vadChanged = false;
      vadRadios.forEach((radio, index) => {
        radio.value = String(vadChoices[index]);
        radio.checked = index === selectedVad;
        const label = radio.closest("label");
        if (label) {
          label.classList.remove("border-2", "border-primary", "bg-surface-container-low", "shadow-sm");
          label.classList.add("border", "border-border-subtle", "bg-surface-panel");
          if (radio.checked) {
            label.classList.remove("border", "border-border-subtle", "bg-surface-panel");
            label.classList.add("border-2", "border-primary", "bg-surface-container-low", "shadow-sm");
          }
          const valueLabel = label.querySelector(".font-label-numeric");
          if (valueLabel) valueLabel.textContent = `${(20 * Math.log10(vadChoices[index])).toFixed(0)} dBFS`;
          label.querySelector(".voiceguard-saved-vad")?.remove();
          if (radio.checked) {
            const savedGate = document.createElement("span");
            savedGate.className = "voiceguard-saved-vad text-[11px] text-secondary";
            savedGate.textContent = `Saved gate: ${(20 * Math.log10(settings.vad_threshold)).toFixed(1)} dBFS`;
            label.append(savedGate);
          }
        }
        radio.addEventListener("change", () => { if (radio.checked) vadChanged = true; });
      });
      if (band) band.value = settings.uncertain_band;
      if (bandValue) bandValue.textContent = `±${Number(settings.uncertain_band).toFixed(2)}`;
      if (ema) ema.value = settings.smoothing_alpha;
      if (emaValue) emaValue.textContent = `α = ${Number(settings.smoothing_alpha).toFixed(2)}`;
      if (consecutive) consecutive.value = settings.alert_consecutive_windows;
      if (threshold) {
        threshold.value = model.threshold;
        const thresholdValue = document.querySelector("#threshold-val");
        if (thresholdValue) thresholdValue.textContent = Number(model.threshold).toFixed(3);
        threshold.addEventListener("input", () => {
          const value = Number(threshold.value);
          if (thresholdValue) thresholdValue.textContent = value.toFixed(3);
          const pin = document.querySelector("#gauge-pin");
          if (pin) pin.style.left = `${value * 100}%`;
        });
      }
      const save = [...document.querySelectorAll("button")].filter((element) => element.textContent.includes("Save"));
      save.forEach((button) => {
        button.onclick = async () => {
          const payload = {
            threshold: Number(threshold?.value ?? model.threshold),
            uncertain_band: Number(band?.value ?? settings.uncertain_band),
            hop_seconds: settings.hop_seconds,
            vad_threshold: vadChanged ? Number(document.querySelector('input[name="vad_level"]:checked')?.value ?? settings.vad_threshold) : settings.vad_threshold,
            smoothing_alpha: Number(ema?.value ?? settings.smoothing_alpha),
            alert_consecutive_windows: Number(consecutive?.value ?? settings.alert_consecutive_windows),
          };
          const toast = document.querySelector("#save-toast");
          const toastTitle = toast?.querySelector(".font-headline-sm");
          const toastDetail = toast?.querySelector(".font-label-code");
          button.disabled = true;
          try {
            const saved = await fetch(`/api/settings?profile=${encodeURIComponent(activeProfile)}`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            }).then(async (result) => {
              if (!result.ok) {
                const body = await result.json().catch(() => ({}));
                throw new Error(body.detail || "Settings could not be saved");
              }
              return result.json();
            });
            Object.assign(settings, saved);
            model.threshold = Number(saved.threshold);
            vadChanged = false;
            const selectedGate = document.querySelector('input[name="vad_level"]:checked')?.closest("label")?.querySelector(".voiceguard-saved-vad");
            if (selectedGate) selectedGate.textContent = `Saved gate: ${(20 * Math.log10(saved.vad_threshold)).toFixed(1)} dBFS`;
            window.updateBands?.();
            button.textContent = "Saved";
            if (toastTitle) toastTitle.textContent = "Settings saved";
            if (toastDetail) toastDetail.textContent = "Saved settings apply to future analyses.";
            toast?.classList.remove("opacity-0", "pointer-events-none");
            window.setTimeout(() => { button.textContent = "Save Changes"; }, 1500);
            window.setTimeout(() => toast?.classList.add("opacity-0", "pointer-events-none"), 3000);
            return saved;
          } catch (error) {
            if (toastTitle) toastTitle.textContent = "Settings not saved";
            if (toastDetail) toastDetail.textContent = error.message || String(error);
            toast?.classList.remove("opacity-0", "pointer-events-none");
          } finally {
            button.disabled = false;
          }
        };
      });
      const unsupportedDuration = [...document.querySelectorAll("label")].find((label) => label.textContent.includes("Minimum Speech Segment Duration"));
      unsupportedDuration?.parentElement?.parentElement?.remove();
      [...document.querySelectorAll("main span")].find((element) => element.textContent.trim() === "Local SQLite Storage")?.parentElement?.parentElement?.remove();
      [...document.querySelectorAll("main span")].find((element) => element.textContent.trim() === "Execution Context")?.closest(".bg-surface-panel")?.remove();
      const analysisCount = document.querySelector("#settings-analysis-count");
      if (analysisCount) analysisCount.textContent = `${history.length} saved analyses`;
      replaceText("Retention: 30 Days", "");
      replaceText("34.8 MB", "");
      document.querySelectorAll("button").forEach((button) => { if (button.textContent.includes("Export Backup")) button.remove(); });
      replaceText("Default: 0.50 (Validated on FoR-2s test set)", "Saved validated threshold");
      replaceText("Default: ±0.10", `Saved band: ±${Number(settings.uncertain_band).toFixed(2)}`);
      replaceText("Default: 0.35", `Saved smoothing: α = ${Number(settings.smoothing_alpha).toFixed(2)}`);
      replaceText("consecutive windows (1.0s hop)", `consecutive windows (${Number(settings.hop_seconds).toFixed(2)}s hop)`);
      replaceText("Trigger critical incident alert banner when N consecutive speech windows exceed the synthetic threshold (≥ 0.50).", activeProfile === "legacy_for2sec" ? `Alert after N consecutive speech windows score above the FoR synthetic boundary (${Math.min(1, Number(model.threshold) + Number(settings.uncertain_band)).toFixed(3)}).` : "Live alerting uses the saved FoR model threshold; this ASVspoof threshold applies to complete-clip uploads.");
      replaceText("Scores at or above this value trigger a \"Likely Synthetic\" verdict. Lower values increase sensitivity but elevate false alarms.", `The saved threshold is ${Number(model.threshold).toFixed(3)}. Scores above ${Math.min(1, Number(model.threshold) + Number(settings.uncertain_band)).toFixed(3)} are Likely Synthetic; scores in the uncertain band are not.`);
      replaceText("Windows below this RMS audio power are classified as \"no speech\" and skipped by the inference pipeline to preserve GPU/CPU cycles.", "Audio windows below the selected RMS energy gate are marked as no speech; no model score is produced for those windows.");
      replaceText("-45 dBFS (Default)", "-45 dBFS preset");
      replaceText("TABLES: SESSIONS, SPECTRAL_CHUNKS, AUDIT_LOG", "Local analysis history");
      replaceText("Active Profile: #SEC-STITCH-LOCAL-01", `Active model: ${model.name}`);
      replaceText("/api/v1/forensics/settings", "local application settings");
      replaceText("VoiceGuard Forensics Platform · Build ID 2024.11-RC2", "VoiceGuard Forensics · research prototype");
      replaceText("FoR-2s CORE", model.name);
      replaceText("Changes to detection thresholds and streaming buffers take effect immediately on subsequent live windows and uploaded audio analyses. Stored case history is not retroactively altered.", activeProfile === "legacy_for2sec" ? "Saved threshold and stream settings apply to following FoR uploads and live sessions. Stored history is not retroactively changed." : "The threshold applies to uploads scored by the selected ASVspoof model. Live sessions continue to use the FoR model and its threshold; shared stream settings apply to future live sessions. Stored history is not retroactively changed.");
      window.updateBands?.();
      document.querySelector("#toggle-store-raw")?.closest(".flex.items-center.justify-between")?.parentElement?.remove();
      document.querySelector("#toggle-drop-buffer")?.closest(".flex.items-center.justify-between")?.parentElement?.remove();
      const clearButton = [...document.querySelectorAll("button")].find((button) => button.textContent.includes("Clear All History"));
      const modal = document.querySelector("#clear-modal");
      if (clearButton && modal) clearButton.onclick = () => modal.classList.remove("hidden");
      const modalButtons = [...(modal?.querySelectorAll("button") || [])];
      const abort = modalButtons.find((button) => button.textContent.includes("Abort"));
      const confirm = modalButtons.find((button) => button.textContent.includes("Confirm Destructive Purge"));
      if (abort && modal) abort.onclick = () => modal.classList.add("hidden");
      if (confirm && modal) confirm.onclick = async () => {
        confirm.disabled = true;
        try {
          const response = await fetch("/api/history", { method: "DELETE" });
          if (!response.ok) throw new Error("History could not be cleared");
          location.reload();
        } catch (error) {
          confirm.disabled = false;
          const toast = document.querySelector("#save-toast");
          const title = toast?.querySelector(".font-headline-sm");
          const detail = toast?.querySelector(".font-label-code");
          if (title) title.textContent = "History was not cleared";
          if (detail) detail.textContent = error.message || String(error);
          toast?.classList.remove("opacity-0", "pointer-events-none");
        }
      };
      const reset = [...document.querySelectorAll("button")].find((button) => button.textContent.includes("Reset to defaults"));
      if (reset) reset.textContent = "Reload saved settings";
    } catch (error) {
      throw error;
    }
  }

  async function bindActualReports(model, metrics, dashboard, history) {
    const report = metrics.results || {};
    const test = report.models?.svm?.test || report.test;
    const validation = report.models?.svm?.validation || report.validation;
    window.voiceguardThreshold = Number(model.threshold);
    window.voiceguardBand = Number(model.uncertain_band);
    window.voiceguardWindow = Number(model.window_s);
    window.voiceguardSampleRate = Number(model.sample_rate);
    replaceText("16 kHz · Mono PCM (Linear-16)", `${Number(model.sample_rate).toLocaleString()} Hz · mono PCM16`);
    replaceText("ws://localhost:8000/ws/live", audioSocketUrl());
    replaceText("Async-Thread-01 (GPU: 0)", "CPU inference · latency measured per window");
    replaceText("FoR-2s v1.4.2 (ResNet-W2S)", `${model.name} · ${model.model_version}`);
    replaceText("REAL-TIME INFERENCE (ROLLING 2.0s WINDOW)", `STREAM INFERENCE · ${Number(model.window_s).toFixed(1)}s MODEL WINDOW`);
    replaceText("Captures ambient speakerphone audio via local microphone. For softphones/meetings, use System/tab audio.", "Choose microphone, shared-tab audio, or demo replay. Call Monitor analyzes only the audio stream sent from this browser.");
    document.querySelectorAll('img[alt*="VoiceGuard"]').forEach((image) => image.remove());
    replaceText("Uncertain boundary: 0.40–0.60 (calibrated for EER min)", `Uncertain boundary: ${(model.threshold - model.uncertain_band).toFixed(3)}–${(model.threshold + model.uncertain_band).toFixed(3)} (configured band)`);
    replaceText("Public acoustic corpus (latest dual-corpus release)", `Evaluation and training data: ${model.training_dataset}`);
    replaceText("WINDOW LENGTH & HOP", model.window_s == null ? "MODEL INPUT DURATION" : "WINDOW LENGTH & HOP");
    const modelWindowLabel = textNodes().find((node) => node.nodeValue.trim().toUpperCase() === "WINDOW LENGTH & HOP");
    if (modelWindowLabel && model.window_s == null) modelWindowLabel.nodeValue = "MODEL INPUT DURATION";
    replaceText("2.0s Window / 1.0s Hop", model.window_s == null ? "Complete variable-duration clip" : `${Number(model.window_s).toFixed(1)}s model window`);
    replaceText("50% rolling overlap, sliding window evaluation", model.window_s == null ? "One score is produced from each complete clip; there is no fixed window or hop." : `${Number(model.window_s).toFixed(1)} s model windows; hop settings apply to live scoring`);
    replaceText("DECISION THRESHOLD: 0.50", `DECISION THRESHOLD: ${Number(model.threshold).toFixed(3)}`);
    replaceText("Pipeline: D-STFT-v2", `Model: ${model.model_version}`);
    replaceText("Real (<0.40)", `Real (<${(model.threshold - model.uncertain_band).toFixed(3)})`);
    replaceText("Uncertain (0.40–0.60)", `Uncertain (${(model.threshold - model.uncertain_band).toFixed(3)}–${(model.threshold + model.uncertain_band).toFixed(3)})`);
    replaceText("Synthetic (≥0.60)", `Synthetic (≥${(model.threshold + model.uncertain_band).toFixed(3)})`);
    replaceText("Inconclusive Band (0.40 - 0.60)", `Inconclusive Band (${(model.threshold - model.uncertain_band).toFixed(3)} - ${(model.threshold + model.uncertain_band).toFixed(3)})`);
    replaceText("< 0.40 Real", `< ${(model.threshold - model.uncertain_band).toFixed(3)} Real`);
    replaceText("0.40-0.60 Band", `${(model.threshold - model.uncertain_band).toFixed(3)}–${(model.threshold + model.uncertain_band).toFixed(3)} Band`);
    replaceText("> 0.60 Synth", `> ${(model.threshold + model.uncertain_band).toFixed(3)} Synth`);
    replaceText("Real (< 0.40)", `Real (< ${(model.threshold - model.uncertain_band).toFixed(3)})`);
    replaceText("Flagged Synthetic (≥ 0.60)", `Flagged Synthetic (≥ ${(model.threshold + model.uncertain_band).toFixed(3)})`);
    replaceText("Uncertain (0.40 – 0.60)", `Uncertain (${(model.threshold - model.uncertain_band).toFixed(3)} – ${(model.threshold + model.uncertain_band).toFixed(3)})`);
    replaceText("DECISION THRESHOLD (0.50)", `DECISION THRESHOLD (${Number(model.threshold).toFixed(3)})`);
    replaceText("ISO/IEC 30107-3 COMPLIANT REPORTING", "Research prototype · no biometric certification");
    replaceText("ENGINE: FoR-2s REALTIME KERNEL", `ENGINE: ${model.name}`);
    replaceText("0.50 Fake Score", `${Number(model.threshold).toFixed(3)} Fake Score`);
    replaceText("Score: ≥ 0.50", `Score: ≥ ${Number(model.threshold).toFixed(3)}`);
    replaceText("0.50 [Cutoff]", `${Number(model.threshold).toFixed(3)} [Cutoff]`);
    replaceText("Split Cutoff: 0.50", `Split Cutoff: ${Number(model.threshold).toFixed(3)}`);
    replaceText("Uncertain Region [0.40 – 0.60]", `Uncertain Region [${(model.threshold - model.uncertain_band).toFixed(3)} – ${(model.threshold + model.uncertain_band).toFixed(3)}]`);
    const main = document.querySelector("main");
    if (location.pathname === "/call-monitor") {
      const fakeSummary = [...document.querySelectorAll("main h2,main h3,main span")].find((element) => element.textContent.trim() === "Ongoing Session Buffer Summary");
      let summaryCard = fakeSummary;
      while (summaryCard && summaryCard !== main && !summaryCard.className?.includes("bg-surface-panel")) summaryCard = summaryCard.parentElement;
      summaryCard?.remove();
      const injectedAlert = textNodes().find((node) => /synthetic voice injected/i.test(node.nodeValue));
      let injection = injectedAlert?.parentElement;
      while (injection && injection !== main && !injection.className?.includes("absolute")) injection = injection.parentElement;
      if (injection && injection !== main) injection.remove();
      const detector = textNodes().find((node) => node.nodeValue.includes("SPEECH ACTIVITY DETECTOR"));
      if (detector) detector.nodeValue = "Audio activity";
    }
    if (main && location.pathname === "/model-and-evaluation") {
      const unsupportedLatency = [...main.querySelectorAll("h2,h3")].find((heading) => heading.textContent.includes("Inference Latency & Streaming Profile"));
      let latencyCard = unsupportedLatency;
      while (latencyCard && latencyCard !== main && !latencyCard.className?.includes("bg-surface-panel")) latencyCard = latencyCard.parentElement;
      latencyCard?.remove();
      const unsupportedRobustness = [...main.querySelectorAll("h2,h3")].find((heading) => heading.textContent.includes("Acoustic Stress & Out-of-Distribution Robustness"));
      let robustnessCard = unsupportedRobustness;
      while (robustnessCard && robustnessCard !== main && !robustnessCard.className?.includes("bg-surface-panel")) robustnessCard = robustnessCard.parentElement;
      robustnessCard?.remove();
    }
    replaceText("Deterministic Audio Spectral Gate", "Saved SVM Audio Scoring Pipeline");
    replaceText("The neural inference pipeline extracts short-time Fourier transform (STFT) bi-spectral phase coherencies. Synthetic speech models struggle to preserve authentic vocal tract resonances above 4.8 kHz, creating localized phase discrepancies.", "The saved SVM uses MFCC, delta, and delta-delta summary features. The score is an additional verification signal, not proof of authenticity.");
    replaceText("GPU Accelerated FFT", "CPU inference");
    replaceText("NVIDIA T4", "CPU-only evaluation");
    replaceText("Async-Thread-01 (GPU: 0)", "Local CPU process");
    replaceText("ISO/IEC 30107-3 BIOMETRIC PRESENTATION ATTACK STANDARD COMPLIANT REPORTING", "Research prototype · no biometric certification claimed");
    replaceText("FoR-ResNet34-STFT", model.model_type);
    replaceText("ResNet34-STFT", model.model_type);
    replaceText("v1.4.2-prod", model.model_version);
    replaceText("v1.4.2 · FoR-2s", `${model.model_version} · ${model.training_dataset}`);
    replaceText("v1.4.2 (", `${model.model_version} (`);
    replaceText("Production Checkpoint", "Loaded Model Artifact");
    replaceText("Production Model Specifications", "Model Specifications");
    replaceText("Constituent deep neural architecture, front-end extraction topology, and hyperparameter calibrations", "Verified model, feature extraction, and runtime configuration from the saved training pipeline");
    replaceText("FoR-2s v1.4.2 (ResNet-W2S)", `${model.name} · ${model.window_s}s`);
    replaceText("Fake-or-Real (FoR-2sec)", model.training_dataset);
    replaceText("Fake-or-Real (FoR-2s)", model.training_dataset);
    replaceText("80-bin Mel-filterbank", model.features);
    replaceText("2D Log-Mel Spectrogram + Bi-spectral Inverted Residuals", model.feature_details);
    replaceText("25ms FFT window, 10ms frame shift, Δ + ΔΔ coefficients", model.feature_details);
    replaceText("48.2k train · 10.32k validation · 10.35k test clips", `${model.data_split.training.toLocaleString()} train · ${model.data_split.validation.toLocaleString()} validation · ${model.data_split.testing.toLocaleString()} test clips`);
    replaceText("70 / 15 / 15 Partition", `${model.data_split.training.toLocaleString()} / ${model.data_split.validation.toLocaleString()} / ${model.data_split.testing.toLocaleString()} clips`);
    replaceText("0.50 Baseline Cutoff", Number(model.threshold).toFixed(3) + " Validation EER Cutoff");
    replaceText("Decision Threshold (0.50)", `Decision Threshold (${Number(model.threshold).toFixed(3)})`);
    replaceText("0.50 (Band:", `${Number(model.threshold).toFixed(3)} (Band:`);
    replaceText("(Band: 0.40–0.60)", `(Band: ${(model.threshold - model.uncertain_band).toFixed(3)}–${(model.threshold + model.uncertain_band).toFixed(3)})`);
    replaceText("0.40–0.60 Band", `${(model.threshold - model.uncertain_band).toFixed(3)}–${(model.threshold + model.uncertain_band).toFixed(3)} Band`);
    replaceText("0.40 - 0.60", `${(model.threshold - model.uncertain_band).toFixed(3)} - ${(model.threshold + model.uncertain_band).toFixed(3)}`);
    const modelHash = document.querySelector("#model-hash-display");
    if (modelHash) modelHash.textContent = `${model.model_hash.slice(0, 16)}...`;
    replaceText("FastAPI · Uvicorn #2", "FastAPI on this device");
    replaceText("FP16 TorchScript serialization", "Joblib SVM pipeline artifact");
    replaceText("+0.8% vs v1.3", "Measured on saved test report");
    replaceText("-0.64% EER min", "Measured on saved test report");
    replaceText("High separation", "Saved test report");
    replaceText("Optimal", "Measured");
    if (test) {
      Object.entries({ Accuracy: test.accuracy, Precision: test.precision, Recall: test.recall, "F1-Score": test.f1, EER: test.eer, FPR: test.fpr, FNR: test.fnr, "ROC-AUC": test.roc_auc }).forEach(([label, value]) => setValueNear(label, `${(Number(value) * 100).toFixed(2)}%`));
      replaceText("Evaluated on N = 10,350 held-out FoR-2s test clips", `Evaluated on N = ${Number(test.count).toLocaleString()} held-out test clips`);
    }
    if (validation) replaceText("Active Checkpoint: " + model.model_version, `Validation threshold source: EER (${Number(validation.eer).toFixed(3)})`);
    const dashboardBindings = {
      "dashboard-total": dashboard.total,
      "dashboard-flagged": dashboard.flagged,
      "dashboard-uncertain": dashboard.uncertain,
      "dashboard-flagged-percent": `${dashboard.total ? (100 * dashboard.flagged / dashboard.total).toFixed(1) : "0.0"}%`,
      "dashboard-uncertain-percent": `${dashboard.total ? (100 * dashboard.uncertain / dashboard.total).toFixed(1) : "0.0"}%`,
      "dashboard-total-count": dashboard.total,
      "dashboard-recent-count": Math.min(history.length, 6),
    };
    Object.entries(dashboardBindings).forEach(([id, value]) => {
      const element = document.getElementById(id);
      if (element) element.textContent = String(value);
    });
    setValueNear("FLAGGED SYNTHETIC", String(dashboard.flagged));
    setValueNear("INCONCLUSIVE BAND", String(dashboard.uncertain));
    setValueNear("ENGINE LATENCY", dashboard.avg_latency_ms == null ? "—" : `${Number(dashboard.avg_latency_ms).toFixed(1)}ms`);
    drawDashboardGraph(dashboard.series || [], Number(model.threshold), Number(model.uncertain_band));
    replaceText("Confidence ≥ 0.60 threshold", `Score ≥ ${Number(model.threshold).toFixed(3)} threshold`);
    replaceText("Range [0.40 – 0.60] split", `Range [${(model.threshold - model.uncertain_band).toFixed(3)} – ${(model.threshold + model.uncertain_band).toFixed(3)}]`);
    replaceText("Decision Threshold\n0.50 (±0.10)", `Decision Threshold\n${Number(model.threshold).toFixed(3)} (±${Number(model.uncertain_band).toFixed(3)})`);
    replaceText("Validation threshold source: EER (0.007)", `Validation split EER: ${Number(validation?.eer).toFixed(3)}; cutoff selected on validation data`);
    replaceText("Decision boundary cutoff is set at 0.50 probability. Samples landing in the uncertain corridor (0.40 – 0.60) are assigned by nearest Euclidean distance to cluster centroids in downstream bi-spectral post-processing.", `Scores below ${(model.threshold - model.uncertain_band).toFixed(3)} are Likely Real, scores within the configured band are Uncertain, and scores above ${(model.threshold + model.uncertain_band).toFixed(3)} are Likely Synthetic. The saved SVM score is not a calibrated real-world probability.`);
    replaceText("Model weights were trained primarily on FoR-2sec. In-the-wild synthesized speech, voice cloning zero-shot models (e.g. recent diffusion vocoders), and unseen codecs can reduce detection confidence.", `The loaded model was trained on ${model.training_dataset}. Performance can degrade on unseen synthesis methods, codecs, acoustic environments, and recording chains.`);
    replaceText("Microphone-to-speaker transfer functions (air acoustics) attenuate high-frequency phase cues, shifting probability scores toward the Uncertain band (0.40 – 0.60).", `Microphone and room effects can shift scores; this model's configured Uncertain band is ${(model.threshold - model.uncertain_band).toFixed(3)}–${(model.threshold + model.uncertain_band).toFixed(3)}.`);
    replaceText("Audio samples under 1.5 seconds contain fewer spectral window transitions, yielding higher variance in per-window classification.", `Audio shorter than the ${Number(model.window_s).toFixed(1)}s model window contains less evidence and may produce an Uncertain result.`);
    replaceText("ISO/IEC 30107-3 compliant reporting conventions", "Research prototype · no biometric certification");
    replaceText("Engine Revision: build-2024.11-rc4", `Loaded model: ${model.model_version}`);
    replaceText("0.50 (±0.10)", `${Number(model.threshold).toFixed(3)} (±${Number(model.uncertain_band).toFixed(3)})`);
    replaceText("Cutoff = 0.50", `Cutoff = ${Number(model.threshold).toFixed(3)}`);
    replaceText("Class assignment on balanced evaluation set (N = 10,350: 5,175 Real / 5,175 Synthetic)", `Saved ${activeProfile === "asvspoof_la_balanced2500" ? "balanced subset" : "test split"} result · N = ${Number(test?.count || 0).toLocaleString()}`);
    if (Array.isArray(test?.confusion_matrix)) {
      const [[tn, fp], [fn, tp]] = test.confusion_matrix;
      replaceText("5,175 samples", `${Number(tn) + Number(fp)} samples`);
      replaceText("4,921", Number(tn).toLocaleString());
      replaceText("254", Number(fp).toLocaleString());
      replaceText("238", Number(fn).toLocaleString());
      replaceText("4,937", Number(tp).toLocaleString());
      const realTotal = Number(tn) + Number(fp);
      const fakeTotal = Number(fn) + Number(tp);
      replaceText("95.1%", `${realTotal ? (100 * Number(tn) / realTotal).toFixed(1) : "—"}%`);
      replaceText("4.9%", `${realTotal ? (100 * Number(fp) / realTotal).toFixed(1) : "—"}%`);
      replaceText("4.6%", `${fakeTotal ? (100 * Number(fn) / fakeTotal).toFixed(1) : "—"}%`);
      replaceText("95.4%", `${fakeTotal ? (100 * Number(tp) / fakeTotal).toFixed(1) : "—"}%`);
    }
    replaceText("True Human (TP)", "True Real (TN)");
    replaceText("True Synthetic (TN)", "True Synthetic (TP)");
    replaceText("False Synthetic (FP)", "False Synthetic (FP)");
    replaceText("False Real (FN)", "False Real (FN)");
    replaceText("SVM with RBF kernel and probability estimates", model.model_type);
    replaceText("STFT bi-spectral phase coherencies. Synthetic speech models struggle to preserve authentic vocal tract resonances above 4.8 kHz, creating localized phase discrepancies.", "MFCC, delta, and delta-delta summaries are scored by the saved SVM pipeline. Interpret results with the measured test and robustness limitations.");
    replaceText("For court-admissible submissions, cross-verify with spectral phase analysis and dual-microphone acoustic coherence.", "Use this result as an additional verification signal and cross-check it with independent evidence.");
    const recentTable = [...document.querySelectorAll("table")].find((table) => table.textContent.toLowerCase().includes("session / file"));
    if (recentTable?.querySelector("tbody")) {
      const recentRows = history.slice(0, 6);
      recentTable.querySelector("tbody").innerHTML = recentRows.length ? recentRows.map((row) => `<tr class="hover:bg-surface-canvas/60 transition-colors"><td class="py-3.5 px-4 font-label-numeric text-label-numeric text-secondary whitespace-nowrap">${escapeHtml(new Date(row.created_at).toLocaleTimeString())}</td><td class="py-3.5 px-3">${escapeHtml(row.source)}</td><td class="py-3.5 px-4 font-medium text-on-surface">${escapeHtml(row.name)}</td><td class="py-3.5 px-3 font-label-numeric text-label-numeric text-secondary">${Number(row.duration_s).toFixed(2)}s</td><td class="py-3.5 px-4">${escapeHtml(row.verdict)}</td><td class="py-3.5 px-4 text-right font-label-numeric text-label-numeric">${row.mean_prob == null ? "—" : Number(row.mean_prob).toFixed(3)}</td><td class="py-3.5 px-4 text-right">${Number(row.id)}</td></tr>`).join("") : '<tr><td colspan="7" class="py-8 px-4 text-center text-secondary">No saved analyses yet. Analyze a file or start a live microphone check.</td></tr>';
      [...recentTable.querySelectorAll("tbody tr")].slice(6).forEach((row) => row.remove());
      textNodes().forEach((node) => {
        if (/Showing\s+\d+\s+of\s+\d+\s+analyses/i.test(node.nodeValue)) node.nodeValue = `Showing ${recentRows.length} of ${dashboard.total} analyses`;
      });
    }
    const historyTable = location.pathname === "/history"
      ? document.querySelector("main table")
      : [...document.querySelectorAll("table")].find((table) => table.textContent.toLowerCase().includes("session / file"));
    let historyFooter = null;
    if (historyTable?.querySelector("tbody")) {
      if (location.pathname === "/history") {
        document.querySelector("main .flex.items-center.bg-surface-canvas.p-1")?.remove();
        [...document.querySelectorAll("main *")].find((element) => element.children.length === 0 && element.textContent.includes("Oct 1") && element.textContent.includes("2024"))?.closest(".cursor-pointer")?.remove();
        replaceText("SEC-LEVEL 4", "");
        const selected = [...document.querySelectorAll("main *")].find((element) => element.children.length === 0 && element.textContent.trim() === "SELECTED RECORD");
        let drawer = selected;
        while (drawer && drawer !== document.querySelector("main") && !drawer.className?.includes("xl:col-span-4")) drawer = drawer.parentElement;
        drawer?.remove();
        const historyCard = historyTable.closest(".xl\\:col-span-8");
        const layout = historyCard?.parentElement;
        if (historyCard) { historyCard.classList.remove("xl:col-span-8"); historyCard.style.gridColumn = "1 / -1"; }
        if (layout) layout.style.gridTemplateColumns = "minmax(0, 1fr)";
        historyFooter = [...(historyCard?.querySelectorAll("span") || [])].find((element) => element.textContent.includes("Showing"))?.closest(".bg-surface-canvas");
        historyFooter?.querySelector(".flex.items-center.gap-1")?.remove();
        [...document.querySelectorAll("main p")].filter((element) => element.textContent.includes("Telemetry metrics represent probabilistic anomaly vectors")).forEach((element) => element.closest(".bg-surface-panel")?.remove());
        replaceText("BUFFER POOL: SYNCED", `${history.length} saved analyses`);
      }
      const verdictFilter = document.querySelector("#voiceguard-verdict-filter");
      const search = document.querySelector('main input[placeholder*="Search by session"]');
      const sourceMount = document.querySelector("#voiceguard-source-filter-mount");
      let sourceFilter = document.querySelector("#voiceguard-source-filter");
      if (sourceMount && !sourceFilter) {
        const label = document.createElement("label");
        label.className = "sr-only";
        label.textContent = "Filter by source";
        sourceFilter = document.createElement("select");
        sourceFilter.id = "voiceguard-source-filter";
        sourceFilter.className = verdictFilter?.className || "rounded-lg border border-border-subtle bg-surface-canvas px-3 py-2";
        sourceFilter.setAttribute("aria-label", "Filter by source");
        sourceFilter.add(new Option("All sources", ""));
        const sourceNames = { Upload: "File upload", mic: "Live check", system: "System or tab audio", replay: "Demo replay", Demo: "Demo clip analysis" };
        [...new Set(history.map((row) => row.source))].sort().forEach((source) => sourceFilter.add(new Option(sourceNames[source] || source, source)));
        label.append(sourceFilter);
        sourceMount.replaceChildren(label);
      }
      const drawRows = () => {
        const query = search?.value.trim().toLowerCase() || "";
        const verdict = verdictFilter?.value || "";
        const source = sourceFilter?.value || "";
        const rows = history.filter((row) => (!source || row.source === source) && (!verdict || row.verdict === verdict) && (!query || `${row.id} ${row.name} ${row.source}`.toLowerCase().includes(query)));
        historyTable.querySelector("tbody").innerHTML = rows.length ? rows.map((row) => `<tr class="hover:bg-surface-canvas/60 transition-colors"><td class="py-3.5 px-4 font-label-numeric text-label-numeric text-secondary whitespace-nowrap">${escapeHtml(new Date(row.created_at).toLocaleString())}</td><td class="py-3.5 px-4">${escapeHtml(row.source)}</td><td class="py-3.5 px-4 font-medium">${escapeHtml(row.name)} <span class="text-secondary">#${Number(row.id)}</span></td><td class="py-3.5 px-3 text-right">${Number(row.duration_s).toFixed(2)}s</td><td class="py-3.5 px-4">${escapeHtml(row.verdict)}</td><td class="py-3.5 px-3 text-right">${row.mean_prob == null ? "—" : Number(row.mean_prob).toFixed(3)}</td><td class="py-3.5 px-3 text-right">${row.max_prob == null ? "—" : Number(row.max_prob).toFixed(3)}</td><td class="py-3.5 px-3 text-right">${Number(row.latency_ms).toFixed(1)} ms</td><td class="py-3.5 px-3 text-center"><button type="button" data-analysis-detail="${Number(row.id)}" class="text-primary">Details</button></td></tr>`).join("") : '<tr><td colspan="9" class="py-8 px-4 text-center text-secondary">No analyses match these filters.</td></tr>';
        if (location.pathname === "/history") {
          if (historyFooter) historyFooter.textContent = `Showing ${rows.length} of ${history.length} saved analyses`;
        }
      };
      drawRows();
      sourceFilter?.addEventListener("change", drawRows);
      verdictFilter?.addEventListener("change", drawRows);
      search?.addEventListener("input", drawRows);
      historyTable.addEventListener("click", async (event) => {
        const button = event.target.closest("[data-analysis-detail]");
        if (!button) return;
        const existing = button.closest("tr").nextElementSibling;
        if (existing?.classList.contains("voiceguard-detail")) { existing.remove(); return; }
        const next = document.createElement("tr");
        next.className = "voiceguard-detail bg-surface-canvas";
        const cell = document.createElement("td");
        cell.colSpan = 9;
        cell.className = "p-4";
        cell.textContent = "Loading analysis details…";
        next.append(cell);
        button.closest("tr").after(next);
        try {
          const response = await fetch(`/api/history/${button.dataset.analysisDetail}`);
          const detail = await response.json();
          if (!response.ok) throw new Error(detail.detail || "Analysis details are unavailable.");
          const pre = document.createElement("pre");
          pre.className = "overflow-auto text-xs";
          pre.textContent = JSON.stringify(detail.windows, null, 2);
          cell.replaceChildren(pre);
        } catch (error) {
          cell.textContent = error.message || "Analysis details are unavailable.";
        }
      });
    }
    if (document.querySelector("#audio-input")) addLiveResultPanel();
    if (location.pathname === "/call-monitor") {
      replaceText("ACTIVE SESSION #4092", "NO ACTIVE SESSION");
      replaceText("MONITORING ACTIVE", "READY TO MONITOR");
      replaceText("Stop Monitoring", "Start Monitoring");
      replaceText("4m 18s", "—");
      replaceText("04:18 active", "—");
      replaceText("41ms", "—");
      replaceText("0.78", "—");
      replaceText("0.89 Fake", "—");
      const rttNode = textNodes().find((node) => node.nodeValue.trim() === "RTT");
      rttNode?.parentElement?.parentElement?.remove();
      const readyNode = textNodes().find((node) => node.nodeValue.includes("READY TO MONITOR"));
      if (readyNode) {
        readyNode.nodeValue = "Ready";
        readyNode.parentElement.id = "voiceguard-monitor-status";
        readyNode.parentElement.querySelector(".animate-ping")?.classList.remove("animate-ping");
      }
    }
    if (["/live-check", "/call-monitor"].includes(location.pathname)) drawLiveGraph([], Number(model.threshold), Number(model.uncertain_band));
    const checksumCopy = document.querySelector("#copy-model-hash");
    if (checksumCopy) checksumCopy.onclick = async () => {
      try {
        await navigator.clipboard.writeText(model.model_hash);
        checksumCopy.title = "Model hash copied";
      } catch (error) {
        checksumCopy.title = error.message || "Clipboard access is unavailable";
      }
    };
    bindPageActions();
    bindLiveControls();
    await bindSettings(model, history);
  }

  async function bindRepositoryData() {
    try {
      const [model, metrics, dashboard, history] = await Promise.all([
        fetch(`/api/model/info?profile=${encodeURIComponent(activeProfile)}`).then((response) => response.json()),
        fetch(`/api/model/metrics?profile=${encodeURIComponent(activeProfile)}`).then((response) => response.json()),
        fetch("/api/dashboard/summary").then((response) => response.json()),
        fetch("/api/history").then((response) => response.json()),
      ]);
      await bindActualReports(model, metrics, dashboard, history);
      document.documentElement.style.visibility = "visible";
    } catch (error) {
      const main = document.querySelector("main");
      if (main) main.innerHTML = `<div class="mx-auto mt-16 max-w-2xl rounded-xl border border-verdict-synthetic-border bg-surface-panel p-8 text-on-surface"><h1 class="font-headline-lg">Backend unavailable</h1><p class="mt-3">The page is not showing example results. Start the FastAPI app and reload this page.</p><p class="mt-2 text-sm text-secondary">${escapeHtml(error.message || error)}</p></div>`;
      document.documentElement.style.visibility = "visible";
    }
  }

  bindNavigation();
  applyResponsiveShell();
  bindProfile();
  bindModelStatus();
  bindRepositoryData();
})();
