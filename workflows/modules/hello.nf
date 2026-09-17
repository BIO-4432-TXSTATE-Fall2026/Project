// Template module; replace with a real tool.
process HELLO {
    tag "${name}"

    input:
    val name

    output:
    path "${name}.txt"

    script:
    """
    echo "Hello, ${name}!" > ${name}.txt
    """
}
