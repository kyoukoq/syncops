# SyncOps engineering guide

Read `PROJECT_STATUS.md`, `PROJECT_SPEC.md`, and `git status --short --branch` at the start of a session. Follow `ROADMAP.md` and take the next verifiable vertical slice. Write engineering artifacts in English and communicate with the Product Owner in Ukrainian.

## Boundaries

- Keep the additional budget at $0. Verify the official terms before adopting external services. Use local infrastructure and synthetic data, with no corporate accounts, systems, or credentials.
- Use the documented trust boundaries. Validate inputs, authorize writes, keep secrets untracked, redact logs, and refuse user-supplied destination origins. Keep services local by default.
- Preserve existing work. Use feature branches, isolated worktrees where available, and Conventional Commits. Avoid unnecessary dependencies and prepare pull requests from verified changes.

## Ownership and coordination

| Role | Ownership |
| --- | --- |
| Lead | Shared API contracts, integrations, merge decisions, acceptance and status |
| Architect | Design review, ADRs and contracts assigned by the lead |
| Backend | `backend/` and backend test suites |
| Frontend | `frontend/` and component tests |
| Platform | `deploy/`, `scripts/`, Compose and workflows |
| QA | Independent end-to-end and recovery acceptance |
| Security | Read-only defensive review unless assigned remediation |
| Documentation | Assigned files in `docs/` and root documentation |

For material milestones, define acceptance and contracts before delegating independent tasks to native Codex agents. Limit execution to three subagents, avoid recursion and reserve QA and security reviews for agents independent from the implementation. Use separate worktrees for changes likely to overlap and explicitly assign non-overlapping paths when sharing a worktree. The lead integrates and verifies the result.

## Definition of done

Trace each feature through its normal entry point. Test success, authorization, retries, partial failure, duplicate delivery and recovery as relevant. Run migration, build, lint, type and deployment checks where supported. Record actual commands, results and blockers in `PROJECT_STATUS.md`. Keep screenshots and docs consistent with the running product. Scan tracked content for secrets before publishing. Document substantially changed decisions in an ADR and document any unverified capabilities before release.
