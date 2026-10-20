# COPILOT PROMPT — ASVspoof 2019 LA: acquire, verify, parse, split (Copilot does everything)

**Where it goes:** `docs/COPILOT_ASVSPOOF_DATA_PROMPT.md`. Use Copilot **Agent mode** (it runs terminal commands on this laptop; the student only clicks "allow" on commands). This replaces the data parts of Phase R1 in `docs/COPILOT_RECOVERY_PROMPT.md`; all rules in that file still apply (evidence over assertion, no fabricated data, no leakage, one phase at a time, update `docs/PROJECT_STATE.md`).

Start with:
> Read #file:docs/COPILOT_ASVSPOOF_DATA_PROMPT.md and #file:docs/COPILOT_RECOVERY_PROMPT.md. Do not run anything yet. Summarize the plan in 10 lines and list risks. Then wait for "start D0".

---

## 1. The dataset (verified facts from the official record)
- **ASVspoof 2019, Logical Access (LA) partition**, University of Edinburgh DataShare: `https://datashare.ed.ac.uk/handle/10283/3336` (record DOI cited on the page: 10.7488/ds/2555). Files listed there: `LA.zip` (**7.116 GB**), `PA.zip` (16.44 GB, **not needed**), `README.txt`, a Licence file, the evaluation plan PDF.
- Built from the VCTK corpus (107 speakers). LA partitions: **train 20 speakers, dev 10, eval 48**, speaker-disjoint, identical recording conditions. Train and dev contain "known" attacks; **eval also contains "unknown" attacks** (different algorithms), which makes an unseen-generator test possible.
- Audio is PCM compressed with FLAC; the page states no telephone or mobile codec was used.
- A Zenodo mirror exists (`https://zenodo.org/records/6906306`). Use it only as a fallback after inspecting its file list yourself.
- **Everything not on this list (file names, protocol format, attack IDs, class counts) must be discovered from the actual files, not assumed.**

## 2. Rules for this task
1. Download **LA only**. Do not download PA.
2. **No substituting another dataset** and **no synthetic stand-in data** if the download fails. Stop and tell the student exactly what manual step is needed.
3. Read the **Licence file and README.txt**, summarize the terms in `docs/DATASET_NOTES.md`, and quote nothing long. The dataset must **never be committed or redistributed**: add `data/` and `models/` to `.gitignore` first.
4. Show real command output as proof for every step. Anything not run = NOT VERIFIED.
5. If `data/raw/` already contains an ASVspoof copy, **do not re-download**: verify it using the same checks below.

## 3. Steps (stop after each and show proof)

**D0 — Pre-flight.**
- Report free disk space on the drive that holds the repo. Require roughly 20 GB free (zip plus extracted copy; a design estimate). If lower, stop and report options.
- Check whether `curl.exe` works (Windows 11 normally has it) and `python`/venv are active. No new packages unless you show me the exact command first.
- Create `data/raw/`, `data/manifests/`, `data/features/`, and the `.gitignore` entries.
- Look for an existing copy of the dataset in the repo and report what you find.

**D1 — Download (automated, resumable).**
- Fetch the DataShare record page, locate the real download link for `LA.zip`, `README.txt` and the Licence file **from the page itself**. Do not guess URLs. If the page needs interaction you cannot automate, use the Zenodo mirror after inspecting it; if that also fails, stop and give the student step-by-step manual instructions.
- Download with a **resumable** command (e.g. `curl.exe -L -C - -o <file> <url>`), in a background terminal; tell the student it will take a while and poll the file size. Do not start loops that spam the server.
- Proof: final file size vs the 7.116 GB listed (state the exact byte count and whether it matches the listing within a small tolerance).

**D2 — Integrity.**
- If the README or record gives checksums, verify them. Otherwise test the archive (`python -m zipfile -t` or equivalent) and report the result.
- Extract to `data/raw/ASVspoof2019_LA/`. Keep the zip until D3 passes, then **ask before deleting**.

**D3 — Discover the structure (no assumptions).**
Read `README.txt` and list the extracted tree. Report: folder names, protocol/key files and their column format, file extension and count per partition, speakers per partition, **attack IDs per partition**, label values, bona fide vs spoof counts per partition, sample rate, duration distribution and channels (measure on the actual audio, sampling if needed). Check that the numbers match the official description (20/10/48 speakers; unknown attacks only in eval) and **report any mismatch**. Write all of this to `docs/DATASET_NOTES.md`.

**D4 — Manifests and the four sets.**
Build manifests (`path, label, split, speaker, attack_id, sr, duration_s, sha1`) with label `0 = bona fide, 1 = spoof`, then:

| Project set | Source |
|---|---|
| `train` | official train partition |
| `val` | official dev partition (model selection, hyperparameters, **threshold**) |
| `test` | official eval partition **minus the demo speakers** |
| `demo_holdout` | a few **whole speakers** held out of the official eval partition |

- Hold out the demo speakers **by speaker**, so `test` and `demo_holdout` share no speakers (not just no files). Choose speakers with a fixed seed, not by hand. Number of demo speakers: the smallest that yields a balanced sample of **25 bona fide + 25 spoof** files (configurable; design choice; each demo file labeled with its real attack ID), with the spoof sample spanning the attack types available among those speakers.
- Lock `demo_holdout`: save the manifest read-only, and make `tests/test_no_leakage.py` assert no path/hash/speaker overlap between `demo_holdout` and `train`, `val`, `test`.
- Confirm train/val/test speaker-disjointness with a test, not by assumption.

**D5 — Data quality and shortcut checks (before any training).**
- Class balance per partition (this dataset is expected to be imbalanced: **measure**, then handle with class weights or balanced subsampling and say which; report EER plus metrics on both a balanced subsample and the natural distribution).
- Duration, leading/trailing silence ratio, energy and sample rate **by class**, with plots. The literature has reported that silence can act as a shortcut in this dataset; verify with our own data before trusting any accuracy, and check the paper's exact claim before citing it.
- Run the metadata-only baseline from the recovery prompt; report it.
- 8 GB RAM: provide `max_files_per_class`, stream FLAC decoding, cache features as float32.

**D6 — Evaluation hooks specific to this dataset.**
- Per-**attack-ID** breakdown on `test` (EER or detection rate per attack) and a **known vs unknown attack** summary. This is the unseen-generator evidence required by the research questions.
- State clearly that standard ASVspoof LA reporting also uses **min t-DCF**, which we do **not** compute (it needs speaker-verification scores). We report EER, F1, precision, recall, FPR, FNR, AUC.
- Store these in `results/` so the Model & Evaluation page can display them.

**D7 — Hand-off.**
Update `docs/PROJECT_STATE.md` (dataset facts, split sizes, demo speakers count, discovered protocol format, open issues). Then wait for me before starting Phase R2 (model pipeline).

## 4. Known limitations to record (do not hide)
- ASVspoof LA is clean read speech from VCTK; the live microphone and call demo audio is a different condition, so live readings may degrade. The system must show "Uncertain" rather than overclaim.
- LA has no telephone-channel condition. Telephone behavior is tested only through our simulated degradations, labeled as simulations.
- Do not blindly merge another dataset (e.g. Fake-or-Real) into these sets; if added later, it is a separate, separately-reported domain.

## 5. Response format (every step)
1. Plan (≤6 lines) 2. Commands run **with real output** 3. Files created/changed 4. Proof against the step's gate 5. NOT VERIFIED items / risks 6. `PROJECT_STATE.md` updated 7. Next step (wait for go-ahead).

## 6. Paste-ready prompts
**Start:** `Start D0. Run the pre-flight checks only. Show real output. Do not download anything yet.`
**Next:** `Proceed to D<N> exactly as specified in #file:docs/COPILOT_ASVSPOOF_DATA_PROMPT.md. Show real command output as proof and stop at the end of the step.`
**If the download fails:** `Show the exact error and the response headers/status. Do not substitute data. Give me the manual steps as a numbered list.`
