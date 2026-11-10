# What this project does

One picture of the whole project. The claim being tested is in `docs/problem.md`, the
step-by-step plan in `docs/todo.md`.

In one line: **genuine microbes are populations and kit contaminants are clones, so
tandem-repeat allele length should vary across samples for one and not the other** — and
that difference becomes a contaminant filter that needs no negative control.

```mermaid
flowchart TD
    subgraph ACQ["1. Data acquisition"]
        HMP["HMP1 shotgun reads<br/>274 samples, 1.77 TB"]
        SALT["Salter 2014 dilution series<br/>35 runs, 4 extraction kits"]
        META["SRA metadata freeze"]
        REFG["HMP reference genomes<br/>198, target genera"]
        MOCK["Mock community<br/>22 known strains"]
        CONTG["Contaminant genomes<br/>5 kit genera"]
        CHM13["T2T-CHM13<br/>human reference"]
        GIHAWI["Gihawi 2023 audit<br/>taxa rejected as misclassified"]
    end

    subgraph CATALOG["2. Reference cataloging"]
        FIND["TR finder over reference contigs<br/>(inTRuder fork)"]
        MERGE["Merge calls into loci<br/>canonical motif + overlap"]
        CAT["TR locus catalog"]
        SELFCHK{{"Ground-truth check:<br/>do catalog loci recover<br/>in the mock strains?"}}
        HUMSCR{{"Human screen:<br/>motif also present<br/>in CHM13?"}}
    end

    subgraph MEASURE["3. Allele calling"]
        GATE["Search sequences<br/>catalog loci and their flanks"]
        STREAM["Keep only reads that<br/>match a catalog locus"]
        ANCHOR["Assign each kept read to its locus"]
        ALLELE["Per-sample allele lengths"]
        SPIKE["Known contaminant reads<br/>mixed into HMP samples"]
    end

    subgraph STATS["4. Entropy and the hypotheses"]
        ENT["Cross-sample allele-length entropy per locus<br/>depth as a covariate"]
        GENUINE["Entropy of real microbes<br/>HMP body sites"]
        CLONAL["Entropy of kit contaminants<br/>Salter kits"]
        H1{{"H1: Is there an entropy gap,<br/>and does it hold as<br/>read depth falls?"}}
        H2{{"H2: Do contaminants cluster<br/>by kit/batch while genuine<br/>taxa do not?"}}
    end

    subgraph OUTPUT["5. Classification and validation"]
        FEAT["TR diversity + batch features"]
        MODEL["Gradient boosting + SHAP<br/>(isolation forest fallback)"]
        BASE["Baseline: decontam<br/>on the Salter dilution series"]
        TRANSFER["Test: do we flag<br/>the taxa the audit rejected?"]
        DELIV(["Hopeful output:<br/>control-free contaminant detection<br/>flags kit contaminants<br/>in existing datasets"])
    end

    REFG --> FIND
    MOCK --> FIND
    CONTG --> FIND
    FIND --> MERGE --> CAT
    MOCK --> SELFCHK
    CAT --> SELFCHK
    CHM13 --> HUMSCR
    CAT --> HUMSCR
    SELFCHK -->|"loci that recover"| GATE
    HUMSCR -->|"loci unique to microbes"| GATE

    HMP --> STREAM
    SALT --> STREAM
    CONTG --> SPIKE
    SPIKE --> STREAM
    GATE --> STREAM
    STREAM --> ANCHOR --> ALLELE

    ALLELE --> ENT
    ENT --> GENUINE
    ENT --> CLONAL
    GENUINE --> H1
    CLONAL --> H1
    META --> H2
    ENT --> H2

    H1 --> FEAT
    H2 --> FEAT
    FEAT --> MODEL
    SPIKE -.->|"training labels"| MODEL
    MODEL --> DELIV
    BASE --> DELIV
    GIHAWI --> TRANSFER
    MODEL --> TRANSFER
    TRANSFER --> DELIV

    classDef genuine fill:#cfe6f7,stroke:#30566e,color:#10242f
    classDef contaminant fill:#e8dfc0,stroke:#7a6a35,color:#2b2512
    classDef reference fill:#ded0ec,stroke:#5e4878,color:#241a30
    class HMP,GENUINE genuine
    class SALT,CONTG,SPIKE,CLONAL,GIHAWI contaminant
    class REFG,MOCK,CHM13,FIND,MERGE,CAT,SELFCHK,HUMSCR,GATE reference
```

A rendered copy of the same diagram is in `docs/flowchart.png`, for viewers that do
not draw Mermaid. Rebuild it after editing the block above:

```sh
docs/render-flowchart.sh docs/flowchart.md docs/flowchart.png 2
```

The script drives the local Chrome in headless mode: it renders the Mermaid block with
the ELK layout engine, lifts the lane titles clear of the edges, gives each edge a white
halo so crossings read as jumps, and screenshots the result at the trailing scale factor.
It needs Google Chrome installed and network access for the Mermaid module, so it is a
macOS helper rather than a Pixi task. GitHub draws the block above with its own layout
engine, so the page and the PNG route their edges differently.

## How to read it

- **Three colours, three roles.** Blue is the genuine side (HMP, real people, real
  diversity). Tan is the contaminant side (Salter's kits, the clonal spike-ins, the known
  false positives). Purple is reference material — the genomes that say *where* to look,
  and the screens that decide which loci are trustworthy.
- **The two hexagons in lane 2 are checks, not steps.** Everything downstream is
  conditional on them: a locus that does not recover in genomes of known strains is a
  finder artifact, and a motif that also occurs in human cannot separate contamination
  from host — that is the same confusion one level down.
- **Lane 3 never lands the data.** The HMP samples are ~6.5 TB decompressed, so each is
  read, unpacked and filtered in a single pass on the cluster, and only locus-hitting
  reads are kept.
- **Lane 4 is the experiment.** Lanes 1–3 are machinery whose only purpose is to produce
  a defensible number for the entropy of one locus in one sample.

## State of play

Lanes 1–3 are partly built: data acquisition and the streaming read filter exist, the TR
finder runs over reference genomes, and the mock-community catalog has been built once.
The locus merge, the human screen, allele calling, the stutter model, entropy, both
hypothesis tests and the classifier do not exist yet — `--stage pipeline` stops after the
read filter. `docs/todo.md` tracks each box.
