# Validation Results: IntelliQ Session Lifecycle

**Date**: 2026-08-23

## Automated Validation

```text
.venv/bin/python -m pytest backend/tests -q
52 passed in 2.68s

PYTHONPYCACHEPREFIX=/tmp/smart-eval-pyc .venv/bin/python -m compileall -q backend
passed

bash -n *.sh
passed

git diff --check
passed
```

The automated suite covers Session creation success and business failure, real provider Session ID propagation, stateful Chat ID validation, cleanup success/failure, cleanup persistence, migration fields, task outcome preservation, cancellation callbacks, and RAGFlow regression behavior.

## Stateful Mock

`backend/tests/mock_intelliq_server.py` now maintains created Sessions, active Session IDs, deletion batches, and request audit records. The lifecycle unit/integration tests verify that Agent Chat only accepts created Session IDs and cleanup batches contain only created IDs.

## Controlled IntelliQ Smoke Test

Not run on August 23, 2026 because no disposable IntelliQ tenant and test-only API Key were supplied for this run. This is the only remaining external validation boundary. Follow `quickstart.md` before marking a production tenant validated.

No real API Key, Authorization header, tenant identifier, or real Session ID was written to this validation record.

## Local Stateful Mock HTTP Check

The local mock was started on August 23, 2026 and the following sequence passed without credentials:

```text
POST /api/v1/sessions
-> POST /api/v1/agent-chat/{returned-session-id}
-> SSE done=true
-> DELETE /api/v1/sessions/batch
-> success=true
```

The mock returned `mock-session-1` for this local validation. This identifier is synthetic and carries no external tenant or credential information.

## Container Build

```text
docker build -t smart-eval:intelliq-session-lifecycle-test .
passed
```

The Dockerfile compiled the updated provider, evaluation service, database model, and active Flask route modules successfully.
