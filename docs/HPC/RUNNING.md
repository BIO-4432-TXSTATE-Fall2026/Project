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

Images come from `ghcr.io/bio-4432-txstate-fall2026/project/<name>`. The Containers
workflow in GitHub Actions publishes them. A pull fails with `unauthorized` if the package
is private. Make the package public, or run
`apptainer registry login --username <github-user> docker://ghcr.io` with a token that
has the `read:packages` scope.

## Test run

From the clone:

```sh
pixi run pipeline -profile slurm,apptainer --slurm_queue shared --names Alice,Bob,Carol
```

Add `--slurm_account <account>` if you have no default account. The template launches
three `HELLO` jobs, visible in `squeue -u $USER`, and writes to `results/greetings/`.

## Longer runs

A login node may kill long processes, and image pulls use its CPU. For real runs, submit
Nextflow itself as a small job that submits the task jobs:

```sh
sbatch -p shared -c 1 --mem=4G -t 2-00:00:00 -J nf-head -o nf-head-%j.log \
  --wrap "pixi run pipeline -profile slurm,apptainer --slurm_queue shared -ansi-log false -resume"
```

Give the head job a time limit longer than the whole pipeline. `-ansi-log false` keeps
the log readable as a file. Follow it with `tail -f nf-head-<jobid>.log`.

For a short run from the login node instead, start it inside `tmux new -s nf`, detach
with `Ctrl-b d`, and reattach with `tmux attach -t nf`.

## Resuming

Add `-resume` to rerun only tasks that failed or changed:

```sh
pixi run pipeline -profile slurm,apptainer --slurm_queue shared -resume
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
