"""Run the SyncOps PostgreSQL reliability drill on a local Docker engine."""

import argparse
import json
import math
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from e2e.native_delivery import Lab as Api
from e2e.native_delivery import as_time

from .runtime import Lab, LabError

LOAD_EVENTS = 24
WORKER_COUNT = 2


def check(condition, message):
    if not condition:
        raise LabError(message)


def wait_until(read, accept, *, timeout, description, interval=0.2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = read()
        if accept(current):
            return current
        time.sleep(interval)
    raise LabError(f"Timed out waiting for {description}")


def login(lab):
    api = Api(lab.api_origin())
    api.login("admin", lab.admin_password)
    return api


def create_integration(api, run_id):
    return api.request(
        "POST",
        "/integrations",
        role="admin",
        status=201,
        data={
            "name": f"PostgreSQL reliability lab {run_id}",
            "description": "Synthetic delivery and backup acceptance.",
            "source": "crm",
            "destination": "erp",
            "timeout_seconds": 5.0,
            "max_attempts": 1,
            "retry_base_seconds": 1.0,
        },
    )["id"]


def submit(api, integration, nonce, *, crash_marker=None, latency_ms=0):
    payload = {"name": f"Synthetic company {nonce}", "reference": nonce}
    if crash_marker:
        payload["lab_crash"] = crash_marker
    return api.request(
        "POST",
        "/events",
        role="admin",
        key=nonce,
        status=202,
        data={
            "integration_id": integration,
            "event_type": "company.created",
            "payload": payload,
            "latency_ms": latency_ms,
        },
    )["id"]


def event_and_effects(lab, event_id):
    event_id = str(UUID(event_id))
    return json.loads(
        lab.sql(
            "SELECT json_build_object("
            "'status', e.status, 'lease_until', e.lease_until, 'attempt_count', e.attempt_count, "
            "'effects', (SELECT count(*) FROM mock_operations WHERE event_id = e.id)) "
            f"FROM events e WHERE e.id = '{event_id}'"
        )
    )


def delivered(api, event_id, timeout=75):
    return wait_until(
        lambda: api.detail(event_id, role="admin"),
        lambda event: event["status"] in {"succeeded", "dead_letter"},
        description="the event to reach a terminal state",
        timeout=timeout,
    )


def crash_check(lab, api, integration):
    event_id = submit(api, integration, f"{lab.run_id}-crash", crash_marker=lab.run_id)
    at_commit = wait_until(
        lambda: event_and_effects(lab, event_id),
        lambda event: event["effects"] == 1,
        description="the mock's committed effect",
        timeout=15,
    )
    check(
        at_commit["status"] == "processing" and at_commit["attempt_count"] == 1,
        "The mock committed outside the intended processing window",
    )
    started = time.monotonic()
    lab.crash()
    after_crash = event_and_effects(lab, event_id)
    check(
        after_crash == at_commit,
        "The worker changed the event before the crash took effect",
    )

    lab.up("worker", worker_count=WORKER_COUNT, dependencies=False)
    recovered = delivered(api, event_id)
    attempts = recovered["attempts"]
    check(
        recovered["status"] == "succeeded"
        and [attempt["status"] for attempt in attempts] == ["interrupted", "succeeded"]
        and as_time(attempts[1]["started_at"]) >= at_commit["lease_until"]
        and event_and_effects(lab, event_id)["effects"] == 1,
        "Lease reclaim or the single business effect could not be verified",
    )
    return event_id, {
        "worker_signal": "SIGKILL",
        "observed_exit_code": 137,
        "committed_effects_before_worker_exit": at_commit["effects"],
        "persisted_status_after_worker_exit": after_crash["status"],
        "final_effect_count": 1,
        "attempt_outcomes": ["interrupted", "succeeded"],
        "reclaim_after_lease_expiry": True,
        "recovery_observed_seconds": round(time.monotonic() - started, 3),
    }


def batch_outcomes(lab, event_ids):
    ids = ",".join(f"'{UUID(event_id)}'" for event_id in event_ids)
    return json.loads(
        lab.sql(
            "SELECT COALESCE(json_agg(json_build_object("
            "'id', e.id, 'state', e.status, 'attempt_count', e.attempt_count, 'created', e.created_at, "
            "'started', a.started_at, 'finished', a.finished_at, "
            "'effect_count', (SELECT count(*) FROM mock_operations WHERE event_id = e.id))), '[]') "
            "FROM events e LEFT JOIN attempts a ON a.event_id = e.id AND a.number = 1 "
            f"WHERE e.id IN ({ids})"
        )
    )


def percentile(samples, quantile):
    ordered = sorted(samples)
    return round(ordered[math.ceil(quantile * len(ordered)) - 1], 3)


def distribution(samples):
    return {
        "p50_ms": percentile(samples, 0.50),
        "p95_ms": percentile(samples, 0.95),
        "max_ms": round(max(samples), 3),
    }


def worker_assignments(lab, event_ids):
    by_worker = []
    for container in lab.containers("worker"):
        output = lab.command(
            "logs",
            "--tail",
            "512",
            container,
            operation="read lab worker delivery logs",
        )
        messages = [
            json.loads(line) for line in output.splitlines() if line.startswith("{")
        ]
        ids = [
            row["event_id"]
            for row in messages
            if row.get("message") == "attempt_finished"
            and row.get("event_id") in event_ids
            and row.get("status") == "succeeded"
        ]
        by_worker.append(ids)
    check(
        len(by_worker) == WORKER_COUNT
        and all(by_worker)
        and Counter(event_id for ids in by_worker for event_id in ids)
        == Counter(event_ids),
        "The two lab worker logs did not account for each event exactly once",
    )
    return by_worker


def load_check(lab, api, integration):
    started = time.monotonic()

    def send(index):
        return index, submit(
            api, integration, f"{lab.run_id}-load-{index}", latency_ms=250
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        submitted = list(
            pool.map(send, [index for index in range(LOAD_EVENTS) for _ in range(2)])
        )
    duplicate_groups = {
        index: {value for slot, value in submitted if slot == index}
        for index in range(LOAD_EVENTS)
    }
    check(
        all(len(group) == 1 for group in duplicate_groups.values()),
        "A duplicate produced a new event ID",
    )
    ids = set().union(*duplicate_groups.values())
    check(
        len(ids) == LOAD_EVENTS, "Different idempotency keys collapsed into one event"
    )
    rows = wait_until(
        lambda: batch_outcomes(lab, ids),
        lambda batch: (
            len(batch) == LOAD_EVENTS
            and all(row["state"] in {"succeeded", "dead_letter"} for row in batch)
        ),
        description="the bounded batch to finish",
        timeout=60,
    )
    elapsed = time.monotonic() - started
    check(
        all(
            row["state"] == "succeeded"
            and row["attempt_count"] == row["effect_count"] == 1
            for row in rows
        ),
        "One or more load events had a failed, repeated, or missing operation",
    )
    by_worker = worker_assignments(lab, ids)
    by_id = {row["id"]: row for row in rows}
    overlap = any(
        max(by_id[first]["started"], by_id[second]["started"])
        < min(by_id[first]["finished"], by_id[second]["finished"])
        for first in by_worker[0]
        for second in by_worker[1]
    )
    check(
        overlap,
        "The persisted attempts did not overlap between the two worker containers",
    )
    queue = [(row["started"] - row["created"]) * 1000 for row in rows]
    delivery = [(row["finished"] - row["created"]) * 1000 for row in rows]
    check(
        min(queue) >= 0 and min(delivery) >= 0,
        "Invalid event timing in the load snapshot",
    )
    return {
        "requests": len(submitted),
        "unique_events": len(ids),
        "success_rate": 1.0,
        "duplicate_business_effects": 0,
        "events_by_worker": sorted(map(len, by_worker)),
        "overlapping_worker_attempts": True,
        "elapsed_seconds": round(elapsed, 3),
        "observed_events_per_second": round(LOAD_EVENTS / elapsed, 3),
        "queue_wait": distribution(queue),
        "enqueue_to_terminal": distribution(delivery),
    }


def fingerprint(lab):
    tables = ("events", "attempts", "mock_operations", "integrations", "audit")
    entries = ", ".join(
        f"'{name}', (SELECT json_build_object('count', count(*), 'digest', "
        f"md5(COALESCE(string_agg(to_jsonb(t)::text, E'\\n' ORDER BY to_jsonb(t)::text), ''))) "
        f"FROM {name} AS t)"
        for name in tables
    )
    return json.loads(lab.sql(f"SELECT json_build_object({entries})"))


def backup_restore_check(lab, api, integration, crash_event, archive):
    lab.stop("crash-worker", "worker", "gate")
    baseline = fingerprint(lab)
    started = time.monotonic()
    size, checksum = lab.backup(archive)
    completed = time.monotonic()
    check(archive.stat().st_size > 0, "The PostgreSQL backup is empty")

    # Workers are stopped to establish an exact acknowledged event boundary.
    canary = submit(api, integration, f"{lab.run_id}-post-backup")
    check(
        event_and_effects(lab, canary)["status"] == "queued",
        "Expected a queued post-backup canary",
    )
    lab.stop("api", "mock")
    check(
        fingerprint(lab)["events"]["count"] == baseline["events"]["count"] + 1,
        "The isolated dataset did not have exactly one acknowledged post-backup event",
    )

    outage = time.monotonic()
    lab.drop_source()
    lab.restore(archive)
    restored = fingerprint(lab)
    check(
        restored == baseline,
        "The restored database fingerprints differ from the backed up dataset",
    )
    lab.up("api", "mock", dependencies=False)
    lab.up("worker", worker_count=WORKER_COUNT, dependencies=False)
    restored_api = login(lab)
    restored_event = restored_api.detail(crash_event, role="admin")
    check(
        restored_event["status"] == "succeeded"
        and [row["status"] for row in restored_event["attempts"]]
        == ["interrupted", "succeeded"]
        and event_and_effects(lab, crash_event)["effects"] == 1,
        "Expected the restored API to retain the recovered crash event and attempts",
    )
    restored_api.request("GET", f"/events/{canary}", role="admin", status=404)
    verification = submit(restored_api, integration, f"{lab.run_id}-restore-probe")
    check(
        delivered(restored_api, verification)["status"] == "succeeded"
        and event_and_effects(lab, verification)["effects"] == 1,
        "The restored stack did not deliver a new event",
    )
    rto = time.monotonic() - outage
    restored_api.logout("admin")
    return {
        "archive_bytes": size,
        "archive_sha256": checksum,
        "backup_seconds": round(completed - started, 3),
        "source_database_removal_confirmed": True,
        "restored_table_counts": {name: row["count"] for name, row in restored.items()},
        "restored_fingerprints_match": True,
        "restored_api_and_new_delivery_verified": True,
        "observed_recovery_time_seconds": round(rto, 3),
        "seconds_from_completed_backup_to_data_loss": round(outage - completed, 3),
        "acknowledged_records_after_backup_missing_on_restore": 1,
    }


def run(lab, scratch):
    lab.verify_context()
    lab.assert_isolated(empty=True)
    print(f"Starting isolated project {lab.project}.", flush=True)
    try:
        lab.compose("config", "--quiet")
        lab.compose("build", "api", timeout=480)
        lab.up("db", "migrate", "mock", "gate", "api", "crash-worker")
        api = login(lab)
        integration = create_integration(api, lab.run_id)
        print("Checking effect-commit crash and lease recovery.", flush=True)
        crash_event, crash = crash_check(lab, api, integration)
        print("Checking concurrent delivery and duplicate exclusion.", flush=True)
        load = load_check(lab, api, integration)
        print(
            "Checking logical backup, isolated loss and service restoration.",
            flush=True,
        )
        recovery = backup_restore_check(
            lab, api, integration, crash_event, scratch / "reliability.dump"
        )
        return {
            "project": lab.project,
            "postgresql": lab.sql("SHOW server_version"),
            "compose": lab.compose("version", "--short"),
            "crash": crash,
            "load": load,
            "backup_and_restore": recovery,
        }
    finally:
        lab.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence", type=Path, help="Write verified evidence to a new JSON file"
    )
    args = parser.parse_args()
    if args.evidence and args.evidence.exists():
        parser.error("The evidence path already exists")
    try:
        with TemporaryDirectory(prefix="syncops-postgres-reliability-") as temporary:
            scratch = Path(temporary)
            evidence = run(Lab(scratch), scratch)
        rendered = json.dumps(evidence, indent=2) + "\n"
        if args.evidence:
            with args.evidence.open("x", encoding="utf-8") as output:
                output.write(rendered)
        print(rendered, end="")
    except (LabError, AssertionError) as error:
        parser.exit(1, f"PostgreSQL reliability drill failed: {error}\n")


if __name__ == "__main__":
    main()
