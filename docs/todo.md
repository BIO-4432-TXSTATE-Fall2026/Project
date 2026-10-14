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
- [ ] Screen the misclassified genomes and the TR catalog against CHM13. This is a motif
      screen, not a coordinate one — a bacterial contig and CHM13 share no coordinate
      system — so it needs the motif-keyed query in §2
- [ ] Extract false-positive labels from the supplement into `data/derived/`: the
      misclassified group from Tables S1–S7; normalization artifacts and extremophiles
      are only named in the paper's text
- [ ] Fetch *S. bongori* genomes, the true organism of the Salter dilution series, and
      *Ralstonia* if the stool screen clears it

### Zeller et al. (2014) reads (optional)

- [ ] Map `ERP005534` to run accessions, then sync and convert

## 2. Reference cataloging

### inTRuder fork changes

The fork targets human long-read SV calls. Its only TR finder reads insertion sequences
out of a VCF, and nothing in it opens a FASTA, so it cannot yet catalog loci in a
bacterial reference genome.

The dividing line worth building on is not human versus microbe. It is where the
sequence came from — a reference contig, or sequence a sample carries that the reference
does not — which is exactly what `trcore.io` already names `Genomic` and `Inserted`. A
human SV run and a microbial genome run differ in the reader and the parameter profile;
everything after the finder should be the same code.

#### Reading sequence

- [x] `trcore/io`: `SeqRecord` holds a named sequence and the `Genomic`/`Inserted` origin
      its offsets are measured against, with FASTA (pyfastx) and VCF-insertion (cyvcf2)
      adapters behind it. Both dependencies are optional extras imported inside the
      readers, so `import trcore.io` stays pure-stdlib, and `Inserted.locate` returns
      `None` rather than a coordinate that indexes nothing
- [x] Commit `trcore/io` and `tests/python/trcore/io`, then bump the submodule pin here
- [x] A FASTA genome scanner feeding the same `pytrf.ATRFinder` from `trcore.io` records
      instead of VCF ALT sequences (`pipeline/trf/find.py`, chosen by `--format`)
- [x] Route the VCF path through `trcore.io.read_insertions` as well, so both entry
      points share one record type. `sv_trfcaller.py` is gone and `pipeline/trf/cli.py`
      reads either source
- [x] Catalog output schema, with no sample, depth or insertion columns, plus BED4 export
      for the read filter (§3) and the CHM13 screen (`pipeline/trf/writers.py`)
- [ ] Settle the bacterial TR parameter profile. `params.PROFILES` carries a provisional
      `genome` profile beside `sv`, and the SV gates are now offered only for VCF input,
      but its values came from synthetic checks. Choosing them needs real genomes and the
      same enumeration `novelty.search` does, not an optimum

#### `pipeline/novelty`

`pipeline/novelty` is the module closest to what this project needs, and it is more
general than its name: it indexes a reference TR catalogue, then classifies a query
locus + motif as `known`, `novel_motif`, `novel_locus` or `unscreened`. Reusable as-is:

- The normalised catalogue schema (`chrom, start, end, motif` plus optional annotations)
  and the `bed` platform, so the §2 locus catalog can be screened without a new reader
- `RepeatCatalog`, a column-wise numpy interval index with motif interning and an
  on-disk cache — 1.05M hg38 rows, so 198 bacterial genomes are not a size problem
- `trcore.motifs`: canonical motifs under rotation and reverse complement, plus the
  edit-distance and tiling tolerances. Needed anywhere "the same repeat" has to mean
  something across genomes, which is most of §2 and all of §4
- `UNSCREENED`, which keeps "no catalogue row here" apart from "no repeat here" — the
  distinction the CHM13 screen turns on
- `novelty.search`: an Optuna grid or TPE sweep over the screen thresholds, with an
  `agreement` objective (cross-catalogue Jaccard on the novel sets) that needs no ground
  truth. The project has no labelled loci, so this is how the §2 merge and tolerance
  thresholds get chosen rather than guessed

What it cannot do yet:

- [ ] **A motif-keyed screen.** Every entry point (`screen`, `screen_frame`,
      `overlapping`) is keyed on `(chrom, point)`. The CHM13 screen asks whether a
      bacterial locus's *motif* also occurs in human, and there is no shared coordinate
      system between a bacterial contig and CHM13 — a coordinate query returns
      `unscreened` for every row, correctly and uselessly. Add a query keyed on canonical
      motif, which the interned `_canon` array already supports
- [ ] Make the `chr` prefixing in `trcore.coords.normalize_chrom` opt-in. It rewrites
      `NZ_CP012345.1` as `chrNZ_CP012345.1` and folds a contig named `MT` onto `chrM`,
      and every catalogue read and query routes through it
- [ ] A platform entry for the project's own catalog, so a per-genus catalog screens
      against CHM13 and against the other genera by name rather than by file path
- [ ] `novelty.insertions` (purity, union length, insertion filters) only applies to
      `Inserted` records. Split the purity and coverage checks, which are general, from
      the insertion-size filters, which are not
- [ ] Point `NOVELTY_CACHE` at a project path. `trcore.paths.repo_root` otherwise caches
      downloaded catalogues into `submodules/inTRuder/data/`, inside a submodule this
      repo tracks by commit

#### Module layout and flow

The fork has grown four pipeline steps and a model package with no shared spine. Worth
fixing before adding a fifth, and each of these makes the microbial path cheaper:

- [ ] **Fold `strchive` into the screen.** `pipeline/strchive` and `pipeline/novelty` are
      the same step: read a table of TR calls, index an external catalogue, join on locus
      and motif, append prefixed columns. STRchive is a platform with a disease
      annotation, not a pipeline of its own. Folding it in gives one command, one cache
      root, one set of tolerance flags, and puts STRchive inside the `novelty.search`
      sweep. It also demotes the one human-disease-only step to an optional platform
- [x] **Make `pipeline/trf` a package.** `cli.py`, `__main__.py`, `find.py`, `params.py`,
      `writers.py` and `filters.py`, with one `find` command that takes either a FASTA or
      a VCF and only offers the SV gates for a VCF
- [ ] **Get insertion parsing out of `modeling`.**
      `isolation_forest.features` imports `pipeline.novelty.insertions.parse_sizes`, so
      scoring a FASTA-derived table drags VCF semantics in. Move the shared column
      normalisation into `trcore` and let each source contribute its own feature block
- [ ] **One catalog record type.** `novelty.catalog.ReferenceRepeat` and the §2 catalog
      schema should be the same rows, with `genome`, `purity` and `rep_units` riding in
      `annotations` the way the platform readers already allow
- [ ] **Subworkflows in `workflows/main.nf`.** It is one flat `workflow` block of
      `if (params.run_*)` branches on a hardwired VCF input. A `find` subworkflow per
      source feeding one shared downstream chain lets the human and microbial runs share
      everything after the finder. It is also where this repo's own layout applies — one
      process per file under `workflows/modules/`, and the strict-parser limits in
      `docs/workflows/README.md`

### Catalog

- [ ] Run inTRuder on target-genus and contaminant-genus reference genomes to build the
      TR locus catalog
- [ ] Decide what counts as one locus: `pytrf` reports overlapping calls over the same
      stretch, and six genomes per genus repeat near-identical loci, so raw calls need a
      merge step before cross-sample entropy means anything. Merge on canonical motif
      (`trcore.motifs.canonical_motif`, already rotation- and strand-aware) plus interval
      overlap, so the merge rule is the same one the screen matches with
- [ ] Choose the merge window and motif tolerance with `novelty.search` in enumeration
      mode rather than by eye: there is no labelled locus set, so what is wanted is the
      sensitivity analysis, not an optimum
- [ ] Adapt PhasomeIt cataloging logic
- [ ] Check catalog loci against the mock community genomes — a `known` verdict from the
      screen with the mock strain genomes as the catalogue

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
- [ ] Build TR diversity and batch features. The fork's
      `modeling/unsupervised/isolation_forest` already has the feature registry, motif
      strata, SHAP attribution and per-candidate split traces; its intrinsic features
      (GC, Shannon entropy, purity, motif length, rep units) carry over, while its cohort
      features (VAF, DV/DR depth) are VCF-only and need per-sample equivalents
- [ ] Train a gradient boosting model with SHAP attribution. Isolation forest is the
      unsupervised fallback if the spike-in benchmark yields too few labels to train on;
      its STRchive recall gate is a human-only calibration and needs replacing with the
      mock community
- [ ] Test H1: entropy gap between biological signal and contaminants, including at low
      depth (Salter et al. and spike-ins)
- [ ] Test H2: contaminants cluster by kit (Salter et al.) and synthetic batch; genuine
      HMP taxa do not cluster by center. The HMP centers are unbalanced — WUGSC and BI are
      91% of the 568 runs, BCM 34 and JCVI 19 — so the two small centers carry little
      weight (`docs/data/derived/hmp-sra-runs.md`)
- [ ] Compare against decontam as the baseline

## 6. Open source

- [ ] Contribute microbial TR locus discovery improvements to inTRuder. Most of §2 is
      upstreamable as written — `trcore.io`, the FASTA finder, the motif-keyed screen,
      the opt-in `chr` prefixing and the `strchive`-into-`novelty` fold generalize the
      fork rather than branching it, and they are what lets one pipeline serve humans and
      microbes instead of two
