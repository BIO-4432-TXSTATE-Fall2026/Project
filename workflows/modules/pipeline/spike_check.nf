// Pipeline: the allele caller scored against genomes whose repeat lengths are known. The
// simulated reads went through the gate and the caller as a sample's do, so the fraction of
// loci called at exactly the true length is a check of both together. See
// `hmp_project spike-check`.
process SPIKE_CHECK {
    label 'filter'

    input:
    path panel             // tr-panel.tsv
    path alleles           // the spike samples' alleles
    path stats             // and their statistics, which list every sample

    output:
    path 'spike-check.tsv', emit: check

    script:
    """
    ${params.cli} spike-check --panel ${panel} --alleles ${alleles} --stats ${stats} \\
        --out spike-check.tsv
    """

    stub:
    """
    printf 'genome\\treads\\tloci_expected\\tloci_called\\texact_fraction\\twithin_one_unit_fraction\\tloci_unexpected\\n' > spike-check.tsv
    printf 'stub\\t1000\\t1\\t1\\t1.0000\\t1.0000\\t0\\n' >> spike-check.tsv
    """
}
