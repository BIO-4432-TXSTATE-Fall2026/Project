# `contaminants/kit`

Genomes for the five kit-contaminant genera the spike-in benchmark uses: the contaminant
half of the TR locus catalog, and the source of the clonal reads laid onto HMP samples.
Which genera, and why those five, is the rest of this page.

```sh
pixi run new contaminants/kit --dataset=slacken \
  --accession=GCF_000284275.1 ...  # one --accession per genome, 30 in all
  --description="Kit-contaminant genomes for the spike-in benchmark: complete RefSeq \
genomes for Bradyrhizobium, Burkholderia, Methylobacterium, Sphingomonas and \
Flavobacterium, six species each (Salter et al. 2014 Table 1)"
pixi run sync manifests/contaminants/kit.json
```

30 genomes, about 192 MB. Every one is a complete RefSeq assembly, one per species, cut
by byte range out of the `slacken` bacterial library (RefSeq release 224), so the 583 GB
library is never downloaded. **Sync on a compute node**: the first slacken sync fetches
the library's index files, about 725 MB, to find where each genome starts.

## The genera

| Genus | Class | GC, about | Genomes | Evidence in Salter et al. (2014) |
| ----- | ----- | --------- | ------- | -------------------------------- |
| *Bradyrhizobium* | Alphaproteobacteria | 63–65% | 6, 47 MB | Dominates the PSP kit in the shotgun series; Table 1, also reported by Laurence et al. |
| *Burkholderia* | Betaproteobacteria | 66–68% | 6, 48 MB | Dominates the FP (FastDNA) kit in the shotgun series; Table 1, also reported by Laurence et al. |
| *Methylobacterium* | Alphaproteobacteria | 68–71% | 6, 41 MB | Table 1, also reported by Barton et al. |
| *Sphingomonas* | Alphaproteobacteria | 62–68% | 6, 31 MB | Table 1, reported by three other sources; dominant at UB in the 16S series |
| *Flavobacterium* | Bacteroidetes | 32–37% | 6, 25 MB | Table 1, also reported by Laurence et al.; Flavobacteriaceae mark the QIA kit in the shotgun series |

*Bradyrhizobium* and *Burkholderia* are the only genera the paper names as dominating a
kit in shotgun data, which is the data type this project reads, so they anchor the set.
The other three are Table 1 genera with independent reports, chosen to fill the gaps
below. Six species per genus means a synthetic batch can use a strain no other batch used.

## Why these five

1. **In Salter et al. Table 1**, which lists genera found in sequenced blank extractions
   over four years at three labs ([`salter-article.md`](salter-article.md)). Genera with
   a superscript there were reported as contaminants by at least one other study; every
   choice has one.
2. **No HMP reference genome.** A genus HMP isolated from people could be genuinely
   present in HMP samples, and then a spike-in no longer has a known label. Checked
   against `list.json` from [`hmp/reference-genomes-list`](../hmp/reference-genomes-list.md):
   24 of the 92 named Table 1 genera have an HMP genome, and none of these five does.
3. **GC must not give the answer away.** The four Proteobacteria sit at 62–71% GC; every
   HMP target genus (*Streptococcus*, *Prevotella*, *Fusobacterium*, *Veillonella*,
   *Campylobacter*, *Porphyromonas*) sits well below 60%. A classifier could separate
   them by composition alone, without TR entropy. *Flavobacterium* is a low-GC
   contaminant inside the targets' range, so the benchmark has a case GC cannot solve.
4. **Complete genomes only.** A TR locus that falls on a contig boundary is lost or
   truncated, so draft assemblies would bias the catalog against long repeats.

## Left out

- ***Ralstonia*.** Table 1 lists it with four other reports, but HMP has two stool
  isolates (`Ralstonia sp. 5_2_56FAA`, `5_7_47FAA`), which breaks rule 2. Those isolates
  may themselves be contamination. It becomes a sixth spike-in genus only if screening
  HMP stool finds no *Ralstonia* background; 65 complete genomes are available if so.
- ***Pseudomonas*.** HMP has a gut isolate, and in Salter et al. it dominates the water
  control rather than any kit.
- ***Stenotrophomonas*.** Reported by all five sources and absent from HMP's genomes, but
  *S. maltophilia* is an opportunistic pathogen found in human airway samples, so finding
  it in a real sample is not proof of contamination.
- **The *Burkholderia pseudomallei* group** (*pseudomallei*, *mallei*, *thailandensis*,
  *oklahomensis*). Kit *Burkholderia* is environmental, so the six are *B. cepacia*
  complex species instead.
- ***Acinetobacter*, *Escherichia*, *Enterobacter*, *Corynebacterium*,
  *Propionibacterium*, *Streptococcus* and the other Table 1 genera with HMP genomes.**
  Rule 2. *Streptococcus* is also an HMP target genus, and appears here only in
  [`misclassified.md`](misclassified.md), for a different reason.

## Traps

- **The lock tracks the library, not the genome.** Slacken locks record `library.fna`'s
  ETag, so a rebuilt library marks all 30 genomes changed even when the sequence did not
  move. RefSeq release 224 is what the accessions were chosen against.
- **Kraken headers.** Sequence headers keep the `kraken:taxid|<taxid>|` prefix the
  library uses. Anything parsing accessions out of FASTA headers has to strip it.
- **Genus, not strain, is the label.** Salter et al. identify kit contaminants to genus.
  Which species within the genus was in any given kit is unknown, so the six species per
  genus are diversity, not a claim about what was in the reagent.

## Sources

- [Salter et al. 2014, BMC Biology](https://doi.org/10.1186/s12915-014-0087-z), Table 1
  and "Shotgun metagenomics of a pure *S. bongori* culture"
- [Slacken metagenomic reference libraries, Registry of Open Data on AWS](https://registry.opendata.aws/slacken/)
