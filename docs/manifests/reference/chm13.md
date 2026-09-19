# `reference/chm13`

The complete human reference, T2T-CHM13 v2.0. It is a **screen**, not a data source: no
human reads are analyzed and nothing human is spiked into anything. It answers one
question — which TR loci in the catalog also occur in the human genome — because those
loci will collect human reads and report alleles for a bacterium that was never there.

```sh
pixi run new reference/chm13 --dataset=human-pangenomics \
  --prefix=T2T/CHM13/assemblies/analysis_set --include='chm13v2.0.fa.gz*' \
  "--description=T2T-CHM13 v2.0 analysis set: the complete human reference used to \
screen TR catalog loci and reference genomes for human sequence"
pixi run sync manifests/reference/chm13.json
```

2 files, 982 MB: `chm13v2.0.fa.gz` and its `.gzi` bgzip index, from
`s3://human-pangenomics/T2T/CHM13/assemblies/analysis_set/`, dataset
`human-pangenomics`. Last modified 2022-09-28. **Sync on a compute node.**

## Why CHM13 and not GRCh38

The `slacken` bucket carries GRCh38.p14 in its standard library, which would save a
dataset. It is the wrong reference for this particular job. GRCh38 leaves most
centromeric, acrocentric and satellite sequence as modelled gaps, and those regions are
where the human genome's own tandem repeats live. Screening a TR catalog against a
reference whose repeat regions are missing would clear loci that do match human.
CHM13 v2.0 is gapless, so a locus that survives the screen survives it for a reason.

## Uses

- **Catalog screen.** Any TR locus inTRuder finds in a bacterial reference genome that
  also matches CHM13 is dropped, or flagged, before allele calling.
- **Misclassified genera.** The genomes in
  [`contaminants/misclassified`](../contaminants/misclassified.md) are screened directly:
  how much human sequence sits in the reference genomes of the genera Gihawi et al.
  attribute to human-read misclassification.

## Traps

- **Not a contaminant.** Human DNA in these datasets is the sample's own, misclassified.
  Kit contamination is a different failure with a different fix, which is why this spec
  is under `reference/` and not `contaminants/`.
- **Soft-masked.** Repeats are lowercase, not removed. Any tool that skips lowercase by
  default would ignore precisely the regions this screen exists to find; case has to be
  folded, or masking disabled, before comparing.
- **chrY is not CHM13.** The CHM13 cell line has no Y, so `chm13v2.0.fa.gz` carries
  HG002's chrY. The variants beside it are `_noY` (CHM13 sequence only), `_maskedY`
  (chrY PARs hard masked) and `_maskedY_rCRS`; the plain assembly is the right one for a
  sequence-level screen.
- **HMP reads are already human-screened.** HMP removed human reads from `HHS/HMASM/WGS/`
  before release, so this is not a host-filtering step for them. It guards the catalog.

## Sources

- [Nurk et al. 2022, Science (T2T-CHM13)](https://doi.org/10.1126/science.abj6987)
- [Human Pangenome Reference Consortium, Registry of Open Data on AWS](https://registry.opendata.aws/hpgp-data/)
