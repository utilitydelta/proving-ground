---
name: present
description: Choose how to surface a session's results beyond report.md. Use at the end of a Task, Tend, Factory run or long debrief, or when the human asks for a podcast, audio, diagram or video of results.
---

# Present

Default is `report.md`. Offer more only when the content earns it; never produce media unasked, except a diagram when structure is the finding.

| Content | Use |
|---|---|
| Most results | `report.md` |
| The mental model behind a build the human will rewrite | `human-replay:podcast` |
| A relationship or flow: time, control, data, ownership | `human-replay:diagram`. A list of facts is a table, not a diagram |
| A mechanism that only makes sense in motion: a race, a recovery order | `human-replay:explainer-video` |

Media goes in the session's `media/`. Git keeps small text a human reads (diagram sources, SVGs); audio, video and renders stay local and gitignored. `report.md` says what was made and the command that rebuilds it.
