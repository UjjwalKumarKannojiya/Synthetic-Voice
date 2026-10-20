# Code Flow

## System boundary

The system will accept an audio file and produce a fake score, a threshold-based decision, and
reproducibility metadata. Training and evaluation are offline workflows; the future app will reuse
the same preprocessing and feature code rather than implementing a second audio pipeline.

## Planned dependency flow

```text
raw audio + dataset metadata
        |
        v
audit_data.py  ---> audit JSON/text report
        |
        v
manifest.py    ---> manifest CSV with path, label, split, metadata
        |
        v
audio_io.py    ---> mono, configured sample rate, optional safe transforms
        |
        +------------------+
        v                  v
features/mfcc.py     features/cqcc.py
        |                  |
        +--------+---------+
                 v
        cached float32 feature arrays
                 |
                 v
        models/classical.py
                 |
                 v
        validation threshold selection
                 |
                 v
        eval/metrics.py ---> JSON/CSV results
                 |
                 v
        robustness + latency + app
```

## Responsibilities

### Audit

The audit discovers extensions, folders, metadata files, labels, splits, sample rates, durations,
channels, and possible speaker/generator identifiers. It must report unknown fields instead of
guessing them.

### Manifest

The manifest is the contract between data discovery and modeling. Each row identifies one audio file,
its fixed label, split source, and available metadata. It checks duplicate paths and split overlap.

### Preprocessing

`audio_io.py` is the only owner of shared audio preparation. The same settings must be used for train,
validation, test, robustness conditions, and the app. Fixed-length padding/cropping is only enabled
when the selected model requires it.

### Features

Feature modules receive preprocessed audio and return finite, typed arrays. Classical features are
summarized into fixed-length vectors. CNN features retain a fixed time-frequency shape only when the
CNN stage is approved.

### Models

Classical models are the first executable baseline. Scalers are fit on training data only. A future
CNN will be small and CPU-oriented, with validation-based early stopping if it is approved.

### Evaluation

Metrics consume labels and fake scores. Threshold selection belongs to validation; test metrics use
the frozen threshold. Every run records configuration, seed, runtime, environment, metrics, and
failure cases in `results/`.

### Robustness and app

Robustness transformations apply to test audio only unless an explicitly named augmentation study
changes that rule. The app imports the same loader, feature extractor, model, and threshold artifact
used by evaluation. It is an additional verification signal, not proof of identity.

## First executable path

The first code path to implement after the dataset path is supplied is:

`python scripts/audit_data.py --data-path <DATASET_PATH>`

That command will be written only after the actual dataset location is known. Its output will decide
the next manifest and split decisions; it will not fabricate missing labels or metadata.

## Validation gates

1. Scaffold: paths and configuration are present.
2. Audit: discovered structure is saved and read by the user.
3. Manifest: split, label, duplicate, and speaker-overlap checks pass or are documented.
4. Features: shapes and finite values pass tests on small synthetic inputs.
5. Models: validation threshold and test metrics are reproducible.
6. Robustness/app: failures are explicit and latency is measured on the actual machine.