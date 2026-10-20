# Decision Record

## Purpose

This file records decisions that affect scientific validity, reproducibility, or the public API of
the project. It is deliberately explicit about what is known, what is pending, and why a choice was
made. Numbers from the handbook or presentation are background guidance, not experiment results.

## Current context

- Workspace state: Stage 3 classical baselines completed.
- Primary dataset: `for-2sec`; rerecorded data remains separate.
- Python environment: project-local `.venv`.
- Hardware details: not yet measured.
- Results: audit, shortcut, and classical baseline artifacts exist.

## Decisions made

### D-001: Build in stages

We will implement Stage 0 first: structure, configuration, and documentation. Dataset audit comes
before manifests, features, or models. This prevents folder names, counts, labels, and split behavior
from being invented.

### D-002: Keep labels and scores fixed

`0` means real/bona fide and `1` means fake/spoof. Every model-facing fake score increases toward
fake speech. A threshold is selected on validation data and then held unchanged for test evaluation.

### D-003: Use one shared preprocessing path

Audio loading, mono conversion, resampling, optional trimming, and optional normalization will live
in one module and be reused by training, evaluation, robustness tests, and the app. Silence trimming
and normalization are disabled by default until an audit checks that they do not create a shortcut.

### D-004: CPU-first and memory-bounded

The initial design uses streaming file iteration, disk feature caches, and `float32` arrays. A CNN
will not be selected or trained until the classical baseline protocol works and the machine has been
measured. No CUDA or large pretrained model is assumed.

### D-005: Official splits are authoritative

If the dataset provides official train/validation/test splits, they will be preserved. If it does
not, a split strategy will be proposed and approved after inspecting speaker and generator metadata.
No split will be created by mixing files blindly.

### D-006: No result claims before artifacts exist

Accuracy, dataset sizes, file counts, latency, and similar values will only be reported when produced
by scripts and saved under `results/`. The current documents contain no measured results.

## Pending decisions

- Dataset and version.
- Whether ASVspoof, FoR, or another dataset is scientifically usable after audit.
- Whether speaker and generator identifiers are available.
- Exact split protocol and subset limit.
- Feature parameters beyond the initial configurable MFCC defaults.
- Classical model hyperparameters.
- Whether the CNN is feasible within CPU and time limits.
- Compression experiment availability, which depends on `ffmpeg`.

## Dataset audit findings

The first audit was run on 2026-10-15 using the Python standard-library WAV reader. Reports are
saved under `results/`.

| Variant | Files | Train / validation / test | Labels | Audio metadata |
| --- | ---: | --- | --- | --- |
| `for-2sec` | 17,870 | 13,956 / 2,826 / 1,088 | 8,935 fake / 8,935 real | mono, 16 kHz, exactly 2.0 s |
| `for-rerec` | 13,268 | 10,208 / 2,244 / 816 | 6,655 fake / 6,613 real | mono, 16 kHz, 1.448-2.477 s |

Both variants had zero WAV read errors and no unknown split or label path parts. These are measured
audit counts, not model results.

### Dataset decision

Keep the variants separate until their provenance, speaker identity, and relationship are verified.
Do not merge them, use one as a hidden test set, or claim unseen-generator generalization yet. The
two-second variant is a suitable first baseline candidate because its duration and class counts are
controlled, subject to the manifest and duplicate checks.

### Manifest gate

Separate manifests were built successfully at `data/manifests/for_2sec.csv` and
`data/manifests/for_rerec.csv`. Their row counts and split counts match the audit reports. The builder
rejected duplicate paths and duplicate SHA-256 content within each variant; no such failure occurred.
This is a file-content check, not proof of speaker independence or generator independence.

### Shortcut baseline finding

The metadata-only baseline on `for-2sec` used duration, sample rate, channels, file size, RMS, and
silence ratio. Scaling was fit on training rows only. It achieved validation accuracy `0.6638358103`
and test accuracy `0.6856617647`; the full report is
`results/metadata_baseline_for_2sec.json`.

This is materially above chance for the balanced primary dataset. Until the source construction and
class-wise metadata distributions are investigated, MFCC or later model scores must not be described
as evidence of syntheticness alone. The result is a dataset-bias warning, not a model result for the
planned detector.

### Classical baseline finding

The full MFCC cache contains 17,870 primary-dataset clips, summarized into 120-dimensional vectors.
SVM and Random Forest were fit on training features only. Each test report uses a threshold selected
from validation EER; the test set was not used for threshold selection.

The saved report is `results/classical_for_2sec.json`. Test ROC-AUC was `0.7349021410` for SVM and
`0.3785277898` for Random Forest. At the selected SVM threshold, test recall was `0.1764705882` and
FNR was `0.8235294118`; the Random Forest test accuracy was `0.4071691176`. These are baseline
measurements, not evidence that the detector is deployment-ready. The Random Forest result requires
investigation before it is used in later comparisons.

### Metadata distribution finding

The saved distribution report is `results/metadata_distributions_for_2sec.json`. Duration, sample
rate, channels, and file size are identical between classes. RMS differs notably by class, supporting
the earlier shortcut warning; normalization remains disabled so this effect is visible rather than
silently removed.

### CQCC scope and comparison

CQCC unit tests passed and a 600-vector comparison subset was extracted with 100 files per class per
official split. The matched subset reports are `results/mfcc_subset_for_2sec.json` and
`results/cqcc_subset_for_2sec.json`. On this subset, SVM test ROC-AUC was `0.1477` for MFCC and
`0.9108` for CQCC; Random Forest test ROC-AUC was `0.1549` for MFCC and `0.8828` for CQCC.
These subset measurements are exploratory and must not replace the full-data baseline.

Full CQCC extraction was attempted but proved too slow for the CPU constraint. It was stopped after
17,205 indexed lines and preserved under `data/features/cqcc_for_2sec_partial`. No full-dataset CQCC
claim is made.

### Robustness finding

The saved bounded report is `results/robustness_for_2sec_svm.json`. It evaluated 50 real and 50 fake
test clips per condition using the frozen SVM threshold from the clean validation run. On this subset,
fake recall was `0.00` at 20 dB, 10 dB, and 0 dB white noise; telephone simulation fake recall was
`0.02`; 1-second duration fake recall was `0.10`; 2-second fake recall was `0.26`; and 3-second
center-pad fake recall was `0.76`. These are controlled subset measurements, not general population
claims.

MP3/compression was not run because `ffmpeg` was not found. The experiment reports this explicitly and
does not substitute another codec.

The separate rerecorded transfer report is `results/cross_condition_rerec_for_2sec_svm.json`. It uses
the `for-2sec` SVM and frozen threshold without retraining on rerecorded data. On its clean bounded
subset, test ROC-AUC was `0.6744`, fake recall was `0.10`, and FNR was `0.90`. This is a measured
cross-condition limitation, not evidence that the rerecorded dataset is intrinsically harder in all
settings.

### CNN scope and finding

The approved CPU-only PyTorch build is `2.14.1+cpu`; CUDA is unavailable. A compact two-block CNN
with fixed `(64, 200)` log-mel inputs was implemented and tested. Full-dataset CNN training was not
attempted because the project is CPU-constrained. The bounded comparison used 100 files per class per
official split, five maximum epochs, batch size 16, and validation early stopping.

The saved report is `results/cnn_for_2sec_subset.json`. Its test ROC-AUC was `0.5494`, accuracy was
`0.545`, and FPR was `0.64`. This is an exploratory subset result; it does not demonstrate an
improvement over the classical baselines.

### Latency finding

The saved report is `results/latency_for_2sec_svm.json`. On 20 two-second test clips with three
repeats each, the complete SVM path (load, shared preprocessing, MFCC extraction, and prediction)
had mean latency `17.7765 ms`, median `4.10885 ms`, and p95 `5.7252 ms`. One cold-start measurement
was `813.8378 ms`; it is retained in the report and means the mean should not be treated as a steady
state guarantee. Hardware details remain incomplete.

### Prototype decision

PyTorch `2.14.1+cpu` and Streamlit were installed only inside the project `.venv`. The Streamlit app
uses the saved SVM, shared preprocessing, MFCC features, and frozen validation threshold. It accepts
WAV uploads, reports fake probability, decision, duration, and end-to-end latency, and displays a
research disclaimer. It is not an identity or access-control decision system.

The app is organized into Dashboard, Live Check, Robustness, Evidence, and Methodology views. The
Dashboard shows artifact-backed metrics and warnings; Live Check is the only upload surface;
Robustness and Evidence expose saved experiment artifacts; Methodology explains the controlled flow.
This keeps operational checking separate from evidence review and avoids implying that the upload
screen is a general authentication service.

### UI and security hardening

The interface was simplified so normal users see the Dashboard and Live Check without raw artifact
paths or implementation details. Research evidence remains available on dedicated views. Uploaded
files are restricted to WAV, 10 MB, and 30 seconds; non-finite audio is rejected; temporary files are
deleted; upload errors do not expose internal exception text. Streamlit is started on `127.0.0.1`
with a 10 MB server upload cap by default.

This is practical local hardening, not a claim that the application is breach-proof. It has no user
authentication, authorization, TLS, audit logging, or production threat model. It must not be exposed
to an untrusted network without adding those controls.

## Approval quiz before major changes

Before accepting a major change, I will ask a short quiz and wait for your answers. A major change
includes changing labels, split policy, preprocessing, dataset, score meaning, model family, adding a
large dependency, or changing the evaluation protocol.

1. What behavior or evidence requires this change?
2. Which leakage or shortcut risk could it introduce?
3. Which existing artifact or test would prove the change is safe?
4. Should the change be accepted, rejected, or recorded as an experiment branch?

The change is not accepted until the answers and the resulting decision are recorded here. Small
bug fixes that preserve the documented contract do not require this quiz.

## Change log

| ID | Status | Change | Evidence | Approval |
| --- | --- | --- | --- | --- |
| D-001 | accepted | Stage 0 scaffold before data-dependent code | Empty workspace inspection | automatic initial decision |
| D-002 | accepted | Fixed label and score convention | Project brief | automatic initial decision |
| D-003 | accepted | Shared preprocessing contract | Project brief | automatic initial decision |
| D-004 | accepted | CPU and memory constraints | Project brief | automatic initial decision |
| D-005 | accepted | Preserve official splits | Project brief | automatic initial decision |
| D-006 | accepted | Keep the two extracted variants separate pending provenance checks | Audit reports in `results/` | stage decision |
| D-007 | accepted | Build separate manifests with duplicate-content checks | CSV manifests in `data/manifests/` | stage validation |
| D-008 | accepted | Treat metadata shortcut as a mandatory limitation | `results/metadata_baseline_for_2sec.json` | stage validation |
| D-009 | accepted | Save classical baseline report under `results/` and freeze validation threshold for test | `results/classical_for_2sec.json` | stage validation |
| D-010 | accepted | Bound CQCC comparison after full CPU run proved impractical | Subset reports and partial cache | stage validation |
| D-011 | accepted | Evaluate test-only noise, telephone, and duration conditions with frozen threshold | `results/robustness_for_2sec_svm.json` | stage validation |
| D-012 | accepted | Evaluate separate rerecorded condition without retraining | `results/cross_condition_rerec_for_2sec_svm.json` | stage validation |
| D-013 | accepted | Add CPU-only compact log-mel CNN with bounded training | `results/cnn_for_2sec_subset.json` | stage validation |
| D-014 | accepted | Add Streamlit prototype using the evaluated SVM pipeline | `app/streamlit_app.py` and local runtime check | stage validation |
| D-015 | accepted | Expand prototype into dashboard, live check, robustness, evidence, and methodology views | `app/streamlit_app.py` and browser validation | stage validation |
| D-016 | accepted | Harden upload surface and bind local app to localhost by default | `app/streamlit_app.py`, local server check, full tests | stage validation |