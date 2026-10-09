# SRA Search Pegasus Workflow

Pegasus workflow which downloads and aligns SRA data, using SRA Toolkit,
Samtools and Bowtie2

## Container

SRA Tools, samtools and Bowtie2 are all included in a single container
defined in `container/sra.def`. If the container is not already built
(no `container/sra.sif` file), build it with:

  cd container && apptainer build sra.sif sra.def

## Workflow

The number of concurrent downloads is limited with a DAGMan
category profile.

The output bam/bai files are merged into a single tarball which is
the final output of the workflow.

The generator lives in `sra_search.py` (the `SraSearchWorkflow` class);
`./sra-search.py` is its command-line entry point and
[`SRA-Search-Workflow.ipynb`](SRA-Search-Workflow.ipynb) drives the same class
interactively.

## Running the workflow

The generator writes `workflow.yml` and its catalogs (`pegasus.properties`,
`replicas.yml`, `transformations.yml`) and prints the `pegasus-plan` command.
It never plans or submits by itself.

```bash
# 1. Build the container (once)
(cd container && apptainer build sra.sif sra.def)

# 2. Generate (here: a plain HTCondor pool with no site catalog)
./sra-search.py --sra-id-list examples/10/sra_ids.txt \
    --reference examples/10/crassphage.fna -e condorpool

# 3. Plan and submit (the command the generator printed)
pegasus-plan --dir submit -s condorpool -o local \
    --output-dir "$PWD/output" --submit workflow.yml
```

The final tarball lands in `output/results.tar.gz`. Or open
`SRA-Search-Workflow.ipynb`, which generates, plans, submits (from an explicit
cell), monitors and shows the results.

## Testing

Please test the workflow with the single SRA input:

    ./sra-search.py --sra-id-list examples/1/sra_ids.txt --reference examples/1/crassphage.fna -e condorpool

`python3 test_workflow.py -v` does this end to end: it generates with
`-e condorpool` (override with `SRA_TEST_SITE`), runs the printed
`pegasus-plan --submit` command, and waits for `output/results.tar.gz`.

## Site catalogs

Where jobs run depends on your resource provider and allocation, so it lives
in a site catalog you choose, never in the generator, which writes no site
catalog. Jobs run on a site named `compute` (`-e`, the default), the one site
every centrally hosted catalog
([pegasushub/pegasus-site-catalogs](https://github.com/pegasushub/pegasus-site-catalogs/tree/main/conf))
defines; `pegasus-plan` downloads the catalog from the branch matching its
Pegasus version.

```bash
ARGS="--sra-id-list examples/1/sra_ids.txt --reference examples/1/crassphage.fna"

# Hosted catalog for this workflow (written to pegasus.properties)
./sra-search.py $ARGS -s access-pegasus.yml
pegasus-plan --dir submit -s compute -o local --output-dir "$PWD/output" --submit workflow.yml

# Plain HTCondor pool with no site catalog: Pegasus has no built-in
# "compute", but provides a default "condorpool" site
./sra-search.py $ARGS -e condorpool
pegasus-plan --dir submit -s condorpool -o local --output-dir "$PWD/output" --submit workflow.yml
```

A hosted catalog can also be set once per user (as the ACCESS training setup
does) in `~/.pegasusrc`, together with the allocation values it references;
then generate with no `-s`:

```
pegasus.catalog.site.repo.file = unity.yml
env.RESOURCE_USERNAME = jdoe
env.RESOURCE_PROJECT = my_lab
```

| Option | Default | Meaning |
|---|---|---|
| `-s, --hosted-site-catalog` | none (`~/.pegasusrc` if set) | Hosted catalog to plan against, e.g. `access-pegasus.yml`, `unity.yml`; written to `pegasus.properties`. |
| `-e, --execution-site-name` | `compute` | Execution site name; `condorpool` on a plain HTCondor pool with no site catalog. |
| `-o, --output` | `workflow.yml` | Workflow file to write. |

`create_sites_catalog()` (a self-contained `local` + HTCondor `compute`
catalog) is only used by the notebook.

Note that `fasterq-dump` downloads from NCBI, so the execution site's workers
need outbound internet access over **IPv4**: SRA serves the data from AWS S3
(`sra-pub-run-odp.s3.amazonaws.com`), which has no IPv6 address. On IPv6-only
workers (e.g. FABRIC nodes) the job fails with `error from srapath ...
rcConnection,rcNotAvailable`. Pin the execution site's jobs to workers that
have IPv4 with a site-scoped Condor profile set as a property, e.g. in
`pegasus.properties` (after generating) or `~/.pegasusrc`, for the site you
plan on:

```
pegasus.catalog.site.sites.condorpool.profiles.condor.requirements = (Machine == "submit.example.org")
```

Keep it site-scoped: a global `condor.requirements` also lands on Pegasus's
local-universe jobs (`create_dir`, stage-in), which then never match and stay
idle.

## Workflow Details

* All jobs run inside a local Singularity/Apptainer `.sif` image (`container/sra.sif`). `bowtie2-build` is installed in the image (transformation site `incontainer`, not staged); the three wrappers in `executables/` are stageable and staged into each job.
* Data staging follows the site: HTCondor file transfer (`condorio`) on an HTCondor pool, the site's own setting (e.g. `nonsharedfs`) on a hosted batch catalog.
* Each job carries a pegasus `memory` profile (1-2 GB, `TOOL_CONFIGS` in `sra_search.py`), mapped to `request_memory` on HTCondor and `--mem` on Slurm. Hosted batch catalogs supply the wall-clock default.
