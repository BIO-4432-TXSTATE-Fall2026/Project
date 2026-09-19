# `hmp/reference-genomes-target`

Isolate genomes for the six target genera, from which inTRuder builds the TR locus
catalog: where the pipeline looks for repeats.

```sh
pixi run new hmp/reference-genomes-target --dataset=hmp --prefix=reference_genomes \
  --include='19051/*.nuc.fsa' ...  # one --include per genome directory, 198 in all
  --exclude='64737/64737.AFPX01000001-AFPX01000086.nuc.fsa' \
  --description="HMP reference genomes for target genera (Streptococcus, Prevotella, \
Fusobacterium, Veillonella, Campylobacter, Porphyromonas); nucleotide FASTA, GenBank \
where no usable FASTA"
pixi run sync manifests/hmp/reference-genomes-target.json
```

The spec holds the full list of 198 globs; the command above, with all of them, reproduces
it byte for byte. The directories are those whose GenBank `ORGANISM` line names a target genus. That
includes *S. infantis* `158721`, which
[`reference-genomes-list.md`](reference-genomes-list.md) does not list.

316 files, 760 MB, from 198 genomes. Last modified 2013-08-14 to 2013-08-15; synced
2026-09-17.

| Genus         | Genomes | Notable species                                |
| ------------- | ------- | ---------------------------------------------- |
| Streptococcus | 112     | S. sanguinis (21), S. mitis (9), S. oralis (8) |
| Prevotella    | 35      | P. melaninogenica, P. denticola, P. buccae     |
| Fusobacterium | 27      | F. nucleatum (4), F. periodonticum (2)         |
| Veillonella   | 11      | V. parvula, V. atypica                         |
| Campylobacter | 7       | C. showae, C. rectus, C. gracilis              |
| Porphyromonas | 6       | P. gingivalis (2), P. endodontalis             |

## Traps

- **Two FASTAs for most genomes.** 118 genomes have both a contig and a scaffold
  `.nuc.fsa`, and both are synced. Pick one per genome when cataloging, or loci are
  counted twice.
- **GenBank where FASTA fails.** *V. dispar* `30491` has no FASTA and *Fusobacterium* sp.
  `50399`'s `.nuc.fsa` is empty, so both are synced as `.nuc.gbk`.
- **One excluded file.** *P. nigrescens* `64737`'s contig FASTA is access denied; only its
  scaffold FASTA is synced.
- **FASTA only.** Most of `reference_genomes/`'s 129 GB is BLAST index files, which the
  per-directory globs leave out.
