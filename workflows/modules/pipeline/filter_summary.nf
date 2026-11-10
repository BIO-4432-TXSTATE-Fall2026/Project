// Pipeline: every sample's filter counts in one table, with the fraction of reads that
// passed the gate. That fraction is what the disk budget turns on -- the published reads
// scale with it -- so the plaque pilot exists to measure it before stool and tongue run.
// The reads seen per sample are also the depth covariate the entropy model needs.
process FILTER_SUMMARY {
    label 'filter'

    input:
    path counts, stageAs: 'counts/*'
    val summary_table

    output:
    path summary_table, emit: summary

    script:
    """
    # One header, then every sample's row, sorted so a rerun writes the same file.
    head -n 1 \$(ls counts/* | head -n 1) | awk '{ print \$0 "\\tpass_fraction" }' > ${summary_table}
    for f in counts/* ; do tail -n +2 "\$f" ; done | sort \\
        | awk 'BEGIN { FS = OFS = "\\t" }
               { print \$0, (\$7 > 0 ? sprintf("%.6f", \$8 / \$7) : "NA") }' >> ${summary_table}
    """
}
