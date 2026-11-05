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
//
// Each row summarises the point's calls rather than counting them. A yield alone cannot
// say which loci a threshold bought, and the two questions the grid exists to answer are
// both about composition: `min_seed_length` moves the mono-, di- and trinucleotide
// counts while `min_seed_units` only binds on motifs long enough for the length floor to
// stop deciding, and overlapping calls -- the §2 merge's whole subject -- multiply as the
// seed loosens, so a raw yield inflates unevenly down the grid. The calls themselves stay
// out of the table: TR_CATALOG at a chosen point is where they come from.
def sweep_header() {
    'min_identity\tmin_seed_units\tmin_seed_length\tgenome\tloci\toverlaps' +
        '\tmotif_1\tmotif_2\tmotif_3\tmotif_4_5\tmotif_6p\tunits_2\tmin_rep_length'
}

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

    # One pass over a point's calls. Written to a file rather than inlined in the loop so
    # that awk's fields stay readable: every \$ in the script block is escaped once for
    # Groovy already, and a quoted heredoc keeps the shell out of it entirely.
    cat > summarise.awk <<'AWK'
BEGIN { FS = OFS = "\\t" }
{
    loci++
    if (\$7 == 1) m1++
    else if (\$7 == 2) m2++
    else if (\$7 == 3) m3++
    else if (\$7 <= 5) m45++
    else m6p++
    # units_2 is a check as much as a count: with min_seed_units at 3 the finder cannot
    # return a two-unit call, so a nonzero column here means the floor did not bind.
    if (\$9 == 2) u2++
    if (minrl == "" || \$8 < minrl) minrl = \$8
    # Sorted by contig then start on the way in, so the previous row is the neighbour.
    if (\$2 == contig && \$3 < end) ov++
    contig = \$2 ; end = \$4
}
END {
    if (minrl == "") minrl = "NA"
    printf "%d\\t%d\\t%d\\t%d\\t%d\\t%d\\t%d\\t%d\\t%s\\n", loci+0, ov+0, m1+0, m2+0, m3+0, m45+0, m6p+0, u2+0, minrl
}
AWK

    printf '%s\\n' '${sweep_header()}' > ${sweep_table}

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
            # sniffer cannot place. point.tsv is a scratch file: it is summarised and
            # overwritten by the next point.
            ${params.trf} find "\$genome" point.tsv \\
                --format fasta --profile ${profile} --genome "\$name" \\
                --min-identity "\$identity" \\
                --min-seed-units "\$units" \\
                --min-seed-length "\$length"
            # The sort is what makes `overlaps` mean anything: the finder's own order is
            # contig-then-position already, but a summary that silently undercounts when
            # it is not would be worse evidence than none.
            summary=\$(tail -n +2 point.tsv \\
                | sort -t "\$(printf '\\t')" -k2,2 -k3,3n \\
                | awk -f summarise.awk)
            printf '%s\\t%s\\t%s\\t%s\\t%s\\n' \\
                "\$identity" "\$units" "\$length" "\$name" "\$summary" >> ${sweep_table}
          done < genomes.txt
        done
      done
    done

    # The sequence was only ever the input to the finder.
    rm -rf ./${spec.simpleName} genomes.txt point.tsv summarise.awk
    """

    stub:
    """
    printf '%s\\n' '${sweep_header()}' > ${sweep_table}
    for identity in ${identities} ; do
      for units in ${seed_units} ; do
        for length in ${seed_lengths} ; do
          # The motif bands sum to loci, so a notebook cell that checks that holds here too.
          printf '%s\\t%s\\t%s\\tstub\\t13\\t1\\t4\\t3\\t3\\t2\\t1\\t0\\t12\\n' \\
              "\$identity" "\$units" "\$length" >> ${sweep_table}
        done
      done
    done
    """
}
