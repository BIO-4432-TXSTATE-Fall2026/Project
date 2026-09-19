# `salter-runs.tsv`

Run-level SRA metadata for Salter et al. (2014), `ERP006808`: which run is which
extraction kit, and how far down the dilution series it sits. It is what H1's low-biomass
contaminant reads and H2's kit batch labels are built from. Source and rebuild cost are in
[`../README.md`](../README.md); this page is about what is in the file and what the numbers
do and do not mean.

Rebuild with the preprocessing stage, never by hand:

```sh
pixi run pipeline --stage preprocess -profile slurm,apptainer --slurm_queue shared
```

## Shape

35 rows, one per run, 16 columns. One run per sample and one sample per run, so `run` and
`sample` are equally unique. The first 13 columns are the same as
[`hmp-sra-runs.md`](hmp-sra-runs.md); the last three are what this table exists for.

| Column | Is |
| ------ | -- |
| `alias` | the submitter's sample name, `<KIT>_<step>` or `Water` |
| `kit` | extraction kit, parsed from `alias` |
| `dilution` | dilution step, parsed from `alias`; empty for the water control |

`alias` is kept beside the two parsed columns on purpose. The kit and the step are not
SRA fields — they exist only in free text the submitter wrote — so the raw string stays in
the table and the parse can be checked against it without re-reading the catalog.

## What the runs are

A pure *Salmonella bongori* culture, serially diluted and sequenced at each step, once per
extraction kit, plus one negative water control. Every run is Illumina MiSeq, paired, 
released 2014-08-31, submitted by `UBP-CNRS` from the University of Birmingham.

| Kit | Runs | Steps | Runs |
| --- | ---- | ----- | ---- |
| `CAMBIO` | 10 | 1–10 | ERR588920–ERR588929 |
| `MP_BIO` | 10 | 1–10 | ERR588930–ERR588939 |
| `QIAGEN` | 10 | 1–10 | ERR588940–ERR588949 |
| `PSP_PLUS` | 4 | 1–4 | ERR588950–ERR588953 |
| water control | 1 | — | ERR588954 |

Kit names keep the underscores of the alias, so they are `MP_BIO` and `PSP_PLUS` rather
than the paper's "MP BIO" and "PSP PLUS". The alias is the only form that is also a legal
identifier, and it is what the water control shares with the rest.

## Three traps

**A dilution step is not a concentration, and it is not comparable across kits.**
`PSP_PLUS` has four steps, the other three kits have ten. `PSP_PLUS_4` is the *end* of its
series; `CAMBIO_4` is early in a series that runs to 10. Treating `dilution` as a number
that means the same thing in every kit compares the most dilute PSP sample against a
middling CAMBIO one. Within a kit it orders the series correctly, and that is all it does.

**These runs are tiny, and that is the point.** 0.83 Gbp over all 35 runs, and `mbases`
runs from 229 down to 0 as the series is diluted — 15 of the 35 runs report 0 or 1. The
contaminant signal is what is left when the template runs out, so the shallow end of each
series is the interesting end, not a set of failed runs to drop. It also means depth is
confounded with dilution step by construction: any comparison across steps is also a
comparison across depths.

**`ERP006808` is not all of Salter et al. (2014).** It is the dilution-series experiment
only, which is the part with kit labels and the part the project needs. The paper's other
data — the samples run at different institutes, and the soil and environmental
comparisons — are under other accessions and are not in this table. Anything claimed here
is about one culture, one sequencer, and one site, so the kit is the only batch variable
that varies cleanly.

## Which rows to use

All of them, with the water control kept apart: it has no kit and no dilution, so it is
excluded by any filter on either, and it is the right baseline for what the reagents
contribute on their own. As in `hmp-sra-runs.tsv`, the table keeps every row and filtering
belongs to whoever reads it.
