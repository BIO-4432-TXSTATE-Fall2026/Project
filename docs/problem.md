# What this project is

The proposal is `docs/documents/proposal.pdf`; this page is the short version. The
pipeline it turns into is `docs/todo.md`, the data choices behind each source are in
`docs/data/`, and what was deliberately not used is in `docs/comparisons.md`.

## The problem

Metagenomic datasets carry DNA that came from the lab rather than the sample: bacteria
living in extraction kits and reagents (Salter et al., 2014). This is not a nuisance at
the margins. It produced headline results that had to be retracted — the Poore et al.
blood-microbiome cancer classifier, taken apart by Gihawi et al. (2023).

The standard defense, `decontam` (Davis et al., 2018), needs negative controls and works
on taxon abundance. Most published datasets have no usable controls, and abundance cannot
answer the question that matters: *Ralstonia* in ten patients is either ten real
colonizations or one kit strain counted ten times, and the read counts look the same
either way.

## The idea

Genuine host-associated microbes are **populations**. They diverge between people, so the
same species carries different strain structure in every sample.

Kit contaminants are **clones**. They are a few strains from one manufacturing run, so
they are near-identical in every sample they appear in.

Tandem repeat (TR) loci mutate faster than anything else in a bacterial genome
(van Belkum et al., 1998), which makes TR allele lengths a high-resolution fingerprint of
provenance. Reading them across samples turns a biological measurement into a
computational filter, and one that needs no negative control.

**H1 (primary).** At a given locus, genuine signal shows high cross-sample entropy in TR
allele length; contaminants show low entropy. The gap should remain detectable at the low
sequencing depths characteristic of tumor samples.

**H2 (secondary).** Contaminant TR signatures cluster by technical variables — kit,
center, batch. Genuine TR calls do not.

De novo contaminant detection without controls has been approached before at the level of
cross-sample taxonomic co-occurrence (Liu et al., 2022, Squeegee). The open question here
is whether within-taxon *sequence* variation carries the signal at finer resolution.

## What each dataset is for

| Data | Scale | Role |
| ---- | ----- | ---- |
| HMP1 shotgun reads (`HHS/HMASM/WGS/`) | 274 samples: stool 139 (998 GB), tongue dorsum 128 (760 GB), subgingival plaque 7 | The positive side. Real, diverse microbiomes across hundreds of people: the baseline for what high TR entropy looks like, and the taxa that must *not* cluster by center under H2 |
| Salter et al. (2014) reads (ENA `ERP006808`) | 35 MiSeq runs, 0.49 GB; 4 kits × 10 dilution steps, plus `PSP_PLUS` at 4 and one water control | The negative side. A pure-contaminant dataset with known kit labels: tests H1's low-entropy prediction directly and supplies real batch labels for H2 |
| SRA run metadata freeze (`sra/metadata_json/`, `09_01_2020`) | 60 files, 2.3 GB → 568 WGS/Illumina runs over all 274 HMP samples | H2's batch labels. Which center sequenced each HMP sample and when, and the only place Salter's kit and dilution can be recovered from (they live in free text) |
| HMP reference genomes (`reference_genomes/`) | 198 genomes for target genera, 760 MB | The TR locus catalog that inTRuder builds — where to look |
| HMP mock community (`HHS/HMMC/`) | 22 known strains, 27 MB | Ground truth. Checks the catalog and the allele caller before either is trusted on real samples |
| Contaminant genomes and spike-ins | 30 genomes: 5 kit genera, 6 species each (`docs/manifests/contaminants/kit.md`) | The controlled benchmark: clonal contaminant reads laid onto HMP samples, one strain per synthetic batch, titrated to tumor-like depth |

Per-dataset provenance, exact prefixes, and the manifest that fetches each one are in the
Table 1 of `docs/todo.md`.

### Known weakness

The HMP centers are unbalanced: WUGSC and BI account for 91% of the 568 runs, BCM has 34
and JCVI 19. H2's "genuine taxa do not cluster by center" test therefore rests on two
dominant centers, and the two small ones carry little weight
(`docs/data/derived/hmp-sra-runs.md`).

## The arc

1. Catalog TR loci in reference genomes with inTRuder, using cataloging logic adapted
   from PhasomeIt.
2. Stream HMP reads from S3 through a locus filter on SLURM, one array task per sample —
   nothing bulk is stored.
3. Call allele lengths, correcting short-read error with a stutter model adapted from
   STRling and HipSTR.
4. Compute cross-sample entropy per locus with a bias-corrected estimator (Chao–Shen),
   sequencing depth as a covariate, no rarefying.
5. Train a gradient boosting classifier with SHAP attribution on the TR diversity and
   batch features; benchmark against `decontam`.

In one line: HMP shows what real diversity looks like, Salter shows what a kit
contaminant looks like, and TR entropy is the ruler that separates them without a
negative control.
