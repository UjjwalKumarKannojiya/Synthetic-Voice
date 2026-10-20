# Stage A0 Audit

This audit records the verified state of the repository before adding the web
application. It covers the existing `for-2sec` baseline, the newly added
`for-norm` dataset, and the Stitch export archive.

## Existing detector

- The primary saved detector is the SVM at
  `models/classical_for_2sec/svm.joblib`.
- It is trained by `scripts/train_classical.py` using an
  `sklearn.pipeline.Pipeline` containing `StandardScaler` and `SVC` with an
  RBF kernel and `probability=True`.
- The feature index is
  `data/features/mfcc_for_2sec/index.csv`.
- Features are 120-value vectors: 20 MFCC means, 20 MFCC standard
  deviations, and the corresponding delta and delta-delta summaries.
- MFCC settings are 16 kHz audio, 20 coefficients, 400-sample FFT,
  160-sample hop, and 40 mel bands. The implementation is in
  `src/svf/features/mfcc.py`.
- The training clips in the primary `for-2sec` dataset are exactly 2.0
  seconds. This is verified by `results/audit_for_2sec.json` and
  `results/metadata_distributions_for_2sec.json`.
- The validation EER threshold is `0.6786657728693419`, recorded in
  `results/classical_for_2sec.json`. It is correctly frozen for the reported
  test metrics.
- The SVM's `predict_proba(...)[, 1]` output is a model probability estimate
  produced by scikit-learn's probability calibration. It is not evidence of
  a calibrated real-world probability and must be presented as a model score
  or estimated fake probability with the research disclaimer.

## Preprocessing and inference gap

Training feature extraction uses the shared `src.svf.audio_io.load_audio`
and `src.svf.features.mfcc` modules. The current Streamlit upload path also
uses those modules, so its MFCC calculation matches the training path for
single clips.

There is no reusable detector, fixed-window aggregation, VAD, streaming
engine, API, database, or model metadata artifact yet. The current upload
screen only accepts WAV files and scores one whole clip. It does not provide
per-window results, live WebSocket inference, history, or call monitoring.
The next implementation stage must create these pieces around the existing
shared preprocessing rather than duplicate it.

## Evaluation actually available

The saved primary SVM test report records:

- Accuracy: `0.5542`
- Precision: `0.7218`
- Recall: `0.1765`
- F1: `0.2836`
- False-positive rate: `0.0680`
- False-negative rate: `0.8235`
- ROC-AUC: `0.7349`
- EER: `0.3272`

The validation metrics are much stronger than the held-out test metrics, so
the validation result must not be used as a product-performance claim.

The metadata-only shortcut baseline is above chance on the test split
(accuracy `0.6857`, F1 `0.7311`). This is an active shortcut warning: acoustic
results must be interpreted alongside metadata distributions.

The bounded robustness report shows severe degradation under several
conditions. For example, the reported fake recall is `0.0` at 10 dB and 20 dB
noise, and `0.1` for the 1-second condition. MP3 compression was not run
because `ffmpeg` was unavailable. The saved end-to-end latency report has a
median of `4.11 ms` and a p95 of `5.73 ms` over 60 measurements, but also a
maximum of `813.84 ms`; the hardware is not recorded.

## Newly added `for-norm` dataset

The audit is saved at `results/audit_for_norm.json`. It found:

- 69,300 WAV files with no standard-library read errors.
- Training: 53,868; validation: 10,798; testing: 4,634.
- Real: 34,605; fake: 34,695.
- All files are mono at 16 kHz.
- Durations range from `0.0` to `38.6834` seconds; median is
  `2.2999` seconds and p95 is `8.2114` seconds.

This is not interchangeable with the 2-second training corpus. The zero
duration and broad duration range require investigation before using the
variant for training or window evaluation. Speaker and generator identity
are not inferred by the audit, so unseen-speaker or unseen-generator claims
remain unsupported.

The follow-up file-level inspection found:

- 2 zero-frame files, both in `training/real`, each only 44 bytes.
- 5,765 duplicated basenames (8,159 extra occurrences), so basenames are not
  stable unique identifiers.
- 2 exact-content overlaps with the existing `for-2sec` corpus, both fake
  files in validation/testing. They must be excluded from any cross-dataset
  evaluation or reported as overlap.
- The files are named with preprocessing-history suffixes such as
  `_16k.wav_norm.wav_mono.wav_silence.wav`, which is useful provenance evidence
  but is not a verified speaker or generator identifier.

The new dataset therefore cannot be treated as an independent held-out set
until the two overlaps are removed (or explicitly accounted for), the zero
duration files are quarantined, and the provenance/preprocessing relationship
is documented.

A reproducible clean manifest is now available at
`data/manifests/for_norm_clean.csv`. It contains 69,296 rows with unique paths
and unique content hashes, no zero-duration rows, and split counts of 53,866
training, 10,797 validation, and 4,633 testing files. The exclusions and their
matching paths are recorded in `results/for_norm_exclusions.json`; the
manifest builder now supports repeatable `--exclude-path` arguments.

## Stitch archive

`D:\stitch_go_starter_project.zip` contains seven HTML exports and screenshots
for Dashboard, Analyze File, Live Check, Call Monitor, History,
Model & Evaluation, and Settings, plus a shared platform export and a design
file. The exports are visual starting points only; their placeholder values
must be replaced with API data before they are shipped.

The UI brief is consistent with the repository constraints: seven pages only,
Likely Real / Uncertain / Likely Synthetic labels, explicit uncertain bands,
empty/loading/error states, no phone-network integration, and no raw-audio
storage by default.

## Risks and required changes

1. Add verified model metadata, including the 2-second window, sample rate,
   feature configuration, threshold source, and model-score semantics.
2. Add a detector that uses the existing audio and MFCC helpers, with explicit
   padding/cropping behavior for short and long clips.
3. Add a configurable VAD, verdict mapping, per-window aggregation, and
   streaming backpressure handling.
4. Add a SQLite history layer and the REST/WebSocket contract from
   `docs/APP_BLUEPRINT.md`.
5. Keep raw audio out of storage by default and require consent before live
   capture.
6. Expose the poor test and robustness behavior in the Model & Evaluation
   page; do not replace missing measurements with placeholders.
7. Keep `for-norm` separate until its zero-duration files and provenance are
   investigated and a new evaluation is run.

## Stage A1 implementation status

The initial reusable inference layer is now in `app/core/`:

- `models/model_meta.json` records the verified 2-second SVM contract.
- `app/core/detector.py` reuses shared audio/MFCC code, pads short input,
  emits per-window scores, and excludes VAD-gated silent windows.
- `app/core/vad.py`, `app/core/verdict.py`, and `app/core/audio_utils.py`
  provide shared runtime helpers.
- The detector CLI is available with
  `python -m app.core.detector <wav-path>`.

This does not yet claim that the FastAPI/WebSocket application is complete;
history, streaming, and UI binding remain later stages.
