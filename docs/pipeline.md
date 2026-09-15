# Pipeline

Steps for the project in `docs/proposal.pdf`, in rough order. Data choices are in
`docs/HMP_proposed.md`.

## 0. Proposal

- [x] Write problem statement, hypotheses (H1, H2), data sources, and pipeline
- [ ] Write the abstract
- [ ] Pin the inTRuder commit in the reference
- [ ] Cite or drop Vogler et al. (2006) and Zepeda-Rivera et al. (2024)

## 1. Data loading tooling

- [x] S3 provider, dataset selection by prefix and globs, manifest CLI
- [x] `sync --no-download` to record listings without fetching
- [x] Full HMP bucket listing (`manifests/hmp.lock.json`)
- [x] Choose which HMP products to use (`docs/HMP_proposed.md`)
- [x] `sra-metadata` dataset and per-spec region selection
- [x] iHMP provider (HMP DACC portal)
- [ ] ~~TCGA COAD/STAD provider (NCI GDC; needs dbGaP access)~~

## 2. Data acquisition

- [ ] Sync `HHS/HMASM/WGS/subgingival_plaque` (pilot)
- [ ] Verify HMP1 WGS read length
- [ ] Sync `HHS/HMMC/` mock community genomes
- [ ] Map `reference_genomes/` directory IDs to organisms
- [ ] Sync `*.nuc.fsa` or `*.gbk` for target genera
- [ ] Sync SRA metadata and map each `SRS` sample to its runs, center, and date (H2)
- [ ] Sync `tongue_dorsum` and `stool` WGS
- [ ] Collect Gihawi et al. (2023) retained and rejected taxon calls
- [ ] Apply for dbGaP access and fetch TCGA COAD/STAD reads

## 3. Reference cataloging

- [ ] Run inTRuder on target-genus reference genomes to build the TR locus catalog
- [ ] Adapt PhasomeIt cataloging logic
- [ ] Check catalog loci against the mock community genomes

## 4. Allele calling and error correction

- [ ] Anchor reads to cataloged loci
- [ ] Measure allele lengths per sample
- [ ] Apply a stutter model adapted from STRling and HipSTR
- [ ] Decide whether `HHS/HMSCP/` alignments are usable (soft-clipping bias)

## 5. Confounder control

- [ ] Compute cross-sample TR entropy per locus
- [ ] Use a bias-corrected estimator (e.g. Chao–Shen), no rarefying
- [ ] Include sequencing depth as a covariate
- [ ] Establish HMP baseline entropy for shared taxa (positive control)

## 6. Classification and validation

- [ ] Build TR diversity and batch features
- [ ] Train a gradient boosting model with SHAP attribution
- [ ] Test H1: entropy gap between biological signal and contaminants, including at low depth
- [ ] Test H2: TR signatures cluster by center and batch for contaminants only
- [ ] Compare against decontam as the baseline
- [ ] Evaluate on TCGA against Gihawi et al. (2023) labels

## 7. Open source

- [ ] Contribute microbial TR locus discovery improvements to inTRuder

