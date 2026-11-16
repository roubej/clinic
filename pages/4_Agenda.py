from datetime import date

import pandas as pd
import streamlit as st

import ui
from db import slots

repo = ui.setup("Agenda", "🗓️")

doctors = repo.list_doctors()
if not doctors:
    st.warning("Add a doctor first.")
    st.stop()

doctors_by_id = {d["doctor_id"]: d for d in doctors}

tab_day, tab_upcoming = st.tabs(["Doctor's day", "Upcoming appointments"])

# ----------------------------------------------------------- doctor's day
with tab_day:
    c1, c2 = st.columns(2)
    doctor_id = c1.selectbox(
        "Doctor",
        list(doctors_by_id),
        format_func=lambda i: ui.doctor_label(doctors_by_id[i]),
        key="agenda_doctor",
    )
    day = c2.date_input("Date", value=date.today(), key="agenda_date")
    doctor = doctors_by_id[doctor_id]

    rows_by_time = {a["slot_time"]: a for a in repo.get_agenda(doctor, day)}
    all_times = sorted(set(slots.generate_slots(doctor, day)) | set(rows_by_time))

    if not all_times:
        st.info(f"{doctor['full_name']} does not work on {day:%A}.")
    else:
        table = []
        for t in all_times:
            a = rows_by_time.get(t)
            if a is None:
                table.append({"Time": ui.hhmm(t), "Status": "🟢 free", "Patient": "", "Reason": ""})
            else:
                table.append(
                    {
                        "Time": ui.hhmm(t),
                        "Status": ui.STATUS_LABELS.get(a["status"], a["status"]),
                        "Patient": a["patient_name"],
                        "Reason": a["reason"],
                    }
                )
        booked = sum(1 for a in rows_by_time.values() if a["status"] in ("scheduled", "completed"))
        free_count = len(all_times) - booked
        m1, m2, m3 = st.columns(3)
        m1.metric("Slots", len(all_times))
        m2.metric("Booked", booked)
        m3.metric("Free", free_count)
        ui.show_table(pd.DataFrame(table))
        st.caption("Cancelled slots can be booked again.")

# -------------------------------------------------------------- upcoming
with tab_upcoming:
    u1, u2 = st.columns(2)
    days_ahead = u1.slider("Days ahead", min_value=1, max_value=60, value=14, key="upcoming_days")
    doctor_filter = u2.selectbox(
        "Doctor",
        [None] + list(doctors_by_id),
        format_func=lambda i: "All doctors" if i is None else ui.doctor_label(doctors_by_id[i]),
        key="upcoming_doctor",
    )
    upcoming = repo.get_upcoming(days_ahead, doctor_filter)
    st.caption(f"{len(upcoming)} scheduled appointment(s) in the next {days_ahead} day(s).")
    if upcoming:
        ui.show_table(
            pd.DataFrame(
                [
                    {
                        "Date": f"{a['appt_date']:%a %d %b %Y}",
                        "Time": ui.hhmm(a["slot_time"]),
                        "Doctor": a["doctor_name"],
                        "Patient": a["patient_name"],
                        "Reason": a["reason"],
                    }
                    for a in upcoming
                ]
            )
        )
    else:
        st.info("Nothing scheduled in this period.")
