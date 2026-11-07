"""Public synthetic-data educational demo; intentionally no login."""
import os
import requests
import streamlit as st

BASE = os.getenv('PHARMACARE_API_BASE_URL', 'https://882bi13uqb.execute-api.ap-southeast-2.amazonaws.com/Dev').rstrip('/')
st.set_page_config(page_title='PharmaCare AI | Patient Demo', page_icon='🩺', layout='wide')
st.title('🩺 PharmaCare AI — Patient Demo')
st.warning('PUBLIC SYNTHETIC DEMO ONLY. Do not enter real names, contact details, or health information. AI output and review are not clinical advice.')
st.error('For dangerous symptoms seek emergency medical help immediately; never wait for a demo review.')

def api(method, path, **kwargs):
    try:
        r = requests.request(method, BASE + path, timeout=(10, 110), **kwargs)
        try:
            payload = r.json()
        except ValueError:
            raise RuntimeError(f'API HTTP {r.status_code} returned invalid JSON')
        if not r.ok:
            raise RuntimeError(f'API HTTP {r.status_code}: {payload.get("error", "Request failed")}')
        return payload
    except requests.RequestException as exc:
        raise RuntimeError(f'Cannot reach API: {type(exc).__name__}') from exc

with st.form('intake'):
    age = st.number_input('Fictional age', min_value=1, max_value=120, value=28)
    duration = st.text_input('Symptom duration', placeholder='e.g. 2 days')
    symptoms = st.text_area('Fictional symptoms', height=140)
    extra = st.text_area('Other fictional context (optional)')
    synthetic = st.checkbox('I confirm that this scenario contains synthetic test data only')
    submitted = st.form_submit_button('Generate assessment and save case', type='primary')

if submitted:
    if not synthetic:
        st.error('Confirm synthetic test data first.')
    elif not duration.strip() or len(symptoms.strip()) < 10:
        st.error('Enter symptom duration and at least 10 characters of fictional symptoms.')
    else:
        question = '\n'.join([
            'Fictional/synthetic medical education scenario; not a real patient.',
            f'Age: {age}. Duration: {duration.strip()}.',
            f'Symptoms: {symptoms.strip()}.',
            f'Other context: {extra.strip()}.',
            'Using retrieved references, explain possibilities and uncertainty, urgent warning signs and when to seek care. Do not diagnose or prescribe doses.',
        ])
        if len(question) > 3000:
            st.error('Input is too long (maximum 3000 characters after formatting).')
        else:
            with st.spinner('Generating one AI draft and saving it to DynamoDB…'):
                try:
                    result = api('POST', '/cases', json={'question': question, 'synthetic_only': True})
                except RuntimeError as exc:
                    st.error(str(exc))
                else:
                    st.session_state['case_id'] = result['case_id']
                    st.session_state['draft'] = result['draft_answer']
                    st.session_state['sources'] = result.get('sources', [])
                    st.success('Case saved to DynamoDB: ' + result['case_id'])
                    st.info('PENDING_REVIEW — unreviewed AI-generated educational draft')
                    if result.get('emergency_warning'):
                        st.error(result['safety_message'])

if st.session_state.get('draft'):
    st.subheader('Unreviewed AI draft')
    st.markdown(st.session_state['draft'])
    with st.expander('Sources'):
        st.json(st.session_state.get('sources', []))

st.divider()
st.subheader('Look up a synthetic case')
case_id = st.text_input('Case ID', value=st.session_state.get('case_id', ''))
if st.button('Refresh case status'):
    if not case_id.strip():
        st.error('Enter a case ID.')
    else:
        try:
            record = api('GET', '/cases/' + case_id.strip())
        except RuntimeError as exc:
            st.error(str(exc))
        else:
            st.write('Status:', record.get('status'))
            if record.get('status') == 'APPROVED':
                st.info('Demo approval only — not verified clinician approval.')
                st.markdown(record.get('approved_text', ''))
            elif record.get('status') == 'REJECTED':
                st.warning('Demo review rejected this case.')
            else:
                st.info('Pending demo review.')
