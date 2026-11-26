"""Role-based entry point for the clinic portals."""
from __future__ import annotations

import streamlit as st

import auth_ui
import ui

st.set_page_config(page_title="Clinic appointments", page_icon="🏥", layout="wide")

try:
    repo = ui.get_repository()
except Exception as exc:
    st.error(
        "Cannot reach Cassandra. Start the three-node cluster with "
        "`docker compose up -d --build` and wait for it to become healthy."
    )
    st.caption(f"Technical details: {exc}")
    st.stop()

user = st.session_state.get("clinic_user")
if user:
    current_account = repo.get_account(user["username"])
    if (
        current_account is None
        or not current_account["enabled"]
        or current_account["identity_id"] != user["identity_id"]
    ):
        st.session_state.pop("clinic_user", None)
    else:
        st.session_state["clinic_user"] = current_account

user = st.session_state.get("clinic_user")
if user is None:
    auth_ui.render_sign_in(repo)
    st.stop()

auth_ui.render_account_sidebar()

if user["role"] == "patient":
    pages = [
        st.Page(
            "app_pages/patient_portal.py",
            title="My patient portal",
            icon=":material/person:",
            help="Book appointments and view or cancel your own appointments.",
        )
    ]
elif user["role"] == "doctor":
    pages = [
        st.Page(
            "app_pages/doctor_portal.py",
            title="My doctor portal",
            icon=":material/medical_services:",
            help="View your agenda and patient details linked to your appointments.",
        )
    ]
else:
    pages = [
        st.Page(
            "app_pages/admin_home.py",
            title="Overview",
            icon=":material/dashboard:",
            help="Clinic-wide appointment and patient overview for administrators.",
        ),
        st.Page(
            "app_pages/1_Patients.py",
            title="Patients",
            icon=":material/group:",
            help="Search, add, update, and manage patient profiles and portal access.",
        ),
        st.Page(
            "app_pages/2_Doctors.py",
            title="Doctors",
            icon=":material/medical_services:",
            help="Manage doctors, schedules, and doctor portal accounts.",
        ),
        st.Page(
            "app_pages/3_Appointments.py",
            title="Appointments",
            icon=":material/event:",
            help="Manage clinic appointments across patients and doctors.",
        ),
        st.Page(
            "app_pages/4_Agenda.py",
            title="Agenda",
            icon=":material/calendar_month:",
            help="Review any doctor's daily schedule and upcoming appointments.",
        ),
        st.Page(
            "app_pages/5_Patient_History.py",
            title="Patient history",
            icon=":material/history:",
            help="Review appointment history for any patient.",
        ),
        st.Page(
            "app_pages/6_Dashboard.py",
            title="Dashboard",
            icon=":material/analytics:",
            help="Analyze clinic appointments by date, doctor, and status.",
        ),
    ]

pages.append(
    st.Page(
        "app_pages/account.py",
        title="Account",
        icon=":material/lock:",
        help="Change the password for your clinic portal account.",
    )
)

page = st.navigation(pages, position="sidebar")
page.run()
