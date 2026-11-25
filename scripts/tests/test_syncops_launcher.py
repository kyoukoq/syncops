"""Exercise launcher boundaries without a Docker daemon or live data."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


LAUNCHER = Path(__file__).resolve().parents[1] / "syncops.sh"
DOCKER = """#!/usr/bin/env bash
set -eu
printf '%s\n' "$*" >>"$DOCKER_TEST_CALLS"
case "$*" in
    'context show') echo rootless ;;
    'context inspect '*) echo "$TEST_ENDPOINT" ;;
    'version --format '*) echo 29.10.1 ;;
    'compose version') echo 5.1.0 ;;
    'ps -a --format '*working_dir*) printf '%s\n' "$TEST_OWNER" ;;
    'ps -a --format '*service*) printf '%s\n' "$TEST_SERVICES" ;;
    'ps --format '*service*) ;;
    'compose '*port*) echo "$TEST_BINDING" ;;
    'compose '*up*)
        if [[ -v SYNCOPS_ADMIN_PASSWORD ]]; then exit 4; fi ;;
    *) exit 3 ;;
esac
"""
CURL = """#!/usr/bin/env bash
set -eu
[[ "${!#}" == http://127.0.0.1:* ]] || exit 3
printf '%s' "$TEST_HTTP"
"""


@unittest.skipUnless(os.name == "posix", "Launcher requires Bash on Linux")
class LauncherTests(unittest.TestCase):
    def setUp(self):
        sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(sandbox.cleanup)
        self.root = Path(sandbox.name)
        (self.root / "scripts").mkdir()
        self.script = self.root / "scripts" / "syncops.sh"
        shutil.copyfile(LAUNCHER, self.script)
        tools = self.root / "bin"
        tools.mkdir()
        for name, content in {"docker": DOCKER, "curl": CURL}.items():
            executable = tools / name
            executable.write_text(content)
            executable.chmod(0o700)
        self.calls = self.root / "calls"
        self.env = {
            **os.environ,
            "PATH": f"{tools}:{os.environ['PATH']}",
            "DOCKER_TEST_CALLS": str(self.calls),
            "TEST_ENDPOINT": "unix:///run/user/1000/docker.sock",
            "TEST_OWNER": str(self.root),
            "TEST_SERVICES": "web",
            "TEST_BINDING": "127.0.0.1:8080",
            "TEST_HTTP": "200",
        }
        self.settings = self.root / ".env"
        self.settings.write_text("SYNCOPS_ADMIN_PASSWORD=private-fixture-value\n")
        self.settings.chmod(0o600)

    def invoke(self, *args):
        return subprocess.run(
            ["bash", str(self.script), *args],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_remote_docker_context_refused_before_daemon_access(self):
        self.env["TEST_ENDPOINT"] = "ssh://remote.example"
        result = self.invoke("stop", "compose")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local Unix socket", result.stderr)
        self.assertNotIn("version", self.calls.read_text())

    def test_foreign_project_refused_before_compose_action(self):
        self.env["TEST_OWNER"] = "/tmp/unrelated"
        result = self.invoke("stop", "compose")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("another checkout", result.stderr)
        self.assertNotIn(" stop", self.calls.read_text())

    def test_start_preserves_settings_and_excludes_shell_override(self):
        self.env["SYNCOPS_ADMIN_PASSWORD"] = "process-override"
        result = self.invoke("start", "compose")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.settings.read_text(), "SYNCOPS_ADMIN_PASSWORD=private-fixture-value\n"
        )
        self.assertIn("Verified", result.stdout)
        self.assertNotIn("private-fixture-value", result.stdout + result.stderr)

    def test_urls_require_expected_bind_and_exact_success_status(self):
        self.env["TEST_HTTP"] = "302"
        result = self.invoke("urls", "compose")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unverified", result.stdout)
        self.env["TEST_HTTP"] = "200"
        self.env["TEST_BINDING"] = "0.0.0.0:8080"
        result = self.invoke("urls", "compose")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("0.0.0.0", result.stdout + result.stderr)

    def test_symlink_credentials_are_rejected(self):
        original = self.settings.rename(self.root / "external-settings")
        self.settings.symlink_to(original)
        result = self.invoke("start", "observability")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("non-symlink", result.stderr)
        self.assertNotIn("GRAFANA_PASSWORD", original.read_text())


if __name__ == "__main__":
    unittest.main()
