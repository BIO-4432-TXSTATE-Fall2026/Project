# Pipeline

Steps for the project in `docs/proposal.pdf`, in rough order. Data choices are in
`docs/HMP_proposed.md` and, with no TCGA controlled access,
`docs/tcga_controlled_alternative.md`. Data deferred to future comparisons is in
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
| Contaminant reference genomes  | NCBI assemblies (S3 mirror if one exists)         | none yet       | TR locus catalog for contaminant genera; source of spike-in reads     |
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
- **Contaminant reference genomes:** [NCBI Datasets genomes](https://www.ncbi.nlm.nih.gov/datasets/genome/);
  [NCBI assembly FTP](https://ftp.ncbi.nlm.nih.gov/genomes/all/)
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

### HMP1 shotgun reads

- [x] Full bucket listing (`manifests/hmp.lock.json`) and product choice
      (`docs/HMP_proposed.md`)
- [x] Record the `subgingival_plaque` listing with `sync --no-download` (pilot; too few
      samples for entropy). Reads are streamed from S3, not downloaded
- [x] Verify read length: Illumina GAIIx, trimmed to 60–100 bp (median 97–100); each
      tarball holds `.1`, `.2`, and `.singleton` FASTQ, in varying order
- [x] Record the `tongue_dorsum` (128 samples, 760 GB) and `stool` (139 samples, 998 GB)
      listings with `sync --no-download`; reads are streamed, not downloaded

### HMP reference and mock community genomes

- [x] Map `reference_genomes/` directory IDs to organisms
      (`manifests/hmp-reference-genomes-list.json`)
- [x] Sync `*.nuc.fsa` or `*.gbk` for target genera: 198 genomes, 760 MB
      (`manifests/hmp-reference-genomes-target.json`)
- [x] Sync `HHS/HMMC/`: 22 strain genomes and the strain sheet, 27 MB
      (`manifests/hmp-mock-community.json`)

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
- [ ] Sync the freeze on a compute node, extract the 274 HMP `SRS` samples to
      `data/derived/hmp-sra-runs.tsv`, then delete the catalog
- [ ] Decide which runs count per sample: samples carry 454 amplicon runs alongside the
      Illumina WGS ones, so batch labels need filtering by `platform`/`assay_type`

### iHMP

- [x] `hmpdcc` dataset
- [ ] Choose data from `ihmp/`, or drop iHMP from Table 1

### Salter et al. (2014) reads

- [x] `sra` dataset
- [ ] Map `ERP006808` to run accessions with kit and dilution per run
- [ ] Sync and convert the runs

### Contaminant reference genomes

- [ ] Choose spike-in contaminant genera, informed by Gihawi et al. (2023) rejected taxa
- [ ] Find an NCBI assembly source and add a dataset (or provider) for it
- [ ] Fetch genomes for *S. bongori*, *Ralstonia*, *Bradyrhizobium*, and the chosen
      spike-in genera, with several strains per genus

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
      HMP taxa do not cluster by center
- [ ] Compare against decontam as the baseline

## 6. Open source

- [ ] Contribute microbial TR locus discovery improvements to inTRuder
