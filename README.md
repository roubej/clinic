# Clinic Appointments

A web app for a small clinic: manage patients and doctors, book appointments, and follow the activity on a dashboard. The interface is built with **Streamlit** and the data lives in **Apache Cassandra**.

A doctor's time slot can only be booked once, even if two people click at the same moment.

## Features

- **Patients**: add, search, edit, delete (name, phone, email, date of birth). Phone numbers are unique.
- **Doctors**: add and edit, with working days, working hours and slot length.
- **Appointments**: book, cancel, mark as completed, reschedule. Statuses: `scheduled`, `completed`, `cancelled`.
- **Views**: a doctor's agenda for one day, a patient's history, upcoming appointments for the whole clinic.
- **Dashboard**: appointments per day, per doctor and per status (Plotly charts).
- Every form is validated (empty fields, invalid email or phone, dates in the past, slots outside working hours).

## Requirements

- Python 3.11 or 3.12
- Docker (to run Cassandra locally)

## Quick start

```bash
# 1. Get the code and install the dependencies
cd clinic-appointments
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Start Cassandra (the first start takes about a minute)
docker compose up -d
docker compose ps                  # wait until the status says "healthy"

# 3. Create the keyspace and the tables
python -m db.init_schema

# 4. Optional: load demo data (4 doctors, 25 patients, appointments from two weeks ago to two weeks ahead)
python seed.py

# 5. Run the app
streamlit run app.py
```

The app opens at http://localhost:8501.

To start over with fresh demo data: `python seed.py --reset`.
To stop Cassandra: `docker compose down` (add `-v` to also delete the data).

If Cassandra runs somewhere else, set `CASSANDRA_HOSTS` (comma-separated) and `CASSANDRA_PORT` before starting the app.

## Project structure

```
clinic-appointments/
  app.py                       home page (counters and today's appointments)
  ui.py                        helpers shared by the pages
  pages/
    1_Patients.py
    2_Doctors.py
    3_Appointments.py          book / cancel / complete / reschedule
    4_Agenda.py                doctor's day + upcoming appointments
    5_Patient_History.py
    6_Dashboard.py
  db/
    schema.cql                 keyspace and tables
    init_schema.py             runs schema.cql
    connection.py              Cassandra session (cached by Streamlit)
    repository.py              every CQL query lives here
    slots.py                   slot generation and checks (no database access)
    validators.py              input validation
  tests/                       unit tests for slots and validators
  seed.py                      demo data
  docker-compose.yml           Cassandra 4.1
  requirements.txt
```

The pages never contain CQL. They call `db/repository.py`, which keeps the queries in one place.

## Data model

Cassandra has no joins, so each table is designed around one question the app asks.

| Table | Primary key | Why it exists |
|---|---|---|
| `patients` | `patient_id` | Read, edit and delete a patient. |
| `patients_by_phone` | `phone` | Cassandra cannot enforce a unique column, so the phone number is a primary key and is claimed with `IF NOT EXISTS`. |
| `doctors` | `doctor_id` | Doctor profile and schedule rules. |
| `appointments_by_doctor` | `((doctor_id, appt_date), slot_time)` | The doctor's agenda. One partition per doctor and day, one row per slot, so a slot cannot exist twice. |
| `appointments_by_patient` | `(patient_id, appt_datetime DESC, appointment_id)` | A patient's history, newest first. |

An appointment is written to both appointment tables. The `schema.cql` file has the full column list.

## How double-booking is prevented

Booking runs in three steps:

1. `INSERT ... IF NOT EXISTS` on `appointments_by_doctor`. This is a lightweight transaction (LWT). Only one request can win a given slot.
2. If it succeeds, the appointment is copied to `appointments_by_patient`.
3. If step 2 fails, the slot row from step 1 is deleted, so no half-booked slot stays behind.

A logged batch is not used here: Cassandra does not allow a conditional (LWT) statement in a batch that touches several partitions, and the two tables are in different partitions.

A cancelled appointment keeps its row. Booking it again uses `UPDATE ... IF status = 'cancelled'`, which is also an LWT. Cancel and complete use `IF appointment_id = ? AND status = 'scheduled'`, so two people cannot close the same appointment twice.

Rescheduling books the new slot first and cancels the old one only if that worked.

## Design notes and limits

- Patient and doctor names are copied into appointment rows. Renaming someone does not change appointments that already exist.
- Changing a doctor's working hours does not move existing appointments.
- A patient with scheduled appointments cannot be deleted. Cancel or complete them first.
- Name search is done in Python, because Cassandra has no `LIKE`. This is fine for a clinic-sized table.
- The dashboard and the upcoming list read one partition per doctor and day, in parallel. The dashboard is limited to 92 days.
- Times are the clinic's local wall-clock time. No time zone conversion is done.
- `SimpleStrategy` with a replication factor of 1 is meant for one local node. A real cluster needs `NetworkTopologyStrategy` and a higher replication factor.
- There is no login. Anyone who can open the app can edit the data.

## Tests

```bash
pip install pytest
python -m pytest -q
```

The tests cover slot generation, free slots, slot checks and input validation. They do not need Cassandra.

## Screenshots

Add your own here once the app runs:

| Page | Screenshot |
|---|---|
| Home | `docs/home.png` |
| Book an appointment | `docs/book.png` |
| Doctor's agenda | `docs/agenda.png` |
| Dashboard | `docs/dashboard.png` |

## Troubleshooting

- **"Cannot reach the Cassandra database"** in the app: run `docker compose ps`, wait for `healthy`, then `python -m db.init_schema`.
- **`init_schema` keeps waiting**: Cassandra needs about a minute on first start. It retries for 2.5 minutes.
- **Port 9042 already in use**: stop the other Cassandra, or change the left side of `9042:9042` in `docker-compose.yml` and set `CASSANDRA_PORT`.
- **Container uses too much memory**: the heap is already limited to 512 MB in `docker-compose.yml`.
