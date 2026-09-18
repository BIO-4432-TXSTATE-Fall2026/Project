include { HELLO } from './modules/hello'
include { SRA_RUN_METADATA } from './modules/data/sra_metadata'

// Data compilation: rebuild the committed tables in data/derived/ from their upstream
// catalogs. A stage of its own rather than part of the pipeline below, because its
// outputs are committed and rebuilding them is a rare, deliberate act.
workflow DATA {
    main:
    spec = file(params.sra_metadata_spec, checkIfExists: true)
    lock = file("${spec.parent}/${spec.simpleName}.lock.json", checkIfExists: true)
    sample_locks = files(params.hmp_sample_locks, checkIfExists: true)
    SRA_RUN_METADATA(spec, lock, sample_locks, params.hmp_sra_runs_table)

    emit:
    SRA_RUN_METADATA.out
}

workflow {
    main:
    greetings = channel.empty()
    derived = channel.empty()
    if (params.stage == 'pipeline') {
        names = channel.fromList(params.names.tokenize(','))
        greetings = HELLO(names)
    }
    else if (params.stage == 'data') {
        derived = DATA()
    }
    else {
        error("unknown --stage '${params.stage}'; use 'pipeline' or 'data'")
    }

    publish:
    greetings = greetings
    derived = derived
}

output {
    greetings {
        path 'greetings'
    }
    // The derived tables are committed, so they are published into the working tree,
    // not into results/. docs/data/README.md says what each one is.
    derived {
        path 'derived'
    }
}
