// Push notifications, so a long SLURM run can be left alone: one when a phase starts,
// one when it finishes, and one when the run ends, whether it succeeded or failed.
// Silent unless a topic is set, in `.env` or in the environment.
//
// Everything lives here, including the run-end handler, because Nextflow's config can
// register only `onComplete` and `onError` and cannot call into a module or a lib/ class:
// a handler written in `conf/` would have to carry its own copy of the POST below. A
// module function can register the same handler, so one copy serves all three events.
// `nextflow.config` keeps only the two settings.
//
// The handlers and the channel taps all run in the driver process, so only the node that
// launched the run needs outbound HTTPS.

include { dotenv } from './dotenv'

// The topic to post to, or null to stay silent.
//
// ntfy has no authentication: the topic name is the only thing keeping strangers off the
// channel, so it cannot be committed to a public repository and comes from `.env`.
// `--ntfy_topic` and the `NTFY_TOPIC` environment variable both reach `params` through
// `nextflow.config` and win over the file, so a one-off run or a SLURM job can override
// what the clone is set up with.
//
// Unset and empty mean different things, which is why this is not an `?:`. Unset is "not
// configured here, look in `.env`"; empty is an explicit "send nothing", which is how
// `tests/nextflow.config` keeps a test run from pushing to a channel other people are
// subscribed to.
def ntfyTopic() {
    return params.ntfy_topic != null ? params.ntfy_topic : dotenv('NTFY_TOPIC')
}

// Where to post: a self-hosted ntfy, or the public service. Resolved the same way as the
// topic, so a setting means the same thing wherever it is written; the default is here
// rather than in `nextflow.config` so that an unset `params` can fall through to `.env`.
def ntfyServer() {
    return params.ntfy_server ?: dotenv('NTFY_SERVER') ?: 'https://ntfy.sh'
}

// Post one notification. Silent unless a topic is set; a failure is logged, never thrown,
// so a missed notification cannot change the run's outcome.
def ntfy(String server, String topic, String title, String body, String priority, String tags) {
    if( !topic )
        return
    try {
        def conn = new URL("${server}/${topic}").openConnection()
        conn.requestMethod = 'POST'
        conn.connectTimeout = 10000
        conn.readTimeout = 10000
        conn.setRequestProperty('Title', title)
        conn.setRequestProperty('Priority', priority)
        conn.setRequestProperty('Tags', tags)
        conn.doOutput = true
        conn.outputStream.withWriter('UTF-8') { it << body }
        conn.responseCode
    }
    catch( Exception e ) {
        log.warn "could not notify ${server}: ${e.message}"
    }
}

// Announce the end of the run. Call once, first thing in the entry workflow: the handler
// has to be registered from inside a workflow body, since the strict parser allows no
// statements at the top level of a script.
//
// `workflow` and `params` are unbound by the time the handler runs, so everything it says
// is captured here, while the binding still exists. onComplete covers a failed run as
// well as a successful one, which is why there is no separate onError handler.
def notifyRun() {
    def meta = workflow
    def server = ntfyServer()
    def topic = ntfyTopic()
    def stage = params.stage

    meta.onComplete {
        def ok = meta.success
        def lines = [
            "stage ${stage}, ${meta.duration}",
            "${meta.stats.succeededCount} ok, ${meta.stats.failedCount} failed",
            "${meta.runName} in ${meta.launchDir}",
        ]
        if( !ok && meta.errorMessage )
            lines << meta.errorMessage.readLines().first()

        ntfy(server, topic,
             "${meta.manifest.name}: run ${ok ? 'complete' : 'failed'}",
             lines.join('\n'),
             ok ? 'default' : 'high',
             ok ? 'white_check_mark' : 'rotating_light')
    }
}

// Announce `name` as starting, when the first item reaches `ch`, and returns `ch` so it
// can be dropped into a pipe without changing what flows through it.
//
// These fire on channel events, not on where the call sits in the workflow body. The body
// runs once at startup to build the DAG, so a bare notification between two phases would
// announce every one of them before any work began. A tap instead fires when data
// actually reaches that point, which for a phase's input is when the phase begins.
def announceStart(ch, String name) {
    def server = ntfyServer()
    def topic = ntfyTopic()
    def run = workflow.runName
    def project = workflow.manifest.name

    def announced = false
    ch.subscribe {
        if( !announced ) {
            announced = true
            ntfy(server, topic, "${project}: ${name} started", run,
                 'low', 'hourglass_flowing_sand')
        }
    }
    return ch
}

// Announce `name` as finished, when `ch` closes: for a process output that is after its
// last task, so it means the whole phase is done, not just its first result.
//
// There is no matching per-phase failure notification, because Nextflow exposes no
// per-process error event outside a plugin. A failed task ends the run under the
// `finish` strategy in `conf/base.config`, and the run-end notification above reports it
// with the first line of the error, which names the process that failed.
def announceDone(ch, String name) {
    def server = ntfyServer()
    def topic = ntfyTopic()
    def run = workflow.runName
    def project = workflow.manifest.name

    def count = 0
    ch.subscribe(
        onNext: { count += 1 },
        onComplete: {
            ntfy(server, topic, "${project}: ${name} finished",
                 "${count} output${count == 1 ? '' : 's'}, ${run}",
                 'default', 'white_check_mark')
        })
    return ch
}
