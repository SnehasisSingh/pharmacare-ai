"""Patient clinical case status, using the authenticated patient portal session."""
import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import requests,streamlit as st
from shared_login import login_widget
st.title('Clinical review status')
base=os.getenv('PHARMACARE_REVIEW_API_BASE_URL','https://882bi13uqb.execute-api.ap-southeast-2.amazonaws.com/Dev').rstrip('/')
with st.sidebar:token=login_widget(base,'patient')
if not token:st.stop()
case_id=st.text_input('Case ID',value=st.session_state.get('clinical_review_case_id',''))
if st.button('Check case status') and case_id:
    try:
        r=requests.get(base+'/cases/'+case_id,headers={'Authorization':'Bearer '+token},timeout=25)
        data=r.json()
        if not r.ok:st.error(data.get('error','Request failed'))
        else:
            st.write('Status:',data.get('status'))
            if data.get('status')=='APPROVED':st.markdown(data.get('approved_text',''))
            elif data.get('status')=='PENDING_REVIEW':st.info('Awaiting doctor review. No approved report is available.')
    except (requests.RequestException,ValueError):st.error('Unable to retrieve case')
