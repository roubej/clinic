"""Slot helpers: which time slots exist for a doctor, and which are free.

A doctor is a plain dict with the keys used below (working_days, start_time,
end_time, slot_minutes, full_name). Nothing here talks to Cassandra, which
keeps the logic easy to unit test.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta


def generate_slots(doctor: dict, day: date) -> list[time]:
    """Every slot the doctor offers on `day` (empty list on a day off)."""
    if day.isoweekday() not in doctor["working_days"]:
        return []

    step = timedelta(minutes=doctor["slot_minutes"])
    current = datetime.combine(day, doctor["start_time"])
    end = datetime.combine(day, doctor["end_time"])

    slots: list[time] = []
    while current + step <= end:
        slots.append(current.time())
        current += step
    return slots


def free_slots(
    doctor: dict,
    day: date,
    booked_rows: list[dict],
    now: datetime | None = None,
) -> list[time]:
    """Slots that can still be booked.

    A slot is taken when a row exists for it and that row is not cancelled.
    Slots that are already in the past are left out.
    """
    now = now or datetime.now()
    taken = {row["slot_time"] for row in booked_rows if row["status"] != "cancelled"}
    return [
        t
        for t in generate_slots(doctor, day)
        if t not in taken and datetime.combine(day, t) > now
    ]


def check_slot(
    doctor: dict,
    day: date,
    slot: time,
    allow_past: bool = False,
    now: datetime | None = None,
) -> str | None:
    """Return an error message if the slot cannot be booked, else None."""
    if day.isoweekday() not in doctor["working_days"]:
        return f"{doctor['full_name']} does not work on {day:%A}."
    if slot not in generate_slots(doctor, day):
        return "That time is not one of the doctor's slots."
    if not allow_past and datetime.combine(day, slot) <= (now or datetime.now()):
        return "You cannot book a slot in the past."
    return None
