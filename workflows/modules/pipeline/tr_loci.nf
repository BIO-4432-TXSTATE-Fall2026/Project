// Pipeline: merge every panel spec's catalog into loci, and write the gate's reference --
// each locus with its flanks, as FASTA -- beside the table that says what each locus is.
//
// A process of its own rather than a step of TR_CATALOG, because the merge needs every
// spec's calls at once (a locus is the same motif and anchors across genomes, and across
// specs), and because the flank, anchor and length limit are hyperparameters of the gate,
// not of the finder: this is rebuilt more often than the catalogs, and rebuilding it
// should not re-run the finder. The cost is one more sync of the genomes, which
// TR_CATALOG deletes when it is done.
//
// Same sync, reduce, delete shape as TR_CATALOG, and in its image, because the genomes
// are read through inTRuder -- the reader the catalogs were built with, so the contig
// names agree by construction. The genomes are listed by `genomes`, as TR_CATALOG lists
// them, for the same reason: `loci` looks each catalog row up by the genome name it
// carries.
process TR_LOCI {
    tag "flank${flank}:anchor${anchor}"
    label 'catalog'

    // sync rewrites each spec's lockfile; the trap TR_CATALOG documents.
    stageInMode 'copy'

    input:
    path catalogs          // every spec's tr-catalog.<spec>.tsv
    path specs
    path locks             // staged, never named: sync finds each beside its spec; none if never synced
    val flank
    val anchor
    val max_rep_length

    output:
    path 'tr-loci.tsv', emit: table
    path 'tr-loci.fa', emit: fasta
    path 'tr-loci-stats.tsv', emit: stats

    script:
    def spec_list = specs instanceof Collection ? specs : [specs]
    def sync = spec_list.collect { spec ->
        // `auto` names each genome by its spec's layout: HMP by directory, the rest by
        // file. The names match TR_CATALOG's, because it was given `auto` too.
        "${params.cli} sync ${spec} --data-dir .\n" +
        "    ${params.cli} genomes ${spec} --data-dir . --name-from auto --out genomes.${spec.simpleName}.tsv"
    }.join('\n    ')
    def cleanup = spec_list.collect { spec -> "./${spec.simpleName}" }.join(' ')
    """
    # The container's home is read-only, and slacken specs cache their assembly index
    # under \$XDG_CACHE_HOME. Keep that cache in the task directory.
    export XDG_CACHE_HOME="\$PWD/.cache"

    ${sync}

    cat genomes.*.tsv > genomes.tsv

    ${params.cli} loci ${catalogs} --genomes genomes.tsv \\
        --flank ${flank} --anchor ${anchor} --max-rep-length ${max_rep_length} \\
        --table tr-loci.tsv --stats tr-loci-stats.tsv --out tr-loci.fa

    rm -rf ${cleanup} genomes*.tsv .cache
    """

    stub:
    """
    printf 'locus_id\\tspec\\tgenome\\tcontig\\tstart\\tend\\tmotif\\tmotif_length\\trep_length\\tpurity\\tn_calls\\tmotifs\\tleft_anchor\\tright_anchor\\n' > tr-loci.tsv
    printf 'L000001\\tstub\\tstub\\tcontig_1\\t100\\t126\\tCGG\\t3\\t26\\t0.846\\t1\\tCGG\\tACGTACGTACGTACGTACGT\\tTGCATGCATGCATGCATGCA\\n' >> tr-loci.tsv
    printf '>L000001|stub|contig_1:50-176\\nACGT\\n' > tr-loci.fa
    printf 'metric\\tspec\\tvalue\\ncalls\\tall\\t1\\ngroups\\tall\\t1\\n' > tr-loci-stats.tsv
    """
}
