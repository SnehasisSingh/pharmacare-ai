"""PharmaCare AI patient portal (synthetic-data educational prototype)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
import streamlit as st

DEFAULT_API_BASE = "https://882bi13uqb.execute-api.ap-southeast-2.amazonaws.com/Dev"
REVIEW_API_BASE = os.getenv("PHARMACARE_REVIEW_API_BASE_URL", os.getenv("PHARMACARE_API_BASE_URL", DEFAULT_API_BASE)).rstrip("/")
API_BASE = os.getenv("PHARMACARE_API_BASE_URL", DEFAULT_API_BASE).rstrip("/")
REQUEST_TIMEOUT = (10, 110)

st.set_page_config(page_title="PharmaCare AI | Patient Portal", page_icon="🩺", layout="wide")
st.markdown("""<style>
.block-container {max-width: 1100px; padding-top: 2rem;}
.hero {padding: 1.5rem 1.7rem; border-radius: 14px; background: linear-gradient(110deg,#113e64,#126c83);color:white;margin-bottom:1.2rem;}
.hero h1 {color:white;margin:0;font-size:2rem;}
.hero p {color:#e5f3fa;margin:.5rem 0 0;}
.smallnote {color:#5e6878;font-size:.86rem;}
</style>""", unsafe_allow_html=True)


def call_medical_api(question: str) -> dict:
    """Call existing backend without sending secrets or logging patient text."""
    try:
        res = requests.post(
            f"{API_BASE}/medical/ask",
            json={"question": question},
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise RuntimeError("The assessment request timed out. Please try again later.") from exc
    except requests.RequestException as exc:
        raise RuntimeError("Unable to reach the PharmaCare API. Check connectivity and deployment.") from exc
    if not res.ok:
        raise RuntimeError(f"Medical API returned HTTP {res.status_code}. Please check Lambda logs if this persists.")
    try:
        payload = res.json()
    except ValueError as exc:
        raise RuntimeError("The medical API returned an invalid JSON response.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("answer"), str) or not payload["answer"].strip():
        raise RuntimeError("The medical API did not return a usable assessment.")
    return payload


def submit_clinical_case(question: str, id_token: str) -> dict:
    """Submit synthetic scenario to authenticated clinical workflow.

    Current /cases backend independently regenerates the draft before storing it.
    This intentionally does NOT send the first /medical/ask answer as an approved report.
    """
    try:
        response = requests.post(
            f"{REVIEW_API_BASE}/cases",
            json={"question": question},
            headers={"Authorization": "Bearer " + id_token, "Content-Type": "application/json"},
            timeout=(10, 110),
        )
    except requests.RequestException as exc:
        raise RuntimeError("Clinical case submission failed to connect; check review API and Lambda logs.") from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(f"Clinical case API returned HTTP {response.status_code} with invalid JSON.") from exc
    if not response.ok:
        raise RuntimeError(f"Clinical case API returned HTTP {response.status_code}: {data.get('error', 'Request failed')}")
    if not data.get("case_id"):
        raise RuntimeError("Clinical case API returned no case_id; persistence is unconfirmed.")
    return data


def build_question(age, duration, symptoms, extra):
    lines = [
        "This is a fictional/synthetic patient scenario for an educational prototype.",
        f"Age: {age} years.",
        f"Symptom duration: {duration.strip()}.",
        f"Symptoms and concerns: {symptoms.strip()}.",
    ]
    if extra.strip():
        lines.append(f"Additional context: {extra.strip()}.")
    lines.append(
        "Using the retrieved medical references, explain possible causes without diagnosing, "
        "state uncertainty, identify urgent warning signs, advise when to seek clinical care, "
        "and cite the source documents. Do not prescribe medication or dosage."
    )
    return "\n".join(lines)


def draft_report(result, age, duration, symptoms):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sources = result.get("sources") or []
    refs = "\n".join(
        f"- {s.get('source', 'Unknown source')} — page {s.get('page', 'N/A')}"
        for s in sources if isinstance(s, dict)
    ) or "- No sources returned"
    return (
        "# PharmaCare AI — Unreviewed Educational Draft\n\n"
        "**NOT A PRESCRIPTION OR MEDICAL DIAGNOSIS. NOT REVIEWED BY A DOCTOR.**\n\n"
        f"Generated: {now}\n\n"
        f"Synthetic patient age: {age}\n\n"
        f"Symptom duration: {duration}\n\n"
        f"Reported symptoms: {symptoms}\n\n"
        "## AI-generated information\n\n"
        f"{result['answer']}\n\n"
        "## Retrieved references\n\n"
        f"{refs}\n\n"
        "---\nThis document is for educational testing with synthetic data only. "
        "It is not clinically validated and must not be used to make treatment decisions.\n"
    )


st.markdown('<div class="hero"><h1>🩺 PharmaCare AI</h1><p>Medical knowledge assistant · Patient prototype</p></div>', unsafe_allow_html=True)
st.warning("**Educational demo only.** Use fictional patient scenarios. This system is not validated for clinical use, does not diagnose or prescribe; any doctor-review workflow is a synthetic-data prototype.")
st.error("**Emergency warning:** For severe breathing problems, chest pain, confusion, seizures, or other immediately dangerous symptoms, seek emergency medical care now. Do not wait for an AI assessment.")

with st.sidebar:
    st.header("System")
    st.caption("Streamlit → API Gateway → Lambda → Qdrant + Claude")
    if st.button("Check backend health", use_container_width=True):
        try:
            r = requests.get(f"{API_BASE}/health", timeout=(5, 10))
            r.raise_for_status()
            status = r.json().get("status", "unknown")
            st.success(f"API status: {status}")
        except (requests.RequestException, ValueError):
            st.error("Backend health check failed.")
    st.divider()
    from shared_login import login_widget
    patient_token = login_widget(REVIEW_API_BASE, 'patient')
    st.caption('Cases are saved automatically when signed in as a patient.')
    st.divider()
    st.caption("Phase 1: Patient intake + educational RAG answer")
    st.caption("Phase 2: Doctor approval, authentication and case persistence")

left, right = st.columns([1.1, 0.9], gap="large")
with left:
    st.subheader("Patient symptom intake")
    with st.form("patient_intake", clear_on_submit=False):
        age = st.number_input("Age (fictional patient)", min_value=1, max_value=120, value=28, step=1)
        duration = st.text_input("How long have the symptoms lasted?", placeholder="e.g., 3 days")
        symptoms = st.text_area("Describe symptoms and concerns", height=160, placeholder="e.g., Fever, headache, body pain and weakness")
        extra = st.text_area("Additional relevant context (optional)", height=100, placeholder="e.g., Recent travel or known exposure (fictional details only)")
        consent = st.checkbox("I confirm this is synthetic test information, not real patient data.")
        submitted = st.form_submit_button("Generate educational assessment", type="primary", use_container_width=True)

    if submitted:
        if not consent:
            st.error("Please confirm that your scenario uses synthetic data.")
        elif not duration.strip() or not symptoms.strip():
            st.error("Please enter symptom duration and symptoms.")
        elif len(symptoms.strip()) < 10:
            st.error("Please provide a little more detail about the symptoms.")
        else:
            question = build_question(age, duration, symptoms, extra)
            st.session_state.pop("clinical_review_case_id", None)
            st.session_state.pop("clinical_review_status", None)
            with st.spinner("Retrieving medical references and requesting Claude assessment…"):
                try:
                    result = call_medical_api(question)
                except RuntimeError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["latest_assessment"] = {
                        "result": result, "age": age, "duration": duration, "symptoms": symptoms
                    }
                    st.success("Educational assessment generated.")
                    # One submission per explicit Generate click, never on Streamlit reruns.
                    if not patient_token.strip():
                        st.warning("Assessment generated, but NOT saved to DynamoDB. Log in as a patient in the sidebar and generate again to auto-submit.")
                    else:
                        with st.spinner("Submitting case for doctor review (backend creates its own draft)…"):
                            try:
                                saved = submit_clinical_case(question, patient_token.strip())
                            except RuntimeError as exc:
                                st.error(f"Assessment generated, but clinical case was NOT confirmed saved: {exc}")
                            else:
                                st.session_state["clinical_review_case_id"] = saved["case_id"]
                                st.session_state["clinical_review_status"] = saved.get("status", "PENDING_REVIEW")
                                st.success(f"Clinical case saved. Case ID: {saved['case_id']}")
                                st.info("Awaiting doctor review. The generated assessment is not an approved report.")
                                if saved.get("emergency_warning"):
                                    st.error("Emergency symptoms flagged: seek immediate emergency care for real emergencies; do not wait for review.")

with right:
    st.subheader("AI assessment")
    latest = st.session_state.get("latest_assessment")
    if latest:
        if st.session_state.get("clinical_review_case_id"):
            st.info(f"Clinical case: {st.session_state['clinical_review_case_id']} · {st.session_state.get('clinical_review_status', 'PENDING_REVIEW')}")
        result = latest["result"]
        st.info("**Status: AI draft — not doctor reviewed or approved.**")
        st.markdown(result["answer"])
        st.divider()
        st.markdown("#### Retrieved document references")
        sources = result.get("sources") or []
        if sources:
            for idx, source in enumerate(sources, 1):
                if isinstance(source, dict):
                    st.write(f"{idx}. **{source.get('source', 'Unknown source')}** — page {source.get('page', 'N/A')}")
        else:
            st.caption("No source references were returned.")
        report = draft_report(result, latest["age"], latest["duration"], latest["symptoms"])
        st.download_button(
            "Download unreviewed draft (.md)", data=report,
            file_name="pharmacare_unreviewed_draft.md", mime="text/markdown",
            use_container_width=True,
        )
    else:
        st.caption("Complete the fictional patient form and submit it to see a source-grounded assessment.")

st.divider()
st.caption("PharmaCare AI • Prototype • The medical reference corpus is synthetic and not clinically validated.")
