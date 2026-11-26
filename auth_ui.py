"""Local sign-in and patient self-registration."""
from __future__ import annotations

from datetime import date

import streamlit as st

from db.repository import ClinicError
from db.security import password_error
from db.validators import normalize_phone, validate_patient


def render_sign_in(repo) -> None:
    st.title("Clinic appointments")
    st.caption("Sign in to your patient, doctor, or administrator portal.")
    login_tab, signup_tab = st.tabs(["Sign in", "Patient sign up"])

    with login_tab:
        with st.form("sign_in_form"):
            username = st.text_input("Email or username", key="signin_username")
            password = st.text_input("Password", type="password", key="signin_password")
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            account = repo.authenticate(username, password)
            if account is None:
                st.error("Sign-in failed. Check your username and password.")
            else:
                st.session_state["clinic_user"] = account
                st.rerun()

    with signup_tab:
        st.info(
            "Patient sign-up creates a new profile. Existing profiles must have "
            "portal access created by an administrator."
        )
        with st.form("patient_signup_form"):
            first_name = st.text_input("First name", key="signup_first")
            last_name = st.text_input("Last name", key="signup_last")
            phone = st.text_input("Phone", placeholder="+216 20 123 456", key="signup_phone")
            email = st.text_input("Email (used to sign in)", key="signup_email")
            birth_date = st.date_input(
                "Date of birth",
                value=date(1990, 1, 1),
                min_value=date(1900, 1, 1),
                max_value=date.today(),
                key="signup_birth_date",
            )
            new_password = st.text_input(
                "Password (12–128 characters)",
                type="password",
                key="signup_password",
            )
            confirm_password = st.text_input(
                "Confirm password",
                type="password",
                key="signup_password_confirm",
            )
            submitted = st.form_submit_button("Create patient account", type="primary")

        if submitted:
            errors = validate_patient(
                first_name, last_name, phone, email, birth_date
            )
            password_problem = password_error(new_password)
            if password_problem:
                errors.append(password_problem)
            if new_password != confirm_password:
                errors.append("Passwords do not match.")

            if errors:
                for message in errors:
                    st.error(message)
            else:
                try:
                    repo.register_patient(
                        first_name.strip(),
                        last_name.strip(),
                        normalize_phone(phone),
                        email.strip(),
                        birth_date,
                        new_password,
                    )
                except ClinicError as exc:
                    st.error(str(exc))
                else:
                    account = repo.authenticate(email, new_password)
                    if account is None:
                        st.error("Account created, but automatic sign-in failed. Please sign in.")
                    else:
                        st.session_state["clinic_user"] = account
                        st.rerun()


def render_account_sidebar() -> None:
    user = st.session_state["clinic_user"]
    with st.sidebar:
        st.caption(f"Signed in as **{user['username']}**")
        st.caption(f"Role: {user['role'].capitalize()}")
        if st.button("Sign out", key="sign_out"):
            st.session_state.pop("clinic_user", None)
            st.rerun()
