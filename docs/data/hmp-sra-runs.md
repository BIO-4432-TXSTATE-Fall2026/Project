# `hmp-sra-runs.tsv`

Run-level SRA metadata for the 274 HMP1 shotgun samples the project uses: which runs a
sample has, which center produced them, and when they were released. It is what H2's
batch labels are built from. Source and rebuild cost are in `README.md`; this page is
about what is in the file and which rows to use.

Rebuild with the preprocessing stage, never by hand:

```sh
pixi run pipeline --stage preprocess -profile slurm,apptainer --slurm_queue shared
```

## Shape

916 rows, one per run, 13 columns. The samples come from the three body-site lockfiles
(`manifests/hmp-{stool,subgingival-plaque,tongue-dorsum}.lock.json`) through
`extract --from-lock`, so the table covers exactly the samples those specs synced: all
274, with no sample missing and none that was not asked for.

| Column | Is |
| ------ | -- |
| `run` | `SRR` accession, unique in this file |
| `sample`, `study`, `bioproject`, `biosample` | the accessions the run belongs to |
| `center` | submitting center — the H2 batch label, with the caveat below |
| `releasedate` | when the run was released, not when it was sequenced |
| `platform`, `instrument` | `ILLUMINA`/`LS454`, and the machine |
| `librarylayout`, `libraryselection`, `assay_type` | `PAIRED`/`SINGLE`, `RANDOM`/`PCR`, `WGS`/`AMPLICON` |
| `mbases` | run size, a rough depth proxy |

## Which rows to use

**`assay_type == 'WGS' and platform == 'ILLUMINA' and study == 'SRP002163'`.** That is
568 runs covering all 274 samples. Each clause drops rows the project must not analyse:

| Rows kept by | Runs | Samples |
| ------------ | ---- | ------- |
| everything in the file | 916 | 274 |
| `assay_type == 'WGS'` | 662 | 274 |
| `+ platform == 'ILLUMINA'` | 593 | 274 |
| `+ study == 'SRP002163'` | 568 | 274 |

The table itself keeps all 916 rows. Filtering belongs to whoever reads it, so the
decision stays visible and reversible rather than baked into a file nobody re-derives.

## Three traps

**Amplicon runs share the sample accession.** HMP samples carry their 16S amplicon runs
under the same `SRS` as their shotgun runs — 254 of the rows here. Joining on sample alone
analyses 454 amplicon data as if it were WGS.

**`assay_type` alone does not separate them.** 69 runs are `WGS` *on LS454*, across 9
samples. A filter that only excludes `AMPLICON` still leaves 454 shotgun data in the
table, so `platform` has to be named too. This is the trap that survives the obvious fix.

**`SRP175119` is a 2019 reanalysis, not HMP1.** 25 Illumina WGS runs submitted in January
2019 by `CRASSPHAGE CONSORTIUM`, re-depositing 22 samples that already have their original
runs — dropping the study loses no sample. Keeping it costs twice over: `center` gains a
fifth value that is a reanalysis group rather than a sequencing center, which is a
manufactured batch in the middle of the hypothesis that genuine taxa do *not* cluster by
center; and those 22 samples count their reads twice in any depth covariate.

## What the filtered rows look like

All 568 are Illumina Genome Analyzer II, released 2010-07 to 2011-12, consistent with the
60–100 bp reads `docs/todo.md` records. Centers are unbalanced, which matters for how much
H2 can claim:

| Center | Runs |
| ------ | ---- |
| WUGSC | 321 |
| BI | 194 |
| BCM | 34 |
| JCVI | 19 |

WUGSC and BI are 91% of the runs, so the two small centers carry little weight in any
test of clustering by center.

**A sample is usually more than one run.** After filtering, 232 of the 274 samples have 2
runs, 19 have 3, 8 have 4, and 15 have a single run — 259 samples have more than one. Runs
have to be pooled per sample before sequencing depth means anything as a covariate.
