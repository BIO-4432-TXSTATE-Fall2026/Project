// Pipeline: every sample's alleles in one table, and every sample's read statistics in
// another. The allele table is what the entropy stage reads, and is the form `spike-mix`
// sums over; the statistics say how much of each sample the caller could use.
//
// Shell, as in FILTER_SUMMARY: one header, then every sample's rows, sorted so a rerun
// writes the same file. Run for the HMP samples and, by alias, for the spike-ins.
process ALLELE_TABLE {
    label 'filter'

    input:
    path alleles, stageAs: 'alleles/*'
    path stats, stageAs: 'stats/*'
    val alleles_table
    val stats_table

    output:
    path alleles_table, emit: alleles
    path stats_table, emit: stats

    script:
    """
    head -n 1 \$(ls alleles/* | head -n 1) > ${alleles_table}
    for f in alleles/* ; do tail -n +2 "\$f" ; done | LC_ALL=C sort -t \$'\\t' -k1,1 -k2,2 -k3,3n >> ${alleles_table}
    head -n 1 \$(ls stats/* | head -n 1) > ${stats_table}
    for f in stats/* ; do tail -n +2 "\$f" ; done | LC_ALL=C sort >> ${stats_table}
    """

    stub:
    """
    head -n 1 \$(ls alleles/* | head -n 1) > ${alleles_table}
    for f in alleles/* ; do tail -n +2 "\$f" ; done >> ${alleles_table}
    head -n 1 \$(ls stats/* | head -n 1) > ${stats_table}
    for f in stats/* ; do tail -n +2 "\$f" ; done >> ${stats_table}
    """
}
