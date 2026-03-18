# Review Queue And Task State Machine

## Current Workflow

ClinicalClaw now treats review as a strict workflow instead of a loose status label.

Allowed transitions:

- `draft -> queued`
- `queued -> running`
- `queued -> failed`
- `running -> in_review`
- `running -> approved`
- `running -> failed`
- `in_review -> approved`
- `in_review -> rejected`
- `approved -> filed`

Terminal states:

- `rejected`
- `filed`
- `failed`

## Review Queue

The review queue is the set of `TaskRunRecord` items currently in `in_review`.

Current service helpers:

- `list_review_queue()`
- `approve_task()`
- `reject_task()`
- `file_task()`
- `transition_task()`

## Artifact Status Synchronization

Task transitions now update artifact state automatically:

- `in_review` -> artifact `in_review`
- `approved` -> artifact `approved`
- `filed` -> artifact `exported`
- `rejected` -> artifact `draft`

## Audit Behavior

Every review or filing transition writes an `AccessEventRecord`, so the queue is not just visible state; it is auditable state.
