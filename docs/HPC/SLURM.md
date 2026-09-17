# SLURM

Everyday SLURM commands for the cluster. Replace `shared` with another partition and add
`-A <account>` only if your jobs need a non-default account. To run the pipeline, see
`docs/HPC/RUNNING.md`.

## Cluster and account

```sh
sinfo -s                                                  # partitions and node states
sinfo -p shared -o "%P %l %c %m %D %t"                    # time limit, CPUs, memory, nodes
sacctmgr show user $USER format=user,defaultaccount%30    # your default account
sacctmgr show assoc user=$USER format=account%30,partition%20
```

If `defaultaccount` is blank, pass `-A <account>` to `srun`, `salloc`, and `sbatch`.

## Running jobs

Login nodes are for editing, submitting, and short checks. Run real work on compute nodes.

**Interactive shell on a compute node:**

```sh
srun -p shared -c 2 --mem=4G -t 01:00:00 --pty bash -l
```

Exit the shell to release the node.

**One command, output in a file:**

```sh
sbatch -p shared -c 1 --mem=2G -t 00:10:00 -o hostname-%j.log --wrap "hostname"
```

**Batch script:**

```sh
#!/bin/bash
#SBATCH -J my-job
#SBATCH -p shared
#SBATCH -c 4
#SBATCH --mem=8G
#SBATCH -t 04:00:00
#SBATCH -o %x-%j.log

pixi run python -m hmp_project --help
```

Submit it with `sbatch my-job.sh`. `%x` is the job name and `%j` the job ID. Command-line
options override `#SBATCH` lines.

| Option        | Meaning                                        |
| ------------- | ---------------------------------------------- |
| `-p`          | Partition                                      |
| `-A`          | Account to charge                              |
| `-c`          | CPUs per task                                  |
| `--mem`       | Memory for the job                             |
| `-t`          | Time limit: `MM:SS`, `HH:MM:SS`, or `D-HH:MM:SS` |
| `-J`          | Job name                                       |
| `-o` / `-e`   | Stdout / stderr file                           |

Jobs start in the submitting directory and inherit its environment, `PATH` included.

## Stopping jobs

```sh
scancel <jobid>                      # one job
scancel -u $USER                     # all of your jobs
scancel -u $USER -t PENDING          # only jobs still waiting
scancel -u $USER --name nf-HELLO     # jobs with this exact name
```

## Current jobs

```sh
squeue -u $USER                                   # pending and running jobs
squeue -u $USER -o "%.10i %.30j %.8T %.10M %.10l %R"
squeue -j <jobid> --start                         # estimated start of a pending job
scontrol show job <jobid>                         # full details of a queued or running job
```

`%R` shows the node list for running jobs and the reason a job is still pending, such as
`Priority` or `Resources`.

## Finished jobs

```sh
sacct -u $USER -S today                           # today's jobs
sacct -u $USER -S 2026-09-01 -E now
sacct -j <jobid> -o JobID,JobName%30,State,ExitCode,Elapsed,MaxRSS,NodeList
seff <jobid>                                      # CPU and memory efficiency, if installed
```

Common states: `COMPLETED`, `FAILED` (non-zero exit), `CANCELLED`, `TIMEOUT` (raise
`-t`), and `OUT_OF_MEMORY` (raise `--mem`). Compare `MaxRSS` with the memory you
requested to size later jobs.
