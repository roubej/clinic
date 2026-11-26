-- Clinic appointments: Cassandra schema.
-- Run with:  python -m db.init_schema
-- Every table name is prefixed with the keyspace so the file can be executed
-- statement by statement without a USE command.
-- One logical cluster with three nodes in datacenter1. LOCAL_QUORUM reads and
-- writes continue when one node is unavailable.

CREATE KEYSPACE IF NOT EXISTS clinic
  WITH replication = {'class': 'NetworkTopologyStrategy', 'datacenter1': 3};

ALTER KEYSPACE clinic
  WITH replication = {'class': 'NetworkTopologyStrategy', 'datacenter1': 3};

-- One row per patient. Read by id, listed with a full scan (small clinic).
CREATE TABLE IF NOT EXISTS clinic.patients (
  patient_id    uuid PRIMARY KEY,
  first_name    text,
  last_name     text,
  phone         text,
  email         text,
  date_of_birth date,
  created_at    timestamp
);

-- Uniqueness guard for phone numbers. Cassandra cannot enforce a unique
-- constraint on a normal column, so the phone number becomes a primary key
-- and is claimed with INSERT ... IF NOT EXISTS.
CREATE TABLE IF NOT EXISTS clinic.patients_by_phone (
  phone      text PRIMARY KEY,
  patient_id uuid
);

CREATE TABLE IF NOT EXISTS clinic.doctors (
  doctor_id    uuid PRIMARY KEY,
  full_name    text,
  specialty    text,
  working_days set<int>,   -- ISO weekday: 1 = Monday ... 7 = Sunday
  start_time   time,
  end_time     time,
  slot_minutes int
);

-- Source of truth for the agenda and for double-booking protection.
-- One partition per doctor and day, one row per slot. Two appointments can
-- never share a primary key, so a slot can only be claimed once.
CREATE TABLE IF NOT EXISTS clinic.appointments_by_doctor (
  doctor_id      uuid,
  appt_date      date,
  slot_time      time,
  appointment_id uuid,
  patient_id     uuid,
  patient_name   text,
  reason         text,
  status         text,      -- scheduled / completed / cancelled
  created_at     timestamp,
  PRIMARY KEY ((doctor_id, appt_date), slot_time)
);

-- Same appointments, organised for "what are this patient's appointments?".
-- Newest first.
CREATE TABLE IF NOT EXISTS clinic.appointments_by_patient (
  patient_id     uuid,
  appt_datetime  timestamp,
  appointment_id uuid,
  doctor_id      uuid,
  doctor_name    text,
  reason         text,
  status         text,
  PRIMARY KEY ((patient_id), appt_datetime, appointment_id)
) WITH CLUSTERING ORDER BY (appt_datetime DESC, appointment_id ASC);

-- Login lookup and one-account-per-profile guard.
CREATE TABLE IF NOT EXISTS clinic.accounts_by_username (
  username      text PRIMARY KEY,
  role          text,
  identity_id   uuid,
  password_salt blob,
  password_hash blob,
  enabled       boolean,
  created_at    timestamp
);

CREATE TABLE IF NOT EXISTS clinic.accounts_by_identity (
  role        text,
  identity_id uuid,
  username    text,
  PRIMARY KEY ((role, identity_id))
);
