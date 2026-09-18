// Data compilation: build a committed table under data/derived/ from a synced catalog.
// See docs/data/README.md for why the catalog is fetched whole and then thrown away.
process SRA_RUN_METADATA {
    tag "${spec.simpleName}"
    label 'data'

    // sync rewrites the spec's lockfile. Copy the staged manifests rather than symlink
    // them, so the task writes its own copies and never the ones in the clone.
    stageInMode 'copy'

    input:
    path spec
    path lock          // staged, not named on the command line: extract finds it beside the spec
    path sample_locks  // lockfiles whose keys name the samples to keep
    val table

    output:
    path table

    script:
    def from_locks = sample_locks.collect { "--from-lock ${it}" }.join(' ')
    """
    # The catalog lands in ./${spec.simpleName}/ and stays inside the task directory:
    # 2.3 GB that is cheaper to re-sync than to keep. --data-dir . keeps it there.
    ${params.cli} sync ${spec} --data-dir .
    ${params.cli} extract ${spec} --data-dir . ${from_locks} --out ${table}
    rm -rf ./${spec.simpleName}
    """

    stub:
    """
    printf 'run\\tsample\\tstudy\\n' > ${table}
    """
}
