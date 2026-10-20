"""Streamlit research prototype for synthetic voice scoring."""

from __future__ import annotations

import json
import html
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.svf.audio_io import AudioConfig, load_audio
from src.svf.features.mfcc import MFCCConfig, extract_mfcc, summarize_mfcc


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "classical_for_2sec" / "svm.joblib"
RESULTS_PATH = ROOT / "results" / "classical_for_2sec.json"
ROBUSTNESS_PATH = ROOT / "results" / "robustness_for_2sec_svm.json"
REREC_PATH = ROOT / "results" / "cross_condition_rerec_for_2sec_svm.json"
LATENCY_PATH = ROOT / "results" / "latency_for_2sec_svm.json"
DECISION_PATH = ROOT / "docs" / "decision.md"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_DURATION_SECONDS = 30.0


@st.cache_resource
def load_artifacts():
    import joblib

    model = joblib.load(MODEL_PATH)
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    threshold = float(results["models"]["svm"]["test"]["threshold"])
    return model, threshold


@st.cache_data
def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_status() -> pd.DataFrame:
    artifacts = {
        "Detection check": RESULTS_PATH,
        "Changed-audio checks": ROBUSTNESS_PATH,
        "Rerecorded check": REREC_PATH,
        "Speed check": LATENCY_PATH,
    }
    return pd.DataFrame(
        [{"Check": name, "Status": "Ready" if path.exists() else "Missing"} for name, path in artifacts.items()]
    )


def page_header(label: str, title: str, description: str) -> None:
    st.markdown(f"<div class='eyebrow'>{label}</div>", unsafe_allow_html=True)
    st.title(title)
    st.markdown(f"<p class='lede'>{description}</p>", unsafe_allow_html=True)


def render_table(headers: list[str], rows: list[list[str]]) -> None:
    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in row) + "</tr>"
        for row in rows
    )
    st.markdown(
        f"<div class='table-wrap'><table class='clean-table'><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def render_dashboard() -> None:
    page_header("Synthetic Voice Forensics / Overview", "Check suspicious audio", "A local research screen for checking a clip and reviewing measured reliability.")
    results = load_json(RESULTS_PATH)
    latency = load_json(LATENCY_PATH)
    svm_test = results["models"]["svm"]["test"]
    metric_columns = st.columns(4)
    metric_columns[0].metric("Detection AUC", f"{svm_test['roc_auc']:.3f}")
    metric_columns[1].metric("Error rate", f"{svm_test['eer']:.3f}")
    metric_columns[2].metric("Median latency", f"{latency['latency_ms']['median']:.2f} ms")
    metric_columns[3].metric("Decision threshold", f"{svm_test['threshold']:.3f}")
    st.markdown("### Current readout")
    left, right = st.columns([1.4, 1])
    with left:
        render_table(
            ["Measure", "Value"],
            [
                ["Detection AUC", f"{svm_test['roc_auc']:.3f}"],
                ["False-negative rate", f"{svm_test['fnr']:.3f}"],
                ["Median latency", f"{latency['latency_ms']['median']:.2f} ms"],
            ],
        )
    with right:
        st.markdown("#### Signal status")
        st.warning("A result is a signal for review, not proof that a speaker is genuine or synthetic.")
        st.info("Performance changes when audio is noisy, short, compressed, or rerecorded.")
    st.caption("Research evidence and implementation artifacts are available from the Evidence page.")


def analyze_upload(uploaded_file) -> None:
    st.audio(uploaded_file)
    temporary_path: Path | None = None
    try:
        file_name = (uploaded_file.name or "").lower()
        if not file_name.endswith(".wav"):
            raise ValueError("Only WAV files are accepted.")
        if uploaded_file.size is not None and uploaded_file.size > MAX_UPLOAD_BYTES:
            raise ValueError("The file is larger than the 10 MB upload limit.")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary:
            temporary.write(uploaded_file.getvalue())
            temporary_path = Path(temporary.name)
        started = time.perf_counter()
        audio, sample_rate = load_audio(temporary_path, AudioConfig())
        duration = audio.size / sample_rate if sample_rate else 0.0
        if duration <= 0.0:
            raise ValueError("The audio clip is empty.")
        if duration > MAX_DURATION_SECONDS:
            raise ValueError("The clip is longer than the 30 second analysis limit.")
        if not np.isfinite(audio).all():
            raise ValueError("The audio contains invalid numeric samples.")
        features = summarize_mfcc(extract_mfcc(audio, MFCCConfig(sample_rate=sample_rate))).reshape(1, -1)
        model, threshold = load_artifacts()
        fake_probability = float(model.predict_proba(features)[0, 1])
        latency_ms = (time.perf_counter() - started) * 1000.0
        prediction = "SYNTHETIC / FAKE" if fake_probability >= threshold else "REAL / BONA FIDE"
        st.markdown("### Analysis result")
        result_columns = st.columns(3)
        result_columns[0].metric("Prediction", prediction)
        result_columns[1].metric("Fake probability", f"{fake_probability:.3f}")
        result_columns[2].metric("Latency", f"{latency_ms:.2f} ms")
        st.progress(min(fake_probability, 1.0), text="Fake probability")
        st.caption(f"Threshold: {threshold:.3f}  |  Clip duration: {duration:.3f} s  |  Sample rate after preprocessing: {sample_rate} Hz")
        st.warning("Use this result as an additional verification signal, never as the sole identity, fraud, or access decision.")
    except Exception:  # noqa: BLE001 - user uploads must fail without exposing internals.
        st.error("This clip could not be analyzed. Check that it is a valid WAV file under 10 MB and 30 seconds.")
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def render_live_check() -> None:
    page_header("Synthetic Voice Forensics / Live Check", "Test a voice", "Choose a short live recording or upload an existing WAV clip.")
    live_tab, upload_tab = st.tabs(["Record live speech", "Upload a clip"])
    with live_tab:
        st.markdown("### Live recording")
        st.caption("Record a short sample, then release the control to analyze it.")
        live_audio = st.audio_input("Record speech", key="live_recording")
        if live_audio is not None:
            analyze_upload(live_audio)
    with upload_tab:
        st.markdown("### Existing audio")
        uploaded = st.file_uploader("Choose a WAV clip", type=["wav"], key="file_upload")
        if uploaded is not None:
            analyze_upload(uploaded)


def render_robustness() -> None:
    page_header("Synthetic Voice Forensics / Robustness", "Where the detector bends", "Measured test-only conditions, shown as evidence of behavior rather than promises of reliability.")
    robustness = load_json(ROBUSTNESS_PATH)
    rows = []
    for condition, values in robustness["conditions"].items():
        rows.append({"Condition": condition, "ROC-AUC": values["roc_auc"], "Recall": values["recall"], "FNR": values["fnr"], "Count": values["count"]})
    render_table(
        ["Condition", "ROC-AUC", "Recall", "FNR", "Count"],
        [[row["Condition"], f"{row['ROC-AUC']:.3f}", f"{row['Recall']:.3f}", f"{row['FNR']:.3f}", str(row["Count"])] for row in rows],
    )
    st.caption("Noise, telephone simulation, and duration transformations were applied to test audio only. MP3 compression was not run because ffmpeg was unavailable.")
    rerec = load_json(REREC_PATH)
    clean = rerec["conditions"]["clean"]
    st.markdown("### Rerecorded transfer")
    cols = st.columns(3)
    cols[0].metric("ROC-AUC", f"{clean['roc_auc']:.3f}")
    cols[1].metric("Fake recall", f"{clean['recall']:.3f}")
    cols[2].metric("FNR", f"{clean['fnr']:.3f}")


def render_evidence() -> None:
    page_header("Synthetic Voice Forensics / Evidence", "What is actually measured", "Evidence is the saved result of an experiment, not a promise about every future recording.")
    st.info("Use this page to see whether a result has a saved report, whether a condition was actually tested, and which limitations remain. It is the audit trail behind the user-facing check.")
    status = artifact_status()
    render_table(["Check", "Status"], status[["Check", "Status"]].values.tolist())
    st.markdown("### Known limitations")
    st.markdown("""
- The metadata-only baseline is above chance, indicating shortcut risk.
- Speaker and generator identities have not been verified from authoritative metadata.
- CQCC and CNN comparisons are bounded subset experiments.
- Compression evaluation is unavailable until ffmpeg is installed.
- This service is not an authentication authority.
""")
    st.download_button("Download decision record", DECISION_PATH.read_bytes(), file_name="decision.md", mime="text/markdown")


def render_methodology() -> None:
    page_header("Synthetic Voice Forensics / Methodology", "How the signal moves", "Methodology explains the controlled steps between an audio clip and the displayed result.")
    st.info("The purpose of this page is transparency: it shows the safeguards used to reduce leakage and explains why the result should be treated as an additional verification signal.")
    st.markdown("""
    **Input**  audio clip  ->  **Shared preparation**  standardize the signal  ->  **Evidence score**  compare with measured patterns  ->  **Fixed review threshold**  result
    """)
    st.markdown("### Guardrails")
    st.markdown("""
- Labels are fixed: `0 = real/bona fide`, `1 = fake/spoof`.
- Official train, validation, and testing folders are preserved.
- Scaling and thresholds are learned from training/validation only.
- Test transformations are never used to train the clean baseline.
- Results are saved under `results/` before they are shown here.
""")
    st.markdown("### What this screen means")
    st.info("The service compares acoustic evidence with patterns measured in the research dataset. It cannot prove who is speaking and may fail on new recording conditions.")


st.set_page_config(page_title="Synthetic Voice Forensics", page_icon="SVF", layout="wide")
st.markdown("""
<style>
:root { --ink: #17212b; --muted: #53636d; --teal: #087f8c; --coral: #d95d39; --line: #d3dfe2; --paper: #f4f7f6; --panel: #ffffff; }
.stApp { background: var(--paper); color: var(--ink); }
.block-container { width: min(1180px, calc(100% - 2rem)); max-width: 100%; padding-top: clamp(1rem, 4vw, 2rem); padding-bottom: 5rem; }
.eyebrow { color: var(--teal); font-size: 0.74rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; }
.lede { color: var(--muted); font-size: clamp(0.95rem, 2vw, 1.05rem); max-width: 760px; overflow-wrap: anywhere; }
.app-masthead { display: flex; align-items: end; justify-content: space-between; gap: 1rem; border-bottom: 1px solid var(--line); padding: 0.25rem 0 1.1rem; margin-bottom: 1.5rem; }
.app-brand { color: var(--ink); font-size: clamp(1.15rem, 3vw, 1.55rem); font-weight: 750; letter-spacing: 0.01em; }
.app-tagline { color: var(--muted); font-size: 0.82rem; text-align: right; }
.stMarkdown, .stCaption, [data-testid="stMetricValue"], [data-testid="stMetricLabel"] { overflow-wrap: anywhere; word-break: normal; }
.table-wrap { width: 100%; overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }
.clean-table { width: 100%; min-width: 420px; border-collapse: collapse; color: var(--ink); font-size: 0.92rem; }
.clean-table th { background: #e8f0ef; color: var(--ink); font-weight: 700; text-align: left; white-space: nowrap; }
.clean-table th, .clean-table td { padding: 0.72rem 0.85rem; border-bottom: 1px solid var(--line); vertical-align: top; }
.clean-table tbody tr:last-child td { border-bottom: 0; }
.clean-table tbody tr:nth-child(even) { background: #f8faf9; }
[data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--line); padding: 1rem; border-radius: 8px; box-shadow: 0 2px 8px rgba(23, 33, 43, 0.04); }
[data-testid="stMetricLabel"] { color: var(--muted); }
[data-testid="stAlert"] { border-radius: 8px; border-left-width: 4px; }
[data-testid="stAlert"] p, [data-testid="stAlert"] span { color: #17212b !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
.stDataFrame, [data-testid="stDataFrame"] > div { max-width: 100%; overflow-x: auto; }
.stTabs [data-baseweb="tab-list"] { gap: 0.25rem; overflow-x: auto; scrollbar-width: thin; }
.stTabs [data-baseweb="tab"] { white-space: nowrap; }
header[data-testid="stHeader"] [data-testid="stAppDeployButton"] { display: none; }
section[data-testid="stSidebar"] { background: #e8f0ef; border-right: 1px solid var(--line); }
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: var(--muted); }
button[kind="secondary"] { border-color: var(--line); }
footer { visibility: hidden; }
@media (max-width: 720px) {
    .block-container { width: calc(100% - 1rem); padding-left: 0.5rem; padding-right: 0.5rem; }
    h1 { font-size: 1.8rem !important; line-height: 1.12 !important; }
    h2, h3 { line-height: 1.2 !important; }
    .app-masthead { align-items: flex-start; flex-direction: column; gap: 0.25rem; }
    .app-tagline { text-align: left; }
    [data-testid="stMetric"] { padding: 0.75rem; }
    [data-testid="stMetricValue"] { font-size: 1.25rem; }
    .stButton button, .stDownloadButton button { width: 100%; }
    .clean-table { min-width: 390px; font-size: 0.84rem; }
    .clean-table th, .clean-table td { padding: 0.6rem; }
}
</style>
""", unsafe_allow_html=True)

if not MODEL_PATH.exists() or not RESULTS_PATH.exists():
    st.error("The trained SVM artifact or threshold record is missing.")
    st.stop()

st.markdown("""
<div class="app-masthead">
    <div class="app-brand">Synthetic Voice Forensics</div>
    <div class="app-tagline">Audio authenticity screening</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## SVF / Console")
    st.caption("Synthetic voice screening")
    page = st.radio("Navigate", ["Dashboard", "Live Check", "Robustness", "Evidence", "Methodology"], label_visibility="collapsed")
    st.divider()
    st.caption("Audio screening console")

if page == "Dashboard":
    render_dashboard()
elif page == "Live Check":
    render_live_check()
elif page == "Robustness":
    render_robustness()
elif page == "Evidence":
    render_evidence()
else:
    render_methodology()

st.markdown("---")
st.caption("Synthetic Voice Forensics  /  Additional verification signal only")