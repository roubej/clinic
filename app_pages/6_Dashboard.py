from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

import ui

repo = ui.setup("Dashboard", "📊")

MAX_DAYS = 92  # one Cassandra partition is read per doctor and day, so keep the range bounded
COLORS = {"scheduled": "#2563eb", "completed": "#16a34a", "cancelled": "#9ca3af"}
STATUS_ORDER = ["scheduled", "completed", "cancelled"]

doctors = repo.list_doctors()
if not doctors:
    st.warning("Add a doctor first.")
    st.stop()
doctors_by_id = {d["doctor_id"]: d for d in doctors}

today = date.today()
f1, f2 = st.columns(2)
period = f1.date_input(
    "Period",
    value=(today - timedelta(days=30), today + timedelta(days=30)),
    key="dash_period",
)
chosen = f2.multiselect(
    "Doctors (empty means all)",
    list(doctors_by_id),
    format_func=lambda i: doctors_by_id[i]["full_name"],
    key="dash_doctors",
)

if not (isinstance(period, (tuple, list)) and len(period) == 2):
    st.info("Pick a start date and an end date.")
    st.stop()
start, end = period
if (end - start).days + 1 > MAX_DAYS:
    st.error(f"Please choose a period of at most {MAX_DAYS} days.")
    st.stop()

appointments = repo.get_appointments_range(start, end, chosen or None)
if not appointments:
    st.info("No appointment in this period.")
    st.stop()

df = pd.DataFrame(appointments)
df["appt_date"] = pd.to_datetime(df["appt_date"])

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total", len(df))
for col, status in zip((m2, m3, m4), STATUS_ORDER):
    col.metric(status.capitalize(), int((df["status"] == status).sum()))

per_day = df.groupby(["appt_date", "status"]).size().reset_index(name="appointments")
fig_day = px.bar(
    per_day,
    x="appt_date",
    y="appointments",
    color="status",
    color_discrete_map=COLORS,
    category_orders={"status": STATUS_ORDER},
    title="Appointments per day",
    labels={"appt_date": "Date", "appointments": "Appointments", "status": "Status"},
)
ui.show_chart(fig_day)

left, right = st.columns(2)
with left:
    per_doctor = df.groupby(["doctor_name", "status"]).size().reset_index(name="appointments")
    fig_doctor = px.bar(
        per_doctor,
        x="doctor_name",
        y="appointments",
        color="status",
        color_discrete_map=COLORS,
        category_orders={"status": STATUS_ORDER},
        title="Appointments per doctor",
        labels={"doctor_name": "Doctor", "appointments": "Appointments", "status": "Status"},
    )
    ui.show_chart(fig_doctor)
with right:
    per_status = df.groupby("status").size().reset_index(name="appointments")
    fig_status = px.pie(
        per_status,
        names="status",
        values="appointments",
        color="status",
        color_discrete_map=COLORS,
        hole=0.45,
        title="Appointments per status",
    )
    ui.show_chart(fig_status)
