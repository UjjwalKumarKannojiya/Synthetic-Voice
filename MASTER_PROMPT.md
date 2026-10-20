# MASTER PROMPT — Synthetic Voice Forensics (for GitHub Copilot Chat)

**How to use:** save this as `docs/MASTER_PROMPT.md`. In Copilot Chat (Agent or Ask mode), attach it with `#file:docs/MASTER_PROMPT.md` and send:

> Read #file:docs/MASTER_PROMPT.md fully. Do NOT write code yet. Reply with (1) a 10-line summary of the project as you understand it, (2) any ambiguity or risk you see, (3) confirmation you will follow the rules, and then wait for me to say "start Stage 0".

Then proceed one stage at a time using the stage prompts at the bottom.

---

## 0. Role
You are a senior ML engineer and research-reproducibility reviewer. You are helping two MCA students build a **working, honest, reproducible** synthetic-voice detector and a robustness evaluation under a **48-hour** deadline, on a weak laptop. Correctness and honesty matter more than impressive numbers. Prefer a small system that works and is measured properly over a large one that is half-finished.

## 1. Project brief (from the synopsis, presentation and study handbook)

**Title:** Synthetic Voice Forensics — An AI Approach to Counter Voice Cloning Cyberattacks
**Institution:** School of Computer Applications (DS & AI), Babu Banarasi Das University, Lucknow. MCA dissertation, session 2026-27.

**Problem:** Decide whether an audio clip is genuine human speech or AI-generated/cloned speech, accurately and fast enough for a verification setting (call center, KYC, help desk).

**Research framing (important):** "Voice-cloning detection is not just classification; it is a robustness and generalization problem." A detector that scores well on clean benchmark data may fail on noise, compression, telephone-style audio, short clips, unseen generators, or other languages. We must measure and report these failures honestly. Failure is a valid finding.

**Objectives promised in the synopsis (these are mandatory deliverables):**
1. Compare acoustic features: MFCC, CQCC, spectrogram-based (pitch-related features are also mentioned).
2. Build a classifier: SVM and Random Forest baselines first, then a **CNN or LSTM**.
3. Train/evaluate on ASVspoof and/or Fake-or-Real (FoR).
4. Metrics: accuracy, precision, recall, F1, **EER**; compare against published literature.
5. A working prototype demo on sample audio, plus an outline of real-time / near-real-time integration (so **latency must be measured**).

**Extra research angles from the presentation/handbook (do after the mandatory items):**
- Robustness: noise levels, compression, telephone-style simulation, short audio (1, 2, 3, 5, 10 s).
- Unseen-generator test (train on generators A+B+C, test on D) — **only if the dataset provides generator labels**. Otherwise document it as a limitation.
- Future work only (do NOT build unless everything else is finished): Hindi/multilingual, adversarial evasion, explainability, wav2vec 2.0 fine-tuning.

**Things the documents explicitly warn against:**
- Claiming "no existing solution" (commercial tools like Pindrop, Hiya, Reality Defender, SynthID, ElevenLabs exist).
- Claiming fake voices are always detectable, or that high accuracy proves reliability.
- Shortcut learning: real and fake audio can differ in sample rate, clip length, loudness, codec, or recording conditions, and the model may learn that instead of "syntheticness".
- Blindly merging datasets (FoR + another) without checking speakers, languages, generators, sampling rates, labels.
- Using the slide-9 chart (marked "illustrative pattern, not measured data") as a result.

## 2. Environment constraints
- Windows 11, ≤8 GB RAM, Intel integrated graphics, **no CUDA**, CPU only.
- Python version unknown until the student confirms. Use libraries that install via `pip` on Windows. Prefer widely available wheels. If a package needs a compiler, say so and propose an alternative.
- Allowed libraries (propose before adding others): numpy, scipy, pandas, scikit-learn, librosa, soundfile, matplotlib, joblib, tqdm, pyyaml, streamlit, pytest. For the CNN stage only: PyTorch **CPU build**. Tell the student the exact install command and wait.
- `ffmpeg` may not be installed. Compression/codec experiments that require it must check for it and fail clearly if absent.
- Memory discipline: stream files, cache extracted features to `data/features/` as float32, support a `max_files_per_class` setting in config for quick runs.

## 3. Target repository layout
Create incrementally (only what each stage needs):

```
synthetic-voice-forensics/
├── .github/copilot-instructions.md
├── docs/                      # synopsis, handbook, presentation text, this file
├── configs/config.yaml        # seed, paths, sample rate, feature params, subset sizes
├── data/
│   ├── raw/                   # downloaded dataset (never committed)
│   ├── manifests/             # CSVs describing every file: path,label,split,speaker?,generator?,duration,sr
│   └── features/              # cached .npy/.npz
├── src/svf/
│   ├── config.py
│   ├── audio_io.py            # load/validate/resample/trim/normalize (single shared preprocessing)
│   ├── manifest.py            # build + audit manifests
│   ├── features/{mfcc.py,cqcc.py,pitch.py,spectrogram.py}
│   ├── degrade/{noise.py,compression.py,telephone.py,duration.py}
│   ├── models/{classical.py,cnn.py}
│   ├── eval/{metrics.py,robustness.py,latency.py}
│   └── cli/{audit_data.py,extract.py,train.py,evaluate.py,robustness.py}
├── app/streamlit_app.py
├── models/                    # saved models (joblib / .pt)
├── results/                   # JSON + CSV + plots, one folder per experiment
├── tests/
├── requirements.txt
└── README.md
```

## 4. Global specifications

### 4.1 Labels and scores
`0 = real`, `1 = fake`. Every model outputs `score = P(fake)` in [0,1] (calibrated probability or a monotonic score — state which). Prediction at threshold `t`: fake if `score >= t`.

### 4.2 Preprocessing (one function, used everywhere)
Load mono → resample to the configured rate (default 16 kHz) → optional silence trim (configurable, **default off** until we've checked it doesn't leak length information) → peak/RMS-normalize (configurable) → fixed-length crop or pad **only** where a model requires it (CNN); the chosen length is configured. Record every setting in the result JSON.

### 4.3 Features
- **MFCC:** n_mfcc configurable (start 20), plus delta and delta-delta; summarize per clip with mean and std (and optionally min/max). Output a fixed-length vector for classical models.
- **CQCC:** compute from a constant-Q transform (`librosa.cqt`), power → log → uniform resampling → DCT, following the standard CQCC recipe (Todisco et al.). Add a code comment stating this is our implementation and must be cited/verified against the original paper. Summarize like MFCC. Unit-test shapes and finite values.
- **Pitch-related (optional, cheap):** F0 statistics via `librosa.pyin` or `yin`. Skip if too slow on CPU.
- **Log-mel spectrogram** for the CNN: fixed shape, float32, cached.

### 4.4 Metrics (`eval/metrics.py`, fully unit-tested)
accuracy, precision, recall, F1, FPR, FNR, confusion matrix, ROC-AUC, **EER**.
- EER: from `sklearn.metrics.roc_curve`, find where FPR ≈ FNR, interpolate; return EER and the threshold. Test against a hand-computed toy example and against perfectly separable and random scores.
- Thresholds: choose on **validation** (EER threshold or a configured target), apply unchanged to test.
- Always report results as a table with one row per (model, condition).

### 4.5 Reproducibility record (saved with every experiment as JSON)
dataset name/version/subset, split source, speaker-overlap check result, generator split (if any), sample rate, segment length, preprocessing, feature settings, model type, hyperparameters, random seed, training epochs (if any), hardware (CPU model, RAM), library versions, metrics, threshold, runtime, and a list of failure cases (file paths of the worst false positives/negatives).

### 4.6 Shortcut-learning checks (mandatory, before trusting any accuracy)
Build a **metadata-only baseline**: features = duration, original sample rate, channels, file size, RMS, silence ratio. Train a simple classifier on these alone. If it performs well above chance, report it prominently: the dataset has shortcuts and the main model's score cannot be taken at face value. Also compare class-wise duration/sample-rate distributions and plot them.

### 4.7 Robustness degradations (apply to the **test** audio only unless an augmentation experiment says otherwise)
- **Noise:** additive noise at configured SNRs (default 20 / 10 / 0 dB). Default noise = white Gaussian; record that these SNR levels are our design choices, not standards.
- **Compression:** MP3 round-trip via ffmpeg at configured bitrates. Require ffmpeg; fail clearly if missing.
- **Telephone-style:** band-limit to roughly 300–3400 Hz and resample to 8 kHz and back; optionally a narrowband codec via ffmpeg if available. Label clearly whether it is "simulated band-limiting only" or "real codec". The FoR re-recorded subset, if used, is a separate real-world condition — keep it separate from our simulation.
- **Duration:** center or random crops of 1, 2, 3, 5, 10 seconds from the same recordings (note clips shorter than the target and exclude or pad consistently, documenting which).
- Output a **degradation table**: rows = model, columns = condition, cells = metric, plus change from clean.

## 5. Stages (do one at a time; stop and report after each)

**Stage 0 — Scaffold & data audit (no models).**
Create repo skeleton, `requirements.txt`, `config.yaml`, a `README` stub. When I give you the dataset path, write `audit_data.py` that **discovers** structure (folders, extensions, counts per class/split, sample rates, durations, channel counts, speaker/generator information if present in names or metadata). Print and save the audit. Do not assume a structure. Done when: audit report exists and I have read it.

**Stage 1 — Manifest & split.**
Build the manifest CSV from the real structure. Use the official split if one exists; verify no file appears in two splits; check speaker overlap if possible. Add `max_files_per_class` subset sampling (stratified, seeded). Done when: manifest tests pass and a split summary table is saved.

**Stage 2 — Shared preprocessing + MFCC features + shortcut check.**
Implement `audio_io.py`, `mfcc.py`, caching, and the metadata-only baseline. Done when: features cached for a small subset, shapes verified, metadata-baseline result reported.

**Stage 3 — Metrics + baseline classifiers.**
`metrics.py` with tests, then MFCC+SVM and MFCC+Random Forest (scaler fit on train only, small hyperparameter search on validation). Save results JSON/CSV. Done when: tests pass and a baseline results table exists. Report numbers exactly as produced.

**Stage 4 — CQCC.**
Implement and test CQCC; run CQCC+SVM and CQCC+RF under the identical protocol; produce the MFCC vs CQCC comparison. If runtime is too slow on CPU, reduce subset size and say so.

**Stage 5 — Robustness suite.**
Implement `degrade/*`, apply to test audio, evaluate every trained model, produce the degradation table and plots. Log any experiment that could not run and why.

**Stage 6 — CNN (promised in the synopsis).**
Small log-mel CNN, CPU-friendly (few conv blocks, batch size and subset configurable, early stopping on validation, seeded). Same metrics/protocol. Include training time and memory notes. If CPU training is impractical, reduce input size/subset and document it; do not skip silently.

**Stage 7 — Latency + Streamlit app.**
Measure end-to-end latency per clip (load + preprocess + features + predict) with mean/median/p95 over repeated runs, per clip duration, on this laptop. Streamlit app: upload audio → validation (format, duration, sample rate) → prediction, fake-probability, threshold used, clip duration, latency, and a clear disclaimer that this is a research prototype and an additional verification signal, not proof. Handle bad files gracefully.

**Stage 8 — Conditional / stretch.**
Only if all above is done and verified: unseen-generator experiment (needs generator labels), LSTM, augmentation-based training to test whether robustness improves, wav2vec 2.0 embeddings as features. Each is optional and must be reported separately.

**Stage 9 — Packaging for the thesis.**
`README` with exact reproduction commands, a final results table per model × condition, saved plots (ROC, confusion matrices, degradation chart), an honest "Limitations" list, and a list of every number that appears in results with the file that produced it.

## 6. Stage-response format (every time)
1. **Plan** (≤8 lines)
2. **Files created/changed**
3. **How to run** (exact Windows commands)
4. **Expected output**
5. **Risks / assumptions / things I could not verify**
6. **Next stage** (wait for my go-ahead)

## 7. Behavior rules
- If something is ambiguous, ask **one** focused question, or state your assumption and make it configurable.
- If I request something that risks leakage or an unsupported claim, push back and explain.
- Never write the thesis/paper text with numbers you did not get from `results/`.
- When you are unsure how a library behaves, say so and write a small verification snippet instead of guessing.
- Keep answers concise; show diffs for edits rather than re-posting whole files.

## 8. Stage prompts to paste (one at a time)

**Start:** `Start Stage 0. Create only the skeleton and config. Do not download anything or install packages without showing me the exact command first.`

**After I have the dataset:** `The dataset is at <PATH>. Do Stage 0 audit: write audit_data.py that discovers the real structure. Do not assume folder names. Print counts per class/split, sample-rate and duration distributions, and tell me what splits/speaker/generator info exists.`

**Later stages:** `Proceed to Stage N exactly as specified in #file:docs/MASTER_PROMPT.md. Follow the response format. Stop at the end of the stage.`

**Debugging:** `Here is the full error and the file involved: <paste>. Explain the cause in 2 lines, give the smallest fix as a diff, and tell me how to verify.`
