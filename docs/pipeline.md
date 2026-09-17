# Pipeline

Steps for the project in `docs/proposal.pdf`, in rough order. Data choices are in
`docs/HMP_proposed.md` and, with no TCGA controlled access,
`docs/tcga_controlled_alternative.md`.

## 0. Proposal

- [x] Write problem statement, hypotheses (H1, H2), data sources, and pipeline
- [ ] Write the abstract
- [ ] Pin the inTRuder commit in the reference
- [ ] Cite or drop Vogler et al. (2006) and Zepeda-Rivera et al. (2024)
- [ ] Replace TCGA and Gihawi et al. (2023) validation in Table 1 and Section 3 with
      Salter et al. (2014) and the spike-in benchmark; move TCGA to future work

## 1. Data loading tooling

- [x] S3 provider, dataset selection by prefix and globs, manifest CLI
- [x] `sync --no-download` to record listings without fetching
- [x] Full HMP bucket listing (`manifests/hmp.lock.json`)
- [x] Choose which HMP products to use (`docs/HMP_proposed.md`)
- [x] `sra-metadata` dataset and per-spec region selection
- [x] iHMP provider (HMP DACC portal)
- [ ] ~~TCGA COAD/STAD provider (NCI GDC; needs dbGaP access)~~
- [x] SRA runs dataset (`sra-pub-run-odp`, selected by run accession; `.sra` files still
      need `fasterq-dump`)
- [ ] NCBI genome provider for contaminant genera

## 2. Data acquisition

### HMP (positive control; genuine-taxa side of H2)

- [ ] Sync `HHS/HMASM/WGS/subgingival_plaque` (pilot; too few samples for entropy)
- [ ] Verify HMP1 WGS read length
- [ ] Sync `HHS/HMMC/` mock community genomes
- [ ] Map `reference_genomes/` directory IDs to organisms
- [ ] Sync `*.nuc.fsa` or `*.gbk` for target genera
- [ ] Sync SRA metadata and map each `SRS` sample to its runs, center, and date (H2)
- [ ] Sync `tongue_dorsum` and `stool` WGS
- [ ] Choose iHMP data from `hmpdcc` `ihmp/`, or drop iHMP from Table 1

### Contaminant ground truth (replaces TCGA)

- [ ] Fetch Salter et al. (2014) shotgun reads (`ERP006808`) with kit and dilution per run
- [ ] Fetch reference genomes for contaminant genera (*S. bongori*, *Ralstonia*,
      *Bradyrhizobium*)
- [ ] Choose spike-in contaminant genera, informed by Gihawi et al. (2023) rejected taxa
- [ ] Optional: fetch Zeller et al. (2014) CRC fecal metagenomes (`ERP005534`)

## 3. Reference cataloging

- [ ] Run inTRuder on target-genus and contaminant-genus reference genomes to build the
      TR locus catalog
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

- [ ] Build the spike-in benchmark: clonal contaminant reads on HMP samples, one strain
      per synthetic batch, titrated to tumor-like depths
- [ ] Build TR diversity and batch features
- [ ] Train a gradient boosting model with SHAP attribution
- [ ] Test H1: entropy gap between biological signal and contaminants, including at low
      depth (Salter et al. and spike-ins)
- [ ] Test H2: contaminants cluster by kit (Salter et al.) and synthetic batch; genuine
      HMP taxa do not cluster by center
- [ ] Compare against decontam as the baseline

## 7. Open source

- [ ] Contribute microbial TR locus discovery improvements to inTRuder

