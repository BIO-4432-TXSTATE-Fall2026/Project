// Pipeline: one HMP sample streamed from S3 through the k-mer gate, keeping the reads
// that touch a TR locus. One task per sample, which is the unit SLURM arrays.
//
// The stream is the project CLI's, not a shell pipeline here: `filter` owns S3 ->
// decompressor -> tar -> bbduk -> gzip as one process and checks every stage's exit
// status, so a transfer that dies part way fails the sample rather than handing on a
// truncated one. That is also why this is one process and not three: the only boundary
// between them would be decompressed FASTQ, ~25 GB of it per sample, parked in work/.
//
// The sample arrives as values, never as a `path` to the object: Nextflow would localise
// an s3:// path, which downloads exactly what this exists to avoid. The ETag rides along
// so that an upstream change to the object invalidates the -resume cache. The spec and
// its lock are staged because `filter` reads the key's record, and the bucket, from them.
process TR_FILTER {
    tag "${sample}"
    label 'filter'
    label 'stream'

    input:
    tuple val(sample), path(spec), path(lock), val(key), val(etag)
    path reference
    val k
    val hdist
    val threads            // bbduk's; the rest of the task's cores decompress
    val decompressor
    val max_reads          // '' for no cap

    output:
    path "${sample}.loci.fastq.gz", emit: reads
    path "${sample}.counts.tsv", emit: counts

    script:
    def cap = max_reads == '' ? '' : " --max-reads ${max_reads}"
    def unpack_threads = Math.max(1, task.cpus - (threads as int))
    // Three quarters of the task's memory for bbduk's heap: the JVM needs room above its
    // heap, and the Python side holds no more than a few megabytes of pipe buffers.
    def heap = "${(task.memory.toMega() * 3).intdiv(4)}m"
    """
    ${params.cli} filter ${spec} --key ${key} --sample ${sample} \\
        --ref ${reference} --k ${k} --hdist ${hdist} --threads ${threads} --memory ${heap} \\
        --decompressor ${decompressor} --decompressor-threads ${unpack_threads}${cap}
    """

    stub:
    """
    printf '@stub/1\\nACGT\\n+\\nIIII\\n' | gzip > ${sample}.loci.fastq.gz
    printf 'sample\\tspec\\tkey\\treads_1\\treads_2\\treads_singleton\\treads_seen\\treads_passed\\treads_written\\tbytes_read\\tbytes_decompressed\\telapsed_s\\n' > ${sample}.counts.tsv
    printf '${sample}\\t${spec.simpleName}\\t${key}\\t1\\t0\\t0\\t1\\t1\\t1\\t0\\t0\\t0.0\\n' >> ${sample}.counts.tsv
    """
}
