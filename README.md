# Clinic Appointments

A Streamlit clinic app backed by a three-node Apache Cassandra cluster. Patients
sign in to their own portal, doctors see their own agenda and patients with
appointments to them, and administrators manage the clinic.

This is a development/demo project. It is not ready for real patient data:
patient sign-up does not verify email or phone ownership, and production
identity, Cassandra authentication/TLS, audit, backup, HTTPS, and regulatory
controls are not included.

## Requirements

- Docker Desktop with Docker Compose, with enough memory for three Cassandra nodes
- Python 3.11 for local tests

The local Compose setup puts all three Cassandra nodes on one computer. It can
tolerate a Cassandra container/node failure, but not a failure of that computer,
Docker Desktop, or its storage.

## Run locally

From the project directory in PowerShell:

```powershell
docker compose up -d --build
docker compose ps
```

On the first launch, Cassandra may take several minutes to initialize its three
nodes. Wait until all three Cassandra services are `healthy` and the `app`
service is running. The app keeps retrying the schema connection during startup.
It creates or updates the schema once Cassandra is ready. Open
http://localhost:8501.

Create the first administrator from a second PowerShell window:

```powershell
docker compose exec app python -m db.create_admin
```

The command prompts for a username and password. Passwords must be 12–128
characters. Sign in with that administrator account to create doctor profiles
and their portal accounts, manage patient profiles, and access the clinic
dashboard. Existing patient profiles can be given portal accounts from the
Patients page. New patients can register from the sign-in page.

Optional synthetic demo data:

```powershell
docker compose exec app python seed.py
```

`seed.py --reset` clears the clinic tables, including all login accounts. If you
use it, you must create a new administrator with `db.create_admin` afterward.

Run the unit tests on the host using your Python 3.11 environment:

```powershell
.\.venv311\Scripts\python.exe -m pytest -q
```

Stop the containers but keep their data:

```powershell
docker compose down
```

**Do not use `docker compose down -v` unless you intend to delete all Cassandra
data.**

## Portals and permissions

- **Patient:** can book appointments, view their own appointment history, and
  cancel their own scheduled appointments.
- **Doctor:** can view their own agenda and patient details only for patients
  with an appointment on the selected day. Their displayed patient history is
  limited to appointments with that doctor.
- **Administrator:** can manage clinic-wide patients, doctors, appointments,
  schedules, and dashboards.

Patients self-register using their email as the username. An administrator
creates doctor accounts and can provision accounts for existing patients.
Administrators are created only with the local `db.create_admin` command; there
is no public admin sign-up. Passwords are stored as salted scrypt hashes.

Local accounts have no email verification or password-recovery flow. Do not
deploy this app publicly with real health information as-is.

## Cassandra availability

The three Cassandra services are **nodes in one Cassandra cluster**, not three
independent clusters. They share the `datacenter1` data center and replicate
each keyspace partition to all three nodes (`NetworkTopologyStrategy`, RF=3).
The application uses `LOCAL_QUORUM` for reads and writes and `LOCAL_SERIAL` for
lightweight transactions. It can continue reads and writes when one node is
down; if fewer than two replicas are available, quorum operations fail rather
than accepting potentially inconsistent writes.

Check cluster membership:

```powershell
docker compose exec cassandra1 nodetool status
```

Ports 9042–9044 are published only on localhost for local inspection. The app
container connects to Cassandra over the private Compose network. Do not expose
Cassandra ports to the public internet.

For real host-level availability, deploy the three nodes on separate machines
or failure domains, configure Cassandra networking/firewalls and the correct
data center, then set `CASSANDRA_HOSTS` to their reachable addresses. Three
containers on one computer do not protect against that computer or its disk
being unavailable.

### Existing single-node data

Back up existing data before changing a single-node installation. The first
Cassandra volume is retained as `cassandra_data`; the other nodes get new
volumes. The schema startup changes the keyspace replication factor to 3, but
changing replication settings does not itself copy existing rows to the new
nodes. After all three nodes have joined, repair the keyspace on each node
before relying on the old data:

```powershell
docker compose exec cassandra1 nodetool repair clinic
docker compose exec cassandra2 nodetool repair clinic
docker compose exec cassandra3 nodetool repair clinic
```

If existing data is not needed, back it up if desired, then remove the specific
project volumes only after confirming the volume names with `docker volume ls`.

## Project structure

```text
app.py                      role-aware login and navigation
auth_ui.py                  sign-in and patient self-registration
app_pages/                  admin, doctor, patient, and account pages
ui.py                       shared Streamlit helpers and page access checks
db/
  connection.py             multi-node Cassandra connection and quorum settings
  create_admin.py           interactive initial-admin setup
  init_schema.py            schema initialization
  repository.py             Cassandra queries and clinic operations
  schema.cql                keyspace and table definitions
  security.py               password hashing and verification
  slots.py                  appointment-slot rules
  validators.py             patient and doctor input validation
seed.py                     synthetic demo data
docker-compose.yml           three Cassandra nodes and the app service
Dockerfile                  Streamlit app image
tests/                      unit tests
```

Cassandra stores appointments in separate tables for doctor agendas and patient
history, because Cassandra has no joins. Booking uses a conditional insert to
prevent two users from claiming the same doctor/time slot.

## Screenshots

See [SCREENSHOTS.md](SCREENSHOTS.md) for the sign-in and patient sign-up page
captures.
