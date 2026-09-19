# `contaminants/misclassified`

Genomes for the four genera Gihawi et al. (2023) attribute to human reads counted as
bacteria, not to reagent contamination. They are here to be screened against the human
reference: if a TR locus cataloged in one of these genomes also matches
[`reference/chm13`](../reference/chm13.md), human reads can land on it and produce
allele calls for an organism that was never in the sample.

```sh
pixi run new contaminants/misclassified --dataset=slacken \
  --accession=GCF_000026745.1 ...  # one --accession per genome, 10 in all
  --description="Complete RefSeq genomes for the genera Gihawi et al. (2023) attribute \
to human-read misclassification: Streptococcus, Mycobacterium and Staphylococcus, three \
species each, and Waddlia chondrophila"
pixi run sync manifests/contaminants/misclassified.json
```

10 genomes, about 32 MB, complete RefSeq assemblies from the `slacken` library.
**Sync on a compute node**, as for [`kit`](kit.md): the first slacken sync fetches about
725 MB of library index files.

| Genus | Genomes |
| ----- | ------- |
| *Streptococcus* | *S. suis* BM407, *S. pseudopneumoniae* IS7493, *S. anginosus* |
| *Mycobacterium* | *M. tuberculosis* H37Rv, *M. kansasii* ATCC 12478, *M. canettii* CIPT 140010059 |
| *Staphylococcus* | *S. aureus* NCTC 8325, *S. argenteus*, *S. xylosus* |
| *Waddlia* | *W. chondrophila* WSU 86-1044, the only complete genome in the library |

## Why these are not spike-ins

[`gihawi-supplement.md`](gihawi-supplement.md) explains the three ways Gihawi et al.
reject a taxon. These four genera are the first way: Poore et al. reported hundreds of
thousands of reads per sample, the re-analysis found tens, and the cause was human
sequence left in draft bacterial genomes. That is a database failure, not kit
contamination, so these genera have no place in the spike-in benchmark
([`kit.md`](kit.md)) — they test whether the TR catalog itself can be fooled.

## Traps

- **Different genomes from the ones that caused the problem.** Poore et al.'s database
  held draft assemblies; these are finished RefSeq genomes, which are exactly the ones
  least likely to carry human sequence. A clean screen here does not clear the drafts,
  it establishes that the catalog built from finished genomes is not the source of the
  artifact.
- ***Streptococcus* is also a target genus.** Its HMP genomes are in
  [`hmp/reference-genomes-target`](../hmp/reference-genomes-target.md) and are cataloged
  as genuine signal. The three here are for the human screen only; keep the two sets
  apart when cataloging, or a target genus picks up ten extra genomes.
- **Species are a guess.** Gihawi et al. name genera, not species. These are well-studied
  species per genus, not the specific assemblies that misled the original classifier.

## Sources

- [Gihawi et al. 2023, mBio](https://doi.org/10.1128/mbio.01607-23), Tables S1 and S5
- [Slacken metagenomic reference libraries, Registry of Open Data on AWS](https://registry.opendata.aws/slacken/)
