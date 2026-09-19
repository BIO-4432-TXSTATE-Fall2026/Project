# Running the pipeline on SLURM

How to run the Nextflow pipeline on the cluster with Pixi and Apptainer. For general
SLURM commands, see `docs/HPC/SLURM.md`.

## How it runs

- Pixi's `nextflow` environment provides Nextflow, nf-test, and the JDK. It lives in
  `.pixi/envs/nextflow/` inside the clone.
- Apptainer comes from the cluster or a user install, not Pixi. It must be on `PATH`
  wherever Nextflow runs and on the compute nodes. To build it yourself, see
  `docs/HPC/INSTALL.md`.
- Nextflow runs where you launch it. It pulls each image once into `work/singularity/`,
  then submits every process as a SLURM job that runs inside that image.
- The clone, `work/`, and `results/` must be on a filesystem the compute nodes share,
  such as `$HOME`.

## One-time setup

On a login node:

```sh
git clone <repo-url> Project && cd Project
pixi install -e nextflow
pixi run -e nextflow nextflow -version
apptainer --version
srun -p shared --pty bash -lc 'which apptainer && cat /proc/sys/user/max_user_namespaces'
```

The last command must print an Apptainer path and a value greater than 0. Otherwise the
compute nodes cannot run the user-space Apptainer.

Optional environment variables for `~/.bashrc`:

```sh
export PIXI_CACHE_DIR=/tmp/pixi-cache-$USER                 # avoids the network-filesystem cache warning
export NXF_APPTAINER_CACHEDIR=$HOME/.apptainer-images       # keeps images when work/ is deleted
```

Then make the clone's `.env`, which is where settings that must not be committed live:

```sh
cp .env.example .env     # then fill in NTFY_TOPIC to get notifications
```

`.env` is git-ignored, and every setting in it is optional — with none of them, a run
behaves the same and says nothing. See [Notifications](#notifications).

Images come from `ghcr.io/bio-4432-txstate-fall2026/project/<name>`. The Containers
workflow in GitHub Actions publishes them. A pull fails with `unauthorized` if the package
is private. Make the package public, or run
`apptainer registry login --username <github-user> docker://ghcr.io` with a token that
has the `read:packages` scope.

## Test run

From the clone. `-stub` runs each task's stub instead of its real script, so nothing is
downloaded and the whole thing takes seconds:

```sh
pixi run pipeline --stage preprocess -stub
```

It writes a header-only `data/derived/hmp-sra-runs.tsv`, which is a placeholder, not a
table — delete it before a real run. To check that SLURM and Apptainer are wired up, add
the profiles and `--slurm_account <account>` if you have no default account:

```sh
pixi run pipeline --stage preprocess -stub -profile slurm,apptainer --slurm_queue shared
```

The job is visible in `squeue -u $USER` while it runs.

## Preprocessing

`--stage preprocess` rebuilds the committed tables in `data/derived/`. Each table is one
job that syncs its upstream catalog into the task directory, extracts the rows the project
needs, and deletes the catalog:

```sh
pixi run pipeline --stage preprocess -profile slurm,apptainer --slurm_queue shared
```

A container profile is required: the tasks run the project CLI out of the stage's image,
so nothing needs installing on the compute nodes. `work/` needs room for the largest
catalog — 2.3 GB for the SRA metadata freeze — while the job runs. A failed job leaves
that catalog behind in its work directory; `nextflow clean` removes it.

What the stage builds is in `docs/workflows/preprocess/`.

## Longer runs

A login node may kill long processes, and image pulls use its CPU. For real runs, submit
Nextflow itself as a small job that submits the task jobs:

```sh
sbatch -p shared -c 1 --mem=4G -t 2-00:00:00 -J nf-head -o nf-head-%j.log \
  --wrap "pixi run pipeline --stage preprocess -profile slurm,apptainer \
          --slurm_queue shared -ansi-log false -resume"
```

Give the head job a time limit longer than the whole pipeline. `-ansi-log false` keeps
the log readable as a file. Follow it with `tail -f nf-head-<jobid>.log`.

For a short run from the login node instead, start it inside `tmux new -s nf`, detach
with `Ctrl-b d`, and reattach with `tmux attach -t nf`.

## Notifications

A run can push notifications to [ntfy.sh](https://ntfy.sh), so a head job need not be
watched. Put the topic in `.env` and subscribe to the same name in the ntfy phone or web
app. With no topic set, nothing is sent.

```sh
cp .env.example .env             # then set NTFY_TOPIC in it
pixi run pipeline --stage preprocess -profile slurm,apptainer --slurm_queue shared
```

The project's topic is not in the repository, for the reason below; ask whoever set it up,
or `uuidgen` your own. `NTFY_TOPIC` in the environment and `--ntfy_topic` on the command
line both override the file, and `sbatch` passes the variable through to the head job, so
a one-off run can go somewhere else without editing anything. Setting the topic to the
empty string is an explicit silence, which is how `tests/nextflow.config` keeps the test
suite from pushing to a shared channel.

Three kinds of message arrive:

| When                    | Says                                                     |
| ----------------------- | -------------------------------------------------------- |
| A phase starts          | `<project>: <phase> started`                              |
| A phase's last task ends| `<project>: <phase> finished`, with the number of outputs |
| The run ends            | `<project>: run complete` or `run failed`                 |

The run-end message carries the stage, the duration, the task counts, and the first line
of the error if it failed — which names the process that failed. There is no per-phase
failure message: a failed task ends the whole run, so the run-end message is the failure
report. A notification that cannot be sent is logged and ignored; it never changes the
run's exit status.

Anyone who knows a topic name can read and post to it, so treat the name as the password
it is — and note the messages carry the run name and launch directory. That is why the
topic lives in the git-ignored `.env` and not in a tracked file: this repository is
public, and a committed topic is a public one, permanently. `NTFY_SERVER` points at a
self-hosted instance instead, and is read the same way. `workflows/modules/notify.nf`
holds all of it, reading `.env` through `workflows/modules/dotenv.nf`.

## Resuming

Add `-resume` to rerun only tasks that failed or changed:

```sh
pixi run pipeline --stage preprocess -profile slurm,apptainer --slurm_queue shared -resume
```

Launch from the same directory as the earlier run, since the cache lives in `.nextflow/`
and `work/`.

## Stopping

- **Foreground or tmux run:** press `Ctrl-C` once and wait. Nextflow cancels its
  submitted jobs before it exits.
- **Head job:** `scancel <head-jobid>`, then check `squeue -u $USER`. Cancel any task jobs
  left behind with `scancel <jobid>`. Task jobs are named `nf-<PROCESS>_(<tag>)`.

## Checking runs

```sh
pixi run -e nextflow nextflow log                                     # past runs in this directory
pixi run -e nextflow nextflow log <run-name> -f name,status,exit,native_id,hostname,duration
```

`native_id` is the SLURM job ID, usable with `sacct -j`. To debug a failed task, open its
work directory, which the error message and `nextflow log` print:

```sh
cat work/<xx>/<hash>/.command.sh     # the command that ran
cat work/<xx>/<hash>/.command.err    # stderr
cat work/<xx>/<hash>/.command.log    # SLURM output
```

The whole run's log is `.nextflow.log` in the launch directory.

## Cleaning up

```sh
pixi run -e nextflow nextflow clean -n -before <run-name>   # list what would be deleted
pixi run -e nextflow nextflow clean -f -before <run-name>   # delete work files of older runs
```

Deleting `work/` removes the `-resume` cache and, unless `NXF_APPTAINER_CACHEDIR` is set,
the pulled images.
