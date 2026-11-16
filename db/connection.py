"""Cassandra connection helpers.

Host and port come from the environment so the same code works on a laptop
and in a container:
    CASSANDRA_HOSTS=127.0.0.1   (comma-separated list)
    CASSANDRA_PORT=9042
"""
from __future__ import annotations

import os

import streamlit as st
from cassandra.cluster import Cluster

from .repository import KEYSPACE, ClinicRepository


def connect(keyspace: str | None = KEYSPACE):
    """Open a plain connection. Returns (cluster, session).

    Used by scripts (seed.py, init_schema.py). Pass keyspace=None to connect
    without selecting one, which is needed before the keyspace exists.
    """
    hosts = [h.strip() for h in os.getenv("CASSANDRA_HOSTS", "127.0.0.1").split(",") if h.strip()]
    port = int(os.getenv("CASSANDRA_PORT", "9042"))
    cluster = Cluster(hosts, port=port, connect_timeout=10)
    session = cluster.connect(keyspace) if keyspace else cluster.connect()
    return cluster, session


@st.cache_resource(show_spinner="Connecting to Cassandra...")
def get_session():
    """One session shared by every Streamlit rerun and every user."""
    _cluster, session = connect()
    return session


@st.cache_resource(show_spinner=False)
def get_repo() -> ClinicRepository:
    """Repository with its prepared statements, created once."""
    return ClinicRepository(get_session())
