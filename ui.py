"""Small helpers shared by every page."""
from __future__ import annotations

from datetime import time

import streamlit as st

from db.connection import get_repo

DAY_NAMES = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}

STATUS_LABELS = {
    "scheduled": "🔵 scheduled",
    "completed": "✅ completed",
    "cancelled": "⚪ cancelled",
}


def get_repository():
    return get_repo()


def setup(title: str, icon: str, allowed_roles: tuple[str, ...] = ("admin",)):
    """Check page access, set the title, and return the shared repository."""
    user = st.session_state.get("clinic_user")
    if user is None or user["role"] not in allowed_roles:
        st.error("You do not have permission to access this page.")
        st.stop()
    st.title(f"{icon} {title}")
    try:
        return get_repository()
    except Exception as exc:  # NoHostAvailable, InvalidRequest (missing keyspace), ...
        st.error(
            "Cannot reach Cassandra. Start the cluster and app with "
            "`docker compose up -d --build`, then check `docker compose ps`."
        )
        st.caption(f"Technical details: {exc}")
        st.stop()


def flash(kind: str, message: str) -> None:
    """Keep a message across the next rerun (kind: success, error, info, warning)."""
    st.session_state["_flash"] = (kind, message)


def show_flash() -> None:
    item = st.session_state.pop("_flash", None)
    if item:
        kind, message = item
        getattr(st, kind)(message)


def show_table(df) -> None:
    """Full-width table without the index column. Works on old and new Streamlit."""
    try:
        st.dataframe(df, hide_index=True, width="stretch")
    except Exception:
        st.dataframe(df, hide_index=True, use_container_width=True)


def show_chart(fig) -> None:
    try:
        st.plotly_chart(fig, width="stretch")
    except Exception:
        st.plotly_chart(fig, use_container_width=True)


def patient_label(patient: dict) -> str:
    return f"{patient['last_name']} {patient['first_name']} ({patient['phone']})"


def doctor_label(doctor: dict) -> str:
    return f"{doctor['full_name']} ({doctor['specialty']})"


def days_text(days: list[int]) -> str:
    return ", ".join(DAY_NAMES[d] for d in sorted(days))


def hhmm(value: time) -> str:
    return value.strftime("%H:%M")
