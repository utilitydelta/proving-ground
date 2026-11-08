---
status: decided
decided_by: bot
touches: product/kvcore.py::read_record, product/kvcore.py::open_log
revisit_when: a disk fault model beyond prefix-torn writes lands in the sim (sector reordering, misdirected writes)
session: session-v1
replaced_by:
---
# D-001: a bad record at the log tail is dropped as a torn write; a bad record with bytes after it is refused

A crash mid-append leaves a prefix of the last record, so recovery must accept a short or bad tail or no store survives its first power cut. Anything bad with valid-looking bytes after it cannot come from a torn append and is refused with `CorruptLog`, naming the offset.

Alternatives:

1. Refuse every bad record. Safe against silent loss, but every crash mid-append needs an operator. Rejected.
2. Drop every bad record and everything after it. Recovers always, and silently throws away acked writes on bitrot. Rejected: plant `accept_mid_log_corruption` is exactly this, and the sim catches it on 1954 of 2000 seeds.
3. Tail drops, mid-log refuses, header checksum separate from body checksum. Chosen. The header checksum stops a flipped length field from making a mid-log record look like a short tail.

The cost: bitrot in the last record's body, after it was acked, looks like a torn write and is dropped. That acked write is lost silently. The sim never injects bitrot into the last record, so this is a known gap, not a covered case.

Evidence: `python3 -m unittest test_torn_tail` (rows `tail last byte lost`, `mid-log body byte flipped`, `tail header byte flipped`); `python3 plant_check.py`.

## History
- 2026-11-09 session-v1: decided by bot while writing the recovery scan; provisional until the human rules on it.
