# Installing Apptainer without root

How to build Go and Apptainer under `$HOME` on a cluster without root access. Tested with
Go 1.27.1 and Apptainer 1.5.3; Apptainer 1.5.3 needs Go 1.25.7 or newer. To run the
pipeline afterwards, see `docs/HPC/RUNNING.md`.

Install into a directory the compute nodes also mount, such as `$HOME`, so tasks find the
same `apptainer`.

## 1. Toolchain

```bash
module load gcc
mkdir -p ~/local ~/src
```

The system must already provide the libraries Apptainer builds against, such as
`libseccomp-devel`, and `mksquashfs` from squashfs-tools. `./mconfig` in step 4 reports
anything missing.

## 2. Go

Go is only needed to build Apptainer.

```bash
cd ~/src
curl -LO https://go.dev/dl/go1.27.1.linux-amd64.tar.gz
tar -C ~/local -xzf go1.27.1.linux-amd64.tar.gz
export PATH=$HOME/local/go/bin:$PATH
go version   # go version go1.27.1 linux/amd64
```

`-L` is required: `go.dev/dl` redirects to `dl.google.com`, and without it `curl` saves
the redirect response instead of the archive.

## 3. Apptainer source

Use the release tarball rather than a git clone. It already includes `vendor/`.

```bash
cd ~/src
curl -LO https://github.com/apptainer/apptainer/releases/download/v1.5.3/apptainer-1.5.3.tar.gz
tar -C ~/local -xzf apptainer-1.5.3.tar.gz
cd apptainer-1.5.3
```

## 4. Build and install

Update the Go dependency before configuring. `go mod vendor` must follow `go get` and
`go mod tidy`, or the build fails because `vendor/` no longer matches `go.mod`:

```bash
go get golang.org/x/net@v0.55.0
go mod tidy
go mod vendor
```

Configure from the source root, then build and install:

```bash
./mconfig --without-suid --prefix=$HOME/local/apptainer
make -C builddir
make -C builddir install
```

- Run `./mconfig` before `make`. It creates `builddir/`, and rerunning it deletes and
  recreates `builddir/`, so `make clean` is not needed.
- Use `$HOME`, not `~`, in `--prefix=`. Bash does not expand `~` after `--prefix=`.
- `--without-suid` is already the default. It is shown to make clear that Apptainer runs
  in unprivileged mode, which requires user namespaces on every node.

## 5. PATH

Add to `~/.bashrc`:

```bash
export PATH=$HOME/local/apptainer/bin:$PATH
```

Putting it first makes this `apptainer` win over any system copy. Go does not need to stay
on `PATH`.

## 6. Verify

```bash
source ~/.bashrc
which apptainer        # ~/local/apptainer/bin/apptainer
apptainer version      # 1.5.3
srun -p shared --pty bash -lc 'which apptainer && cat /proc/sys/user/max_user_namespaces'
```

The last command must print this install's path and a value greater than 0.

## Optional: FUSE tools

Without `squashfuse`, Apptainer cannot mount SIF images unprivileged and extracts each one
to a temporary directory instead, which is slower and uses more disk. To build the FUSE
tools into this install, run from the source directory after step 4:

```bash
./scripts/download-dependencies
./scripts/compile-dependencies
./scripts/install-dependencies
```

`install-dependencies` installs into `~/local/apptainer/libexec`, so it needs no `sudo`.
Compiling needs the FUSE 3, zlib, LZO, LZ4, XZ, and Zstandard development headers. If the
cluster lacks them, skip this section.
