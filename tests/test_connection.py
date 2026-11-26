from unittest.mock import patch

from cassandra.cluster import EXEC_PROFILE_DEFAULT
from cassandra.query import dict_factory

from db.connection import connect


def test_connection_configures_dict_rows_on_default_execution_profile():
    with patch("db.connection.Cluster") as cluster_factory:
        cluster_factory.return_value.connect.return_value = object()

        cluster, session = connect(keyspace=None)

    profile = cluster_factory.call_args.kwargs["execution_profiles"][EXEC_PROFILE_DEFAULT]
    assert profile.row_factory is dict_factory
    assert session is cluster.connect.return_value
