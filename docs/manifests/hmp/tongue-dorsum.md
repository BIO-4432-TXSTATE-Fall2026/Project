# `hmp/tongue-dorsum`

HMP1 shotgun reads from the tongue dorsum: the oral half of the genuine-population side
of H1, and the deepest oral site. **Listing only:** reads are streamed, never stored.

```sh
pixi run new hmp/tongue-dorsum --dataset=hmp --prefix=HHS/HMASM/WGS/tongue_dorsum \
  "--include=SRS*.tar.bz2" \
  --description="HMP1 WGS reads, tongue dorsum; listing only, reads are streamed"
pixi run sync manifests/hmp/tongue-dorsum.json --no-download
```

128 samples, one `SRS*.tar.bz2` each, 760 GB: median 6.1 GB, range 2.0–9.0 GB. Uploaded
2013-09-23 to 2013-09-25; listed 2026-09-17.

Chosen over `buccal_mucosa` for depth: most buccal samples are shallow (median 0.7 GB).

## Used by

- `data/derived/hmp-sra-runs.tsv`, through `extract --from-lock`
  ([`hmp-sra-runs.md`](../../data/derived/hmp-sra-runs.md)).

## Traps

Those of [`stool.md`](stool.md): never sync without `--no-download`, mates by suffix,
60–100 bp reads, several runs per sample.
