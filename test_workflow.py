#!/usr/bin/env python3

"""
Integration test for the sra-search Pegasus workflow.

Shells out to ./sra-search.py (which only writes the workflow and prints the
pegasus-plan command), runs that printed command, captures the submit
directory from its output, attaches a Pegasus Workflow object to that
directory, then polls status until the workflow succeeds, fails, or times out.

The execution site defaults to "condorpool" (Pegasus's built-in HTCondor
site, no site catalog needed); set SRA_TEST_SITE to plan elsewhere.
"""

import os
import re
import shlex
import subprocess
import time
import unittest

from Pegasus.api import Workflow
from Pegasus.client._client import Client


TIMEOUT_MINUTES = 20
POLL_INTERVAL_SECONDS = 60
INITIAL_SLEEP_SECONDS = 30
PEGASUS_HOME = "/usr"
EXEC_SITE = os.environ.get("SRA_TEST_SITE", "condorpool")

# States that mean the workflow is still running
RUNNING_STATES = {"Running", "Unknown", ""}


def _extract_run_dir(output: str) -> str:
    """Parse the submit directory from pegasus-plan output.

    pegasus-plan prints a line like:
        pegasus-remove /path/to/rundir
    We grab the path from that line.
    """
    match = re.search(r"pegasus-remove\s+(\S+)", output)
    if not match:
        raise RuntimeError(
            "Could not find run directory in pegasus-plan output:\n" + output
        )
    return match.group(1)


class TestSraSearchWorkflow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Submit the workflow, wait for it to finish, and store the final state."""
        gen = subprocess.run(
            ["./sra-search.py",
             "--sra-id-list", "examples/1/sra_ids.txt",
             "--reference", "examples/1/crassphage.fna",
             "-e", EXEC_SITE],
            capture_output=True,
            text=True,
        )
        gen_out = gen.stdout + gen.stderr
        match = re.search(r"Plan and submit: (pegasus-plan .*)", gen_out)
        if gen.returncode != 0 or not match:
            raise RuntimeError(
                "sra-search.py did not print a pegasus-plan command; "
                f"stdout={gen.stdout!r}  stderr={gen.stderr!r}"
            )

        result = subprocess.run(
            shlex.split(match.group(1).strip()), capture_output=True, text=True
        )
        combined = result.stdout + result.stderr
        if "pegasus-remove" not in combined:
            raise RuntimeError(
                "pegasus-plan did not produce a pegasus-remove line; "
                f"stdout={result.stdout!r}  stderr={result.stderr!r}"
            )

        cls.run_dir = _extract_run_dir(combined)

        # Attach a Workflow object to the existing run directory
        cls.wf = Workflow("sra-search")
        cls.wf._submit_dir = cls.run_dir
        cls.wf._client = Client(PEGASUS_HOME)

        print(f"\nRun directory: {cls.run_dir}")
        time.sleep(INITIAL_SLEEP_SECONDS)

        state = cls._poll_state()
        print(f"Initial state: {state!r}")

        deadline = time.time() + TIMEOUT_MINUTES * 60

        while state in RUNNING_STATES:
            if time.time() >= deadline:
                cls.wf.remove()
                time.sleep(60)
                raise RuntimeError(
                    f"Workflow did not finish within {TIMEOUT_MINUTES} minutes; "
                    f"called pegasus-remove on {cls.run_dir}"
                )

            time.sleep(POLL_INTERVAL_SECONDS)
            state = cls._poll_state()
            print(f"State: {state!r}")

        cls.final_state = state
        print(f"*** Workflow finished with state {state!r} ***")

    @classmethod
    def _poll_state(cls) -> str:
        """Return the root DAG state string (e.g. 'Running', 'Success', 'Failure')."""
        status = cls.wf.status(json=True, noqueue=True)
        return status.get("dags", {}).get("root", {}).get("state", "")

    def test_workflow_succeeds(self):
        """Workflow should reach 'Success' within TIMEOUT_MINUTES minutes."""
        self.assertEqual(
            self.final_state, "Success",
            msg=f"Workflow ended with state {self.final_state!r} instead of 'Success'",
        )

    def test_workflow_has_jobs(self):
        """After submission the workflow status should report at least one job."""
        status = self.wf.status(json=True, noqueue=True)
        total = status.get("totals", {}).get("total", 0)
        self.assertGreater(total, 0, msg="Expected at least one job in the workflow")

    def test_results_tar_gz_exists(self):
        """output/results.tar.gz should exist after the workflow completes."""
        output_file = os.path.join("output", "results.tar.gz")
        self.assertTrue(
            os.path.isfile(output_file),
            msg=f"Expected output file not found: {output_file}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
