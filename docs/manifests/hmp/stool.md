# `hmp/stool`

HMP1 shotgun reads from stool: the gut half of the genuine-population side of H1, and
samples whose sequencing centers are H2's "should not cluster" batches. **Listing only:**
the reads are streamed from S3 through a locus filter on the cluster, never stored.

```sh
pixi run new hmp/stool --dataset=hmp --prefix=HHS/HMASM/WGS/stool \
  "--include=SRS*.tar.bz2" \
  --description="HMP1 WGS reads, stool; listing only, reads are streamed"
pixi run sync manifests/hmp/stool.json --no-download
```

139 samples, one `SRS*.tar.bz2` each, 998 GB: median 7.3 GB, range 1.5–9.9 GB. Uploaded
2013-09-19 to 2013-09-22; listed 2026-09-17.

## Used by

- `data/derived/hmp-sra-runs.tsv`: the lock's keys name the samples that
  `extract --from-lock` keeps ([`hmp-sra-runs.md`](../../data/derived/hmp-sra-runs.md)).

## Traps

- **Do not sync without `--no-download`.** 998 GB is not meant to land anywhere.
- **Tarball layout.** Each holds `.1`, `.2`, and `.singleton` FASTQ, in varying order,
  so find the mates by suffix, not position.
- **Short reads.** Illumina GAIIx trimmed to 60–100 bp (median 97–100), which caps the
  repeat length a single read can span. Checked on `hmp/subgingival-plaque`; the same
  pipeline produced every body site.
- **Several runs per sample.** Most samples were sequenced in more than one SRA run, so
  pool runs per sample before using depth as a covariate.
