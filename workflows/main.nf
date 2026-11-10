include { SRA_RUN_METADATA } from './modules/preprocess/sra_metadata'
include { TR_CATALOG } from './modules/preprocess/tr_catalog'
include { TR_SWEEP } from './modules/preprocess/tr_sweep'
include { TR_LOCI } from './modules/pipeline/tr_loci'
include { TR_FILTER } from './modules/pipeline/tr_filter'
include { FILTER_SUMMARY } from './modules/pipeline/filter_summary'
include { notifyRun; announceStart; announceDone } from './modules/notify'

// A genome spec's lockfile, or nothing if the spec has never been synced. The catalog
// processes sync inside the task, which writes the lock there, so a spec such as
// contaminants/kit can be cataloged before anyone has synced it by hand. A missing file
// cannot be staged, and an empty list stages nothing.
def specLock(spec) {
    def lock = file("${spec.parent}/${spec.simpleName}.lock.json")
    return lock.exists() ? lock : []
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

        TR_CATALOG(announceStart(channel.of(genome_spec), 'TR catalog'),
                   genome_lock, params.catalog_profile, identity,
                   seed_units, seed_length, max_extension,
                   params.catalog_genome_from, params.catalog_table, params.catalog_bed)

        catalog = announceDone(TR_CATALOG.out.catalog, 'TR catalog')
        beds = TR_CATALOG.out.bed
    }

    emit:
    tables = tables
    catalog = catalog
    beds = beds
    sweep = sweep
}

// The analysis, so far its first part: stream each HMP sample from S3 through a k-mer
// gate built from the TR catalog, keeping only the reads that touch a locus. The samples
// are 1.77 TB compressed and ~6.5 TB of FASTQ, so nothing is downloaded: TR_FILTER owns
// the stream, one task per sample. docs/workflows/pipeline/README.md has the design.
//
// `--pipeline` picks the part, like `--preprocess`. The reference is rebuilt whenever
// the flank width or the catalog moves, the filter is hours per sample, and the summary
// is seconds, so each is worth asking for on its own.
workflow FILTER {
    main:
    built_catalog = channel.empty()
    loci = channel.empty()
    reads = channel.empty()
    counts = channel.empty()
    summary = channel.empty()

    reference = channel.empty()
    if (params.pipeline in ['all', 'loci']) {
        genome_spec = file(params.catalog_spec, checkIfExists: true)
        genome_lock = specLock(genome_spec)

        // The catalog is built here unless one is named. Its preprocessing output is not
        // committed -- its parameters are still being swept -- so a clean clone has none,
        // and the stage has to stand on its own. TR_CATALOG is the same process the
        // preprocessing stage runs, with the same parameters.
        if (params.loci_catalog) {
            catalog = channel.of(file(params.loci_catalog, checkIfExists: true))
        }
        else {
            identity = params.catalog_min_identity == null ? '' : params.catalog_min_identity
            seed_units = params.catalog_min_seed_units == null ? '' : params.catalog_min_seed_units
            seed_length = params.catalog_min_seed_length == null ? '' : params.catalog_min_seed_length
            max_extension = params.catalog_max_extension == null ? '' : params.catalog_max_extension

            TR_CATALOG(announceStart(channel.of(genome_spec), 'TR catalog'),
                       genome_lock, params.catalog_profile, identity,
                       seed_units, seed_length, max_extension,
                       params.catalog_genome_from, params.catalog_table, params.catalog_bed)

            catalog = announceDone(TR_CATALOG.out.catalog, 'TR catalog')
            built_catalog = TR_CATALOG.out.catalog
        }

        TR_LOCI(announceStart(catalog, 'TR loci'),
                genome_spec, genome_lock, params.catalog_genome_from,
                params.filter_flank, params.loci_fasta)

        loci = announceDone(TR_LOCI.out.fasta, 'TR loci')
        reference = TR_LOCI.out.fasta
    }
    else if (params.pipeline == 'filter') {
        reference = channel.value(file("${workflow.outputDir}/filter/${params.loci_fasta}",
                                       checkIfExists: true))
    }

    if (params.pipeline in ['all', 'filter']) {
        // The samples come from the lockfiles rather than a list here: a lock is what
        // was planned against, and its ETags are what the stream is checked against.
        // A body site's spec sits beside its lock, and `filter` reads both.
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

        TR_FILTER(announceStart(samples, 'TR filter'), reference.first(),
                  params.filter_k, params.filter_hdist, params.filter_threads,
                  params.filter_decompressor, max_reads)

        reads = announceDone(TR_FILTER.out.reads, 'TR filter')
        counts = TR_FILTER.out.counts
    }

    if (params.pipeline in ['all', 'filter', 'summary']) {
        // On its own, the summary reads the counts an earlier run published. They feed
        // only the summary then, never `counts`, which would republish them onto
        // themselves.
        tallies = params.pipeline == 'summary'
            ? channel.fromPath("${workflow.outputDir}/filter/counts/*.counts.tsv",
                               checkIfExists: true)
            : counts
        FILTER_SUMMARY(tallies.collect(), params.filter_summary_table)
        summary = FILTER_SUMMARY.out.summary
    }

    emit:
    catalog = built_catalog
    loci = loci
    reads = reads
    counts = counts
    summary = summary
}

workflow {
    main:
    notifyRun()

    derived = channel.empty()
    catalog = channel.empty()
    beds = channel.empty()
    sweep = channel.empty()
    filter_catalog = channel.empty()
    loci = channel.empty()
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
        if (!(params.pipeline in ['all', 'loci', 'filter', 'summary'])) {
            error("unknown --pipeline '${params.pipeline}'; " +
                  "use 'all', 'loci', 'filter' or 'summary'")
        }
        out = FILTER()
        filter_catalog = out.catalog
        loci = out.loci
        reads = out.reads
        counts = out.counts
        summary = out.summary
    }
    else {
        error("unknown --stage '${params.stage}'; use 'preprocess' or 'pipeline'")
    }

    publish:
    derived = derived
    catalog = catalog
    beds = beds
    sweep = sweep
    filter_catalog = filter_catalog
    loci = loci
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
    // The pipeline stage publishes into results/. The reads and counts are copied, not
    // symlinked: a symlink into work/ is destroyed by `nextflow clean`, which is fine for
    // a catalog that rebuilds in minutes and not for reads that took a day to stream.
    // The catalog a pipeline run built its reference from, kept beside the reference so
    // the reads can always be traced to the loci they were gated against.
    filter_catalog {
        path 'filter'
        mode 'copy'
    }
    loci {
        path 'filter'
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
