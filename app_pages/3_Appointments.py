from datetime import date

import streamlit as st

import ui
from db import slots
from db.repository import ClinicError

repo = ui.setup("Appointments", "📅")
ui.show_flash()

patients = repo.list_patients()
doctors = repo.list_doctors()
if not patients or not doctors:
    st.warning("Add at least one patient and one doctor before booking appointments.")
    st.stop()

patients_by_id = {p["patient_id"]: p for p in patients}
doctors_by_id = {d["doctor_id"]: d for d in doctors}


def patient_option(pid):
    return ui.patient_label(patients_by_id[pid])


def doctor_option(did):
    return ui.doctor_label(doctors_by_id[did])


def describe(appt: dict) -> str:
    return (
        f"{appt['appt_date']:%a %d %b %Y} {ui.hhmm(appt['slot_time'])}, "
        f"{appt['doctor_name']}, {appt['reason'] or 'no reason given'}"
    )


tab_book, tab_manage = st.tabs(["Book", "Cancel, complete or reschedule"])

# ---------------------------------------------------------------- book
with tab_book:
    c1, c2, c3 = st.columns(3)
    patient_id = c1.selectbox("Patient", list(patients_by_id), format_func=patient_option, key="book_patient")
    doctor_id = c2.selectbox("Doctor", list(doctors_by_id), format_func=doctor_option, key="book_doctor")
    day = c3.date_input("Date", value=date.today(), min_value=date.today(), key="book_date")

    doctor = doctors_by_id[doctor_id]
    if not slots.generate_slots(doctor, day):
        st.warning(f"{doctor['full_name']} does not work on {day:%A}.")
    else:
        free = slots.free_slots(doctor, day, repo.get_agenda(doctor, day))
        if not free:
            st.warning("No free slot left on this day. Try another date.")
        else:
            st.caption(f"{len(free)} free slot(s) on {day:%A %d %B}.")
            slot = st.selectbox("Time slot", free, format_func=ui.hhmm, key="book_slot")
            reason = st.text_input("Reason for the visit", key="book_reason")
            if st.button("Book appointment", type="primary", key="book_button"):
                if not reason.strip():
                    st.error("Please enter a reason for the visit.")
                else:
                    try:
                        appt = repo.book_appointment(
                            patients_by_id[patient_id], doctor, day, slot, reason
                        )
                    except ClinicError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state.pop("book_reason", None)
                        ui.flash(
                            "success",
                            f"Booked: {appt['patient_name']} with {appt['doctor_name']} on "
                            f"{day:%A %d %B} at {ui.hhmm(slot)}.",
                        )
                        st.rerun()

# -------------------------------------------------------------- manage
with tab_manage:
    manage_patient_id = st.selectbox(
        "Patient", list(patients_by_id), format_func=patient_option, key="manage_patient"
    )
    patient = patients_by_id[manage_patient_id]
    scheduled = [a for a in repo.get_patient_history(manage_patient_id) if a["status"] == "scheduled"]
    scheduled.sort(key=lambda a: (a["appt_date"], a["slot_time"]))

    if not scheduled:
        st.info("This patient has no scheduled appointments.")
    else:
        appts_by_id = {a["appointment_id"]: a for a in scheduled}
        appt_id = st.selectbox(
            "Appointment",
            list(appts_by_id),
            format_func=lambda i: describe(appts_by_id[i]),
            key="manage_appt",
        )
        appt = appts_by_id[appt_id]
        action = st.radio(
            "Action",
            ["Mark as completed", "Cancel", "Reschedule"],
            horizontal=True,
            key="manage_action",
        )

        if action == "Mark as completed":
            if st.button("Mark as completed", type="primary", key="complete_btn"):
                try:
                    repo.complete_appointment(appt)
                except ClinicError as exc:
                    st.error(str(exc))
                else:
                    ui.flash("success", "Appointment marked as completed.")
                    st.rerun()

        elif action == "Cancel":
            if st.button("Cancel this appointment", type="primary", key="cancel_btn"):
                try:
                    repo.cancel_appointment(appt)
                except ClinicError as exc:
                    st.error(str(exc))
                else:
                    ui.flash("success", "Appointment cancelled. The slot is free again.")
                    st.rerun()

        else:  # Reschedule
            doctor_ids = list(doctors_by_id)
            current = doctor_ids.index(appt["doctor_id"]) if appt["doctor_id"] in doctors_by_id else 0
            r1, r2 = st.columns(2)
            new_doctor_id = r1.selectbox(
                "Doctor", doctor_ids, index=current, format_func=doctor_option, key="resched_doctor"
            )
            new_day = r2.date_input(
                "New date", value=max(date.today(), appt["appt_date"]), min_value=date.today(), key="resched_date"
            )
            new_doctor = doctors_by_id[new_doctor_id]

            if not slots.generate_slots(new_doctor, new_day):
                st.warning(f"{new_doctor['full_name']} does not work on {new_day:%A}.")
            else:
                options = slots.free_slots(new_doctor, new_day, repo.get_agenda(new_doctor, new_day))
                if not options:
                    st.warning("No free slot left on this day.")
                else:
                    new_slot = st.selectbox("New time slot", options, format_func=ui.hhmm, key="resched_slot")
                    if st.button("Reschedule", type="primary", key="resched_btn"):
                        try:
                            moved = repo.reschedule_appointment(appt, patient, new_doctor, new_day, new_slot)
                        except ClinicError as exc:
                            st.error(str(exc))
                        else:
                            ui.flash("success", f"Rescheduled to {describe(moved)}.")
                            st.rerun()
