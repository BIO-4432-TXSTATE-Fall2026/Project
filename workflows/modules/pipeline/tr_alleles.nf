// Pipeline: one sample's gated reads turned into allele counts. For each read the panel
// loci it matched are in its header (`filter` runs the gate with rename=t); `alleles` looks
// for each locus's two anchors in the read and measures the repeat between them. See
// `hmp_project alleles` for what a spanning, flanking and ambiguous read is.
//
// The sample crosses as a value beside its reads, named by the workflow from the file's name
// minus `.loci.fastq.gz` and not its first dot's prefix: a spike sample is named for a
// genome, and a genome's accession has a dot in it.
//
// A few minutes of Python per sample over reads that are already a small slice of it, so
// one task per sample and no stream. Run for the HMP samples, and again by alias for the
// simulated spike-in reads.
process TR_ALLELES {
    tag "${sample}"
    label 'filter'

    input:
    tuple val(sample), path(reads)   // <sample>.loci.fastq.gz
    path panel             // tr-panel.tsv
    val anchor             // anchor bases matched; '' for the panel's whole anchor
    val mismatches

    output:
    path "${sample}.alleles.tsv", emit: alleles
    path "${sample}.allele-stats.tsv", emit: stats

    script:
    def anchor_option = anchor == '' ? '' : " --anchor ${anchor}"
    """
    ${params.cli} alleles ${reads} --panel ${panel} --sample ${sample} \\
        --mismatches ${mismatches}${anchor_option}
    """

    stub:
    """
    printf 'sample\\tlocus_id\\tallele_bp\\treads\\n' > ${sample}.alleles.tsv
    printf '${sample}\\tL000001\\t26\\t1\\n' >> ${sample}.alleles.tsv
    printf 'sample\\treads_in\\tspanning\\tflanking\\tambiguous\\tunassigned\\tpairs_collapsed\\tpairs_discordant\\n' > ${sample}.allele-stats.tsv
    printf '${sample}\\t1\\t1\\t0\\t0\\t0\\t0\\t0\\n' >> ${sample}.allele-stats.tsv
    """
}
