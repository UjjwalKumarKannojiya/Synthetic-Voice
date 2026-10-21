# Local demonstration guide

## Start

1. Confirm this checkout has its ignored local model artifacts, `data/manifests/asvspoof_la_val.csv`, and source audio under `LA/`. A clean clone does not contain these research artifacts.
2. If `.local-notes/demo-assets-r9/manifest.csv` is missing, run `.venv\Scripts\python.exe scripts\prepare_demo_assets.py`. This prepares eight attributed replay clips from the validation partition and never uses the locked evaluation holdout. The script refuses to overwrite an existing demo set.
3. From the repository root, run `.venv\Scripts\python.exe scripts\run_app.py` and open `http://127.0.0.1:8000/`.
4. Create or sign in to a local account. Local SQLite persists accounts and analysis history under the ignored `data/` directory.

## Demonstrate a recorded sample

1. Open **Call Monitor** from the sidebar.
2. Accept the audio-use consent.
3. Choose a sample from the demo replay selector. The selector hides the ground-truth label.
4. Click **Start Monitoring** and let the sample play through the browser stream.
5. During playback, point out that the timeline shows windows from the FoR streaming model. When replay finishes, the summary is saved to this account's history.
6. After replay, compare the disclosed ground-truth label with the separate ASVspoof complete-clip result. Say clearly that this complete-clip model is not the model producing the live timeline, and the cross-dataset live timeline is not a valid ASVspoof evaluation.
7. Open **History** to show the saved Call Monitor session.

## Demonstrate live speech

1. Open **Live Check**, choose the microphone source, accept consent, and click **Start Live Check**.
2. Speak for several seconds, then pause. The live window score updates only when speech windows are available; silence can produce a no-speech status rather than a score.
3. Click **Stop** to end the stream and save its summary; confirm the row in **History**.

## Explain limitations

- The displayed fake score is the model's score, not a calibrated probability or proof that a voice is genuine.
- The FoR model's held-out test metrics are weak; it can miss synthetic speech. State this before interpreting any sample.
- Call Monitor reads audio captured by the browser on this device. It does not connect to or inspect a phone call or phone network.
- Browser microphone and shared-tab capture require an interactive browser, user permission, and the selected audio source. Headless fake-audio evidence is not a physical-device test.
- A clean source checkout needs separately provisioned model/evaluation artifacts and demo data before scoring can be demonstrated.
