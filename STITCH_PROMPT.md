# STITCH PROMPT — Synthetic Voice Forensics UI

**How to use**
1. Open Stitch, choose **Web / Desktop**.
2. Paste **PART A** first (design system + app context), then generate the Dashboard using Screen 1.
3. Generate the remaining screens one at a time (Screens 2–7), pasting each screen prompt. Smaller prompts give better results than one giant prompt.
4. When done, export each screen's **HTML/CSS code** (and screenshots) and save them in the project under `frontend_design/` (check Stitch's export/copy-code menu; I can't verify its exact menu names). Give that folder to Copilot, because Copilot generally cannot open a Stitch link.

---

## PART A — Global design brief (paste first)

Design a desktop web application called **"VoiceGuard Forensics"** — a calm, professional analyst tool that checks whether speech audio is real human speech or AI-generated/cloned speech. It is used by a security or fraud analyst. It is a **research prototype**, so the interface must stay modest: no marketing language, no login or signup, no pricing, no fake notifications, no unrelated widgets.

**Layout:** fixed left sidebar (240 px) with the app logo/name and 7 navigation items, in this order: Dashboard, Analyze File, Live Check, Call Monitor, History, Model & Evaluation, Settings. Top header with the page title on the left and, on the right, a small **model status** indicator (green dot + "Model loaded"). Content area on a light neutral background with white rounded cards (12 px radius), subtle borders, generous spacing, 12-column grid, max content width 1280 px.

**Style:** clean, trustworthy, forensic-tool feel. Sidebar in deep navy, content area light. Primary accent: a single blue. Font: Inter (or similar). Use a clear type scale, tabular numerals for data.

**Semantic result system (used on every page):**
- **Likely Real** — green, check icon
- **Uncertain** — amber, exclamation icon
- **Likely Synthetic** — red, cross icon
Always combine color with an icon and a text label (never color alone).

**Probability display:** a horizontal gauge from 0 to 1 showing "fake probability", with a thin vertical marker for the decision threshold and a shaded "uncertain" band around it.

**Timeline display:** a time-based line/bar chart of per-window fake probability, with a dashed threshold line and the uncertain band shaded.

**Data realism:** show plausible *placeholder* values, and give every dynamic element a clear label so developers can bind real data (e.g. "Total analyses", "Average latency (ms)"). Never show claims like "99% accurate" or "bank-grade security".

**States:** include designs or clearly styled components for empty state, loading, and error where relevant.

**Footer note on result screens (small, muted):** "This is a research prototype. A result is an additional verification signal, not proof."

---

## Screen 1 — Dashboard
Page title "Dashboard". Row of 4 KPI cards: **Total analyses**, **Flagged as synthetic** (count and % of total), **Uncertain**, **Average latency (ms)**. Below: left (wide) a table "Recent analyses" with columns Time, Source (Upload / Live / Call), Name, Duration, Verdict chip, Fake probability. Right: a card "Fake probability — recent analyses" with a small bar/line chart; under it a "Model status" card listing model name, training dataset, decision threshold, and a status dot. Top-right of content: three quick-action buttons: "Analyze file", "Start live check", "Monitor a call". Include an empty state for when there are no analyses yet.

## Screen 2 — Analyze File
Page title "Analyze File". A large drag-and-drop zone with "Drop an audio file here or browse" and a muted line listing accepted formats (WAV, FLAC, MP3, OGG) and a max size. After upload, show a progress bar, then a result layout: left, a large **verdict card** (verdict chip + fake probability number + the probability gauge with threshold marker and uncertain band); right, a **Details** card (File name, Duration, Original sample rate, Speech ratio, Windows analyzed, Processing time, Model version, Threshold used). Full width below: a **Timeline** card of per-window fake probability across the file. Buttons: "Export JSON", "Analyze another file". Muted disclaimer line at the bottom.

## Screen 3 — Live Check (microphone)
Page title "Live Check". Top control bar: input-device dropdown, a large primary **Start listening** button that becomes **Stop** while active, and a small status pill that can show "Listening", "No speech detected" or "Lagging". Main area: left, a live **audio level meter** and a big current verdict card with the smoothed fake probability and gauge; right/below, a **rolling timeline chart** of the last 60 seconds of window scores. Small counters: "Windows analyzed", "Latency per window (ms)". A privacy line near the start button: "Audio is analyzed on this device's server and is not saved by default." After stopping, show a **Session summary** card (duration, speech ratio, average and maximum probability, final verdict, "Saved to history" confirmation).

## Screen 4 — Call Monitor
Page title "Call Monitor". A small muted note under the title: "Analyzes the audio stream on this device. Not connected to a phone network." Top: a **source selector** as three segmented tabs — "Microphone (speakerphone)", "System / tab audio", "Demo replay (audio file)" — with a contextual help line for each, then **Start monitoring / End call** button and a live **call timer**. Main area: a prominent **Call risk** card showing one of "No concern", "Uncertain", "Suspected synthetic voice" plus the smoothed probability; a **live timeline** with flagged segments highlighted; a dismissible **alert banner** that appears when sustained synthetic-like audio is detected ("Sustained synthetic-like speech detected — verify the caller through another channel"). After the call ends, a **Call summary** card: duration, speech ratio, number of flagged segments with their time ranges, final risk, buttons "Export report" and "Save to history". Include a consent/privacy notice modal that appears before monitoring starts.

## Screen 5 — History
Page title "History". Filter bar: Source (All/Upload/Live/Call), Verdict (All/Real/Uncertain/Synthetic), date range, and an "Export CSV" button. Table: Date/time, Source, Name, Duration, Verdict chip, Mean probability, Max probability, Latency. Clicking a row opens a right-side **detail drawer** with the verdict, gauge, timeline, and details. Pagination at the bottom. Empty state.

## Screen 6 — Model & Evaluation
Page title "Model & Evaluation". Top: a **Model card** (Model type, Features used, Training dataset, Data split, Window length, Decision threshold). Next: **Performance metrics** as a compact table or cards: Accuracy, Precision, Recall, F1, False positive rate, False negative rate, EER, ROC-AUC. A **confusion matrix** (2×2). A **Robustness table** with rows = test conditions (e.g. Clean, Re-recorded channel, Noise, Compression, Short clip) and columns = key metrics. A **Latency** card (mean / median / p95 ms). A **Limitations** card with 3–4 honest bullet points (e.g. "Trained on a public dataset; live audio may behave differently"). Design an **empty state** for "No evaluation results available yet".

## Screen 7 — Settings
Page title "Settings". Grouped cards: **Detection** (decision threshold slider, uncertain-band width slider), **Streaming** (smoothing strength, silence gate sensitivity, alert rule "alert after N consecutive flagged windows"), **Privacy** (toggle "Store raw audio" default OFF, button "Clear history" with confirmation). "Save changes" and "Reset to defaults" buttons.

---

## Quality check before exporting
- Same sidebar, header, spacing and verdict colors on all 7 screens.
- No extra pages (no login, billing, profile, notifications, team, integrations).
- Every number is clearly a placeholder-style value, and each has a visible label.
