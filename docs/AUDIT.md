# Model evidence and caveats

This page summarizes saved research results. It does not certify real-world detection performance. Scores are model estimates and can be wrong, especially for unseen generators, short clips, codecs, noise, and new recording conditions.

## Existing FoR baseline

The saved SVM uses 120 MFCC, delta, and delta-delta summary features from 16 kHz audio. Its threshold was selected on validation data and frozen before test evaluation.

| Held-out test metric | Saved result |
|---|---:|
| Accuracy | 0.5542 |
| ROC-AUC | 0.7349 |
| Equal error rate | 0.3272 |
| False-negative rate | 0.8235 |

These results are weak for product use. The metadata-only baseline reached test accuracy `0.6857`, which is a shortcut warning: strong aggregate scores can reflect dataset cues rather than robust voice evidence. Existing robustness reports also show poor fake recall under several noise and short-duration conditions. Consult source reports before citing any result.

## ASVspoof experiment

The ASVspoof LA evaluation uses a separate complete-clip MFCC/SVM profile. The recorded 2,500-per-class experiment is a balanced subset: validation accuracy `0.9112`, ROC-AUC `0.9715`, EER `0.0888`; test accuracy `0.8808`, ROC-AUC `0.9418`, EER `0.1280`. Its threshold `0.8323956492443629` was selected on validation. These numbers are not full-set deployment metrics and do not describe the live FoR streaming model.

## Interpretation

- Live monitoring runs the windowed FoR detector. The ASVspoof model is complete-clip only and is not used for the live WebSocket stream.
- Do not infer calibrated real-world probability, authenticity, or biometric certification from the score.
- An Uncertain result is appropriate where evidence is insufficient.
- The app's real inference requires model weights and matching reports/metadata; they are deliberately absent from Git.
- Reproduce or inspect the exact report artifacts locally before using numbers in a dissertation or presentation. The reports and artifacts are ignored under `results/` and `models/`.

The dataset partitions, measured protocol counts, and local copy caveats are in [DATASET_NOTES.md](DATASET_NOTES.md). Current deployment limitations are in [PROJECT_STATE.md](PROJECT_STATE.md).
