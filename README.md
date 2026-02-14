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

To submit a workflow, run:

    ./sra-search.py --sra-id-list tests/10/sra_ids.txt --reference tests/10/crassphage.fna

## Testing

Please test the workflow with the single SRA input:

    ./sra-search.py --sra-id-list tests/1/sra_ids.txt --reference tests/1/crassphage.fna

