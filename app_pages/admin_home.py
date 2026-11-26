from datetime import date

import pandas as pd
import streamlit as st

import ui

repo = ui.setup("Administrator overview", "🏥")
ui.show_flash()

today = date.today()
today_rows = [
    appt
    for appt in repo.get_appointments_range(today, today)
    if appt["status"] == "scheduled"
]

col1, col2, col3 = st.columns(3)
col1.metric("Patients", repo.count_patients())
col2.metric("Doctors", len(repo.list_doctors()))
col3.metric("Scheduled today", len(today_rows))

st.subheader("Today's appointments")
if today_rows:
    ui.show_table(
        pd.DataFrame(
            [
                {
                    "Time": ui.hhmm(appt["slot_time"]),
                    "Doctor": appt["doctor_name"],
                    "Patient": appt["patient_name"],
                    "Reason": appt["reason"],
                }
                for appt in today_rows
            ]
        )
    )
else:
    st.info("No scheduled appointments today.")

st.caption("Use the sidebar to manage clinic records and review the dashboard.")
