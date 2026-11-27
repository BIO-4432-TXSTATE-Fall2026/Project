// Pipeline: real samples' alleles with simulated genomes added, and a label for every locus
// saying whether the genome is a member of it. These are the labelled contaminants the
// contamination model trains and is tested on. See `hmp_project spike-mix`.
//
// Mixing after the gate equals mixing before it: the gate and the caller judge each read
// alone, so the pooled reads' calls are the host's plus the genome's.
process SPIKE_MIX {
    label 'filter'
    label 'spike'

    input:
    path panel             // tr-panel.tsv
    path hosts             // results/alleles/alleles.tsv
    path spikes            // the spike samples' alleles
    val host_samples       // comma-separated; '' for every sample in the table

    output:
    path 'alleles-spiked.tsv', emit: alleles
    path 'spike-labels.tsv', emit: labels

    script:
    def hosts_option = host_samples == '' ? '' : " --host-samples ${host_samples}"
    """
    ${params.cli} spike-mix --panel ${panel} --hosts ${hosts} --spikes ${spikes}${hosts_option} \\
        --out alleles-spiked.tsv --labels spike-labels.tsv
    """

    stub:
    """
    printf 'sample\\tlocus_id\\tallele_bp\\treads\\n' > alleles-spiked.tsv
    printf 'sample\\thost\\tbatch\\treads\\tlocus_id\\tcontaminant\\n' > spike-labels.tsv
    """
}
