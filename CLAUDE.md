# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pegasus workflow that downloads sequencing data from the NCBI SRA database and aligns it against a reference genome using Bowtie2/Samtools. The workflow is designed for distributed execution via HTCondor/DAGMan through the Pegasus workflow management system.

## Key Commands

### Build the container
```bash
cd container && apptainer build sra.sif sra.def
```

### Generate, then plan and submit a workflow
```bash
./sra-search.py --sra-id-list examples/10/sra_ids.txt --reference examples/10/crassphage.fna -e condorpool
pegasus-plan --dir submit -s condorpool -o local --output-dir "$PWD/output" --submit workflow.yml
```

The generator never submits; it prints the `pegasus-plan` command. `SRA-Search-Workflow.ipynb` drives the same class and submits from an explicit cell.

### Run the unit tests (ALWAYS run this to test changes)
```bash
python3 test_workflow.py -v
```

This generates a single-SRA workflow with `-e condorpool` (override with `SRA_TEST_SITE`), runs the printed `pegasus-plan --submit` command, and waits for it to reach "Success" and for `output/results.tar.gz`. All tests must pass before any change is considered complete.

### Test with a single SRA input (manual)
```bash
./sra-search.py --sra-id-list examples/1/sra_ids.txt --reference examples/1/crassphage.fna -e condorpool
```

Test datasets are in `examples/{1,10,1000}/` with SRA ID lists and a crassphage reference genome.

## Architecture

### Workflow Pipeline (sra_search.py)

The entire workflow is defined in `sra_search.py` (class `SraSearchWorkflow`, following the pegasus-gromacs generator pattern) using the `Pegasus.api` Python library; `sra-search.py` is a thin CLI wrapper, and the notebook imports the same class. The DAG structure is:

1. **Index job** (`bowtie2-build`) — builds Bowtie2 index from the reference FASTA
2. **Per-SRA-ID jobs** (parallelized, one pair per SRA ID):
   - `fasterq-dump` — downloads paired-end FASTQ files from SRA (max 20 concurrent via DAGMan category)
   - `bowtie2` — aligns reads to the indexed reference, outputs sorted BAM + BAI
3. **Merge jobs** — hierarchical merge tree (max 25 inputs per merge job) producing `results.tar.gz`

The merge tree is built by `add_merge_jobs()` which recursively chunks parent jobs into groups of 25 until a single final tarball remains.

### Wrapper Scripts (executables/)

All tools run inside a Singularity/Apptainer container (`container/sra.sif`). The wrapper scripts in `executables/` are staged into the container at runtime:

- **bowtie2_wrapper** — runs `bowtie2 | samtools view | samtools sort`, then indexes the BAM
- **fasterq_dump_wrapper** — resets SRA Toolkit config, then runs `fasterq-dump --split-files`
- **merge** — extracts any intermediate tarballs, collects BAM files, creates final tarball

### Container (container/)

Defined in `container/sra.def` (Apptainer/Singularity). Installs SRA Toolkit 2.10.0, Bowtie2 2.5.4, and Samtools 1.10 on Debian 13.

## Key Details

- Python dependency: `Pegasus.api` (Pegasus WMS Python package)
- Resource profiles are set per-transformation from `TOOL_CONFIGS` as Pegasus `memory` profiles (1-2 GB), so they apply on both HTCondor and Slurm
- The generator writes no site catalog. Jobs run on `compute` (`-e` default) from a hosted site catalog (`-s FILE`, written to `pegasus.properties`, or `~/.pegasusrc`); on a plain HTCondor pool with no catalog use `-e condorpool`. `create_sites_catalog()` is a notebook-only placeholder (`local` + HTCondor `compute`)
- Download concurrency is rate-limited to 20 via `dagman.fasterq-dump.maxjobs`
- Wrapper script paths in `sra_search.py` must match the `executables/` directory — keep them in sync if scripts are moved
