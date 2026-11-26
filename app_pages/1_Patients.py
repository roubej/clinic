from datetime import date

import pandas as pd
import streamlit as st

import ui
from db.repository import ClinicError
from db.security import password_error
from db.validators import normalize_phone, validate_patient

repo = ui.setup("Patients", "🧑")
ui.show_flash()

DEFAULT_BIRTH = date(1990, 1, 1)
MIN_BIRTH = date(1900, 1, 1)
ADD_KEYS = ("add_first", "add_last", "add_phone", "add_email", "add_dob")

tab_list, tab_add, tab_edit = st.tabs(["Search and list", "Add patient", "Edit or delete"])

# ---------------------------------------------------------------- list
with tab_list:
    term = st.text_input("Search by name, phone or email", key="patient_search")
    patients = repo.search_patients(term)
    st.caption(f"{len(patients)} patient(s)")
    if patients:
        ui.show_table(
            pd.DataFrame(
                [
                    {
                        "Last name": p["last_name"],
                        "First name": p["first_name"],
                        "Phone": p["phone"],
                        "Email": p["email"],
                        "Date of birth": p["date_of_birth"],
                    }
                    for p in patients
                ]
            )
        )
    else:
        st.info("No patient found.")

# ----------------------------------------------------------------- add
with tab_add:
    with st.form("add_patient_form"):
        c1, c2 = st.columns(2)
        first = c1.text_input("First name", key="add_first")
        last = c2.text_input("Last name", key="add_last")
        phone = c1.text_input("Phone", placeholder="+216 20 123 456", key="add_phone")
        email = c2.text_input("Email", key="add_email")
        dob = c1.date_input(
            "Date of birth",
            value=DEFAULT_BIRTH,
            min_value=MIN_BIRTH,
            max_value=date.today(),
            key="add_dob",
        )
        submitted = st.form_submit_button("Add patient", type="primary")

    if submitted:
        errors = validate_patient(first, last, phone, email, dob)
        if errors:
            for message in errors:
                st.error(message)
        else:
            try:
                repo.create_patient(
                    first.strip(), last.strip(), normalize_phone(phone), email.strip(), dob
                )
            except ClinicError as exc:
                st.error(str(exc))
            else:
                for key in ADD_KEYS:  # empty the form for the next patient
                    st.session_state.pop(key, None)
                ui.flash("success", f"Patient {first.strip()} {last.strip()} added.")
                st.rerun()

# ---------------------------------------------------------- edit / delete
with tab_edit:
    all_patients = repo.list_patients()
    if not all_patients:
        st.info("No patients yet.")
    else:
        by_id = {p["patient_id"]: p for p in all_patients}
        patient_id = st.selectbox(
            "Patient",
            options=list(by_id),
            format_func=lambda i: ui.patient_label(by_id[i]),
            key="edit_patient_select",
        )
        p = by_id[patient_id]
        k = str(patient_id)  # keys include the id so the fields refresh when the selection changes

        with st.form(f"edit_form_{k}"):
            c1, c2 = st.columns(2)
            e_first = c1.text_input("First name", value=p["first_name"] or "", key=f"e_first_{k}")
            e_last = c2.text_input("Last name", value=p["last_name"] or "", key=f"e_last_{k}")
            e_phone = c1.text_input("Phone", value=p["phone"] or "", key=f"e_phone_{k}")
            e_email = c2.text_input("Email", value=p["email"] or "", key=f"e_email_{k}")
            e_dob = c1.date_input(
                "Date of birth",
                value=p["date_of_birth"] or DEFAULT_BIRTH,
                min_value=MIN_BIRTH,
                max_value=date.today(),
                key=f"e_dob_{k}",
            )
            saved = st.form_submit_button("Save changes", type="primary")

        if saved:
            errors = validate_patient(e_first, e_last, e_phone, e_email, e_dob)
            if errors:
                for message in errors:
                    st.error(message)
            else:
                try:
                    repo.update_patient(
                        patient_id,
                        e_first.strip(),
                        e_last.strip(),
                        normalize_phone(e_phone),
                        e_email.strip(),
                        e_dob,
                        old_phone=p["phone"],
                    )
                except ClinicError as exc:
                    st.error(str(exc))
                else:
                    ui.flash("success", "Patient updated.")
                    st.rerun()

        st.divider()
        st.markdown("**Delete this patient**")
        confirm = st.checkbox(
            "I understand that the patient and their appointment history will be deleted.",
            key=f"del_confirm_{k}",
        )
        if st.button("Delete patient", disabled=not confirm, key=f"del_btn_{k}"):
            try:
                repo.delete_patient(patient_id)
            except ClinicError as exc:
                st.error(str(exc))
            else:
                ui.flash("success", "Patient deleted.")
                st.rerun()

        st.divider()
        account_username = repo.get_account_for_identity("patient", patient_id)
        if account_username:
            st.caption(f"Patient portal username: {account_username}")
        else:
            st.markdown("**Create patient portal access**")
            with st.form(f"patient_account_form_{k}"):
                account_name = st.text_input(
                    "Username",
                    value=p["email"] or "",
                    key=f"patient_username_{k}",
                )
                account_password = st.text_input(
                    "Initial password (12–128 characters)",
                    type="password",
                    key=f"patient_password_{k}",
                )
                account_submitted = st.form_submit_button("Create portal account")
            if account_submitted:
                password_problem = password_error(account_password)
                if not account_name.strip():
                    st.error("Username is required.")
                elif password_problem:
                    st.error(password_problem)
                else:
                    try:
                        repo.create_account(
                            account_name,
                            account_password,
                            "patient",
                            patient_id,
                        )
                    except ClinicError as exc:
                        st.error(str(exc))
                    else:
                        ui.flash("success", "Patient portal account created.")
                        st.rerun()
