"""Data access layer: every CQL statement of the application lives here.

Design rules
------------
* Cassandra has no joins, so each query has its own table.
* An appointment is stored twice: in appointments_by_doctor (agenda and
  double-booking guard) and in appointments_by_patient (history).
* The slot row in appointments_by_doctor is the source of truth. It is claimed
  with a lightweight transaction (INSERT ... IF NOT EXISTS). A logged batch
  cannot hold a conditional statement that spans two partitions, so the
  second write is done afterwards and undone if it fails.
* Dates and times are stored as the wall-clock time of the clinic. The driver
  treats naive datetimes as UTC, and we read them back the same way, so
  nothing shifts.
* Names copied into appointment rows (patient_name, doctor_name) are
  snapshots. Renaming a patient or a doctor does not rewrite old appointments.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

from cassandra import util
from cassandra.concurrent import execute_concurrent_with_args

from . import slots
from .security import hash_password, password_error, verify_password

KEYSPACE = "clinic"

SCHEDULED = "scheduled"
COMPLETED = "completed"
CANCELLED = "cancelled"
STATUSES = (SCHEDULED, COMPLETED, CANCELLED)

TABLES = (
    "patients",
    "patients_by_phone",
    "doctors",
    "appointments_by_doctor",
    "appointments_by_patient",
    "accounts_by_username",
    "accounts_by_identity",
)


class ClinicError(Exception):
    """Base class for errors we want to show to the user as a message."""


class DuplicatePhoneError(ClinicError):
    pass


class SlotTakenError(ClinicError):
    pass


class InvalidSlotError(ClinicError):
    pass


class PatientHasAppointmentsError(ClinicError):
    pass


def _fix(row: dict) -> dict:
    """Convert driver types (Date, Time, SortedSet) to plain Python types."""
    out = dict(row)
    for key, value in out.items():
        if isinstance(value, util.Date):
            out[key] = value.date()
        elif isinstance(value, util.Time):
            out[key] = value.time()
        elif isinstance(value, (util.SortedSet, set, frozenset)):
            out[key] = sorted(value)
    return out


def _doctor(row: dict) -> dict:
    doctor = _fix(row)
    doctor["working_days"] = doctor.get("working_days") or []
    return doctor


def _appt_from_doctor_row(row: dict, doctor_name: str) -> dict:
    r = _fix(row)
    return {
        "appointment_id": r["appointment_id"],
        "doctor_id": r["doctor_id"],
        "doctor_name": doctor_name,
        "patient_id": r["patient_id"],
        "patient_name": r.get("patient_name") or "",
        "appt_date": r["appt_date"],
        "slot_time": r["slot_time"],
        "reason": r.get("reason") or "",
        "status": r.get("status") or SCHEDULED,
    }


def _appt_from_patient_row(row: dict) -> dict:
    r = _fix(row)
    when: datetime = r["appt_datetime"]
    return {
        "appointment_id": r["appointment_id"],
        "doctor_id": r["doctor_id"],
        "doctor_name": r.get("doctor_name") or "",
        "patient_id": r["patient_id"],
        "patient_name": "",
        "appt_date": when.date(),
        "slot_time": when.time(),
        "reason": r.get("reason") or "",
        "status": r.get("status") or SCHEDULED,
    }


class ClinicRepository:
    def __init__(self, session):
        self.s = session
        prep = session.prepare

        # ---- patients -------------------------------------------------
        self._insert_patient = prep(
            "INSERT INTO patients (patient_id, first_name, last_name, phone, email, "
            "date_of_birth, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        self._update_patient = prep(
            "UPDATE patients SET first_name = ?, last_name = ?, phone = ?, email = ?, "
            "date_of_birth = ? WHERE patient_id = ?"
        )
        self._get_patient = prep("SELECT * FROM patients WHERE patient_id = ?")
        self._all_patients = prep("SELECT * FROM patients")
        self._delete_patient = prep("DELETE FROM patients WHERE patient_id = ?")
        self._count_patients = prep("SELECT COUNT(*) AS total FROM patients")
        self._claim_phone = prep(
            "INSERT INTO patients_by_phone (phone, patient_id) VALUES (?, ?) IF NOT EXISTS"
        )
        self._release_phone = prep("DELETE FROM patients_by_phone WHERE phone = ?")
        self._phone_lookup = prep(
            "SELECT patient_id FROM patients_by_phone WHERE phone = ?"
        )

        # ---- accounts -------------------------------------------------
        self._get_account = prep(
            "SELECT username, role, identity_id, password_salt, password_hash, enabled "
            "FROM accounts_by_username WHERE username = ?"
        )
        self._get_account_identity = prep(
            "SELECT username FROM accounts_by_identity WHERE role = ? AND identity_id = ?"
        )
        self._create_account = prep(
            "INSERT INTO accounts_by_username "
            "(username, role, identity_id, password_salt, password_hash, enabled, created_at) "
            "VALUES (?, ?, ?, ?, ?, true, ?) IF NOT EXISTS"
        )
        self._claim_account_identity = prep(
            "INSERT INTO accounts_by_identity (role, identity_id, username) "
            "VALUES (?, ?, ?) IF NOT EXISTS"
        )
        self._release_account = prep("DELETE FROM accounts_by_username WHERE username = ?")
        self._release_account_identity = prep(
            "DELETE FROM accounts_by_identity WHERE role = ? AND identity_id = ?"
        )
        self._update_password = prep(
            "UPDATE accounts_by_username SET password_salt = ?, password_hash = ? "
            "WHERE username = ?"
        )

        # ---- doctors --------------------------------------------------
        self._insert_doctor = prep(
            "INSERT INTO doctors (doctor_id, full_name, specialty, working_days, "
            "start_time, end_time, slot_minutes) VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        self._update_doctor = prep(
            "UPDATE doctors SET full_name = ?, specialty = ?, working_days = ?, "
            "start_time = ?, end_time = ?, slot_minutes = ? WHERE doctor_id = ?"
        )
        self._get_doctor = prep("SELECT * FROM doctors WHERE doctor_id = ?")
        self._all_doctors = prep("SELECT * FROM doctors")

        # ---- appointments ---------------------------------------------
        self._claim_slot = prep(
            "INSERT INTO appointments_by_doctor (doctor_id, appt_date, slot_time, "
            "appointment_id, patient_id, patient_name, reason, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) IF NOT EXISTS"
        )
        self._reuse_slot = prep(
            "UPDATE appointments_by_doctor SET appointment_id = ?, patient_id = ?, "
            "patient_name = ?, reason = ?, status = 'scheduled', created_at = ? "
            "WHERE doctor_id = ? AND appt_date = ? AND slot_time = ? "
            "IF status = 'cancelled'"
        )
        self._release_slot = prep(
            "DELETE FROM appointments_by_doctor "
            "WHERE doctor_id = ? AND appt_date = ? AND slot_time = ?"
        )
        self._insert_by_patient = prep(
            "INSERT INTO appointments_by_patient (patient_id, appt_datetime, "
            "appointment_id, doctor_id, doctor_name, reason, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        self._close_slot = prep(
            "UPDATE appointments_by_doctor SET status = ? "
            "WHERE doctor_id = ? AND appt_date = ? AND slot_time = ? "
            "IF appointment_id = ? AND status = 'scheduled'"
        )
        self._close_by_patient = prep(
            "UPDATE appointments_by_patient SET status = ? "
            "WHERE patient_id = ? AND appt_datetime = ? AND appointment_id = ?"
        )
        self._agenda = prep(
            "SELECT * FROM appointments_by_doctor WHERE doctor_id = ? AND appt_date = ?"
        )
        self._history = prep("SELECT * FROM appointments_by_patient WHERE patient_id = ?")
        self._delete_history = prep(
            "DELETE FROM appointments_by_patient WHERE patient_id = ?"
        )

    # ==================================================================
    # Patients
    # ==================================================================
    def count_patients(self) -> int:
        return self.s.execute(self._count_patients).one()["total"]

    def list_patients(self) -> list[dict]:
        rows = [_fix(r) for r in self.s.execute(self._all_patients)]
        rows.sort(key=lambda p: ((p["last_name"] or "").lower(), (p["first_name"] or "").lower()))
        return rows

    def search_patients(self, term: str) -> list[dict]:
        """Case-insensitive search on name, phone and email. Cassandra has no
        LIKE, so we filter in Python (fine for a clinic-sized table)."""
        term = (term or "").strip().lower()
        if not term:
            return self.list_patients()
        return [
            p
            for p in self.list_patients()
            if term in f"{p['first_name']} {p['last_name']}".lower()
            or term in (p["phone"] or "").lower()
            or term in (p["email"] or "").lower()
        ]

    def get_patient(self, patient_id: uuid.UUID) -> dict | None:
        row = self.s.execute(self._get_patient, (patient_id,)).one()
        return _fix(row) if row else None

    def get_patient_by_phone(self, phone: str) -> dict | None:
        row = self.s.execute(self._phone_lookup, (phone,)).one()
        return self.get_patient(row["patient_id"]) if row else None

    @staticmethod
    def normalize_username(username: str) -> str:
        return (username or "").strip().casefold()

    @staticmethod
    def _public_account(row: dict) -> dict:
        return {
            "username": row["username"],
            "role": row["role"],
            "identity_id": row["identity_id"],
            "enabled": row["enabled"],
        }

    def get_account(self, username: str) -> dict | None:
        normalized = self.normalize_username(username)
        row = self.s.execute(self._get_account, (normalized,)).one()
        return self._public_account(row) if row else None

    def get_account_for_identity(self, role: str, identity_id: uuid.UUID) -> str | None:
        row = self.s.execute(self._get_account_identity, (role, identity_id)).one()
        return row["username"] if row else None

    def authenticate(self, username: str, password: str) -> dict | None:
        normalized = self.normalize_username(username)
        row = self.s.execute(self._get_account, (normalized,)).one()
        if not row or not row["enabled"]:
            return None
        if not verify_password(password, row["password_salt"], row["password_hash"]):
            return None
        return self._public_account(row)

    def create_account(
        self, username: str, password: str, role: str, identity_id: uuid.UUID
    ) -> None:
        normalized = self.normalize_username(username)
        if role not in {"patient", "doctor", "admin"}:
            raise ClinicError("Invalid account role.")
        if not normalized:
            raise ClinicError("Username is required.")
        password_problem = password_error(password)
        if password_problem:
            raise ClinicError(password_problem)

        salt, password_hash = hash_password(password)
        account = self.s.execute(
            self._create_account,
            (normalized, role, identity_id, salt, password_hash, datetime.now()),
        )
        if not account.was_applied:
            raise ClinicError("That username is already in use.")
        try:
            claimed = self.s.execute(
                self._claim_account_identity, (role, identity_id, normalized)
            )
            if not claimed.was_applied:
                raise ClinicError("This profile already has an account.")
        except Exception:
            self.s.execute(self._release_account, (normalized,))
            raise

    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        normalized = self.normalize_username(username)
        row = self.s.execute(self._get_account, (normalized,)).one()
        if not row or not row["enabled"]:
            return False
        if not verify_password(old_password, row["password_salt"], row["password_hash"]):
            return False
        password_problem = password_error(new_password)
        if password_problem:
            raise ClinicError(password_problem)
        salt, password_hash = hash_password(new_password)
        self.s.execute(self._update_password, (salt, password_hash, normalized))
        return True

    def delete_account(self, username: str, role: str, identity_id: uuid.UUID) -> None:
        normalized = self.normalize_username(username)
        self.s.execute(self._release_account_identity, (role, identity_id))
        self.s.execute(self._release_account, (normalized,))

    def create_doctor_with_account(
        self,
        full_name: str,
        specialty: str,
        working_days: list[int],
        start_time: time,
        end_time: time,
        slot_minutes: int,
        username: str,
        password: str,
    ) -> uuid.UUID:
        doctor_id = uuid.uuid4()
        self.create_account(username, password, "doctor", doctor_id)
        try:
            self.s.execute(
                self._insert_doctor,
                (
                    doctor_id,
                    full_name,
                    specialty,
                    set(working_days),
                    start_time,
                    end_time,
                    slot_minutes,
                ),
            )
        except Exception:
            self.delete_account(username, "doctor", doctor_id)
            raise
        return doctor_id

    def create_patient(self, first_name, last_name, phone, email, birth_date) -> uuid.UUID:
        patient_id = uuid.uuid4()
        claimed = self.s.execute(self._claim_phone, (phone, patient_id))
        if not claimed.was_applied:
            raise DuplicatePhoneError(f"A patient with phone {phone} already exists.")
        try:
            self.s.execute(
                self._insert_patient,
                (patient_id, first_name, last_name, phone, email, birth_date, datetime.now()),
            )
        except Exception:
            self.s.execute(self._release_phone, (phone,))
            raise
        return patient_id

    def register_patient(
        self,
        first_name: str,
        last_name: str,
        phone: str,
        email: str,
        birth_date: date,
        password: str,
    ) -> uuid.UUID:
        patient_id = self.create_patient(first_name, last_name, phone, email, birth_date)
        try:
            self.create_account(email, password, "patient", patient_id)
        except Exception:
            self.delete_patient(patient_id)
            raise
        return patient_id

    def update_patient(
        self, patient_id, first_name, last_name, phone, email, birth_date, old_phone
    ) -> None:
        phone_changed = phone != old_phone
        if phone_changed:
            claimed = self.s.execute(self._claim_phone, (phone, patient_id))
            if not claimed.was_applied:
                raise DuplicatePhoneError(f"A patient with phone {phone} already exists.")
        self.s.execute(
            self._update_patient,
            (first_name, last_name, phone, email, birth_date, patient_id),
        )
        if phone_changed:
            self.s.execute(self._release_phone, (old_phone,))

    def delete_patient(self, patient_id: uuid.UUID) -> None:
        """Delete a patient and their history. Refused while appointments are
        still scheduled, so nobody is left waiting for a deleted patient."""
        history = self.get_patient_history(patient_id)
        if any(a["status"] == SCHEDULED for a in history):
            raise PatientHasAppointmentsError(
                "This patient still has scheduled appointments. "
                "Cancel or complete them before deleting the patient."
            )
        patient = self.get_patient(patient_id)
        if patient:
            self.s.execute(self._release_phone, (patient["phone"],))
        self.s.execute(self._delete_patient, (patient_id,))
        self.s.execute(self._delete_history, (patient_id,))
        username = self.get_account_for_identity("patient", patient_id)
        if username:
            self.delete_account(username, "patient", patient_id)

    # ==================================================================
    # Doctors
    # ==================================================================
    def list_doctors(self) -> list[dict]:
        rows = [_doctor(r) for r in self.s.execute(self._all_doctors)]
        rows.sort(key=lambda d: (d["full_name"] or "").lower())
        return rows

    def get_doctor(self, doctor_id: uuid.UUID) -> dict | None:
        row = self.s.execute(self._get_doctor, (doctor_id,)).one()
        return _doctor(row) if row else None

    def create_doctor(
        self, full_name, specialty, working_days, start_time, end_time, slot_minutes
    ) -> uuid.UUID:
        doctor_id = uuid.uuid4()
        self.s.execute(
            self._insert_doctor,
            (doctor_id, full_name, specialty, set(working_days), start_time, end_time, slot_minutes),
        )
        return doctor_id

    def update_doctor(
        self, doctor_id, full_name, specialty, working_days, start_time, end_time, slot_minutes
    ) -> None:
        self.s.execute(
            self._update_doctor,
            (full_name, specialty, set(working_days), start_time, end_time, slot_minutes, doctor_id),
        )

    # ==================================================================
    # Appointments
    # ==================================================================
    def book_appointment(
        self,
        patient: dict,
        doctor: dict,
        appt_date: date,
        slot_time: time,
        reason: str,
        allow_past: bool = False,
    ) -> dict:
        """Book a slot. Raises InvalidSlotError or SlotTakenError on failure."""
        problem = slots.check_slot(doctor, appt_date, slot_time, allow_past=allow_past)
        if problem:
            raise InvalidSlotError(problem)

        appointment_id = uuid.uuid4()
        now = datetime.now()
        patient_name = f"{patient['first_name']} {patient['last_name']}"
        reason = (reason or "").strip()
        slot_key = (doctor["doctor_id"], appt_date, slot_time)

        # Step 1: claim the slot. This is the only step that decides who wins.
        result = self.s.execute(
            self._claim_slot,
            (*slot_key, appointment_id, patient["patient_id"], patient_name, reason, SCHEDULED, now),
        )
        if not result.was_applied:
            # A cancelled appointment leaves its row behind, so the slot can be taken again.
            reuse = self.s.execute(
                self._reuse_slot,
                (appointment_id, patient["patient_id"], patient_name, reason, now, *slot_key),
            )
            if not reuse.was_applied:
                raise SlotTakenError("This slot has just been taken. Pick another one.")

        # Step 2: copy the appointment to the patient's table. Undo step 1 on failure.
        try:
            self.s.execute(
                self._insert_by_patient,
                (
                    patient["patient_id"],
                    datetime.combine(appt_date, slot_time),
                    appointment_id,
                    doctor["doctor_id"],
                    doctor["full_name"],
                    reason,
                    SCHEDULED,
                ),
            )
        except Exception:
            self.s.execute(self._release_slot, slot_key)
            raise

        return {
            "appointment_id": appointment_id,
            "doctor_id": doctor["doctor_id"],
            "doctor_name": doctor["full_name"],
            "patient_id": patient["patient_id"],
            "patient_name": patient_name,
            "appt_date": appt_date,
            "slot_time": slot_time,
            "reason": reason,
            "status": SCHEDULED,
        }

    def _close(self, appt: dict, new_status: str) -> None:
        """Move a scheduled appointment to completed or cancelled."""
        result = self.s.execute(
            self._close_slot,
            (
                new_status,
                appt["doctor_id"],
                appt["appt_date"],
                appt["slot_time"],
                appt["appointment_id"],
            ),
        )
        if not result.was_applied:
            raise ClinicError(
                "This appointment is no longer scheduled. Refresh the page and try again."
            )
        self.s.execute(
            self._close_by_patient,
            (
                new_status,
                appt["patient_id"],
                datetime.combine(appt["appt_date"], appt["slot_time"]),
                appt["appointment_id"],
            ),
        )

    def cancel_appointment(self, appt: dict) -> None:
        self._close(appt, CANCELLED)

    def complete_appointment(self, appt: dict) -> None:
        self._close(appt, COMPLETED)

    def reschedule_appointment(
        self, appt: dict, patient: dict, new_doctor: dict, new_date: date, new_time: time
    ) -> dict:
        """Book the new slot first, then cancel the old one. If the new slot
        is taken, nothing changes."""
        if (
            new_doctor["doctor_id"] == appt["doctor_id"]
            and new_date == appt["appt_date"]
            and new_time == appt["slot_time"]
        ):
            raise InvalidSlotError("That is the current slot. Pick a different one.")

        new_appt = self.book_appointment(patient, new_doctor, new_date, new_time, appt["reason"])
        try:
            self.cancel_appointment(appt)
        except Exception:
            self.cancel_appointment(new_appt)  # roll back the new booking
            raise
        return new_appt

    def get_agenda(self, doctor: dict, day: date) -> list[dict]:
        """All rows of one doctor's day, ordered by time."""
        rows = self.s.execute(self._agenda, (doctor["doctor_id"], day))
        return [_appt_from_doctor_row(r, doctor["full_name"]) for r in rows]

    def get_patient_history(self, patient_id: uuid.UUID) -> list[dict]:
        """A patient's appointments, newest first."""
        return [_appt_from_patient_row(r) for r in self.s.execute(self._history, (patient_id,))]

    def get_appointments_range(
        self, start: date, end: date, doctor_ids: list[uuid.UUID] | None = None
    ) -> list[dict]:
        """Every appointment between two dates (inclusive).

        Cassandra has no cheap global scan, so we read one partition per
        (doctor, day), in parallel. Keep the range reasonable.
        """
        doctors = {d["doctor_id"]: d for d in self.list_doctors()}
        ids = [i for i in (doctor_ids or list(doctors)) if i in doctors]
        days = [start + timedelta(days=n) for n in range((end - start).days + 1)]
        params = [(doctor_id, day) for doctor_id in ids for day in days]
        if not params:
            return []

        results = execute_concurrent_with_args(
            self.s, self._agenda, params, concurrency=50, raise_on_first_error=False
        )
        appointments: list[dict] = []
        for (doctor_id, _day), (ok, rows) in zip(params, results):
            if not ok:
                raise rows  # `rows` holds the exception when ok is False
            name = doctors[doctor_id]["full_name"]
            appointments.extend(_appt_from_doctor_row(r, name) for r in rows)
        appointments.sort(key=lambda a: (a["appt_date"], a["slot_time"], a["doctor_name"]))
        return appointments

    def get_upcoming(self, days_ahead: int = 14, doctor_id: uuid.UUID | None = None) -> list[dict]:
        """Scheduled appointments from now until `days_ahead` days from today."""
        today = date.today()
        now = datetime.now()
        rows = self.get_appointments_range(
            today, today + timedelta(days=days_ahead), [doctor_id] if doctor_id else None
        )
        return [
            a
            for a in rows
            if a["status"] == SCHEDULED and datetime.combine(a["appt_date"], a["slot_time"]) >= now
        ]

    # ==================================================================
    # Maintenance (used by seed.py)
    # ==================================================================
    def truncate_all(self) -> None:
        for table in TABLES:
            self.s.execute(f"TRUNCATE {table}")
