# HMP data proposed for the tandem repeat entropy project

Which parts of `s3://human-microbiome-project` fit the proposal in
`docs/documents/proposal.pdf`, where HMP/iHMP is the positive control: high-depth
oral and gut data establishing baseline TR entropy for taxa shared with tumor datasets.

Sizes and counts come from the bucket listing in `manifests/hmp.lock.json`
(`sync --no-download`, 2026-09-15). Genus counts come from the `ORGANISM` line of one
GenBank header per `reference_genomes/` directory.

## Bucket layout

| Prefix               | Contents                                                    | Files  | Size    |
| -------------------- | ----------------------------------------------------------- | ------ | ------- |
| `HHS/`               | Healthy Human Subjects: the main HMP1 cohort                | 35,053 | 5.6 TB  |
| `DEMO/`              | Demonstration Projects: disease-cohort 16S studies          | 6,582  | 104 GB  |
| `reference_genomes/` | Isolate genomes from human body sites                       | 43,740 | 129 GB  |

The data are 2012–2014 snapshots of HMP phase 1. HMP2/iHMP is not in this bucket.

## Constraint

TR allele lengths must be called from shotgun (WGS) reads. 16S amplicons and
processed abundance tables do not contain the TR loci, which rules out most products.

## Use

### 1. `HHS/HMASM/WGS/`: oral and gut shotgun reads

Human contaminant-screened Illumina FASTQ, one `SRS*.tar.bz2` per sample, grouped by
body site. 690 of 752 sequenced samples passed HMP QC and are included.

| Body site              | Samples | Median per sample | Total  |
| ---------------------- | ------- | ----------------- | ------ |
| `subgingival_plaque`   | 7       | 1.7 GB            | 10 GB  |
| `supragingival_plaque` | 118     | 3.9 GB            | 470 GB |
| `tongue_dorsum`        | 128     | 6.1 GB            | 760 GB |
| `stool`                | 139     | 7.3 GB            | 998 GB |

- Pilot on `subgingival_plaque`: small, and enriched for Fusobacterium and Porphyromonas.
- Then scale to `tongue_dorsum` and `stool` for depth and gut coverage.
- Skip `buccal_mucosa`: most samples are shallow (median 0.7 GB).
- HMP1 WGS reads are short: Illumina GAIIx trimmed to 60–100 bp (median 97–100 in the
  first 100k reads of three `subgingival_plaque` samples), which caps the repeat lengths
  a single read can span.

### 2. `reference_genomes/`: TR locus catalog

1,128 isolate genomes, with good coverage of the proposal's target taxa:

| Genus         | Genomes | Notable species                               |
| ------------- | ------- | --------------------------------------------- |
| Streptococcus | 112     | S. sanguinis (21), S. mitis (9), S. oralis (8) |
| Prevotella    | 35      | P. melaninogenica, P. denticola, P. buccae    |
| Fusobacterium | 27      | F. nucleatum (4), F. periodonticum (2)        |
| Veillonella   | 11      | V. parvula, V. atypica                        |
| Campylobacter | 7       | C. showae, C. rectus, C. gracilis             |
| Porphyromonas | 6       | P. gingivalis (2), P. endodontalis            |

- Only `*.nuc.fsa` or `*.gbk` files are needed. Most of the 129 GB is BLAST index
  files (`.nin`, `.nhr`, `.nsq`, …).
- Directories are numeric IDs. The bucket's `reference_genomes/list.json`
  (`manifests/hmp-reference-genomes-list.json`) maps 1,120 of them to organism, body site,
  and file paths; every organism matches its directory's GenBank `ORGANISM` line. The 8
  directories added later are not listed: `158721` (*S. infantis* ATCC 700779),
  `169453`–`169456` (*K. pneumoniae*), `169467` and `169468` (*P. mirabilis*), and
  `170040` (*Capnocytophaga* sp. oral taxon 412).
- 22 genomes have only a `.gbk` and no `.nuc.fsa`, and `75129`'s `.gbk` is access
  denied (its `.nuc.fsa` is readable).
- The six genera above are synced in `manifests/hmp-reference-genomes-target.json`
  (198 genomes, 316 files, 760 MB). 119 genomes have both a contig and a scaffold
  `.nuc.fsa`; both are kept, so pick one per genome when cataloging. `.gbk` is used for
  *V. dispar* `30491` (no FASTA) and *Fusobacterium* sp. `50399` (its `.nuc.fsa` is
  empty). *P. nigrescens* `64737`'s contig FASTA is access denied, so only its scaffold
  FASTA is synced.

### 3. `HHS/HMMC/`: mock community genomes

Reference genomes (0.2 GB) for the HMP mock community strains, including three
Streptococcus species. Useful as known-identity strains for checking allele calls.
Only genomes are present; no mock community reads were found in the bucket.

- Synced in `manifests/hmp-mock-community.json`: each strain's `*.nuc.fsa.bz2` (22
  genomes, 27 MB) and the strain sheet `HMPRP_sT1-Mock.pdf`. The `hmmcref_all.*.tar.gz`
  bundles duplicate the per-strain files and are skipped.
- 21 bacteria and archaea plus *Candida albicans*. Of the target genera only
  *Streptococcus* is present (*S. agalactiae*, *S. mutans*, *S. pneumoniae*).
- Every FASTA's contents match its strain directory, although
  `Pseudomonas_aeruginosa_ATCC_47085/331.AE017283.nuc.fsa.bz2` is named with
  *P. acnes*'s accession; it holds *P. aeruginosa* PAO1 (`AE004091.2`).

## Maybe

- `HHS/HMSCP/` (1.8 TB): per-sample reads already aligned to a reference database
  (`*_vs_RefDb.sorted.bam`). Could replace the read-anchoring step, but aligners tend
  to soft-clip or drop reads with repeat-length indels. That would bias against the
  variation being measured, so check before relying on it.

## Skip

- `DEMO/`: 16S only. Its `water_blank` controls look like contamination labels but
  contain no TR loci.
- 16S products: `HM16STR`, `HMR16S`, `HMQCP`, `HMMCP`.
- Assemblies and gene catalogs: `HMHASM`, `HMGI`, `HMGC`.

## Gaps

- **H2 batch labels.** No sequencing center or run date for WGS samples is in the
  bucket; the run metadata tarballs cover 16S only. Map each `SRS` accession to its
  SRA runs via NCBI SRA, which needs a new provider.
- **iHMP.** Cited in the proposal's Table 1 but not in this bucket; it is hosted on
  the HMP DACC portal and needs its own provider.
- **Contaminant ground truth.** HMP1 healthy-subject WGS carries no known-contaminant
  labels, so H1 validation still depends on TCGA and the Gihawi et al. (2023) labels.
