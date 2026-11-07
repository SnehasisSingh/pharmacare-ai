import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import requests,streamlit as st
from shared_login import login_widget
st.set_page_config(page_title='PharmaCare Admin',layout='wide')
base=os.getenv('PHARMACARE_REVIEW_API_BASE_URL','https://882bi13uqb.execute-api.ap-southeast-2.amazonaws.com/Dev').rstrip('/')
st.title('PharmaCare AI — User Administration')
st.warning('Synthetic test accounts only. Administrator access required.')
with st.sidebar:token=login_widget(base,'admin')
if not token:st.stop()
def api(method,path,**kwargs):
    try:
        r=requests.request(method,base+path,headers={'Authorization':'Bearer '+token},timeout=90,**kwargs)
        data=r.json()
        if not r.ok:st.error(f"HTTP {r.status_code}: {data.get('error','Request failed')}");return None
        return data
    except (requests.RequestException,ValueError):st.error('API unavailable');return None
create_tab,users_tab,sync_tab=st.tabs(['Create account','Manage users','Restore OpenSearch'])
with create_tab:
    with st.form('create_user'):
        role=st.selectbox('Role',['patient','doctor'])
        username=st.text_input('Username')
        full_name=st.text_input('Full name')
        email=st.text_input('Email (optional)')
        password=st.text_input('Initial password (12+ characters)',type='password')
        submitted=st.form_submit_button('Create account')
    if submitted:
        result=api('POST','/admin/users',json={'role':role,'username':username,'full_name':full_name,'email':email,'password':password})
        if result:st.success('Account created in DynamoDB. OpenSearch sync attempted.')
with users_tab:
    if st.button('Refresh users') or 'users' not in st.session_state:
        result=api('GET','/admin/users')
        if result:st.session_state.users=result['users']
    users=st.session_state.get('users',[])
    st.dataframe(users,use_container_width=True)
    if users:
        choices={u['username']+' ('+u['role']+')':u for u in users}
        selected=st.selectbox('Account to update',list(choices))
        current=choices[selected]
        with st.form('edit'):
            full_name=st.text_input('Full name',value=current['full_name'])
            email=st.text_input('Email',value=current.get('email',''))
            active=st.checkbox('Active',value=current['active'])
            new_password=st.text_input('New password (leave blank to keep)',type='password')
            save=st.form_submit_button('Save changes')
        if save:
            data={'full_name':full_name,'email':email,'active':active}
            if new_password:data['password']=new_password
            if api('PATCH','/admin/users/'+current['user_id'],json=data):
                st.session_state.pop('users',None);st.success('Updated')
with sync_tab:
    st.write('Rebuilds the searchable user index from DynamoDB. Existing DynamoDB records remain unchanged.')
    confirm=st.checkbox('I understand this replaces the OpenSearch user index.')
    if st.button('Rebuild index',disabled=not confirm):
        result=api('POST','/admin/opensearch/rebuild')
        if result:st.success(f"Indexed {result['indexed']} user profiles")
