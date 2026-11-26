import streamlit as st

import ui
from db.repository import ClinicError
from db.security import password_error

repo = ui.setup(
    "Account security",
    "🔐",
    allowed_roles=("patient", "doctor", "admin"),
)
ui.show_flash()
username = st.session_state["clinic_user"]["username"]

with st.form("change_password_form"):
    current_password = st.text_input("Current password", type="password")
    new_password = st.text_input(
        "New password (12–128 characters)",
        type="password",
    )
    confirm_password = st.text_input("Confirm new password", type="password")
    submitted = st.form_submit_button("Change password", type="primary")

if submitted:
    password_problem = password_error(new_password)
    if password_problem:
        st.error(password_problem)
    elif new_password != confirm_password:
        st.error("New passwords do not match.")
    else:
        try:
            changed = repo.change_password(username, current_password, new_password)
        except ClinicError as exc:
            st.error(str(exc))
        else:
            if changed:
                st.success("Password changed.")
            else:
                st.error("Current password is incorrect.")
