include { SRA_RUN_METADATA } from './modules/preprocess/sra_metadata'
include { notifyRun; announceStart; announceDone } from './modules/notify'

// Preprocessing: rebuild the committed tables in data/derived/ from their upstream
// catalogs. A stage of its own rather than part of the analysis, because its outputs are
// committed and rebuilding them is a rare, deliberate act.
workflow PREPROCESS {
    main:
    spec = file(params.sra_metadata_spec, checkIfExists: true)
    lock = file("${spec.parent}/${spec.simpleName}.lock.json", checkIfExists: true)
    sample_locks = files(params.hmp_sample_locks, checkIfExists: true)

    // The spec is passed as a channel rather than a value so its arrival can be tapped;
    // the phase has one task either way.
    SRA_RUN_METADATA(announceStart(channel.of(spec), 'SRA run metadata'),
                     lock, sample_locks, params.hmp_sra_runs_table,
                     params.salter_study, params.salter_runs_table)

    emit:
    announceDone(SRA_RUN_METADATA.out.hmp.mix(SRA_RUN_METADATA.out.salter),
                 'SRA run metadata')
}

workflow {
    main:
    notifyRun()

    derived = channel.empty()
    if (params.stage == 'preprocess') {
        derived = PREPROCESS()
    }
    else if (params.stage == 'pipeline') {
        error("--stage pipeline has no analysis yet; see docs/todo.md. Use --stage preprocess")
    }
    else {
        error("unknown --stage '${params.stage}'; use 'preprocess' or 'pipeline'")
    }

    publish:
    derived = derived
}

output {
    // The derived tables are committed, so they are published into the working tree, not
    // into results/. docs/data/README.md says what each one is.
    derived {
        path 'derived'
    }
}
