"""Own and guard one disposable PostgreSQL Compose project."""

import hashlib
import json
import os
import re
import secrets
import subprocess
from pathlib import Path

COMPOSE_FILE = Path(__file__).with_name("compose.yaml").resolve()
LABEL = "io.syncops.reliability.run_id"
PROJECT_LABEL = "com.docker.compose.project"
CONTAINER_ID = re.compile(r"^[0-9a-f]{12,64}$")


class LabError(RuntimeError):
    pass


class Lab:
    def __init__(self, scratch: Path, *, docker_context: str = "default"):
        self.docker_context = docker_context
        self.run_id = secrets.token_hex(6)
        self.project = f"syncops-pg-lab-{self.run_id}"
        self.image = f"syncops/postgres-lab:{self.run_id}"
        self.source = f"syncops_lab_source_{self.run_id}"
        self.target = f"syncops_lab_restore_{self.run_id}"
        self.database = self.source
        self.admin_password = secrets.token_hex(20)
        mock_secret = secrets.token_hex(20)
        database_password = secrets.token_hex(20)
        app_password = secrets.token_hex(20)
        self.secrets = (
            self.admin_password,
            mock_secret,
            database_password,
            app_password,
        )
        self.env = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith(("SYNCOPS_", "DOCKER_", "COMPOSE_", "PG"))
        }
        self.env.update(
            SYNCOPS_LAB_RUN_ID=self.run_id,
            SYNCOPS_LAB_SOURCE_DB=self.source,
            SYNCOPS_LAB_ADMIN_PASSWORD=self.admin_password,
            SYNCOPS_LAB_MOCK_TOKEN=mock_secret,
            SYNCOPS_LAB_PG_PASSWORD=database_password,
            SYNCOPS_LAB_APP_PASSWORD=app_password,
        )
        self.env_file = scratch / "empty.env"
        self.env_file.touch(mode=0o600, exist_ok=False)

    def command(self, *args, timeout=30, stdin=None, stdout=None, operation):
        try:
            result = subprocess.run(
                ("docker", "--context", self.docker_context, *args),
                env={**self.env, "SYNCOPS_LAB_DATABASE": self.database},
                stdin=stdin if stdin is not None else subprocess.DEVNULL,
                stdout=stdout if stdout is not None else subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise LabError(f"{operation} failed: {type(error).__name__}") from None
        if result.returncode:
            # Compose refuses missing inputs with useful diagnostics. Avoid echoing environment values.
            diagnostic = result.stderr.decode(errors="replace").strip()
            for value in self.secrets:
                diagnostic = diagnostic.replace(value, "[redacted]")
            raise LabError(
                f"{operation} exited {result.returncode}: {diagnostic[-2000:]}"
            )
        return result.stdout.decode(errors="replace").strip() if stdout is None else ""

    def compose(self, *args, timeout=30):
        return self.command(
            "compose",
            "--file",
            str(COMPOSE_FILE),
            "--env-file",
            str(self.env_file),
            "--project-name",
            self.project,
            *args,
            timeout=timeout,
            operation=f"docker compose {args[0]}",
        )

    def resources(self, kind):
        all_states = ("--all",) if kind == "container" else ()
        project_items = self.command(
            kind,
            "ls",
            "--quiet",
            *all_states,
            "--filter",
            f"label={PROJECT_LABEL}={self.project}",
            operation=f"enumerate lab {kind} resources",
        ).splitlines()
        reserved = {
            "volume": {f"{self.project}_data"},
            "network": {f"{self.project}_private", f"{self.project}_edge"},
        }.get(kind)
        if not reserved:
            return project_items
        existing = self.command(
            kind, "ls", "--format", "{{.Name}}", operation=f"check lab {kind} names"
        )
        return set(project_items) | (set(existing.splitlines()) & reserved)

    def verify_context(self):
        endpoint = self.command(
            "context",
            "inspect",
            self.docker_context,
            "--format",
            "{{.Endpoints.docker.Host}}",
            operation="inspect Docker endpoint",
        )
        if not endpoint.startswith("unix:///") and endpoint not in {
            "npipe:////./pipe/docker_engine",
            "npipe:////./pipe/dockerDesktopLinuxEngine",
        }:
            raise LabError(
                "Select a Docker context using a local Unix socket or Windows named pipe."
            )

    def assert_isolated(self, *, empty=False):
        if (
            not re.fullmatch(r"[0-9a-f]{12}", self.run_id)
            or self.project != f"syncops-pg-lab-{self.run_id}"
        ):
            raise LabError("Refusing an invalid lab project name")
        for kind in ("container", "volume", "network"):
            items = self.resources(kind)
            if empty and items:
                raise LabError(
                    "Generated lab project already owns resources; refusing to reuse it"
                )
            for item in items:
                self.check_owner(kind, item)

    def check_owner(self, kind, item):
        field = ".Labels" if kind in ("volume", "network") else ".Config.Labels"
        labels = json.loads(
            self.command(
                kind,
                "inspect",
                "--format",
                "{{json " + field + "}}",
                item,
                operation=f"check ownership of lab {kind}",
            )
        )
        if (
            not labels
            or labels.get(LABEL) != self.run_id
            or (kind != "image" and labels.get(PROJECT_LABEL) != self.project)
        ):
            raise LabError(
                "Refusing to mutate a resource without this run's exact ownership labels"
            )

    def up(self, *services, worker_count=None, dependencies=True):
        options = []
        if not dependencies:
            options.append("--no-deps")
        if worker_count:
            options.extend(("--scale", f"worker={worker_count}"))
        self.compose(
            "up",
            "-d",
            "--wait",
            "--wait-timeout",
            "100",
            *options,
            *services,
            timeout=480,
        )

    def stop(self, *services):
        self.assert_isolated()
        self.compose("stop", *services, timeout=80)

    def close(self):
        self.assert_isolated()
        self.compose("down", "--volumes", timeout=120)
        if self.command(
            "image", "ls", "--quiet", self.image, operation="find the lab image"
        ):
            self.check_owner("image", self.image)
            self.command(
                "image", "rm", self.image, operation="remove the owned lab image"
            )

    def api_origin(self):
        binding = self.compose("port", "api", "8000")
        if not re.fullmatch(r"127[.]0[.]0[.]1:[1-9][0-9]{0,4}", binding):
            raise LabError("The generated API binding must be IPv4 loopback")
        return f"http://{binding}"

    def containers(self, service, *, all_states=False):
        args = ("--all",) if all_states else ()
        ids = self.compose("ps", "--quiet", *args, service).splitlines()
        if any(not CONTAINER_ID.fullmatch(container_id) for container_id in ids):
            raise LabError("Compose returned an invalid container ID")
        return ids

    def crash(self):
        ids = self.containers("crash-worker")
        if len(ids) != 1:
            raise LabError("Expected one crash worker before the fault")
        self.check_owner("container", ids[0])
        self.command(
            "kill", "--signal", "KILL", ids[0], operation="kill the isolated worker"
        )
        exit_code = self.command(
            "wait",
            ids[0],
            operation="confirm the isolated worker exit code",
        )
        if exit_code != "137":
            raise LabError(f"Expected SIGKILL exit 137, received {exit_code}")

    def db_exec(self, *args, stdin=None, stdout=None, timeout=20):
        ids = self.containers("db")
        if len(ids) != 1:
            raise LabError("Expected exactly one running lab database container")
        return self.command(
            "exec",
            "-i",
            ids[0],
            *args,
            stdin=stdin,
            stdout=stdout,
            timeout=timeout,
            operation=f"PostgreSQL {args[0]}",
        )

    def sql(self, query, *, database=None):
        selected = self.database if database is None else database
        self.assert_database_name(selected, admin_allowed=True)
        return self.db_exec(
            "psql",
            "--no-psqlrc",
            "--quiet",
            "--no-align",
            "--tuples-only",
            "--set",
            "ON_ERROR_STOP=1",
            "--username",
            "postgres",
            "--dbname",
            selected,
            "--command",
            query,
        )

    def assert_database_name(self, name, *, admin_allowed=False):
        allowed = {
            f"syncops_lab_source_{self.run_id}",
            f"syncops_lab_restore_{self.run_id}",
        }
        if admin_allowed:
            allowed.add("postgres")
        if name not in allowed:
            raise LabError(
                "Refusing PostgreSQL access outside the generated lab databases"
            )

    def assert_source_owner(self):
        self.assert_isolated()
        self.assert_database_name(self.source)
        owner = self.sql(
            f"SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = '{self.source}'",
            database="postgres",
        )
        if owner != "syncops_lab":
            raise LabError(
                "The disposable source database is missing or has unexpected ownership"
            )

    def backup(self, archive):
        self.assert_source_owner()
        with archive.open("xb") as output:
            self.db_exec(
                "pg_dump",
                "--format=custom",
                "--username=postgres",
                "--no-owner",
                "--no-privileges",
                "--dbname",
                self.source,
                stdout=output,
                timeout=120,
            )
        with archive.open("rb") as data:
            self.db_exec("pg_restore", "--list", stdin=data)
            data.seek(0)
            checksum = hashlib.file_digest(data, "sha256").hexdigest()
        return archive.stat().st_size, checksum

    def drop_source(self):
        self.assert_source_owner()
        self.db_exec("dropdb", "--username=postgres", self.source)
        if self.sql(
            f"SELECT 1 FROM pg_database WHERE datname = '{self.source}'",
            database="postgres",
        ):
            raise LabError("The source database still exists after the isolated loss")

    def restore(self, archive):
        self.assert_isolated()
        self.assert_database_name(self.target)
        self.db_exec(
            "createdb",
            "--username=postgres",
            "--template=template0",
            "--owner=syncops_lab",
            self.target,
        )
        self.sql(
            f'REVOKE CONNECT ON DATABASE "{self.target}" FROM PUBLIC',
            database="postgres",
        )
        if self.sql("SELECT to_regclass('public.events')", database=self.target):
            raise LabError("The recovery target is not empty")
        with archive.open("rb") as data:
            self.db_exec(
                "pg_restore",
                "--single-transaction",
                "--exit-on-error",
                "--username=postgres",
                "--role=syncops_lab",
                "--no-owner",
                "--no-privileges",
                "--dbname",
                self.target,
                stdin=data,
                timeout=120,
            )
        self.database = self.target
        self.compose("run", "--rm", "--no-deps", "migrate", timeout=90)
