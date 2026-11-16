"""Home page. Run with:  streamlit run app.py"""
from datetime import date

import pandas as pd
import streamlit as st

import ui

repo = ui.setup("Clinic Appointments", "🏥")
st.caption("Patients, doctors and appointments, stored in Apache Cassandra.")

today = date.today()
today_rows = [a for a in repo.get_appointments_range(today, today) if a["status"] == "scheduled"]

col1, col2, col3 = st.columns(3)
col1.metric("Patients", repo.count_patients())
col2.metric("Doctors", len(repo.list_doctors()))
col3.metric("Scheduled today", len(today_rows))

st.subheader("Today")
if today_rows:
    ui.show_table(
        pd.DataFrame(
            [
                {
                    "Time": ui.hhmm(a["slot_time"]),
                    "Doctor": a["doctor_name"],
                    "Patient": a["patient_name"],
                    "Reason": a["reason"],
                }
                for a in today_rows
            ]
        )
    )
else:
    st.info("No scheduled appointments today.")

st.subheader("Where to go")
st.markdown(
    """
- **Patients**: add, search, edit or delete patients.
- **Doctors**: set working days, hours and slot length.
- **Appointments**: book, cancel, complete or reschedule.
- **Agenda**: a doctor's day, and the upcoming appointments of the whole clinic.
- **Patient History**: every appointment of one patient.
- **Dashboard**: counts per day, per doctor and per status.
"""
)
