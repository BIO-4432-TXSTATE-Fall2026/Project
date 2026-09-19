# `contaminants/gihawi-supplement`

The supplementary files of Gihawi et al. (2023), which re-analyzed the TCGA reads behind
the Poore et al. (2020) cancer microbiome classifiers and found most of the reported
microbes absent. The project uses it as a source of **known false positives**: taxa
that a metagenomic pipeline reported and that were not there. They are labels for
modeling decisions, not reads, since the supplement holds counts only.

Created and synced with:

```sh
pixi run new contaminants/gihawi-supplement --dataset=pmc --prefix=PMC10653788.1 \
  "--include=mbio.01607-23-s*" "--description=Gihawi et al. (2023) supplementary files: \
Kraken database species and genera, Tables S1-S7 (top-20 genera, Poore et al. vs \
re-analysis), S8-S10 (re-analysis counts: BLCA, HNSC, BRCA), S11 (Poore et al. top \
classifier features)"
pixi run sync manifests/contaminants/gihawi-supplement.json
```

7 files, 3.8 MB, from PMC's open-access bucket (`s3://pmc-oa-opendata/PMC10653788.1/`),
dataset `pmc`. The article itself (XML, text, PDF) sits beside them under the same
prefix and is left out by the `mbio.01607-23-s*` include.

## Files

| File | Holds |
| ---- | ----- |
| `s0001.txt` | Every species in the re-analysis Kraken database, one per line (16,428) |
| `s0002.txt` | Every genus in that database, one per line (3,036) |
| `s0003.docx` | Tables S1–S7 and Figures S1–S2: top-20 genera, Poore et al. against re-analysis, as per-sample averages |
| `s0004.xlsx` | Table S8: re-analysis counts, BLCA, sample × genus |
| `s0005.xlsx` | Table S9: re-analysis counts, HNSC, sample × genus (`g_` prefix) |
| `s0006.xlsx` | Table S10: re-analysis counts, BRCA WGS, sample × genus (`g_` prefix) |
| `s0007.xlsx` | Table S11: Poore et al.'s top 25 classifier features per cancer, for the "all putative contaminants removed" (APCR) and "most stringent decontamination" (MSD) datasets |

## What it can and cannot label

Gihawi et al. reject taxa for three different reasons, and the supplement supports them
unevenly.

- **Misclassified: human reads counted as bacteria.** *Streptococcus*, *Mycobacterium*,
  *Staphylococcus*, *Waddlia* and others: Poore et al. report hundreds of thousands of
  reads per sample, the re-analysis finds tens (Tables S1, S5). The cause is human
  sequence left in draft bacterial genomes. **Derivable here**, but only for the genera
  in S1–S7, since those are the only places the original counts appear. S8–S10 are the
  re-analysis alone.
- **Normalization artifacts.** *Hepandensovirus* (ACC), *Mulikevirus* (HNSC),
  *Thiorhodospira* (KICH), *Nitrospira* (LUSC): zero or near-zero raw reads that
  Voom-SNM turned into a clean class signal. **Not derivable here.** It needs Poore
  et al.'s raw and normalized tables side by side; the paper names these in its text
  and Figures 2–5.
- **Implausible organisms.** *Methanothermus*, *Halonatronum*, *Salinarchaeum*:
  extremophiles that follow-up breast cancer studies built on Poore et al.'s tables
  (Parida et al., Mao et al.). **Not derivable here**; the paper names them in its text.

S11 is the useful cross-reference for all three: it says which genera the classifiers
actually leaned on, so a false positive can be weighed by how much it mattered.

## Traps

- **Different databases.** Both studies used Kraken. Poore et al.'s database had no human
  genome and included draft bacterial genomes; the re-analysis database is finished
  genomes plus human and vectors, listed in `s0001`/`s0002`. A genus missing from S8–S10
  may be absent from the re-analysis database rather than absent from the sample, so
  check `s0002` before reading a zero.
- **Averages, not samples.** S1–S7 average over tumor and normal samples together; the
  sample counts are in each legend and differ between tables.
- **Not reagent contaminants.** None of the three groups is the kit contamination this
  project models. They are failures of the database and the statistics, so they do not
  supply spike-in genera. Those come from Salter et al. (2014).

## Sources

- [Gihawi et al. 2023, mBio](https://doi.org/10.1128/mbio.01607-23);
  [PMC10653788](https://pmc.ncbi.nlm.nih.gov/articles/PMC10653788/)
- [PMC Article Datasets, Registry of Open Data on AWS](https://registry.opendata.aws/ncbi-pmc/)
