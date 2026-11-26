import pandas as pd
import streamlit as st

import ui

repo = ui.setup("Patient History", "📋")

patients = repo.list_patients()
if not patients:
    st.warning("No patients yet.")
    st.stop()

by_id = {p["patient_id"]: p for p in patients}
patient_id = st.selectbox(
    "Patient",
    list(by_id),
    format_func=lambda i: ui.patient_label(by_id[i]),
    key="history_patient",
)

history = repo.get_patient_history(patient_id)
if not history:
    st.info("This patient has no appointments yet.")
    st.stop()

counts = {s: sum(1 for a in history if a["status"] == s) for s in ("scheduled", "completed", "cancelled")}
m1, m2, m3 = st.columns(3)
m1.metric("Scheduled", counts["scheduled"])
m2.metric("Completed", counts["completed"])
m3.metric("Cancelled", counts["cancelled"])

wanted = st.multiselect(
    "Show statuses",
    options=list(counts),
    default=list(counts),
    key="history_status",
)
rows = [a for a in history if a["status"] in wanted]  # already newest first

if rows:
    ui.show_table(
        pd.DataFrame(
            [
                {
                    "Date": f"{a['appt_date']:%a %d %b %Y}",
                    "Time": ui.hhmm(a["slot_time"]),
                    "Doctor": a["doctor_name"],
                    "Reason": a["reason"],
                    "Status": ui.STATUS_LABELS.get(a["status"], a["status"]),
                }
                for a in rows
            ]
        )
    )
else:
    st.info("No appointment matches the selected statuses.")
