# Factory templates

Shapes only. The rules for each live in `../SKILL.md`.

## Job file

`jobs/pending/<unit>-<what>.sh`:

```bash
# timeout: 1800
scripts/gate.sh ../lead full
```

Header lines first, then one command: output to stdout, its real exit status, never a closing `exit 0`. Header keys:

- `# timeout: <secs>`: the job's hard limit. Missing means `HEAVY_TIMEOUT_MAX`; over it, the runner refuses the job.
- `# finish: yes`: the job belongs to `finish`. Only these jobs still start or complete during `FACTORY_FINISH_GRACE` after the deadline.

## session-state.md

```markdown
Status: building
human head: <sha>
lead head: <sha>

## Queue
- <unit-id> <one line> | weight: <full|middle|plain> | stage: <stage> | job: <name or none>

## Waiting
- <unit-id> D-NNN: <variants>

## Done
- <unit-id> lead <sha>
- pause-<n> <what changed>
```
