// Preprocessing: the TR locus catalog for one genome manifest, built by streaming the
// genomes through inTRuder's finder and keeping only the calls.
//
// Same shape as SRA_RUN_METADATA, for the same reason: sync, reduce, delete, in one task.
// The genomes are the bulk here -- 982 MB for CHM13, 760 MB for the target genera -- and
// the catalog is small, so a process that emitted the FASTAs would park gigabytes in
// work/ for the next task to read. Nothing downstream wants the sequence; it wants the
// loci. docs/data/README.md makes the same point about the 2.3 GB metadata freeze.
//
// The finder settings arrive as values rather than being baked in, because they are not
// settled: `genome` is provisional (see trf/params.py) and choosing it means enumerating
// the grid. A sweep is then one task per point, which `-resume` caches.
process TR_CATALOG {
    // The thresholds are in the tag because a sweep runs this process once per grid
    // point, and otherwise every task in squeue carries the same name. Unset ones read
    // as the profile's own value rather than as an empty gap.
    tag "${spec.simpleName}:${profile}" +
        "/${min_identity == '' ? 'default' : min_identity}" +
        "/${min_seed_units == '' ? 'default' : min_seed_units}" +
        "/${min_seed_length == '' ? 'default' : min_seed_length}"
    label 'catalog'

    // sync rewrites the spec's lockfile, so the task gets its own copy rather than a
    // symlink into manifests/. The same trap SRA_RUN_METADATA documents.
    stageInMode 'copy'

    input:
    path spec
    path lock              // staged, never named: sync finds it beside the spec
    val profile
    val min_identity
    val min_seed_units
    val min_seed_length
    val genome_from        // 'dir' for HMP layouts, 'file' for one genome per file
    val catalog_table
    val catalog_bed

    output:
    path catalog_table, emit: catalog
    path catalog_bed, emit: bed

    script:
    // Only the thresholds that were actually given: the profile holds the rest, and
    // `--min-identity null` is not a number. The CLI's own `replace` ignores None for
    // the same reason, so an unset flag and a flag set to the profile's value agree.
    //
    // The empty string, not null, marks "not given": Nextflow refuses a `val` input
    // channel that evaluates to null. Compared against '' rather than tested for truth,
    // because 0 is a threshold a sweep may legitimately ask for and would be falsy.
    def overrides = ''
    if (min_identity != '') {
        overrides += " --min-identity ${min_identity}"
    }
    if (min_seed_units != '') {
        overrides += " --min-seed-units ${min_seed_units}"
    }
    if (min_seed_length != '') {
        overrides += " --min-seed-length ${min_seed_length}"
    }
    """
    # The genomes land in ./${spec.simpleName}/ and never leave the task directory.
    ${params.cli} sync ${spec} --data-dir .

    # HMP ships the mock community as .nuc.fsa.bz2, and pyfastx reads plain or gzip only,
    # so bzip2 has to come off before the finder sees it. gzip it opens itself.
    find ./${spec.simpleName} -name '*.bz2' -exec bunzip2 -q {} + || true

    # One table per genome, concatenated below. --format fasta because HMP names its
    # genomes .nuc.fsa, which the extension sniffer cannot place.
    mkdir -p calls
    find ./${spec.simpleName} -type f \\
        \\( -name '*.fsa' -o -name '*.fna' -o -name '*.fa' -o -name '*.fasta' \\
           -o -name '*.fna.gz' -o -name '*.fa.gz' -o -name '*.fasta.gz' \\) \\
        | sort > genomes.txt
    test -s genomes.txt || { echo "no FASTA in ${spec.simpleName}" >&2; exit 1; }

    while IFS= read -r genome ; do
        if [ "${genome_from}" = dir ] ; then
            name=\$(basename "\$(dirname "\$genome")")
        else
            name=\$(basename "\$genome" | sed 's/[.][^.]*\$//')
        fi
        ${params.trf} find "\$genome" "calls/\$name.tsv" \\
            --format fasta --profile ${profile} --genome "\$name" \\
            --bed "calls/\$name.bed"${overrides}
    done < genomes.txt

    # One header, then every genome's rows. The per-genome tables carry the same columns,
    # so the first file's header stands for all of them.
    awk 'FNR == 1 && NR != 1 { next } { print }' calls/*.tsv > ${catalog_table}
    cat calls/*.bed > ${catalog_bed}

    # The sequence was only ever the input to the finder.
    rm -rf ./${spec.simpleName} calls genomes.txt
    """

    stub:
    """
    printf 'genome\\tcontig\\tstart\\tend\\tmotif\\tpurity\\tmotif_length\\trep_length\\trep_units\\n' > ${catalog_table}
    printf 'stub\\tcontig_1\\t100\\t126\\tCGG\\t0.846\\t3\\t26\\t8\\n' >> ${catalog_table}
    printf 'contig_1\\t100\\t126\\tCGG\\n' > ${catalog_bed}
    """
}
