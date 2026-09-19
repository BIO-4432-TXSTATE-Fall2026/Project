// Preprocessing: build the committed tables under data/derived/ from a synced catalog.
// See docs/data/README.md for why the catalog is fetched whole and then thrown away.
//
// Both tables come out of one task rather than one process each, because they read the
// same 2.3 GB catalog: a second process would sync it a second time. The two extracts
// are two passes over the local copy, which costs disk reads, not another download.
process SRA_RUN_METADATA {
    tag "${spec.simpleName}"
    label 'preprocess'

    // sync rewrites the spec's lockfile. Copy the staged manifests rather than symlink
    // them, so the task writes its own copies and never the ones in the clone.
    stageInMode 'copy'

    input:
    path spec
    path lock          // staged, not named on the command line: extract finds it beside the spec
    path sample_locks  // lockfiles whose keys name the HMP samples to keep
    val hmp_table
    val salter_study
    val salter_table

    output:
    path hmp_table, emit: hmp
    path salter_table, emit: salter

    script:
    def from_locks = sample_locks.collect { "--from-lock ${it}" }.join(' ')
    """
    # The catalog lands in ./${spec.simpleName}/ and stays inside the task directory:
    # 2.3 GB that is cheaper to re-sync than to keep. --data-dir . keeps it there.
    ${params.cli} sync ${spec} --data-dir .
    ${params.cli} extract ${spec} --data-dir . ${from_locks} --out ${hmp_table}
    # The kit and dilution of a Salter run are in its free-text sample alias, which the
    # salter profile reads out; docs/data/salter-runs.md says what it makes of them.
    ${params.cli} extract ${spec} --data-dir . --accession ${salter_study} \\
        --profile salter --out ${salter_table}
    rm -rf ./${spec.simpleName}
    """

    stub:
    """
    printf 'run\\tsample\\tstudy\\n' > ${hmp_table}
    printf 'run\\tsample\\tstudy\\talias\\tkit\\tdilution\\n' > ${salter_table}
    """
}
