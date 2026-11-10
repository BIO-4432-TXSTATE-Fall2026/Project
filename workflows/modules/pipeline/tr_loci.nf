// Pipeline: the read filter's reference -- each catalog locus with its flanks, as FASTA.
//
// A process of its own rather than a third output of TR_CATALOG, because the flank width
// is a hyperparameter of the filter, not of the finder: the reference will be rebuilt
// more often than the catalog, and rebuilding it should not re-run the finder. The cost
// is one more sync of the genomes, which TR_CATALOG deletes when it is done.
//
// Same sync, reduce, delete shape as TR_CATALOG, and in its image, because the genomes
// are read through inTRuder -- the reader the catalog was built with, so the contig
// names agree by construction. The genomes are listed by `genomes`, as TR_CATALOG
// lists them, for the same reason: `loci` looks each catalog row up by the genome name
// it carries.
process TR_LOCI {
    tag "${spec.simpleName}:flank${flank}"
    label 'catalog'

    // sync rewrites the spec's lockfile; the trap TR_CATALOG documents.
    stageInMode 'copy'

    input:
    path catalog
    path spec
    path lock              // staged, never named: sync finds it beside the spec; [] if never synced
    val genome_from        // 'dir' for HMP layouts, 'file' for one genome per file
    val flank
    val loci_fasta

    output:
    path loci_fasta, emit: fasta

    script:
    """
    ${params.cli} sync ${spec} --data-dir .

    # One FASTA per genome, named exactly as TR_CATALOG named it, because `loci` looks
    # each catalog row up by that name.
    ${params.cli} genomes ${spec} --data-dir . --name-from ${genome_from} --out genomes.tsv

    ${params.cli} loci ${catalog} --genomes genomes.tsv --flank ${flank} --out ${loci_fasta}

    rm -rf ./${spec.simpleName} genomes.tsv
    """

    stub:
    """
    printf '>stub|contig_1:50-176\\nACGT\\n' > ${loci_fasta}
    """
}
