#!/usr/bin/env python3

"""Command-line entry point for the sra-search workflow generator.

The generator lives in sra_search.py (importable, so the notebook can use the
same SraSearchWorkflow class); this wrapper keeps the ./sra-search.py command.
"""

from sra_search import main

if __name__ == "__main__":
    main()
