import requests,streamlit as st

def login_widget(base,role):
    key='pharmacare_'+role+'_auth'
    session=st.session_state.get(key)
    if session:
        try:
            r=requests.get(base+'/auth/me',headers={'Authorization':'Bearer '+session['token']},timeout=15)
            if r.ok and r.json().get('user',{}).get('role')==role:
                st.success('Signed in: '+session['user']['username'])
                if st.button('Log out',key='logout_'+role):
                    st.session_state.pop(key,None);st.rerun()
                return session['token']
        except (requests.RequestException,ValueError):pass
        st.session_state.pop(key,None)
    with st.form('login_'+role):
        username=st.text_input('Username',key='username_'+role)
        password=st.text_input('Password',type='password',key='password_'+role)
        submit=st.form_submit_button('Sign in')
    if submit:
        try:
            r=requests.post(base+'/auth/login',json={'username':username,'password':password},timeout=20)
            data=r.json()
            if r.ok and data.get("user", {}).get("role") == role:
                st.session_state[key] = data
                st.rerun()
            elif r.ok:
                st.error("Incorrect role for this dashboard.")
            else:
                st.error(
                    f"Login failed: HTTP {r.status_code} - "
                    f"{data.get('error', 'Unknown error')}"
                )
        except (requests.RequestException,ValueError,KeyError):st.error('Login service unavailable')
    return ''
