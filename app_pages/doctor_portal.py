from datetime import date, timedelta

import pandas as pd
import streamlit as st

import ui
from db.repository import ClinicError

repo = ui.setup("My doctor portal", "🩺", allowed_roles=("doctor",))
ui.show_flash()
user = st.session_state["clinic_user"]
doctor = repo.get_doctor(user["identity_id"])
if doctor is None:
    st.error("Your doctor profile is unavailable. Contact the clinic administrator.")
    st.stop()

st.caption(f"Welcome, {doctor['full_name']}. Patient details are limited to your appointments.")

day = st.date_input("Agenda date", value=date.today(), key="doctor_agenda_date")
appointments = repo.get_agenda(doctor, day)
if appointments:
    ui.show_table(
        pd.DataFrame(
            [
                {
                    "Time": ui.hhmm(appt["slot_time"]),
                    "Patient": appt["patient_name"],
                    "Reason": appt["reason"],
                    "Status": ui.STATUS_LABELS.get(appt["status"], appt["status"]),
                }
                for appt in appointments
            ]
        )
    )
    for appt in appointments:
        with st.expander(
            f"{ui.hhmm(appt['slot_time'])} — {appt['patient_name']}"
        ):
            patient = repo.get_patient(appt["patient_id"])
            if patient:
                st.write(f"Phone: {patient['phone']}")
                st.write(f"Email: {patient['email']}")
                st.write(f"Date of birth: {patient['date_of_birth']}")
                patient_history = [
                    item
                    for item in repo.get_patient_history(appt["patient_id"])
                    if item["doctor_id"] == doctor["doctor_id"]
                ]
                st.caption("History of appointments with you")
                if patient_history:
                    ui.show_table(
                        pd.DataFrame(
                            [
                                {
                                    "Date": f"{item['appt_date']:%a %d %b %Y}",
                                    "Time": ui.hhmm(item["slot_time"]),
                                    "Reason": item["reason"],
                                    "Status": ui.STATUS_LABELS.get(item["status"], item["status"]),
                                }
                                for item in patient_history
                            ]
                        )
                    )
            if appt["status"] == "scheduled" and st.button(
                "Mark completed",
                key=f"doctor_complete_{appt['appointment_id']}",
            ):
                try:
                    repo.complete_appointment(appt)
                except ClinicError as exc:
                    st.error(str(exc))
                else:
                    ui.flash("success", "Appointment marked completed.")
                    st.rerun()
else:
    st.info("No appointments for you on this date.")

st.subheader("Upcoming appointments")
upcoming = repo.get_appointments_range(
    date.today(), date.today() + timedelta(days=30), [doctor["doctor_id"]]
)
upcoming = [appt for appt in upcoming if appt["status"] == "scheduled"]
if upcoming:
    ui.show_table(
        pd.DataFrame(
            [
                {
                    "Date": f"{appt['appt_date']:%a %d %b %Y}",
                    "Time": ui.hhmm(appt["slot_time"]),
                    "Patient": appt["patient_name"],
                    "Reason": appt["reason"],
                }
                for appt in upcoming
            ]
        )
    )
else:
    st.info("No upcoming appointments.")
