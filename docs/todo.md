# Pipeline

Steps for the project in `docs/documents/proposal.pdf`, in rough order. Data choices are in
`docs/data/HMP_pilot.md` and, with no TCGA controlled access,
`docs/data/tcga_alternatives.md`. Data deferred to future comparisons is in
`docs/comparisons.md`.

## 0. Proposal

- [x] Write problem statement, hypotheses (H1, H2), data sources, and pipeline
- [ ] Write the abstract
- [ ] Pin the inTRuder commit in the reference
- [ ] Cite or drop Vogler et al. (2006) and Zepeda-Rivera et al. (2024)
- [ ] Replace TCGA and Gihawi et al. (2023) validation in Table 1 and Section 3 with
      Salter et al. (2014) and the spike-in benchmark; move TCGA to future work

## 1. Data acquisition

Every dataset the project uses, where it comes from, and what it is for. "Tool" is the
`dataset` name in a manifest spec; manifests are created with the project CLI.

| Dataset                        | Source                                            | Tool           | Role in the project                                                   |
| ------------------------------ | ------------------------------------------------- | -------------- | --------------------------------------------------------------------- |
| HMP1 shotgun reads             | `s3://human-microbiome-project` `HHS/HMASM/WGS/`  | `hmp`          | Genuine taxa: baseline TR entropy (H1), negative side of H2           |
| HMP reference genomes          | `s3://human-microbiome-project` `reference_genomes/` | `hmp`       | TR locus catalog for target genera                                    |
| HMP mock community genomes     | `s3://human-microbiome-project` `HHS/HMMC/`       | `hmp`          | Known strains for checking catalog loci and allele calls              |
| ~~HMP aligned reads~~          | `s3://human-microbiome-project` `HHS/HMSCP/`      | none           | Future comparison (`docs/comparisons.md`)                             |
| SRA run metadata               | `s3://sra-pub-metadata-us-east-1`                 | `sra-metadata` | Map HMP samples to runs, center, and date (H2 batch labels)           |
| iHMP                           | `s3://hmpdcc` `ihmp/`                             | `hmpdcc`       | Extra oral and gut data, or drop from Table 1                         |
| Salter et al. (2014) reads     | ENA `ERP006808`, runs from `s3://sra-pub-run-odp` | `sra`          | Real contaminants with kit labels: contaminant side of H1, kit batches for H2 |
| Contaminant reference genomes  | `s3://slacken` `index/rspc-224/library/bacteria/` | `slacken`      | TR locus catalog for contaminant genera; source of spike-in reads     |
| Gihawi et al. (2023) supplement | `s3://pmc-oa-opendata` `PMC10653788.1/`          | `pmc`          | Known false-positive taxa: labels for modeling decisions, not reads   |
| Zeller et al. (2014) reads (optional) | ENA `ERP005534`, runs from `s3://sra-pub-run-odp` | `sra`   | Cancer-associated taxa across patients; weak evidence for H2          |
| ~~TCGA COAD/STAD~~             | NCI GDC; needs dbGaP access                       | none           | Future work                                                           |

### Sources

- **HMP1 shotgun reads, reference genomes, mock community, aligned reads:**
  [Human Microbiome Project Consortium 2012, Nature](https://doi.org/10.1038/nature11234);
  [Registry of Open Data on AWS](https://registry.opendata.aws/human-microbiome-project/)
- **SRA run metadata:** [NCBI SRA, Registry of Open Data on AWS](https://registry.opendata.aws/ncbi-sra/)
- **iHMP:** [iHMP Research Network Consortium 2019, Nature](https://doi.org/10.1038/s41586-019-1238-8);
  [HMP DACC](https://www.hmpdacc.org/)
- **Salter et al. (2014) reads:**
  [Salter et al. 2014, BMC Biology](https://link.springer.com/article/10.1186/s12915-014-0087-z);
  [ENA `ERP006808`](https://www.ebi.ac.uk/ena/browser/view/ERP006808);
  [NCBI SRA, Registry of Open Data on AWS](https://registry.opendata.aws/ncbi-sra/)
- **Contaminant reference genomes:** RefSeq release 224 via
  [Slacken metagenomic reference libraries, Registry of Open Data on AWS](https://registry.opendata.aws/slacken/)
- **Human reference (screen):** [Nurk et al. 2022, Science](https://doi.org/10.1126/science.abj6987);
  [Human Pangenome Reference Consortium, Registry of Open Data on AWS](https://registry.opendata.aws/hpgp-data/)
- **Gihawi et al. (2023) supplement:**
  [Gihawi et al. 2023, mBio](https://doi.org/10.1128/mbio.01607-23);
  [PMC Article Datasets, Registry of Open Data on AWS](https://registry.opendata.aws/ncbi-pmc/)
- **Zeller et al. (2014) reads:** [Zeller et al. 2014 data reuse](https://pmc.ncbi.nlm.nih.gov/articles/PMC4865240/);
  [Wirbel et al. 2019, Nature Medicine](https://www.nature.com/articles/s41591-019-0406-6);
  [ENA `ERP005534`](https://www.ebi.ac.uk/ena/browser/view/ERP005534)
- **TCGA COAD/STAD:** [Grossman et al. 2016, NEJM](https://doi.org/10.1056/NEJMp1607591);
  [NCI GDC portal](https://portal.gdc.cancer.gov/)

### Shared tooling

- [x] S3 provider, dataset selection by prefix and globs, manifest CLI
- [x] `sync --no-download` to record listings without fetching
- [x] Selection by accession and per-spec region
- [x] `convert` for `.sra` runs with `fasterq-dump`
- [x] Specs in subdirectories of `manifests/`, with pages mirrored under
      `docs/manifests/`

### HMP1 shotgun reads

- [x] Full bucket listing (`manifests/hmp/bucket.lock.json`) and product choice
      (`docs/data/HMP_pilot.md`)
- [x] Record the `subgingival_plaque` listing with `sync --no-download` (pilot; too few
      samples for entropy). Reads are streamed from S3, not downloaded
- [x] Verify read length: Illumina GAIIx, trimmed to 60–100 bp (median 97–100); each
      tarball holds `.1`, `.2`, and `.singleton` FASTQ, in varying order
- [x] Record the `tongue_dorsum` (128 samples, 760 GB) and `stool` (139 samples, 998 GB)
      listings with `sync --no-download`; reads are streamed, not downloaded

### HMP reference and mock community genomes

- [x] Map `reference_genomes/` directory IDs to organisms
      (`manifests/hmp/reference-genomes-list.json`)
- [x] Sync `*.nuc.fsa` or `*.gbk` for target genera: 198 genomes, 760 MB
      (`manifests/hmp/reference-genomes-target.json`)
- [x] Sync `HHS/HMMC/`: 22 strain genomes and the strain sheet, 27 MB
      (`manifests/hmp/mock-community.json`)

### ~~HMP aligned reads~~

- [x] Decided against `HHS/HMSCP/`: the reads were low-complexity masked and stripped of
      base qualities before a soft-clipping alignment to a 2010 reference database. Kept
      as a future comparison in `docs/comparisons.md`

### SRA run metadata

- [x] `sra-metadata` dataset
- [x] Choose the frozen `sra/metadata_json/` snapshot over the daily Parquet table, and
      record its listing (`manifests/sra-metadata-freeze.json`): 60 files, 2.3 GB, stable
      since 2020-09-09, covering everything released to 2020-09-01
- [x] `extract` command: reduce a synced catalog to the rows an accession list names,
      into a committed TSV under `data/derived/` (`docs/data/README.md`)
- [x] Sync the freeze on a compute node, extract the 274 HMP `SRS` samples to
      `data/derived/hmp-sra-runs.tsv`, then delete the catalog: 916 runs, all 274 samples
- [x] Decide which runs count per sample:
      `assay_type == 'WGS' and platform == 'ILLUMINA' and study == 'SRP002163'`, which is
      568 runs over all 274 samples (`docs/data/derived/hmp-sra-runs.md`). `assay_type`
      alone is not enough — 69 WGS runs are LS454 — and `SRP175119` is a 2019 crAssphage
      reanalysis of 22 samples that already have their original runs, so it is dropped
      rather than counted as a fifth center
- [ ] Pool runs per sample before using depth as a covariate: 259 of the 274 samples have
      more than one run

### iHMP

- [x] `hmpdcc` dataset
- [ ] Choose data from `ihmp/`, or drop iHMP from Table 1

### Salter et al. (2014) reads

- [x] `sra` dataset
- [x] Map `ERP006808` to run accessions with kit and dilution per run: 35 MiSeq runs,
      `ERR588920`–`ERR588954`, one per sample. Four kits — `CAMBIO`, `MP_BIO`, `QIAGEN`
      (10 dilution steps each) and `PSP_PLUS` (4) — plus one water control. Kit and step
      are only in the free-text sample alias, which `extract --profile salter` reads out
      into `data/derived/salter-runs.tsv` (`docs/data/derived/salter-runs.md`). A step
      number is not comparable across kits, and depth falls with dilution by construction
- [x] Build `data/derived/salter-runs.tsv` on the cluster: the extract needs the 2.3 GB
      metadata freeze, so it belongs in a preprocess run, not on a laptop. 35 runs,
      813 Mbases in total; 12 runs report 0 Mbases, most of them `CAMBIO` steps 3–10
- [ ] Sync and convert the runs: 0.49 GB over all 35, paired 2×150

### Contaminant reference genomes

Grouped under `manifests/contaminants/`, one page each in `docs/manifests/contaminants/`.
The human reference they are screened against is `manifests/reference/chm13.json`.

- [x] `pmc` dataset; sync the Gihawi et al. (2023) supplement
      (`manifests/contaminants/gihawi-supplement.json`). Its rejected taxa are human-read
      misclassification, normalization artifacts, and implausible extremophiles — known
      false positives, not kit contaminants, so they label rather than supply spike-ins
- [x] Sync the Salter et al. (2014) article for Table 1 and the per-kit shotgun profiles
      (`manifests/contaminants/salter-article.json`)
- [x] Choose spike-in contaminant genera and write `contaminants/kit`: *Bradyrhizobium*
      (`PSP` kit), *Burkholderia* (FastDNA kit), *Methylobacterium*, *Sphingomonas*, and
      low-GC *Flavobacterium* so GC alone cannot separate them from HMP targets. Six
      complete genomes each, one per species, excluding every genus with an HMP reference
      genome. *Ralstonia* only if HMP stool shows no background
      (`docs/manifests/contaminants/kit.md`)
- [x] Genome source: the existing `slacken` dataset cuts complete RefSeq genomes out of
      the release 224 library by byte range, so no NCBI dataset is needed
- [x] Write `contaminants/misclassified`: three complete genomes each for
      *Streptococcus*, *Mycobacterium* and *Staphylococcus*, plus *Waddlia chondrophila*
- [x] Write `reference/chm13` and a `human-pangenomics` dataset: T2T-CHM13 v2.0, the
      screen for TR loci that also occur in human (`docs/manifests/reference/chm13.md`)
- [ ] Sync `contaminants/kit`, `contaminants/misclassified` and `reference/chm13` on a
      compute node: 192 MB, 32 MB and 982 MB, plus 725 MB of slacken index files on the
      first slacken sync
- [ ] Screen the misclassified genomes and the TR catalog against CHM13
- [ ] Extract false-positive labels from the supplement into `data/derived/`: the
      misclassified group from Tables S1–S7; normalization artifacts and extremophiles
      are only named in the paper's text
- [ ] Fetch *S. bongori* genomes, the true organism of the Salter dilution series, and
      *Ralstonia* if the stool screen clears it

### Zeller et al. (2014) reads (optional)

- [ ] Map `ERP005534` to run accessions, then sync and convert

## 2. Reference cataloging

- [ ] Run inTRuder on target-genus and contaminant-genus reference genomes to build the
      TR locus catalog
- [ ] Adapt PhasomeIt cataloging logic
- [ ] Check catalog loci against the mock community genomes

## 3. Allele calling and error correction

- [ ] Stream HMP1 reads from S3 through a locus filter, one SLURM array task per sample,
      keeping only locus-hitting reads and per-sample read counts; test on
      `subgingival_plaque` first
- [ ] Anchor reads to cataloged loci
- [ ] Measure allele lengths per sample
- [ ] Apply a stutter model adapted from STRling and HipSTR

## 4. Confounder control

- [ ] Compute cross-sample TR entropy per locus
- [ ] Use a bias-corrected estimator (e.g. Chao–Shen), no rarefying
- [ ] Include sequencing depth as a covariate
- [ ] Establish HMP baseline entropy for shared taxa (positive control)

## 5. Classification and validation

- [ ] Build the spike-in benchmark: clonal contaminant reads on HMP samples, one strain
      per synthetic batch, titrated to tumor-like depths
- [ ] Build TR diversity and batch features
- [ ] Train a gradient boosting model with SHAP attribution
- [ ] Test H1: entropy gap between biological signal and contaminants, including at low
      depth (Salter et al. and spike-ins)
- [ ] Test H2: contaminants cluster by kit (Salter et al.) and synthetic batch; genuine
      HMP taxa do not cluster by center. The HMP centers are unbalanced — WUGSC and BI are
      91% of the 568 runs, BCM 34 and JCVI 19 — so the two small centers carry little
      weight (`docs/data/derived/hmp-sra-runs.md`)
- [ ] Compare against decontam as the baseline

## 6. Open source

- [ ] Contribute microbial TR locus discovery improvements to inTRuder
