# `hmp/bucket`

A listing of all of `s3://human-microbiome-project`, recorded without downloading anything.
It is where the sizes and counts in [`../../data/HMP_pilot.md`](../../data/HMP_pilot.md)
come from, and how the other `hmp/` specs were scoped before any were synced.

```sh
pixi run new hmp/bucket --dataset=hmp --prefix= \
  --description="Full listing of s3://human-microbiome-project"
pixi run sync manifests/hmp/bucket.json --no-download
```

85,375 objects, 5.9 TB, last modified 2013-08-14 to 2014-05-19; listed 2026-09-15.

## Traps

- **Never sync it without `--no-download`.** That would download 5.9 TB. The lock is the
  point: every record has a size and ETag, and no `sha256`, since nothing was fetched.
- **The lock is large**, one record per object. Query it rather than reading it, e.g. the
  per-prefix totals in the pilot doc.
- **It is a snapshot of an archive.** Nothing has changed since 2014, so a re-listing that
  reports changes is worth looking at, not just accepting.
