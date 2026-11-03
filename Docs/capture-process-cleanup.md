# Capture process cleanup and diagnostic reliability

The bounded adapter now preserves its first process failure while independently
attempting cleanup. A failed group/job termination no longer skips the parent
kill/wait or remaining pipe checks. A process that otherwise exits successfully
is refused if cleanup checks fail; full-size data remains incomplete and no
capture is retried automatically.

## Confirmed defect and unresolved original incident

An earlier macOS/Python 3.9 CI job expected `diagnostic-limit` but received
`artifact-io-failed`, accompanied by a subprocess ResourceWarning. The same
revision passed on rerun. That incident's exact cause is still unproven.

A separate deterministic fault-injection test established a related defect in
the previous supervisor: an error from group termination escaped the cleanup
block, replaced the diagnostic-limit exception, and skipped waiting for the
parent. The new tests inject termination, job-close, poll, pipe-close, thread-
startup and wait failures. Fixing this demonstrated failure class does not
establish that it caused the original macOS event.

The new CI stress run reproduced a concrete macOS `killpg` EPERM, followed by a
reaped parent with exit zero and finished pipes. Apple's
[XNU group-signal implementation](https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/bsd/kern/kern_sig.c)
filters zombies during group iteration and can return EPERM when no eligible
member is found. The observation is consistent with that exit race. The old
incident had no errno trace, so its exact historical cause remains unproven.

An EPERM is resolved only after the known parent has been reaped **and** a
signal-0 probe reports the group absent through ESRCH. The initial error and
its resolution remain recorded. A present group, a denied probe, an unconfirmed
parent wait or another termination error still fails cleanup. There is no
unconditional permission-error suppression and no repeated capture command.

## Preserved boundaries

The native arguments, read-only protocol, bundle pins, private staging,
capability validation, output sizes and no-retry policy are unchanged. Windows
still starts suspended, assigns a kill-on-close job, then resumes. POSIX still
starts a dedicated session/process group. Cleanup attempts job/group termination
and, if needed, termination of the known parent before waiting up to two seconds.
Each existing diagnostic drainer gets its short 0.2-second finish grace.

Diagnostic drains remain bounded: capability stdout/stderr 4 KiB, capture stdout
16 KiB and capture stderr 8 KiB. Counts saturate at the limit plus one; hashes
cover only the bounded prefix. Snapshots use a lock so count/hash fields are
consistent. A pipe-close error records failure and still signals drain completion.
Raw diagnostic text never enters process summaries.

The [Python subprocess contract](https://docs.python.org/3.9/library/subprocess.html#subprocess.Popen.wait)
distinguishes requesting termination from waiting for the child. The supervisor
keeps concurrent bounded drains rather than buffering unbounded output through
`communicate()`. OS calls, scheduling and filesystem operations do not provide a
hard real-time guarantee. This is not a sandbox for arbitrary untrusted binaries.

## Receipt process fields

Existing process summary fields remain. `cleanup` now records:

- `scope`: Windows job or POSIX process group;
- termination requests, parent wait result/exit code, and whether started drains finished;
- static `errors` and `failures` entries, interrupted status, and `checksPassed`.

`errors` lists unresolved cleanup problems. `failures` also preserves resolved
observations with `resolved`/`resolution` fields. `groupAbsenceCheckRequested`
and `groupAbsenceVerified` distinguish the post-reap probe from an assumption.

These are supervisor observations and API acknowledgements, not proof of physical
reset, complete adversarial descendant containment, USB recovery or normal boot.
`checksPassed` does not establish device identity or grant apply permission.

A normal process result is returned only after successful cleanup checks and
remaining cancellation/deadline checks. Primary failures keep their original
code even if cleanup also fails. With no earlier failure, cleanup problems yield
`process-cleanup-failed`; cleanup interruption yields `cancelled`. Spawn or
supervision OSError/ValueError/RuntimeError failures have static `systemError`
phase/type and an optional bounded numeric errno. Exception messages, paths,
commands, environment values and raw pipe contents are not copied into them.

The adapter's existing failure handling retains full/partial data as incomplete.
Its new regression verifies a full-size successful read is not admitted if its
cleanup fails. Historical successful receipts without these added fields retain
their existing operator-pinned semantics; this change is not provenance or
physical admission for any old receipt.

## Repeated synthetic acceptance

Python 3.9 CI runs 100 independent diagnostic-flood fixtures per OS after the
unit tests. Each uses the reviewed Python fixture launcher, not a native loader
or USB/device code. Every iteration must produce `diagnostic-limit`, keep capture
incomplete, retain bounded summaries, and pass parent/drain cleanup checks.
The first unexpected outcome stops the run; it is not retried. Sanitized code
file/function/line/type/errno observations are retained for investigation.

Stress artifacts include receipt hashes and reviewed source copies. Passing the
stress run does not resolve the original macOS incident's root cause. Actual C
host integration with USB/RCM link stubs also checks successful cleanup metadata.
No real hardware is used by these tests.

Continue with the [bounded adapter](bounded-capture-adapter.md) for the capture
contract and the [combined review](conversion-review-bundle.md) for offline
conversion preparation. No new device window, storage writer, deployment or
apply action is enabled by this reliability work.
