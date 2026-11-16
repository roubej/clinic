"""Input validation. Each function returns a list of error messages
(an empty list means the input is valid)."""
from __future__ import annotations

import re
from datetime import date, time

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_phone(raw: str) -> str:
    """Keep digits and an optional leading +, so '+216 20-123-456' and
    '+21620123456' are treated as the same number."""
    raw = (raw or "").strip()
    digits = re.sub(r"\D", "", raw)
    return ("+" if raw.startswith("+") else "") + digits


def validate_patient(
    first_name: str,
    last_name: str,
    phone: str,
    email: str,
    birth_date: date | None,
    today: date | None = None,
) -> list[str]:
    today = today or date.today()
    errors: list[str] = []

    if not (first_name or "").strip():
        errors.append("First name is required.")
    if not (last_name or "").strip():
        errors.append("Last name is required.")

    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        errors.append("Phone number is required.")
    elif not 8 <= len(digits) <= 15:
        errors.append("Phone number must contain between 8 and 15 digits.")

    if not (email or "").strip():
        errors.append("Email is required.")
    elif not EMAIL_RE.match(email.strip()):
        errors.append("Email address is not valid.")

    if birth_date is None:
        errors.append("Date of birth is required.")
    elif birth_date > today:
        errors.append("Date of birth cannot be in the future.")
    elif birth_date.year < 1900:
        errors.append("Date of birth is too far in the past.")

    return errors


def validate_doctor(
    full_name: str,
    specialty: str,
    working_days: list[int],
    start_time: time | None,
    end_time: time | None,
    slot_minutes: int | None,
) -> list[str]:
    errors: list[str] = []

    if not (full_name or "").strip():
        errors.append("Doctor name is required.")
    if not (specialty or "").strip():
        errors.append("Specialty is required.")
    if not working_days:
        errors.append("Select at least one working day.")

    if start_time is None or end_time is None:
        errors.append("Start and end time are required.")
    elif end_time <= start_time:
        errors.append("End time must be after start time.")

    if not slot_minutes or slot_minutes < 5:
        errors.append("Slot length must be at least 5 minutes.")
    elif start_time and end_time and end_time > start_time:
        total = (end_time.hour * 60 + end_time.minute) - (start_time.hour * 60 + start_time.minute)
        if total < slot_minutes:
            errors.append("Working hours are shorter than one slot.")

    return errors
