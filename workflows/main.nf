include { SRA_RUN_METADATA } from './modules/preprocess/sra_metadata'
include { TR_CATALOG } from './modules/preprocess/tr_catalog'
include { TR_SWEEP } from './modules/preprocess/tr_sweep'
include { TR_LOCI } from './modules/pipeline/tr_loci'
include { TR_SCREEN as SCREEN_HUMAN } from './modules/pipeline/tr_screen'
include { TR_SCREEN as SCREEN_MOCK } from './modules/pipeline/tr_screen'
include { TR_PANEL } from './modules/pipeline/tr_panel'
include { TR_FILTER } from './modules/pipeline/tr_filter'
include { FILTER_SUMMARY } from './modules/pipeline/filter_summary'
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
        if (!(params.pipeline in ['all', 'catalog', 'filter'])) {
            error("unknown --pipeline '${params.pipeline}'; use 'all', 'catalog' or 'filter'")
        }
        // The gate's reference. A run that starts at the filter reads the panel an
        // earlier catalog run published.
        panel_fasta = channel.empty()
        if (params.pipeline in ['all', 'catalog']) {
            built = CATALOG()
            panel_catalogs = built.catalogs
            panel_beds = built.beds
            loci = built.loci
            screens = built.screens
            panel = built.panel
            panel_fasta = built.panel_fasta
        }
        else {
            panel_fasta = channel.value(file("${workflow.outputDir}/catalog/tr-panel.fa",
                                             checkIfExists: true))
        }
        if (params.pipeline in ['all', 'filter']) {
            filtered = FILTER(panel_fasta)
            reads = filtered.reads
            counts = filtered.counts
            summary = filtered.summary
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
}
