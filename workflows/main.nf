include { SRA_RUN_METADATA } from './modules/preprocess/sra_metadata'
include { TR_CATALOG } from './modules/preprocess/tr_catalog'
include { TR_SWEEP } from './modules/preprocess/tr_sweep'
include { notifyRun; announceStart; announceDone } from './modules/notify'

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
        sweep_lock = file("${sweep_spec.parent}/${sweep_spec.simpleName}.lock.json")

        TR_SWEEP(announceStart(channel.of(sweep_spec), 'TR sweep'),
                 sweep_lock, params.catalog_profile, params.sweep_identities,
                 params.sweep_seed_units, params.sweep_seed_lengths,
                 params.catalog_genome_from, params.sweep_table)

        sweep = announceDone(TR_SWEEP.out.sweep, 'TR sweep')
    }

    if (params.preprocess in ['all', 'catalog']) {
        genome_spec = file(params.catalog_spec, checkIfExists: true)
        genome_lock = file("${genome_spec.parent}/${genome_spec.simpleName}.lock.json")

        // Nextflow refuses a null `val` input, so an unset threshold crosses as ''.
        identity = params.catalog_min_identity == null ? '' : params.catalog_min_identity
        seed_units = params.catalog_min_seed_units == null ? '' : params.catalog_min_seed_units
        seed_length = params.catalog_min_seed_length == null ? '' : params.catalog_min_seed_length

        TR_CATALOG(announceStart(channel.of(genome_spec), 'TR catalog'),
                   genome_lock, params.catalog_profile, identity,
                   seed_units, seed_length,
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

workflow {
    main:
    notifyRun()

    derived = channel.empty()
    catalog = channel.empty()
    beds = channel.empty()
    sweep = channel.empty()
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
        error("--stage pipeline has no analysis yet; see docs/todo.md. Use --stage preprocess")
    }
    else {
        error("unknown --stage '${params.stage}'; use 'preprocess' or 'pipeline'")
    }

    publish:
    derived = derived
    catalog = catalog
    beds = beds
    sweep = sweep
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
}
