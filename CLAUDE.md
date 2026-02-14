# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pegasus workflow that downloads sequencing data from the NCBI SRA database and aligns it against a reference genome using Bowtie2/Samtools. The workflow is designed for distributed execution via HTCondor/DAGMan through the Pegasus workflow management system.

## Key Commands

### Build the container
```bash
cd container && apptainer build sra.sif sra.def
```

### Submit a workflow
```bash
./sra-search.py --sra-id-list tests/10/sra_ids.txt --reference tests/10/crassphage.fna
```

### Test with a single SRA input
```bash
./sra-search.py --sra-id-list tests/1/sra_ids.txt --reference tests/1/crassphage.fna
```

Test datasets are in `tests/{1,10,1000}/` with SRA ID lists and a crassphage reference genome.

## Architecture

### Workflow Pipeline (sra-search.py)

The entire workflow is defined in `sra-search.py` using the `Pegasus.api` Python library. The DAG structure is:

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

Defined in `container/sra.def` (Apptainer/Singularity). Installs SRA Toolkit 2.10.0, Bowtie2 2.2.9, and Samtools 1.10 on Debian 13.

## Key Details

- Python dependency: `Pegasus.api` (Pegasus WMS Python package)
- Resource profiles are set per-transformation via Condor profiles (1-2 GB memory per job)
- Download concurrency is rate-limited to 20 via `dagman.fasterq-dump.maxjobs`
- Wrapper script paths in `sra-search.py` must match the `executables/` directory — keep them in sync if scripts are moved
