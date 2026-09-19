# `hmp/reference-genomes-list`

The bucket's own index of `reference_genomes/`: `list.json`, mapping each numeric genome
directory to its organism, body site, and file paths. It is how the directories in
[`reference-genomes-target.md`](reference-genomes-target.md) were chosen.

```sh
pixi run new hmp/reference-genomes-list --dataset=hmp --prefix=reference_genomes \
  --include=list.json \
  --description="HMP reference genome ID to organism and body site listing (list.json)"
pixi run sync manifests/hmp/reference-genomes-list.json
```

1 file, 1.8 MB. Last modified 2013-08-15; synced 2026-09-17.

## Contents

A JSON array, one record per directory: `id`, `organism`, `body_site`, and paths and sizes
for the contig and scaffold `.nuc.fsa`, `.gbk`, `.pep.fsa`, and `.cds.fsa`.

## Traps

- **Not complete.** It lists 1,120 of the 1,128 directories. The 8 added later are
  missing: `158721` (*S. infantis* ATCC 700779), `169453`–`169456` (*K. pneumoniae*),
  `169467` and `169468` (*P. mirabilis*), and `170040` (*Capnocytophaga* sp. oral taxon
  412).
- **Not every genome has a FASTA.** 22 have only a `.gbk`, and a file that exists is not
  always readable (`75129`'s `.gbk` is access denied). Check against `hmp/bucket` before
  selecting.
- Every listed organism does match the `ORGANISM` line of its directory's GenBank header.
