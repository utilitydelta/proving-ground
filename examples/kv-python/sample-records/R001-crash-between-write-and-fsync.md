---
likelihood: 3
consequence: 3
score: 9
control: ack only on FsyncDone; recovery keeps any prefix of unacked ops, the client retries what it was not told succeeded
status: controlled
decision: D-001
session: session-v1
evidence: KV_PLANT=ack_before_fsync python3 harness/sim.py --seeds 200
---
# R001: the process crashes after the record is written but before fsync completes

1. Client calls `put("a", "1")`. The core returns `Append` then `Fsync`.
2. The append lands in the page cache. The process dies before the fsync completes.
3. On restart the record may be gone, whole, or torn, depending on what the kernel flushed.

Likelihood 3: one ordinary crash at the wrong moment, no second fault. Consequence 3 with the control: the client saw no ack, so it gets an error and must retry; the retry may write a value that is already there. Without the control (ack on append) the consequence is 5, acked data lost, which is what the planted mutation shows: `acked write lost: recovered 12 ops of history, 13 were acked`.

The control costs no state: the core already tracks each pending op's end offset to know which fsync covers it. Exactly-once retries would need a client id and sequence per write, a durable field per client; at a score of 9 the human can accept the retry ambiguity by name instead.

## History
- 2026-11-09 session-v1: raised by the sim's crash_before_fsync fault, scored 3x3, control is the existing ack-on-fsync rule.
