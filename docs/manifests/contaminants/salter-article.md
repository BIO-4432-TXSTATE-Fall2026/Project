# `contaminants/salter-article`

Salter et al. (2014), the paper this project's contaminant side rests on: the source of
the kit-contaminant genus list in [`kit.md`](kit.md), and the description of the
experiment behind the reads in [`salter-runs.md`](../../data/derived/salter-runs.md).

```sh
pixi run new contaminants/salter-article --dataset=pmc --prefix=PMC4228153.1 \
  "--description=Salter et al. (2014) article and supplement: Table 1 (contaminant \
genera in blank controls), the four-kit shotgun dilution series, and Additional file 1 \
(Tables S1a/S1b accessions and read counts, Table S2)"
pixi run sync manifests/contaminants/salter-article.json
```

9 files, 3.4 MB, from PMC's open-access bucket (`s3://pmc-oa-opendata/PMC4228153.1/`),
dataset `pmc`. Unlike [`gihawi-supplement`](gihawi-supplement.md), the whole prefix is
synced, article included: here the evidence is in the paper's own tables and figures, not
only in the supplement.

## Files

| File | Holds |
| ---- | ----- |
| `PMC4228153.1.xml` | The article as JATS XML. Table 1 is machine-readable here, one `table-wrap` with the genera by phylum and the prior-report superscripts |
| `PMC4228153.1.txt`, `.pdf` | The same article as text and as the typeset PDF |
| `PMC4228153.1.json` | PMC's record for the article: license, dates, identifiers |
| `12915_2014_87_Fig1–4_HTML.jpg` | Figure 1 (16S dilution series by site), 2 (qPCR copy number), 3 (metagenomic series: 3b is the per-kit family profile), 4 (nasopharyngeal case study, PCoA by kit batch) |
| `12915_2014_87_MOESM1_ESM.docx` | Additional file 1: Figures S1–S2, Tables S1a and S1b (accessions and read counts for the 16S and metagenomic runs), Table S2 (OTUs correlating with kit batch) |

## What each part is for here

- **Table 1** is the candidate list for spike-in genera: 92 named genera found in blank
  extractions at three labs over four years, by phylum, with superscripts marking those
  independently reported elsewhere. [`kit.md`](kit.md) says which five were taken and why.
- **The shotgun results section** is the only place kits are tied to specific genera:
  FP dominated by *Burkholderia*, PSP by *Bradyrhizobium*, QIA diverse, MB too shallow to
  profile. That is what makes kit a usable batch label for H2.
- **Table S1b** lists the metagenomic runs and their read counts, which is a cross-check
  on the twelve `ERP006808` runs that report 0 Mbases in
  [`salter-runs.md`](../../data/derived/salter-runs.md).

## Traps

- **Table 1 is not the dilution experiment.** It is four years of accumulated blank
  controls across three institutes and many kits, mostly FastDNA SPIN for Soil. The
  four-kit comparison in Figure 3 is a separate, single-lab experiment. A genus in
  Table 1 is not thereby tied to any one kit.
- **Genus resolution only.** Neither Table 1 nor Figure 3b goes below genus, and
  Figure 3b is family-level. There is no species-level contaminant list to match against.
- **16S and shotgun are different accessions.** `ERP006737` is the 16S data;
  `ERP006808`, the one this project uses, is the metagenomic dilution series.

## Sources

- [Salter et al. 2014, BMC Biology](https://doi.org/10.1186/s12915-014-0087-z);
  [PMC4228153](https://pmc.ncbi.nlm.nih.gov/articles/PMC4228153/)
- [PMC Article Datasets, Registry of Open Data on AWS](https://registry.opendata.aws/ncbi-pmc/)
