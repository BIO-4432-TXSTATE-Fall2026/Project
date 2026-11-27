include { SRA_RUN_METADATA } from './modules/preprocess/sra_metadata'
include { TR_CATALOG } from './modules/preprocess/tr_catalog'
include { TR_SWEEP } from './modules/preprocess/tr_sweep'
include { TR_LOCI } from './modules/pipeline/tr_loci'
include { TR_SCREEN as SCREEN_HUMAN } from './modules/pipeline/tr_screen'
include { TR_SCREEN as SCREEN_MOCK } from './modules/pipeline/tr_screen'
include { TR_PANEL } from './modules/pipeline/tr_panel'
include { TR_FILTER } from './modules/pipeline/tr_filter'
include { FILTER_SUMMARY } from './modules/pipeline/filter_summary'
include { TR_ALLELES } from './modules/pipeline/tr_alleles'
include { TR_ALLELES as SPIKE_ALLELES } from './modules/pipeline/tr_alleles'
include { ALLELE_TABLE } from './modules/pipeline/allele_table'
include { ALLELE_TABLE as SPIKE_TABLE } from './modules/pipeline/allele_table'
include { SIMULATE_READS } from './modules/pipeline/simulate_reads'
include { TR_GATE } from './modules/pipeline/tr_gate'
include { SPIKE_CHECK } from './modules/pipeline/spike_check'
include { SPIKE_MIX } from './modules/pipeline/spike_mix'
include { notifyRun; announceStart; announceDone } from './modules/notify'

// A genome spec's lockfile, or nothing if the spec has never been synced. The catalog
// processes sync inside the task, which writes the lock there, so a spec such as
// reference/kit can be cataloged before anyone has synced it by hand. A missing file
// cannot be staged, and an empty list stages nothing.
def specLock(spec) {
    def lock = file("${spec.parent}/${spec.simpleName}.lock.json")
    return lock.exists() ? lock : []
}

// A spec named relative to manifests/, as the pipeline's parameters name them:
// `reference/kit` is manifests/reference/kit.json.
def manifestSpec(name) {
    return file("${projectDir}/../manifests/${name.trim()}.json", checkIfExists: true)
}

// Preprocessing: rebuild the committed tables in data/derived/ from their upstream
// catalogs. A stage of its own rather than part of the analysis, because its outputs are
// committed and rebuilding them is a rare, deliberate act.
//
// `--preprocess` picks which part runs. Not a convenience: the tables need a 2.3 GB
// metadata freeze and the catalog needs up to a gigabyte of genomes, so asking for one
// and getting both is an expensive accident. The default is still everything.
workflow PREPROCESS {
    main:
    tables = channel.empty()
    catalog = channel.empty()
    beds = channel.empty()
    sweep = channel.empty()

    if (params.preprocess in ['all', 'tables']) {
        spec = file(params.sra_metadata_spec, checkIfExists: true)
        lock = file("${spec.parent}/${spec.simpleName}.lock.json", checkIfExists: true)
        sample_locks = files(params.hmp_sample_locks, checkIfExists: true)

        // The spec is passed as a channel rather than a value so its arrival can be
        // tapped; the phase has one task either way.
        SRA_RUN_METADATA(announceStart(channel.of(spec), 'SRA run metadata'),
                         lock, sample_locks, params.hmp_sra_runs_table,
                         params.salter_study, params.salter_runs_table)

        tables = announceDone(SRA_RUN_METADATA.out.hmp.mix(SRA_RUN_METADATA.out.salter),
                              'SRA run metadata')
    }

    if (params.preprocess == 'sweep') {
        sweep_spec = file(params.catalog_spec, checkIfExists: true)
        sweep_lock = specLock(sweep_spec)

        TR_SWEEP(announceStart(channel.of(sweep_spec), 'TR sweep'),
                 sweep_lock, params.catalog_profile, params.sweep_max_extensions,
                 params.sweep_identities,
                 params.sweep_seed_units, params.sweep_seed_lengths,
                 params.catalog_genome_from, params.sweep_table)

        sweep = announceDone(TR_SWEEP.out.sweep, 'TR sweep')
    }

    if (params.preprocess in ['all', 'catalog']) {
        genome_spec = file(params.catalog_spec, checkIfExists: true)
        genome_lock = specLock(genome_spec)

        // Nextflow refuses a null `val` input, so an unset threshold crosses as ''.
        identity = params.catalog_min_identity == null ? '' : params.catalog_min_identity
        seed_units = params.catalog_min_seed_units == null ? '' : params.catalog_min_seed_units
        seed_length = params.catalog_min_seed_length == null ? '' : params.catalog_min_seed_length
        max_extension = params.catalog_max_extension == null ? '' : params.catalog_max_extension

        TR_CATALOG(announceStart(channel.of(tuple(genome_spec, genome_lock,
                                                  params.catalog_table, params.catalog_bed)),
                                 'TR catalog'),
                   params.catalog_profile, identity, seed_units, seed_length, max_extension,
                   params.catalog_genome_from)

        catalog = announceDone(TR_CATALOG.out.catalog, 'TR catalog')
        beds = TR_CATALOG.out.bed
    }

    emit:
    tables = tables
    catalog = catalog
    beds = beds
    sweep = sweep
}

// The reference catalog: the loci the gate looks for, and the panel they are filtered to.
// One TR_CATALOG task per spec in `--panel_specs`, merged by TR_LOCI into loci that are the
// same across genomes, then screened against human (excluded) and the mock community
// (annotated) before TR_PANEL writes the gate's reference. docs/workflows/pipeline/README.md
// has the design.
workflow CATALOG {
    main:
    panel_specs = params.panel_specs.tokenize(',').collect { name -> manifestSpec(name) }
    // A spec never synced has no lock yet; its task syncs and writes one.
    panel_locks = panel_specs.collect { spec ->
        file("${spec.parent}/${spec.simpleName}.lock.json")
    }.findAll { lock -> lock.exists() }

    // Nextflow refuses a null `val` input, so an unset threshold crosses as ''.
    identity = params.catalog_min_identity == null ? '' : params.catalog_min_identity
    seed_units = params.catalog_min_seed_units == null ? '' : params.catalog_min_seed_units
    seed_length = params.catalog_min_seed_length == null ? '' : params.catalog_min_seed_length
    max_extension = params.catalog_max_extension == null ? '' : params.catalog_max_extension

    // Each spec carries its own output names, so the tables do not overwrite each other.
    // `auto` names a spec's genomes by its layout: HMP by directory, the rest by file.
    specs = channel.fromList(panel_specs).map { spec ->
        tuple(spec, specLock(spec), "tr-catalog.${spec.simpleName}.tsv",
              "tr-catalog.${spec.simpleName}.bed")
    }
    TR_CATALOG(announceStart(specs, 'TR catalog'),
               params.catalog_profile, identity, seed_units, seed_length, max_extension, 'auto')

    TR_LOCI(announceDone(TR_CATALOG.out.catalog, 'TR catalog').collect(),
            panel_specs, panel_locks,
            params.filter_flank, params.loci_anchor, params.loci_max_rep_length)

    human_spec = manifestSpec(params.screen_human_spec)
    mock_spec = manifestSpec(params.screen_mock_spec)
    SCREEN_HUMAN(announceStart(TR_LOCI.out.fasta, 'TR screen'), human_spec, specLock(human_spec),
                 params.screen_fragment, params.screen_overlap,
                 params.filter_k, params.filter_hdist)
    SCREEN_MOCK(TR_LOCI.out.fasta, mock_spec, specLock(mock_spec),
                params.screen_fragment, params.screen_overlap,
                params.filter_k, params.filter_hdist)

    TR_PANEL(TR_LOCI.out.table, TR_LOCI.out.fasta,
             SCREEN_HUMAN.out.screen, SCREEN_MOCK.out.screen)

    emit:
    catalogs = TR_CATALOG.out.catalog
    beds = TR_CATALOG.out.bed
    loci = TR_LOCI.out.table.mix(TR_LOCI.out.fasta, TR_LOCI.out.stats)
    screens = SCREEN_HUMAN.out.screen.mix(SCREEN_MOCK.out.screen)
    panel = announceDone(TR_PANEL.out.table.mix(TR_PANEL.out.fasta), 'TR panel')
    panel_table = TR_PANEL.out.table
    panel_fasta = TR_PANEL.out.fasta
}

// The streaming read filter: each HMP sample streamed from S3 through a k-mer gate built
// from the panel, keeping only the reads that touch a locus. The samples are 1.77 TB
// compressed and ~6.5 TB of FASTQ, so nothing is downloaded: TR_FILTER owns the stream,
// one task per sample. docs/workflows/pipeline/README.md has the design.
//
// Run on its own, the gate's reference is the panel an earlier `catalog` run published;
// run with it, the panel it just built.
workflow FILTER {
    take:
    panel_fasta

    main:
    // The samples come from the lockfiles rather than a list here: a lock is what was
    // planned against, and its ETags are what the stream is checked against. A body
    // site's spec sits beside its lock, and `filter` reads both.
    // One file per site rather than a brace glob: Nextflow leaves a one-site `{x}`
    // unexpanded, and a site named wrongly should say which one.
    locks = params.filter_sample_locks
        ? channel.fromPath(params.filter_sample_locks, checkIfExists: true)
        : channel.fromList(params.filter_body_sites.tokenize(',')).map { site ->
            file("${projectDir}/../manifests/hmp/${site.trim()}.lock.json",
                 checkIfExists: true)
        }
    samples = locks.flatMap { lock ->
        def spec = file("${lock.parent}/${lock.name.replace('.lock.json', '.json')}",
                        checkIfExists: true)
        lock.splitJson(path: 'files').collect { record ->
            def sample = record.key.tokenize('/').last().tokenize('.').first()
            tuple(sample, spec, lock, record.key, record.etag)
        }
    }

    // Nextflow refuses a null `val` input, so no cap crosses as ''.
    max_reads = params.filter_max_reads == null ? '' : params.filter_max_reads

    TR_FILTER(announceStart(samples, 'TR filter'), panel_fasta.first(),
              params.filter_k, params.filter_hdist, params.filter_threads,
              params.filter_decompressor, max_reads)

    FILTER_SUMMARY(TR_FILTER.out.counts.collect(), params.filter_summary_table)

    emit:
    reads = announceDone(TR_FILTER.out.reads, 'TR filter')
    counts = TR_FILTER.out.counts
    summary = FILTER_SUMMARY.out.summary
}

// Allele calling: each sample's gated reads turned into repeat lengths per panel locus, and
// every sample's table gathered into one. The reads' headers name the panel loci they
// matched, so the panel table is all the caller needs beside them. See
// docs/workflows/pipeline/README.md.
//
// Run on its own, the reads are the ones an earlier filter run published.
workflow ALLELES {
    take:
    reads                  // paths of <sample>.loci.fastq.gz
    panel_table

    main:
    // The panel's anchors are `loci_anchor` long; the caller matches that many unless told
    // otherwise. Nextflow refuses a null `val` input, so the whole anchor crosses as ''.
    anchor = params.alleles_anchor == null ? params.loci_anchor : params.alleles_anchor
    samples = reads.map { file -> tuple(file.name.replace('.loci.fastq.gz', ''), file) }

    TR_ALLELES(announceStart(samples, 'TR alleles'), panel_table.first(), anchor,
               params.alleles_mismatches)
    ALLELE_TABLE(TR_ALLELES.out.alleles.collect(), TR_ALLELES.out.stats.collect(),
                 params.alleles_table, params.alleles_stats_table)

    emit:
    alleles = announceDone(ALLELE_TABLE.out.alleles, 'TR alleles')
    stats = ALLELE_TABLE.out.stats
}

// The spike-in benchmark: reads simulated from the kit genomes go through the gate and the
// caller as a sample's do, and their alleles, whose true lengths the panel records, are
// scored (SPIKE_CHECK) and mixed into the hosts' alleles as labelled contaminants
// (SPIKE_MIX). The mix reads the hosts' allele table, which an earlier alleles run
// published unless the alleles part runs too.
workflow SPIKE {
    take:
    panel_fasta
    panel_table
    host_alleles

    main:
    spec = manifestSpec(params.spike_spec)
    anchor = params.alleles_anchor == null ? params.loci_anchor : params.alleles_anchor
    hosts = params.spike_hosts == null ? '' : params.spike_hosts

    SIMULATE_READS(announceStart(channel.of(spec), 'Spike-in reads'), specLock(spec),
                   params.spike_reads, params.spike_seed)

    simulated = SIMULATE_READS.out.reads.flatten().map { file ->
        tuple(file.name.replace('.fastq.gz', ''), file)
    }
    TR_GATE(simulated, panel_fasta.first(), params.filter_k, params.filter_hdist)

    gated = TR_GATE.out.reads.map { file -> tuple(file.name.replace('.loci.fastq.gz', ''), file) }
    SPIKE_ALLELES(gated, panel_table.first(), anchor, params.alleles_mismatches)
    SPIKE_TABLE(SPIKE_ALLELES.out.alleles.collect(), SPIKE_ALLELES.out.stats.collect(),
                params.spike_alleles_table, params.spike_stats_table)

    SPIKE_CHECK(panel_table.first(), SPIKE_TABLE.out.alleles, SPIKE_TABLE.out.stats)
    SPIKE_MIX(panel_table.first(), host_alleles.first(), SPIKE_TABLE.out.alleles, hosts)

    emit:
    check = announceDone(SPIKE_CHECK.out.check, 'Spike-in check')
    mixed = SPIKE_MIX.out.alleles.mix(SPIKE_MIX.out.labels)
    tables = SPIKE_TABLE.out.alleles.mix(SPIKE_TABLE.out.stats)
}

// What a run of `--pipeline` asks for: each part named, `all` meaning every one, and the
// parts that did not run left for the published outputs of an earlier run to stand in.
def pipelineParts(selection) {
    def known = ['catalog', 'filter', 'alleles', 'spike']
    def named = selection.toString().tokenize(',').collect { part -> part.trim() }
    def unknown = named.findAll { part -> part != 'all' && !(part in known) }
    if (unknown || !named) {
        error("unknown --pipeline '${selection}'; use 'all' or a comma-separated list of " +
              known.join(', '))
    }
    return named.contains('all') ? known : named
}

// A published output of an earlier run, for a part that starts without the part that makes it.
def published(path) {
    return channel.value(file("${workflow.outputDir}/${path}", checkIfExists: true))
}

workflow {
    main:
    notifyRun()

    derived = channel.empty()
    catalog = channel.empty()
    beds = channel.empty()
    sweep = channel.empty()
    panel_catalogs = channel.empty()
    panel_beds = channel.empty()
    loci = channel.empty()
    screens = channel.empty()
    panel = channel.empty()
    reads = channel.empty()
    counts = channel.empty()
    summary = channel.empty()
    alleles = channel.empty()
    allele_stats = channel.empty()
    spike_check = channel.empty()
    spike_mixed = channel.empty()
    spike_tables = channel.empty()
    if (params.stage == 'preprocess') {
        if (!(params.preprocess in ['all', 'tables', 'catalog', 'sweep'])) {
            error("unknown --preprocess '${params.preprocess}'; " +
                  "use 'all', 'tables', 'catalog' or 'sweep'")
        }
        out = PREPROCESS()
        derived = out.tables
        catalog = out.catalog
        beds = out.beds
        sweep = out.sweep
    }
    else if (params.stage == 'pipeline') {
        def parts = pipelineParts(params.pipeline)
        // The panel the gate and the caller read. A part that starts after the catalog
        // reads what an earlier catalog run published.
        panel_fasta = channel.empty()
        panel_table = channel.empty()
        if ('catalog' in parts) {
            built = CATALOG()
            panel_catalogs = built.catalogs
            panel_beds = built.beds
            loci = built.loci
            screens = built.screens
            panel = built.panel
            panel_fasta = built.panel_fasta
            panel_table = built.panel_table
        }
        else {
            if ('filter' in parts || 'spike' in parts) {
                panel_fasta = published('catalog/tr-panel.fa')
            }
            if ('alleles' in parts || 'spike' in parts) {
                panel_table = published('catalog/tr-panel.tsv')
            }
        }
        gated = channel.empty()
        if ('filter' in parts) {
            filtered = FILTER(panel_fasta)
            gated = filtered.reads
            reads = filtered.reads
            counts = filtered.counts
            summary = filtered.summary
        }
        else if ('alleles' in parts) {
            gated = channel.fromPath("${workflow.outputDir}/filter/reads/*.loci.fastq.gz",
                                     checkIfExists: true)
        }
        host_alleles = channel.empty()
        if ('alleles' in parts) {
            called = ALLELES(gated, panel_table)
            alleles = called.alleles
            allele_stats = called.stats
            host_alleles = called.alleles
        }
        else if ('spike' in parts) {
            host_alleles = published('alleles/alleles.tsv')
        }
        if ('spike' in parts) {
            spiked = SPIKE(panel_fasta, panel_table, host_alleles)
            spike_check = spiked.check
            spike_mixed = spiked.mixed
            spike_tables = spiked.tables
        }
    }
    else {
        error("unknown --stage '${params.stage}'; use 'preprocess' or 'pipeline'")
    }

    publish:
    derived = derived
    catalog = catalog
    beds = beds
    sweep = sweep
    panel_catalogs = panel_catalogs
    panel_beds = panel_beds
    loci = loci
    screens = screens
    panel = panel
    reads = reads
    counts = counts
    summary = summary
    alleles = alleles
    allele_stats = allele_stats
    spike_check = spike_check
    spike_mixed = spike_mixed
    spike_tables = spike_tables
}

output {
    // The derived tables are committed, so they are published into the working tree, not
    // into results/. docs/data/README.md says what each one is.
    derived {
        path 'derived'
    }
    // The catalog is not committed: its parameters are not settled, so what lands here is
    // one point in a sweep rather than a result. /data/derived/catalog/ is git-ignored for
    // that reason, and the path encodes the parameters it was built with.
    catalog {
        path 'derived/catalog'
    }
    beds {
        path 'derived/catalog'
    }
    sweep {
        path 'derived/catalog'
    }
    // The pipeline stage publishes into results/. Everything is copied, not symlinked: a
    // symlink into work/ is destroyed by `nextflow clean`, which is fine for a table that
    // rebuilds in minutes and not for reads that took a day to stream.
    // The reference catalog, kept together so the reads can always be traced to the loci
    // they were gated against: each spec's calls, the merged loci and what dropped, the
    // screens, and the panel the gate reads.
    panel_catalogs {
        path 'catalog'
        mode 'copy'
    }
    panel_beds {
        path 'catalog'
        mode 'copy'
    }
    loci {
        path 'catalog'
        mode 'copy'
    }
    screens {
        path 'catalog'
        mode 'copy'
    }
    panel {
        path 'catalog'
        mode 'copy'
    }
    reads {
        path 'filter/reads'
        mode 'copy'
    }
    counts {
        path 'filter/counts'
        mode 'copy'
    }
    summary {
        path 'filter'
        mode 'copy'
    }
    // Allele calls per sample, and what the caller made of each sample's reads.
    alleles {
        path 'alleles'
        mode 'copy'
    }
    allele_stats {
        path 'alleles'
        mode 'copy'
    }
    // The spike-in benchmark: the caller's score against known lengths, the simulated
    // genomes' own alleles, and those mixed into the hosts with their labels.
    spike_check {
        path 'spike'
        mode 'copy'
    }
    spike_mixed {
        path 'spike'
        mode 'copy'
    }
    spike_tables {
        path 'spike'
        mode 'copy'
    }
}
