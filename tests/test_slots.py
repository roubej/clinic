from datetime import date, datetime, time

from db import slots

DOCTOR = {
    "full_name": "Dr. Test",
    "working_days": [1, 2, 3, 4, 5],  # Monday to Friday
    "start_time": time(9, 0),
    "end_time": time(11, 0),
    "slot_minutes": 30,
}

MONDAY = date(2030, 1, 7)
SUNDAY = date(2030, 1, 6)


def test_generate_slots_covers_the_working_hours():
    result = slots.generate_slots(DOCTOR, MONDAY)
    assert result == [time(9, 0), time(9, 30), time(10, 0), time(10, 30)]


def test_no_slots_on_a_day_off():
    assert slots.generate_slots(DOCTOR, SUNDAY) == []


def test_last_slot_must_fit_before_end_of_day():
    doctor = {**DOCTOR, "end_time": time(10, 45)}
    assert slots.generate_slots(doctor, MONDAY)[-1] == time(10, 0)


def test_booked_slot_is_not_free():
    booked = [{"slot_time": time(9, 30), "status": "scheduled"}]
    free = slots.free_slots(DOCTOR, MONDAY, booked, now=datetime(2030, 1, 1))
    assert time(9, 30) not in free
    assert time(9, 0) in free


def test_completed_slot_is_not_free():
    booked = [{"slot_time": time(9, 0), "status": "completed"}]
    free = slots.free_slots(DOCTOR, MONDAY, booked, now=datetime(2030, 1, 1))
    assert time(9, 0) not in free


def test_cancelled_slot_is_free_again():
    booked = [{"slot_time": time(9, 30), "status": "cancelled"}]
    free = slots.free_slots(DOCTOR, MONDAY, booked, now=datetime(2030, 1, 1))
    assert time(9, 30) in free


def test_past_slots_are_left_out():
    free = slots.free_slots(DOCTOR, MONDAY, [], now=datetime(2030, 1, 7, 10, 0))
    assert free == [time(10, 30)]


def test_check_slot_accepts_a_valid_slot():
    assert slots.check_slot(DOCTOR, MONDAY, time(9, 30), now=datetime(2030, 1, 1)) is None


def test_check_slot_rejects_day_off_odd_time_and_past():
    now = datetime(2030, 1, 1)
    assert "does not work" in slots.check_slot(DOCTOR, SUNDAY, time(9, 0), now=now)
    assert "not one of" in slots.check_slot(DOCTOR, MONDAY, time(9, 10), now=now)
    assert "past" in slots.check_slot(DOCTOR, MONDAY, time(9, 0), now=datetime(2030, 1, 8))


def test_check_slot_can_allow_the_past():
    assert slots.check_slot(DOCTOR, MONDAY, time(9, 0), allow_past=True, now=datetime(2031, 1, 1)) is None
