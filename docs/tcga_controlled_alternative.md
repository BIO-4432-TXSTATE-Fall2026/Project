# Alternatives if TCGA controlled access is unavailable

What the project in `docs/proposal.pdf` can use if dbGaP access to TCGA COAD/STAD
raw reads does not come through. HMP data choices are in `docs/HMP_proposed.md`.

## What TCGA provided

- A real low-biomass tumor setting for the "low sequencing depth" claim in H1.
- Clinical sequencing-center and plate batches for H2.
- Evaluation against Gihawi et al. (2023) labels.

The proposal already notes that the Gihawi et al. labels test an adjacent failure mode
(database misclassification and normalization), not the H1 mechanism. Open datasets with
known contaminant identity test H1 more directly.

## Replacements

### 1. Salter et al. (2014) shotgun metagenomes: real contaminants, known labels

ENA `ERP006808`. A pure *Salmonella bongori* culture, serially diluted 10-fold five
times, extracted with four kits. Contamination dominates by the fifth dilution.

- Every non-*S. bongori* read is a contaminant by construction.
- Contaminant profiles differ by kit, so kit is the H2 batch variable.
- Already cited in the proposal for the problem statement.
- The true organism is one clonal culture, so it also has low TR entropy. Use this
  dataset for the contaminant side only: low entropy, stable across dilutions,
  grouping by kit.
- The 16S data from the same study (`ERP006737`) do not contain TR loci.

### 2. Clonal contaminant spike-ins on HMP reads: exact ground truth

Take HMP `stool` and oral WGS samples as genuine diverse populations. Add reads
simulated from a single genome per contaminant genus (e.g. *Ralstonia*,
*Bradyrhizobium*) at controlled fractions, with a distinct contaminant strain per
synthetic batch.

- Tests H1 with exact labels and H2 with known batch structure.
- Titrate depth down to tumor-like microbial read counts to test the low-depth claim.
- Read subsampling here is a sensitivity analysis, not rarefying: the entropy
  estimator still runs on unrarefied counts.
- Salter et al. contaminant reads could replace simulated ones for realism.

### 3. HMP sequencing centers: the negative side of H2

HMP1 WGS was sequenced at several centers. The planned `sra-metadata` mapping from
`SRS` samples to runs, center, and date gives real batch labels. Genuine taxa should
not cluster by center, which is testable without controlled data.

### 4. Public colorectal cancer fecal metagenomes: keeps the cancer angle

Zeller et al. (2014), ENA `ERP005534`: 156 French fecal shotgun samples, with
*Fusobacterium* enriched in CRC. Wirbel et al. (2019) pooled further public cohorts
across countries.

- Real tumor-associated taxa (*Fusobacterium*, *Porphyromonas*) across many patients.
- Cross-study structure gives another batch variable.
- Study and geography are confounded, so genuine strain structure may also cluster by
  cohort. Weak evidence for H2.

## Maybe

- **CCLE RNA-seq** (SRA `PRJNA523380`, open): cancer cell lines, where microbial reads
  are almost entirely contamination. RNA only captures TR loci in expressed genes. The
  AWS Open Data listing also mentions WGS; open access for it is unverified.
- **de Goffau et al. (2019)** placenta study: shotgun and 16S with kit-batch-tracked
  contamination. Only the 16S ENA links are confirmed public; check shotgun availability.

## Not usable

- Poore et al. (2020) TCGA microbial count tables and Gihawi et al. (2023) supplementary
  taxon calls are public but contain no reads, so no TR allele lengths. At most, use the
  Gihawi et al. rejected taxa to choose spike-in contaminant genera.
- TCGA open-tier metadata (center, plate) without reads.

## Proposal changes

- **H1:** testable on (1) and (2). The low-depth tumor claim becomes a simulation
  result.
- **H2:** testable with kit batches (1), synthetic batches (2), and real centers for
  genuine taxa (3). Clinical sequencing batches are not covered.
- **Table 1:** replace the TCGA row with Salter et al. and the spike-in benchmark.
  Reframe Gihawi et al. as motivation rather than evaluation labels.
- **Section 4:** drop confirmation against Gihawi et al.; move TCGA to future work.

## Sources

- [Salter et al. 2014, BMC Biology](https://link.springer.com/article/10.1186/s12915-014-0087-z)
- [de Goffau et al. 2019, author correction](https://www.nature.com/articles/s41586-019-1628-y)
- [Zeller et al. 2014 data reuse](https://pmc.ncbi.nlm.nih.gov/articles/PMC4865240/)
- [Wirbel et al. 2019, Nature Medicine](https://www.nature.com/articles/s41591-019-0406-6)
- [CCLE, Registry of Open Data on AWS](https://registry.opendata.aws/ccle/)
- [Ghandi et al. 2019, Nature](https://www.nature.com/articles/s41586-019-1186-3)
