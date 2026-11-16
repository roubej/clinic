"""Fill the database with demo data.

Usage:
    python seed.py            # only seeds an empty database
    python seed.py --reset    # empties every table first, then seeds

The random generator is seeded, so every run produces the same demo data.
"""
from __future__ import annotations

import random
import sys
from datetime import date, datetime, time, timedelta

from db import slots
from db.connection import connect
from db.repository import ClinicError, ClinicRepository

random.seed(42)

FIRST_NAMES = [
    "Amira", "Youssef", "Salma", "Mehdi", "Nour", "Karim", "Ines", "Hamza", "Leila", "Omar",
    "Yasmine", "Rami", "Sana", "Walid", "Mariem", "Aymen", "Rim", "Bilel", "Hiba", "Fares",
    "Asma", "Skander", "Emna", "Tarek", "Dorra",
]
LAST_NAMES = [
    "Ben Salah", "Trabelsi", "Gharbi", "Jlassi", "Mansouri", "Hammami", "Bouazizi", "Chaabane",
    "Khelifi", "Mejri", "Sassi", "Ayari", "Dridi", "Fourati", "Zouari",
]
DOCTORS = [
    # name, specialty, working days, start, end, slot minutes
    ("Dr. Sonia Haddad", "General medicine", [1, 2, 3, 4, 5], time(8, 0), time(16, 0), 30),
    ("Dr. Anis Ben Amor", "Cardiology", [1, 3, 5], time(9, 0), time(15, 0), 30),
    ("Dr. Rania Cherif", "Pediatrics", [1, 2, 3, 4], time(8, 30), time(14, 30), 20),
    ("Dr. Malek Toumi", "Dermatology", [2, 4, 6], time(10, 0), time(17, 0), 30),
]
REASONS = [
    "Routine check-up", "Follow-up visit", "Blood pressure check", "Persistent cough",
    "Skin rash", "Vaccination", "Back pain", "Headaches", "Prescription renewal", "Test results",
]


def main() -> None:
    reset = "--reset" in sys.argv
    cluster, session = connect()
    repo = ClinicRepository(session)

    if reset:
        repo.truncate_all()
        print("All tables emptied.")
    elif repo.count_patients() > 0 or repo.list_doctors():
        sys.exit("The database already has data. Run `python seed.py --reset` to start over.")

    # Doctors
    doctors = []
    for name, specialty, days, start, end, minutes in DOCTORS:
        doctor_id = repo.create_doctor(name, specialty, days, start, end, minutes)
        doctors.append(repo.get_doctor(doctor_id))

    # Patients (unique phone numbers, thanks to the claim on patients_by_phone)
    patients = []
    for i in range(25):
        first, last = FIRST_NAMES[i], random.choice(LAST_NAMES)
        while True:
            phone = f"+216{random.randint(20_000_000, 99_999_999)}"
            email = f"{first.lower()}.{last.lower().replace(' ', '')}{i}@example.com"
            birth = date(random.randint(1950, 2018), random.randint(1, 12), random.randint(1, 28))
            try:
                patient_id = repo.create_patient(first, last, phone, email, birth)
                break
            except ClinicError:
                continue  # phone already used, draw another one
        patients.append(repo.get_patient(patient_id))

    # Appointments from two weeks ago to two weeks ahead
    now = datetime.now()
    today = date.today()
    created = {"scheduled": 0, "completed": 0, "cancelled": 0}
    for offset in range(-14, 15):
        day = today + timedelta(days=offset)
        for doctor in doctors:
            day_slots = slots.generate_slots(doctor, day)
            for slot in random.sample(day_slots, k=int(len(day_slots) * 0.4)):
                patient = random.choice(patients)
                try:
                    appt = repo.book_appointment(
                        patient, doctor, day, slot, random.choice(REASONS), allow_past=True
                    )
                except ClinicError:
                    continue
                in_past = datetime.combine(day, slot) < now
                roll = random.random()
                if in_past:
                    if roll < 0.75:
                        repo.complete_appointment(appt)
                        created["completed"] += 1
                    elif roll < 0.9:
                        repo.cancel_appointment(appt)
                        created["cancelled"] += 1
                    else:
                        created["scheduled"] += 1  # a visit nobody closed yet
                elif roll < 0.9:
                    created["scheduled"] += 1
                else:
                    repo.cancel_appointment(appt)
                    created["cancelled"] += 1

    print(f"Created {len(doctors)} doctors, {len(patients)} patients and appointments: {created}")
    cluster.shutdown()


if __name__ == "__main__":
    main()
