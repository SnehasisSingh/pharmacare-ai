"""Public synthetic case review demo; any visitor can submit a decision."""
import os
import requests
import streamlit as st

BASE = os.getenv('PHARMACARE_REVIEW_API_BASE_URL', os.getenv('PHARMACARE_API_BASE_URL', 'https://882bi13uqb.execute-api.ap-southeast-2.amazonaws.com/Dev')).rstrip('/')
st.set_page_config(page_title='PharmaCare AI | Review Demo', page_icon='🩺', layout='wide')
st.title('🩺 PharmaCare AI — Review Demo')
st.warning('PUBLIC SYNTHETIC DEMO. No doctor identity is verified. Anyone with access can approve or reject a synthetic case. Never use for actual clinical decisions.')

def api(method, path, **kwargs):
    try:
        r = requests.request(method, BASE + path, timeout=(10, 40), **kwargs)
        try:
            data = r.json()
        except ValueError:
            raise RuntimeError(f'HTTP {r.status_code}: invalid JSON')
        if not r.ok:
            raise RuntimeError(f'HTTP {r.status_code}: {data.get("error", "Request failed")}')
        return data
    except requests.RequestException as exc:
        raise RuntimeError(f'API unavailable: {type(exc).__name__}') from exc

if st.button('Refresh pending cases') or 'pending_cases' not in st.session_state:
    try:
        st.session_state['pending_cases'] = api('GET', '/doctor/cases').get('cases', [])
    except RuntimeError as exc:
        st.error(str(exc))

cases = st.session_state.get('pending_cases', [])
if not cases:
    st.info('No pending cases. Submit a synthetic case in the Patient Demo first.')
else:
    options = {f"{c['created_at']} · {c['case_id']}": c['case_id'] for c in cases}
    chosen = st.selectbox('Select pending case', list(options))
    try:
        case = api('GET', '/cases/' + options[chosen])
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()
    st.subheader('Synthetic scenario')
    st.write(case.get('question', ''))
    st.subheader('Unreviewed AI draft')
    st.markdown(case.get('draft_answer', ''))
    with st.expander('Sources'):
        st.json(case.get('sources', []))
    with st.form('decision'):
        edited = st.text_area('Final demo text', value=case.get('draft_answer', ''), height=240)
        decision = st.radio('Demo decision', ['approve', 'reject'], horizontal=True)
        submitted = st.form_submit_button('Save demo decision')
    if submitted:
        try:
            result = api('POST', '/doctor/cases/' + case['case_id'], json={
                'decision': decision,
                'version': int(case['version']),
                'approved_text': edited if decision == 'approve' else '',
            })
        except RuntimeError as exc:
            st.error(str(exc))
        else:
            st.success('Saved: ' + result['status'] + ' (public demo decision, not verified clinician approval)')
            st.session_state.pop('pending_cases', None)
            st.rerun()
