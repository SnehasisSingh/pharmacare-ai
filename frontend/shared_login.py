
import requests
import streamlit as st


def login_widget(base, role):
    key = f"pharmacare_{role}_auth"
    session = st.session_state.get(key)

    # Check existing login session
    if session:
        token = session.get("token", "")

        try:
            response = requests.get(
                base.rstrip("/") + "/auth/me",
                headers={
                    "Authorization": f"Bearer {token}"
                },
                timeout=15
            )

            if response.ok:
                data = response.json()
                user = data.get("user", {})

                if user.get("role") == role:
                    st.success(
                        "Signed in: "
                        + user.get("username", "Unknown")
                    )

                    if st.button(
                        "Log out",
                        key=f"logout_{role}"
                    ):
                        st.session_state.pop(key, None)
                        st.rerun()

                    return token

                st.error(
                    "Access denied: incorrect account role."
                )

            elif response.status_code == 401:
                st.error(
                    "Your login session is invalid or expired. "
                    "Please sign in again."
                )

            else:
                st.error(
                    f"Session verification failed: "
                    f"HTTP {response.status_code}"
                )

        except requests.RequestException as exc:
            st.error(
                "Cannot connect to authentication API: "
                + type(exc).__name__
            )

        except ValueError:
            st.error(
                "Authentication API returned invalid JSON."
            )

        # Do not automatically delete the session.
        # Do not authorize requests with an unverified token.
        if st.button("Clear session and sign in again"):
            st.session_state.pop(key, None)
            st.rerun()

        return ""

    # Login form
    with st.form(f"login_{role}"):
        username = st.text_input(
            "Username",
            key=f"username_{role}"
        )

        password = st.text_input(
            "Password",
            type="password",
            key=f"password_{role}"
        )

        submit = st.form_submit_button("Sign in")

    if submit:
        try:
            response = requests.post(
                base.rstrip("/") + "/auth/login",
                json={
                    "username": username.strip(),
                    "password": password
                },
                timeout=20
            )

            data = response.json()

            if response.ok:
                user = data.get("user", {})
                token = data.get("token")

                if user.get("role") != role:
                    st.error(
                        "Incorrect role for this dashboard."
                    )

                elif not token:
                    st.error(
                        "Login succeeded but no token returned."
                    )

                else:
                    st.session_state[key] = data
                    st.rerun()

            else:
                st.error(
                    f"Login failed: HTTP "
                    f"{response.status_code} - "
                    f"{data.get('error', 'Unknown error')}"
                )

        except requests.RequestException as exc:
            st.error(
                "Login service unavailable: "
                + type(exc).__name__
            )

        except ValueError:
            st.error(
                "Login API returned invalid JSON."
            )

    return ""
