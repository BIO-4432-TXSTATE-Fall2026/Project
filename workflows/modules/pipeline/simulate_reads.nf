// Pipeline: simulated reads from the kit genomes, the ground truth for the allele caller.
//
// Every kit genome is a member of some panel loci, so its allele lengths are known: the
// panel's `rep_length`. `randomreads.sh` draws paired 100 bp reads from each genome at each
// depth in `spike_reads`, with sequencing errors, and each lands as `<genome>@<reads>.fastq.gz`.
// The same file feeds the gate (TR_GATE) as a sample, and, mixed into a host's alleles after
// the gate, is a labelled contaminant (SPIKE_MIX).
//
// One task for the spec rather than one per genome: sync downloads a spec whole, and the
// kit is 195 MB, so a task per genome would fetch all of it thirty times to use a thirtieth.
// The simulation is seconds per file; the files cross as a flat channel, so the gate and the
// caller downstream are one task each. Same sync, reduce, delete shape as TR_CATALOG: the
// genomes never leave the task directory.
process SIMULATE_READS {
    tag "${spec.simpleName}"
    label 'filter'
    label 'spike'

    // sync rewrites the spec's lockfile; the trap TR_CATALOG documents.
    stageInMode 'copy'

    input:
    path spec
    path lock              // staged, never named: sync finds it beside the spec; [] if never synced
    val depths             // space-separated read-pair counts
    val seed

    output:
    path '*.fastq.gz', emit: reads

    script:
    def heap = "${Math.max(1024, task.memory.toMega().intdiv(2))}m"
    """
    export XDG_CACHE_HOME="\$PWD/.cache"
    export JAVA_TOOL_OPTIONS="-XX:-UsePerfData -Xlog:disable -Xlog:all=warning:stderr -XX:+ExitOnOutOfMemoryError"

    ${params.cli} sync ${spec} --data-dir .
    # The genome's name is the one the panel's `genome` column uses, so the check can join.
    ${params.cli} genomes ${spec} --data-dir . --name-from auto --out genomes.tsv

    while IFS=\$'\\t' read -r name genome ; do
        for n in ${depths} ; do
            randomreads.sh -Xmx${heap} ref="\$genome" reads=\$n length=100 paired=t adderrors=t \\
                seed=${seed} out=stdout.fq | gzip > "\$name@\$n.fastq.gz"
        done
    done < genomes.tsv

    rm -rf ./${spec.simpleName} genomes.tsv .cache
    """

    stub:
    """
    for name in stub-a stub-b ; do
        for n in ${depths} ; do
            printf '@stub 1:\\nACGT\\n+\\nIIII\\n' | gzip > "\$name@\$n.fastq.gz"
        done
    done
    """
}
