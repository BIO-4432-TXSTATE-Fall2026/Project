include { HELLO } from './modules/hello'

workflow {
    main:
    names = channel.fromList(params.names.tokenize(','))
    HELLO(names)

    publish:
    greetings = HELLO.out
}

output {
    greetings {
        path 'greetings'
    }
}
