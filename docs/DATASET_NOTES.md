# ASVspoof 2019 LA Dataset Notes

## Source and local copy

The verified local copy is under `LA\LA\`. No download was performed in D0/D1 because
the required Logical Access files are already present. The tree contains:

- `ASVspoof2019_LA_train\flac`
- `ASVspoof2019_LA_dev\flac`
- `ASVspoof2019_LA_eval\flac`
- `ASVspoof2019_LA_cm_protocols`
- `ASVspoof2019_LA_asv_protocols`
- `ASVspoof2019_LA_asv_scores`
- `README.LA.txt`

The README describes 16 kHz, 16-bit FLAC audio. CM protocol rows use five
whitespace-separated columns:

```text
SPEAKER_ID AUDIO_FILE_NAME SYSTEM_ID UNUSED_FIELD KEY
```

For bona fide rows, the system and unused fields are `-`. For spoof rows, the
attack/system ID is in the fourth field and the final field is `spoof`.

## Measured partition discovery

The following figures were produced by enumerating the local protocol and FLAC files
and calling `soundfile.info` for every FLAC file. There were no metadata read errors.

| Partition | Protocol rows | FLAC files | Speakers | Bona fide | Spoof | Attack IDs |
|---|---:|---:|---:|---:|---:|---|
| train | 25,380 | 25,380 | 20 | 2,580 | 22,800 | A01-A06 |
| dev | 24,844 | 24,986 | 20 | 2,548 | 22,296 | A01-A06 |
| eval | 71,237 | 71,933 | 67 | 7,355 | 63,882 | A07-A19 |

The measured speaker counts are 20/20/67, not the 20/10/48 figures stated in the
task prompt. The local copy therefore does not match that prompt description and the
local files/protocols are treated as authoritative pending provenance resolution.
Train, dev, and eval speaker identifiers should still be checked for overlap by the
manifest test before any training.

Train and dev spoof attacks are known attacks A01-A06. Eval contains A07-A19, which
are not present in train/dev and therefore supports a known-versus-unseen attack
breakdown if the eval protocol is used.

## Audio metadata

All enumerated files are mono, 16,000 Hz FLAC:

| Partition | Sample rates | Channels | Duration min (s) | Median (s) | P05 (s) | P95 (s) | Max (s) |
|---|---|---|---:|---:|---:|---:|---:|
| train | 16,000: 25,380 | 1: 25,380 | 0.6524 | 3.2015 | 1.5993 | 6.0846 | 13.1879 |
| dev | 16,000: 24,986 | 1: 24,986 | 0.6951 | 3.2835 | 1.5334 | 6.2283 | 16.5138 |
| eval | 16,000: 71,933 | 1: 71,933 | 0.4699 | 2.8431 | 1.2742 | 6.1178 | 16.5475 |

These are variable-duration recordings; they are not the fixed two-second clips in
the existing `for-2sec` corpus.

## Protocol/file coverage

- Train: 25,380 protocol IDs, 25,380 files, 0 missing, 0 unreferenced.
- Dev: 24,844 protocol IDs, 24,986 files, 0 missing, 142 unreferenced files.
- Eval: 71,237 protocol IDs, 71,933 files, 0 missing, 696 unreferenced files.

The unreferenced dev/eval files must not be assigned labels by filename alone. The
manifest builder must either exclude them with an explicit reason or resolve them
from an authoritative protocol before modeling.

## README and license summary

`README.LA.txt` documents the directory layout, FLAC format, CM/ASV protocol
formats, attack IDs, and ASV score columns. It identifies attacks A01-A19 and
describes the spoofing systems as TTS, VC, or combined TTS/VC methods.

Each train/dev/eval directory contains `LICENSE.txt`. The license text begins by
identifying the Open Data Commons Attribution License. It permits sharing,
modification, and use of the database subject to attribution, while warning that
individual contents may have separate copyright, privacy, contract, or data
protection rights. The dataset must not be committed or redistributed from this
repository; only derived manifests, reports, and model artifacts are intended to be
tracked as permitted by the project policy.

## Not yet verified

- SHA-1/content duplicates across and within partitions.
- Complete train/dev/eval speaker-disjointness.
- A fixed-seed whole-speaker demo holdout of eval.
- Per-class duration, energy, silence, and metadata shortcut measurements.
- Whether the local copy corresponds exactly to the stated DataShare archive/version.
- License compliance for any future redistribution of derived artifacts.

## D4 leakage-safe manifests

The manifest builder is `scripts\build_asvspoof_manifest.py`. It reads only
protocol-referenced files, computes SHA-1 hashes and FLAC metadata, and writes:

- `data\manifests\asvspoof_la_train.csv`: 25,380 rows, 2,580 bona fide and
  22,800 spoof.
- `data\manifests\asvspoof_la_val.csv`: 24,844 rows, 2,548 bona fide and
  22,296 spoof.
- `data\manifests\asvspoof_la_test.csv`: 69,453 rows, 7,209 bona fide and
  62,244 spoof.
- `data\manifests\asvspoof_la_demo_holdout.csv`: 50 rows, exactly 25 bona fide
  and 25 spoof.

The demo holdout uses fixed seed 42 and whole speaker `LA_0045`; all other files
from that speaker are excluded from test. Spoof files in the demo span attacks
A07, A10, A12-A19. The remaining test set has 66 speakers. The 838
unreferenced dev/eval files are listed in
`data\manifests\asvspoof_la_exclusions.csv` and are not assigned labels.

`tests\test_no_leakage.py` passed with 3 tests. It checks no path, SHA-1, or
speaker overlap among train, val, test, and demo holdout, manifest schema and
labels, and the balanced multi-attack demo condition. The measured speaker
intersections were zero for every pair. The manifests are read-only after
generation.

## D5 data quality and shortcut check

`scripts\asvspoof_data_quality.py` ran with seed 42, a deterministic maximum of
1,000 files per class per train/val/test split, and a silence threshold of 0.01.
The demo holdout was not read or used. The full manifest class counts are:

| Set | Bona fide | Spoof | Spoof fraction |
|---|---:|---:|---:|
| train | 2,580 | 22,800 | 89.84% |
| val | 2,548 | 22,296 | 89.73% |
| test | 7,209 | 62,244 | 89.62% |
| demo_holdout | 25 | 25 | 50.00% |

The quality sample was balanced for comparison (1,000 of each class per split).
Representative train-sample measurements show different class distributions:

- Bona fide mean RMS `0.1171`, median silence ratio `0.5659`.
- Spoof mean RMS `0.1217`, median silence ratio `0.4815`.
- Both classes have fixed 16 kHz mono metadata in the sample.

The metadata-only logistic-regression baseline was fit on sampled train metadata
only, including duration, sample rate, channels, file size, RMS, and silence ratio.
On balanced 1,000-per-class samples, it achieved:

| Split | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|---:|
| val | 0.689 | 0.7203 | 0.618 | 0.6652 | 0.7492 |
| test | 0.794 | 0.7816 | 0.816 | 0.7984 | 0.8658 |

This is a strong shortcut warning. It is not an acoustic-model result and must be
reported alongside all future ASVspoof results. Full JSON evidence is in
`results\asvspoof_la_data_quality.json`; plots are in
`results\asvspoof_la_plots\`.

## D6 evaluation hooks

`scripts\asvspoof_eval_breakdown.py` is the score-file evaluation contract for the
future ASVspoof model. It requires `path,label,attack_id,score` columns and a
threshold selected on validation data. It reports overall metrics, per-attack-ID
metrics, and combined known (`A01`-`A06`) versus unknown (`A07`-`A19`) attack
metrics. Bona fide rows are paired into both known and unknown summaries so the
false-positive behavior remains visible.

The evaluator explicitly records min t-DCF as not computed because this project does
not have the ASV speaker-verification scores required for that metric. It does not
reuse the existing FoR SVM: that model was trained on a different dataset and its
application here would be an invalid cross-dataset result.

The hook and its fixture test are present, but **ASVspoof model attack metrics are
NOT VERIFIED** until an ASVspoof-trained model produces a real score CSV.

## R2 bounded classical baseline

`scripts\train_asvspoof_classical.py` trained an MFCC + delta + delta-delta
summary SVM using 500 files per class from the train manifest. The validation
threshold was selected by validation EER and frozen for test. The validation and
test samples were also 500 per class. The demo holdout was not used.

| Split | Accuracy | Precision | Recall | F1 | FPR | FNR | ROC-AUC | EER |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| validation | 0.895 | 0.8958 | 0.8940 | 0.8949 | 0.1040 | 0.1060 | 0.9538 | 0.1060 |
| test | 0.885 | 0.9176 | 0.8460 | 0.8803 | 0.0760 | 0.1540 | 0.9412 | 0.1220 |

These are bounded subset results, not full-eval claims. Artifacts are
`models\asvspoof_la_svm\svm.joblib`,
`models\asvspoof_la_svm\model_meta.json`,
`results\asvspoof_la_svm.json`, and
`results\asvspoof_la_svm_test_scores.csv`.

The D6 breakdown contains the real unknown-attack result for A07-A19. Its known
group contains only bona fide files because this eval protocol has no A01-A06
spoof rows; known-group ROC-AUC and EER are therefore undefined, not zero.

An expanded CPU-bounded run used 2,500 files per class per train/validation/test
split. It produced validation accuracy `0.9112`, ROC-AUC `0.9715`, and EER
`0.0888`; test accuracy `0.8808`, ROC-AUC `0.9418`, and EER `0.1280`, with the
validation threshold `0.8323956492443629` frozen for test. These remain balanced
subset results, not full natural-distribution test results. The expanded artifacts
are `models\asvspoof_la_svm_balanced2500\`,
`results\asvspoof_la_svm_balanced2500.json`, and
`results\asvspoof_la_svm_balanced2500_breakdown.json`.

## Exact discovery evidence

The discovery run used:

```powershell
Set-Location 'D:\syntheic voice clone'
@' ... '@ | & '.\.venv\Scripts\python.exe' -
```

Its output reported zero FLAC metadata errors, the counts and distributions above,
and the protocol/file coverage values above. The full command output is recorded in
the session response for D1/D3; no archive download or extraction occurred.
