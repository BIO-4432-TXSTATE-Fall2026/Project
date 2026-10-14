// Preprocessing: how many loci the finder reports across a grid of thresholds, for one
// genome manifest. The sensitivity surface behind the §2 parameter choice, not a catalog.
//
// One task for the whole grid, rather than TR_CATALOG once per point. A grid point is
// part of the task hash, so a point per task means Nextflow re-syncs the same genomes for
// every point -- 12 downloads of one spec to answer one question about it. The genomes are
// the expensive part and the finder is the cheap part, so the loop belongs inside the task
// where the sync is already paid for. Same reasoning as SRA_RUN_METADATA running two
// extracts over one downloaded catalog.
//
// What comes back is long format -- one row per (point, genome) -- because that is what a
// sweep is read as: the thresholds are the independent variables, not columns to pivot.
process TR_SWEEP {
    tag "${spec.simpleName}:${profile}"
    label 'catalog'

    // sync rewrites the spec's lockfile; the task gets its own copy.
    stageInMode 'copy'

    input:
    path spec
    path lock              // staged, never named: sync finds it beside the spec
    val profile
    val identities         // space-separated, as a shell for-loop reads them
    val seed_units
    val seed_lengths
    val genome_from        // 'dir' for HMP layouts, 'file' for one genome per file
    val sweep_table

    output:
    path sweep_table, emit: sweep

    script:
    """
    # The genomes land in ./${spec.simpleName}/ and never leave the task directory.
    ${params.cli} sync ${spec} --data-dir .

    # HMP ships the mock community as .nuc.fsa.bz2, and pyfastx reads plain or gzip only.
    find ./${spec.simpleName} -name '*.bz2' -exec bunzip2 -q {} + || true

    find ./${spec.simpleName} -type f \\
        \\( -name '*.fsa' -o -name '*.fna' -o -name '*.fa' -o -name '*.fasta' \\
           -o -name '*.fna.gz' -o -name '*.fa.gz' -o -name '*.fasta.gz' \\) \\
        | sort > genomes.txt
    test -s genomes.txt || { echo "no FASTA in ${spec.simpleName}" >&2; exit 1; }

    printf 'min_identity\\tmin_seed_units\\tmin_seed_length\\tgenome\\tloci\\n' > ${sweep_table}

    for identity in ${identities} ; do
      for units in ${seed_units} ; do
        for length in ${seed_lengths} ; do
          while IFS= read -r genome ; do
            if [ "${genome_from}" = dir ] ; then
                name=\$(basename "\$(dirname "\$genome")")
            else
                name=\$(basename "\$genome" | sed 's/[.][^.]*\$//')
            fi
            # --format fasta because HMP names its genomes .nuc.fsa, which the extension
            # sniffer cannot place. The table is a scratch file: only its row count is
            # wanted, and the catalog itself comes from TR_CATALOG at a chosen point.
            ${params.trf} find "\$genome" point.tsv \\
                --format fasta --profile ${profile} --genome "\$name" \\
                --min-identity "\$identity" \\
                --min-seed-units "\$units" \\
                --min-seed-length "\$length"
            loci=\$(( \$(wc -l < point.tsv) - 1 ))
            printf '%s\\t%s\\t%s\\t%s\\t%s\\n' \\
                "\$identity" "\$units" "\$length" "\$name" "\$loci" >> ${sweep_table}
          done < genomes.txt
        done
      done
    done

    # The sequence was only ever the input to the finder.
    rm -rf ./${spec.simpleName} genomes.txt point.tsv
    """

    stub:
    """
    printf 'min_identity\\tmin_seed_units\\tmin_seed_length\\tgenome\\tloci\\n' > ${sweep_table}
    for identity in ${identities} ; do
      for units in ${seed_units} ; do
        for length in ${seed_lengths} ; do
          printf '%s\\t%s\\t%s\\tstub\\t13\\n' "\$identity" "\$units" "\$length" >> ${sweep_table}
        done
      done
    done
    """
}
