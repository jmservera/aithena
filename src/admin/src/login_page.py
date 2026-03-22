"""Login page UI for the Aithena Admin Dashboard."""

from __future__ import annotations

import streamlit as st

from auth import AuthSettings, login


def render_login_page(settings: AuthSettings) -> None:
    """Render the login form."""
    st.set_page_config(page_title="Aithena Admin - Login", page_icon="\U0001f510", layout="centered")
    st.title("\U0001f510 Aithena Admin")
    st.caption("Sign in to access the admin dashboard.")

    with st.form("login_form"):
        username = st.text_input("Username", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)

    if submitted:
        if not username or not password:
            st.error("Please enter both username and password.")
            return
        user = login(username, password, settings)
        if user is None:
            st.error("Invalid username or password.")
            return
        st.rerun()
