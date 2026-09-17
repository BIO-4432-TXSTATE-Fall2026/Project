# AWS open data candidates

**SOME** Microbial and NCBI datasets from the [Registry of Open Data on AWS](https://registry.opendata.aws/) that may be useful (all public, no AWS account required).

## Genome sequences


| Dataset                                                                                          | Bucket (region)                                  | Contents                                                                                                    |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| [AllTheBacteria](https://registry.opendata.aws/allthebacteria/)                                  | `allthebacteria-assemblies` (eu-west-2)          | Uniform short-read assemblies of all SRA bacterial isolates to Aug 2024, one `<BioSample>.fa.gz` per sample |
|                                                                                                  | `allthebacteria-phylogeneticbatches` (eu-west-2) | Same assemblies as batched xz archives                                                                      |
|                                                                                                  | `allthebacteria-metadata` (eu-west-2)            | S3 inventory listings only                                                                                  |
| [NCBI BLAST databases](https://registry.opendata.aws/ncbi-blast-databases/)                      | `ncbi-blast-databases` (us-east-1)               | BLAST DBs including `ref_prok_rep_genomes` and `nt_prok`; sequences extractable with `blastdbcmd`           |
| [Kraken2 RefSeq Complete V205](https://registry.opendata.aws/kraken2-ncbi-refseq-complete-v205/) | `kraken2-ncbi-refseq-complete-v205` (us-west-2)  | Kraken2 DB of all RefSeq genomes (V205); may include library FASTA                                          |
| [SoilMicrobeDB](https://registry.opendata.aws/soil_microbe_db/)                                  | `kraken2-soil-microbe-database` (us-east-2)      | Kraken2 DB of soil genomes (soil taxa like *Bradyrhizobium*)                                                |
| [Slacken](https://registry.opendata.aws/slacken/)                                                | `slacken` (us-east-1)                            | Metagenomic reference libraries for Slacken                                                                 |
| [krepp references](https://registry.opendata.aws/kreppref/)                                      | `kreppref` (us-west-1)                           | krepp indexes over thousands of reference genomes                                                           |
| [SocialGene](https://registry.opendata.aws/socialgene/)                                          | `socialgene-open-data` (us-east-2)               | Neo4j graphs built from RefSeq genomes                                                                      |
| [Logan](https://registry.opendata.aws/pasteur-logan/)                                            | `logan-pub` (us-east-1)                          | Unitigs and contigs for every SRA run (Dec 2023 freeze)                                                     |


## Reads and metadata


| Dataset                                                                             | Bucket (region)                                                                                                 | Contents                                      |
| ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| [Human Microbiome Project](https://registry.opendata.aws/human-microbiome-project/) | `human-microbiome-project` (us-west-2)                                                                          | HMP1 reads, reference genomes, mock community |
| [NCBI SRA](https://registry.opendata.aws/ncbi-sra/)                                 | `sra-pub-run-odp`, `sra-pub-src-1`, `sra-pub-src-2`, `sra-ca-run-odp`, `sra-pub-metadata-us-east-1` (us-east-1) | SRA runs, original submissions, run metadata  |
| [NCBI SRA RNA-Seq counts](https://registry.opendata.aws/ncbi-sra-rnaseq/)           | `sra-rnaseq-analysis` (us-east-1)                                                                               | Human and mouse gene counts                   |
| [DNAStack COVID-19 SRA](https://registry.opendata.aws/dnastack-covid-19-sra-data/)  | `dnastack-covid-19-sra-data` (us-west-2)                                                                        | SARS-CoV-2 SRA analyses                       |
| [NCBI COVID-19](https://registry.opendata.aws/ncbi-covid-19/)                       | `sra-pub-sars-cov2` (us-east-1)                                                                                 | SARS-CoV-2 reads and metadata                 |
| [OceanOmics](https://registry.opendata.aws/oceanomics/)                             | `minderoo-oceanomics` (us-west-2)                                                                               | Marine eDNA                                   |
| [QIIME 2 tutorial data](https://registry.opendata.aws/qiime2/)                      | `qiime2-data` (us-west-2)                                                                                       | Amplicon tutorial data                        |


## Indexes and annotation databases

Not usable as genome sources; listed for classification or screening steps.


| Dataset                                                         | Bucket (region)                  | Contents                                       |
| --------------------------------------------------------------- | -------------------------------- | ---------------------------------------------- |
| [NCBI FCS-GX](https://registry.opendata.aws/ncbi-fcs-gx/)       | `ncbi-fcs-gx` (us-east-1)        | Foreign contamination screen database          |
| [MetaGraph](https://registry.opendata.aws/metagraph/)           | `metagraph` (eu-west-1)          | Searchable indexes over SRA/ENA reads          |
| [Kaiju indexes](https://registry.opendata.aws/kaiju-indexes/)   | `kaiju-idx` (eu-central-1)       | Protein-level taxonomic classification indexes |
| [BUSCO](https://registry.opendata.aws/busco-data/)              | `busco-data` (us-east-1)         | Lineage marker-gene HMMs for assembly QC       |
| [Hecatomb](https://registry.opendata.aws/hecatomb/)             | `hecatombdatabases` (us-west-2)  | Viral and phage annotation databases           |
| [run_dbcan](https://registry.opendata.aws/run_dbcan/)           | `dbcan` (us-west-2)              | CAZyme annotation database                     |
| [Steinegger Lab](https://registry.opendata.aws/steineggerlab/)  | `steineggerlab` (us-east-1)      | MMseqs2, ColabFold, Foldseek databases         |
| [ESM Atlas](https://registry.opendata.aws/biohub-esm-atlas/)    | `esm-protein-atlas` (us-west-2)  | Predicted protein structures                   |
| [elDORS](https://registry.opendata.aws/eldors_v1/)              | `eldors-v1-database` (us-east-1) | RNA sequence database                          |
| [Serratus](https://registry.opendata.aws/serratus-lovelywater/) | `lovelywater2` (us-east-1)       | Virus discovery results                        |


