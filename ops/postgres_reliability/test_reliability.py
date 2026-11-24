import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ops.postgres_reliability.run import distribution
from ops.postgres_reliability.runtime import LABEL, PROJECT_LABEL, Lab, LabError


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lab = Lab(Path(self.temp.name))

    def test_refuses_remote_daemon(self):
        with patch.object(self.lab, "command", return_value="ssh://example.invalid"):
            with self.assertRaisesRegex(LabError, "local Unix socket"):
                self.lab.verify_context()

    def test_refuses_a_preexisting_project_at_creation(self):
        with patch.object(self.lab, "resources", return_value=["unknown"]):
            with self.assertRaisesRegex(LabError, "already owns resources"):
                self.lab.assert_isolated(empty=True)

    def test_owned_labels_are_required_on_all_resources(self):
        with (
            patch.object(self.lab, "resources", return_value=["resource"]),
            patch.object(
                self.lab,
                "command",
                return_value=json.dumps(
                    {
                        PROJECT_LABEL: self.lab.project,
                        LABEL: self.lab.run_id,
                    }
                ),
            ),
        ):
            self.lab.assert_isolated()
        with (
            patch.object(self.lab, "resources", return_value=["resource"]),
            patch.object(
                self.lab,
                "command",
                return_value=json.dumps({PROJECT_LABEL: self.lab.project}),
            ),
        ):
            with self.assertRaisesRegex(LabError, "ownership labels"):
                self.lab.assert_isolated()

    def test_unowned_database_stops_before_execution(self):
        with patch.object(self.lab, "db_exec") as execute:
            with self.assertRaisesRegex(LabError, "outside the generated lab"):
                self.lab.sql("SELECT 1", database="syncops")
            execute.assert_not_called()

    def test_source_drop_requires_exact_owned_database(self):
        with (
            patch.object(self.lab, "assert_isolated"),
            patch.object(self.lab, "sql", return_value="postgres"),
            patch.object(self.lab, "db_exec") as execute,
        ):
            with self.assertRaisesRegex(LabError, "unexpected ownership"):
                self.lab.drop_source()
            execute.assert_not_called()

    def test_api_authentication_target_must_be_loopback(self):
        with patch.object(self.lab, "compose", return_value="0.0.0.0:32768"):
            with self.assertRaisesRegex(LabError, "IPv4 loopback"):
                self.lab.api_origin()

    def test_evidence_percentiles_use_nearest_rank(self):
        self.assertEqual(
            distribution([50, 20, 100, 10, 30]),
            {"p50_ms": 30, "p95_ms": 100, "max_ms": 100},
        )


if __name__ == "__main__":
    unittest.main()
