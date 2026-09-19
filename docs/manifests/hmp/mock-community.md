# `hmp/mock-community`

Genomes of the HMP mock community strains: known identities for checking catalog loci
and allele calls before either is trusted on real samples.

```sh
pixi run new hmp/mock-community --dataset=hmp --prefix=HHS/HMMC \
  "--include=*/*.nuc.fsa.bz2" --include=HMPRP_sT1-Mock.pdf \
  --description="HMP mock community strain genomes (nucleotide FASTA) and strain sheet"
pixi run sync manifests/hmp/mock-community.json
```

23 files, 27 MB: one `*.nuc.fsa.bz2` per strain (22) and the strain sheet
`HMPRP_sT1-Mock.pdf`. Uploaded 2014-03-17; synced 2026-09-17.

## Contents

- 21 bacteria and archaea plus *Candida albicans*.
- Of the target genera only *Streptococcus* is present: *S. agalactiae*, *S. mutans*,
  *S. pneumoniae*.
- Genomes only. No mock community reads were found in the bucket, so checking the allele
  caller means simulating reads from these.

## Traps

- **A misnamed file.** `Pseudomonas_aeruginosa_ATCC_47085/331.AE017283.nuc.fsa.bz2` carries
  *P. acnes*'s accession but holds *P. aeruginosa* PAO1 (`AE004091.2`). Every other
  FASTA matches its strain directory.
- The `hmmcref_all.*.tar.gz` bundles duplicate the per-strain files and are left out.
