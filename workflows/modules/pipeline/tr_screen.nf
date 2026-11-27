// Pipeline: screen the locus reference against one genome spec, counting per locus the
// fragments of that spec's genomes that the gate's own k-mer match hits.
//
// The genomes are cut into fragments as long as a read (`shred.sh`) and run through the
// same BBDuk match, at the same k and Hamming distance, that gates the HMP reads
// (`filter`). So a locus a fragment hits is a locus a read of that genome would pass the
// gate through: the screen is the gate, applied to a genome instead of a sample.
//
// Run twice, by alias: over CHM13, where a hit excludes the locus (a read matching it
// cannot be told from host), and over the mock community, where a hit only annotates the
// locus (TR_PANEL). Same sync, reduce, delete shape as TR_CATALOG, and CHM13 is 982 MB, so
// the genomes never leave the task directory.
//
// One bbduk run takes every genome's fragments, so its k-mer table is built once. The
// fragments are not stored: shred writes them to the pipe bbduk reads, and only the
// matched ones come out, as headers `screen` counts. See `hmp_project screen`.
process TR_SCREEN {
    tag "${spec.simpleName}"
    label 'filter'
    label 'screen'

    // sync rewrites the spec's lockfile; the trap TR_CATALOG documents.
    stageInMode 'copy'

    input:
    path reference         // tr-loci.fa
    path spec
    path lock              // staged, never named: sync finds it beside the spec; [] if never synced
    val fragment           // fragment length: a read's
    val overlap
    val k
    val hdist

    output:
    path "${spec.simpleName}.screen.tsv", emit: screen

    script:
    // shred runs beside bbduk in the pipe: 2 GB for it, half the task's memory for bbduk's
    // heap, and the rest left for the JVMs' own overhead.
    def heap = "${Math.max(1024, task.memory.toMega().intdiv(2))}m"
    """
    # The container's home is read-only, and slacken specs cache their assembly index
    # under \$XDG_CACHE_HOME. Keep that cache in the task directory.
    export XDG_CACHE_HOME="\$PWD/.cache"

    # The JVM logs its warnings to stdout, which here is the read stream; see
    # hmp_project/cli/filter.py.
    export JAVA_TOOL_OPTIONS="-XX:-UsePerfData -Xlog:disable -Xlog:all=warning:stderr"

    ${params.cli} sync ${spec} --data-dir .
    ${params.cli} genomes ${spec} --data-dir . --name-from auto --out genomes.tsv

    # rename=t writes each matched reference into the fragment's header, which is all
    # `screen` reads. int=f because the fragments are single-ended.
    while IFS=\$'\\t' read -r name genome ; do
        shred.sh -Xmx2g in="\$genome" out=stdout.fa length=${fragment} overlap=${overlap}
    done < genomes.tsv \\
        | bbduk.sh -Xmx${heap} in=stdin.fa out=null outm=stdout.fa ref=${reference} \\
            k=${k} hdist=${hdist} threads=${task.cpus} int=f rename=t \\
        | ${params.cli} screen --out ${spec.simpleName}.screen.tsv

    rm -rf ./${spec.simpleName} genomes.tsv .cache
    """

    stub:
    """
    printf 'locus_id\\tfragments\\n' > ${spec.simpleName}.screen.tsv
    """
}
