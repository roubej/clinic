from datetime import time

import pandas as pd
import streamlit as st

import ui
from db.validators import validate_doctor

repo = ui.setup("Doctors", "🩺")
ui.show_flash()

DAYS = list(ui.DAY_NAMES)  # [1..7]
WEEKDAYS = [1, 2, 3, 4, 5]
ADD_KEYS = ("add_d_name", "add_d_spec", "add_d_days", "add_d_start", "add_d_end", "add_d_slot")

tab_list, tab_add, tab_edit = st.tabs(["Doctors", "Add doctor", "Edit doctor"])

# ---------------------------------------------------------------- list
with tab_list:
    doctors = repo.list_doctors()
    if doctors:
        ui.show_table(
            pd.DataFrame(
                [
                    {
                        "Name": d["full_name"],
                        "Specialty": d["specialty"],
                        "Working days": ui.days_text(d["working_days"]),
                        "Hours": f"{ui.hhmm(d['start_time'])} to {ui.hhmm(d['end_time'])}",
                        "Slot (min)": d["slot_minutes"],
                    }
                    for d in doctors
                ]
            )
        )
    else:
        st.info("No doctors yet. Add one in the next tab.")

# ----------------------------------------------------------------- add
with tab_add:
    with st.form("add_doctor_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Full name", key="add_d_name")
        specialty = c2.text_input("Specialty", key="add_d_spec")
        days = st.multiselect(
            "Working days",
            options=DAYS,
            default=WEEKDAYS,
            format_func=lambda n: ui.DAY_NAMES[n],
            key="add_d_days",
        )
        c3, c4, c5 = st.columns(3)
        start = c3.time_input("Start of day", value=time(9, 0), key="add_d_start")
        end = c4.time_input("End of day", value=time(17, 0), key="add_d_end")
        slot = c5.number_input(
            "Slot length (minutes)", min_value=5, max_value=120, value=30, step=5, key="add_d_slot"
        )
        submitted = st.form_submit_button("Add doctor", type="primary")

    if submitted:
        errors = validate_doctor(name, specialty, days, start, end, int(slot))
        if errors:
            for message in errors:
                st.error(message)
        else:
            repo.create_doctor(name.strip(), specialty.strip(), days, start, end, int(slot))
            for key in ADD_KEYS:
                st.session_state.pop(key, None)
            ui.flash("success", f"Doctor {name.strip()} added.")
            st.rerun()

# ---------------------------------------------------------------- edit
with tab_edit:
    all_doctors = repo.list_doctors()
    if not all_doctors:
        st.info("No doctors yet.")
    else:
        by_id = {d["doctor_id"]: d for d in all_doctors}
        doctor_id = st.selectbox(
            "Doctor",
            options=list(by_id),
            format_func=lambda i: ui.doctor_label(by_id[i]),
            key="edit_doctor_select",
        )
        d = by_id[doctor_id]
        k = str(doctor_id)

        with st.form(f"edit_doctor_form_{k}"):
            c1, c2 = st.columns(2)
            e_name = c1.text_input("Full name", value=d["full_name"] or "", key=f"e_d_name_{k}")
            e_spec = c2.text_input("Specialty", value=d["specialty"] or "", key=f"e_d_spec_{k}")
            e_days = st.multiselect(
                "Working days",
                options=DAYS,
                default=d["working_days"],
                format_func=lambda n: ui.DAY_NAMES[n],
                key=f"e_d_days_{k}",
            )
            c3, c4, c5 = st.columns(3)
            e_start = c3.time_input("Start of day", value=d["start_time"], key=f"e_d_start_{k}")
            e_end = c4.time_input("End of day", value=d["end_time"], key=f"e_d_end_{k}")
            e_slot = c5.number_input(
                "Slot length (minutes)",
                min_value=5,
                max_value=120,
                value=int(d["slot_minutes"] or 30),
                step=5,
                key=f"e_d_slot_{k}",
            )
            saved = st.form_submit_button("Save changes", type="primary")

        if saved:
            errors = validate_doctor(e_name, e_spec, e_days, e_start, e_end, int(e_slot))
            if errors:
                for message in errors:
                    st.error(message)
            else:
                repo.update_doctor(
                    doctor_id, e_name.strip(), e_spec.strip(), e_days, e_start, e_end, int(e_slot)
                )
                ui.flash("success", "Doctor updated. Existing appointments are not moved.")
                st.rerun()
