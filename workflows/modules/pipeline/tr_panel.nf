// Pipeline: the final panel -- the loci a read can be assigned to unambiguously -- and the
// gate's reference built from it.
//
// Joins the loci with both screens. A locus the human screen hit is excluded; the mock
// screen only annotates, because most target genera and every kit genus are not in the
// mock community, so filtering on it would drop most of the panel. See
// `hmp_project panel`.
//
// Seconds of text processing, so it has its own task rather than riding along in
// TR_SCREEN: the screens run once per spec, the join once.
process TR_PANEL {
    label 'filter'

    input:
    path loci              // tr-loci.tsv
    path fasta             // tr-loci.fa
    path human             // chm13.screen.tsv
    path mock              // hmp-mock.screen.tsv

    output:
    path 'tr-panel.tsv', emit: table
    path 'tr-panel.fa', emit: fasta

    script:
    """
    ${params.cli} panel ${loci} ${fasta} --human ${human} --mock ${mock} \\
        --table tr-panel.tsv --out tr-panel.fa
    """

    stub:
    """
    cp ${loci} tr-panel.tsv
    cp ${fasta} tr-panel.fa
    """
}
