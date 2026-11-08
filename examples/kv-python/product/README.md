# product: stands in for the human repo

In real use this is the human's code: agents read, build and test it, and never write here.

`kvcore.py` is a sans-IO log-structured KV core. `open_log(bytes)` recovers state, `put`/`delete` return `Append` and `Fsync` effects, `complete()` takes `AppendDone`/`FsyncDone` and returns the acked ops. A bad record at the tail is a torn write and gets truncated; a bad record with bytes after it raises `CorruptLog`.
