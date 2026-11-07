"""Doctor review prototype using PharmaCare custom login."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os
import requests
import streamlit as st

st.set_page_config(page_title='PharmaCare | Clinical Review', page_icon='🩺', layout='wide')
st.title('PharmaCare AI · Clinical Review')
st.caption('Authenticated prototype · doctor approval required before patient release')
base = os.getenv('PHARMACARE_REVIEW_API_BASE_URL', 'https://882bi13uqb.execute-api.ap-southeast-2.amazonaws.com/Dev').rstrip('/')
if not base:
    st.error('Set PHARMACARE_REVIEW_API_BASE_URL before launching this dashboard.')
    st.stop()
if not base.startswith('https://'):
    st.error('The review API must use HTTPS.')
    st.stop()
with st.sidebar:
    from shared_login import login_widget
    token = login_widget(base, 'doctor')
if not token:
    st.info('Sign in as a doctor to review cases.')
    st.stop()

def api(method, path, **kwargs):
    try:
        response = requests.request(method, base + path, headers={'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'}, timeout=35, **kwargs)
        if response.status_code >= 400:
            st.error(f'API error {response.status_code}: {response.json().get("error", "Request failed")}')
            return None
        return response.json()
    except (requests.RequestException, ValueError):
        st.error('Could not contact the review API.')
        return None

if st.button('Refresh pending cases') or 'pending_cases' not in st.session_state:
    result = api('GET', '/doctor/cases')
    if result is not None:
        st.session_state.pending_cases = result.get('cases', [])

cases = st.session_state.get('pending_cases', [])
if not cases:
    st.info('No pending cases found (or the list has not loaded).')
    st.stop()
options = {f"{c['created_at']} · {c['case_id']}": c['case_id'] for c in cases}
selected = st.selectbox('Pending case', list(options))
case = api('GET', '/cases/' + options[selected])
if not case:
    st.stop()
st.subheader('Patient-submitted narrative')
st.write(case.get('question', ''))
if case.get('emergency_warning'):
    st.warning('Potential emergency language detected. This heuristic is not clinical triage. Escalate according to your clinical protocol.')
st.subheader('AI draft — NOT approved')
st.markdown(case.get('draft_answer', ''))
with st.expander('Retrieved PDF sources'):
    st.json(case.get('sources', []))
with st.form('decision'):
    reviewed = st.text_area('Clinician-reviewed final text', value=case.get('draft_answer', ''), height=300)
    decision = st.radio('Decision', ['approve', 'reject'], horizontal=True)
    confirmed = st.checkbox('I am an authorized clinician and have independently reviewed the content.')
    submitted = st.form_submit_button('Submit decision')
if submitted:
    if not confirmed:
        st.warning('Clinical review confirmation is required.')
    else:
        result = api('POST', '/doctor/cases/' + case['case_id'], json={'decision': decision, 'version': case['version'], 'approved_text': reviewed if decision == 'approve' else ''})
        if result:
            st.success('Decision saved: ' + result['status'])
            st.session_state.pop('pending_cases', None)
            st.rerun()
