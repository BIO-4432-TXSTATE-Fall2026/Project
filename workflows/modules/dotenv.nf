// Read a variable out of the `.env` file at the repository root.
//
// A module rather than part of `nextflow.config`, because the config parser allows no
// variable declarations, and a module function can be included wherever a setting is
// actually needed. `.env` is git-ignored; `.env.example` is the committed copy that says
// what belongs in it, and `docs/HPC/RUNNING.md` says how to make one.
//
// What belongs in `.env` is the settings that must not be committed — a public
// repository's clone is readable by everyone, so an unauthenticated secret such as an
// ntfy topic cannot live in a tracked file. Settings that are merely per-machine belong
// in `nextflow.config` or on the command line, where they are visible.

// The value of `name`, or null if the file does not exist or does not set it. Lines are
// `NAME=value`, optionally `export`ed and optionally quoted; anything else, comments
// included, is skipped. An empty value reads as null, so a placeholder left blank is the
// same as saying nothing.
def dotenv(String name) {
    def envFile = file("${projectDir}/../.env")
    if( !envFile.exists() )
        return null
    // The pattern is built as a plain string and quoted at runtime: the strict parser
    // rejects an interpolated slashy regex, and a name is a literal, never a pattern.
    def key = java.util.regex.Pattern.quote(name)
    def match = envFile.text =~ ('(?m)^[ \t]*(?:export[ \t]+)?' + key + '[ \t]*=[ \t]*(.*?)[ \t]*$')
    if( !match )
        return null
    return match[0][1].replaceAll(/^["']|["']$/, '') ?: null
}
