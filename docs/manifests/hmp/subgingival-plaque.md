# `hmp/subgingival-plaque`

HMP1 shotgun reads from subgingival plaque: the **pilot**. Small, and enriched for the
target genera *Fusobacterium* and *Porphyromonas*, so the streaming locus filter is tested
here before it runs on `hmp/stool` and `hmp/tongue-dorsum`. **Listing only.**

```sh
pixi run new hmp/subgingival-plaque --dataset=hmp \
  --prefix=HHS/HMASM/WGS/subgingival_plaque "--include=SRS*.tar.bz2" \
  --description="HMP1 WGS reads, subgingival plaque (pilot); listing only, reads are streamed"
pixi run sync manifests/hmp/subgingival-plaque.json --no-download
```

7 samples, 10.2 GB: median 1.7 GB, range 0.7–2.0 GB. Uploaded 2013-09-22; listed
2026-09-17.

## Used by

- `data/derived/hmp-sra-runs.tsv`, through `extract --from-lock`
  ([`hmp-sra-runs.md`](../../data/derived/hmp-sra-runs.md)).
- The read-length check in [`stool.md`](stool.md): the first 100k reads of three of these
  samples are Illumina GAIIx trimmed to 60–100 bp, median 97–100.

## Traps

- **Seven samples is too few for entropy.** It proves the pipeline runs; it cannot say
  anything about H1.
- Otherwise those of [`stool.md`](stool.md).
