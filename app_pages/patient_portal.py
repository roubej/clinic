from datetime import date

import pandas as pd
import streamlit as st

import ui
from db import slots
from db.repository import ClinicError

repo = ui.setup("My patient portal", "👤", allowed_roles=("patient",))
ui.show_flash()
user = st.session_state["clinic_user"]
patient = repo.get_patient(user["identity_id"])
if patient is None:
    st.error("Your patient profile is unavailable. Contact the clinic administrator.")
    st.stop()

st.caption(f"Welcome, {patient['first_name']}. You can only access your own clinic records.")

tab_book, tab_appointments = st.tabs(["Book an appointment", "My appointments"])

with tab_book:
    doctors = repo.list_doctors()
    if not doctors:
        st.info("No doctors are available yet.")
    else:
        doctors_by_id = {doctor["doctor_id"]: doctor for doctor in doctors}
        doctor_id = st.selectbox(
            "Doctor",
            list(doctors_by_id),
            format_func=lambda value: ui.doctor_label(doctors_by_id[value]),
            key="patient_book_doctor",
        )
        doctor = doctors_by_id[doctor_id]
        day = st.date_input(
            "Date",
            value=date.today(),
            min_value=date.today(),
            key="patient_book_date",
        )
        if not slots.generate_slots(doctor, day):
            st.warning(f"{doctor['full_name']} does not work on {day:%A}.")
        else:
            free_slots = slots.free_slots(doctor, day, repo.get_agenda(doctor, day))
            if not free_slots:
                st.info("No free times on that date. Choose another date.")
            else:
                slot = st.selectbox(
                    "Time",
                    free_slots,
                    format_func=ui.hhmm,
                    key="patient_book_time",
                )
                reason = st.text_input("Reason for the visit", key="patient_book_reason")
                if st.button("Book appointment", type="primary", key="patient_book_submit"):
                    if not reason.strip():
                        st.error("Please enter a reason for the visit.")
                    else:
                        try:
                            repo.book_appointment(patient, doctor, day, slot, reason)
                        except ClinicError as exc:
                            st.error(str(exc))
                        else:
                            st.session_state.pop("patient_book_reason", None)
                            ui.flash("success", "Appointment booked.")
                            st.rerun()

with tab_appointments:
    history = repo.get_patient_history(patient["patient_id"])
    scheduled = [appt for appt in history if appt["status"] == "scheduled"]
    if scheduled:
        st.subheader("Upcoming appointments")
        for appt in scheduled:
            label = (
                f"{appt['appt_date']:%a %d %b %Y} {ui.hhmm(appt['slot_time'])} — "
                f"{appt['doctor_name']}: {appt['reason'] or 'No reason provided'}"
            )
            col1, col2 = st.columns([4, 1])
            col1.write(label)
            if col2.button("Cancel", key=f"patient_cancel_{appt['appointment_id']}"):
                try:
                    repo.cancel_appointment(appt)
                except ClinicError as exc:
                    st.error(str(exc))
                else:
                    ui.flash("success", "Appointment cancelled.")
                    st.rerun()
    else:
        st.info("You have no scheduled appointments.")

    if history:
        st.subheader("Appointment history")
        ui.show_table(
            pd.DataFrame(
                [
                    {
                        "Date": f"{appt['appt_date']:%a %d %b %Y}",
                        "Time": ui.hhmm(appt["slot_time"]),
                        "Doctor": appt["doctor_name"],
                        "Reason": appt["reason"],
                        "Status": ui.STATUS_LABELS.get(appt["status"], appt["status"]),
                    }
                    for appt in history
                ]
            )
        )
