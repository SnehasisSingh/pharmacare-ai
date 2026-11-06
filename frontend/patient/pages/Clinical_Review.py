"""Optional clinical review patient case submission and approved-result view."""
import os
import requests
import streamlit as st

st.title('Clinical review request · Prototype')
st.warning('Synthetic educational cases only. This is not an emergency or clinical care service.')
base = os.getenv('PHARMACARE_REVIEW_API_BASE_URL', '').rstrip('/')
if not base or not base.startswith('https://'):
    st.error('Set PHARMACARE_REVIEW_API_BASE_URL to your clinical review HTTPS API URL.')
    st.stop()
token = st.text_input('Cognito patient ID token', type='password')

def call(method, path, **kwargs):
    try:
        r = requests.request(method, base + path, headers={'Authorization': token, 'Content-Type': 'application/json'}, timeout=35, **kwargs)
        data = r.json()
        if r.status_code >= 400:
            st.error(data.get('error', f'HTTP {r.status_code}'))
            return None
        return data
    except (requests.RequestException, ValueError):
        st.error('Request failed. Check the API and connectivity.')
        return None

with st.form('case'):
    question = st.text_area('Fictional symptoms and relevant context', max_chars=3000)
    synthetic = st.checkbox('I confirm this is synthetic test information, not a real patient record.')
    submitted = st.form_submit_button('Request doctor review')
if submitted:
    if not token or not synthetic or len(question.strip()) < 10:
        st.error('Provide a token, a synthetic scenario (at least 10 characters), and confirmation.')
    else:
        result = call('POST', '/cases', json={'question': question})
        if result:
            st.session_state['clinical_review_case_id'] = result['case_id']
            st.success('Submitted. Case ID: ' + result['case_id'])
            st.info(result['safety_message'])
            if result['emergency_warning']:
                st.error('Potential emergency symptoms mentioned. Seek emergency help immediately for real emergencies; do not wait for review.')
st.divider()
case_id = st.text_input('Case ID to check', value=st.session_state.get('clinical_review_case_id', ''))
if st.button('Check review status') and token and case_id:
    result = call('GET', '/cases/' + case_id.strip())
    if result:
        st.write('Status:', result['status'])
        if result['status'] == 'APPROVED':
            st.markdown(result.get('approved_text', ''))
            st.caption('Clinician-reviewed educational text. Verify clinician credentials and clinical applicability independently.')
            st.json(result.get('sources', []))
        elif result['status'] == 'REJECTED':
            st.info('The doctor did not approve this draft. No assessment has been released.')
        else:
            st.info('Awaiting doctor review. Unapproved content is not available.')
