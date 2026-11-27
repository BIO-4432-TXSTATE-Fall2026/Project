// Pipeline: a local FASTQ through the same k-mer gate the HMP reads pass, keeping the reads
// that touch a panel locus. Used for the simulated spike-in reads, so what is checked is the
// gate that real samples go through, not a copy of it.
//
// The project CLI's `filter --fastq`, which shares TR_FILTER's gate and writer; only the
// source differs, a file in place of an S3 stream. Outputs are named as TR_FILTER's are, so
// TR_ALLELES takes either.
process TR_GATE {
    tag "${sample}"
    label 'filter'
    label 'spike'

    input:
    tuple val(sample), path(fastq)   // <genome>@<reads>.fastq.gz
    path reference         // tr-panel.fa
    val k
    val hdist

    output:
    path "${sample}.loci.fastq.gz", emit: reads
    path "${sample}.counts.tsv", emit: counts

    script:
    // Three quarters of the task's memory for bbduk's heap, as in TR_FILTER.
    def heap = "${(task.memory.toMega() * 3).intdiv(4)}m"
    """
    ${params.cli} filter --fastq ${fastq} --sample ${sample} \\
        --ref ${reference} --k ${k} --hdist ${hdist} --threads ${task.cpus} --memory ${heap}
    """

    stub:
    """
    printf '@stub/1\\tL000001|stub|contig_1:50-176=1\\nACGT\\n+\\nIIII\\n' | gzip > ${sample}.loci.fastq.gz
    printf 'sample\\tspec\\tkey\\treads_1\\treads_2\\treads_singleton\\treads_seen\\treads_passed\\treads_written\\tbytes_read\\tbytes_decompressed\\telapsed_s\\n' > ${sample}.counts.tsv
    printf '${sample}\\t-\\t${fastq}\\t1\\t0\\t0\\t1\\t1\\t1\\t0\\t0\\t0.0\\n' >> ${sample}.counts.tsv
    """
}
