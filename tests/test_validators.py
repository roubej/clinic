from datetime import date, time

from db.validators import normalize_phone, validate_doctor, validate_patient

TODAY = date(2030, 6, 1)


def patient(**overrides):
    data = dict(
        first_name="Amira",
        last_name="Ben Salah",
        phone="+216 20 123 456",
        email="amira@example.com",
        birth_date=date(1990, 5, 20),
        today=TODAY,
    )
    data.update(overrides)
    return validate_patient(**data)


def test_valid_patient_has_no_errors():
    assert patient() == []


def test_empty_fields_are_rejected():
    errors = patient(first_name=" ", last_name="", phone="", email="")
    assert len(errors) == 4


def test_phone_length_is_checked():
    assert patient(phone="1234") != []
    assert patient(phone="+216 20 123 456 789 000 000") != []


def test_email_format_is_checked():
    assert patient(email="not-an-email") != []
    assert patient(email="a@b") != []


def test_birth_date_cannot_be_in_the_future_or_missing():
    assert patient(birth_date=date(2031, 1, 1)) != []
    assert patient(birth_date=None) != []


def test_normalize_phone_removes_separators_and_keeps_plus():
    assert normalize_phone("+216 20-123.456") == "+21620123456"
    assert normalize_phone("(20) 123 456") == "20123456"


def doctor(**overrides):
    data = dict(
        full_name="Dr. Test",
        specialty="Cardiology",
        working_days=[1, 3],
        start_time=time(9, 0),
        end_time=time(12, 0),
        slot_minutes=30,
    )
    data.update(overrides)
    return validate_doctor(**data)


def test_valid_doctor_has_no_errors():
    assert doctor() == []


def test_doctor_requires_name_specialty_and_days():
    assert len(doctor(full_name="", specialty="", working_days=[])) == 3


def test_end_must_be_after_start():
    assert doctor(end_time=time(9, 0)) != []
    assert doctor(end_time=time(8, 0)) != []


def test_slot_length_must_fit_in_the_working_hours():
    assert doctor(start_time=time(9, 0), end_time=time(9, 20), slot_minutes=30) != []
    assert doctor(slot_minutes=2) != []
