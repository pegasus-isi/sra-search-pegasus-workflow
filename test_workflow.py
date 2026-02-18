#!/usr/bin/env python3

"""
Integration test for the sra-search Pegasus workflow.

Shells out to ./sra-search.py, captures the submit directory from its output,
attaches a Pegasus Workflow object to that directory, then polls status until
the workflow succeeds, fails, or times out.
"""

import re
import subprocess
import time
import unittest

from Pegasus.api import Workflow
from Pegasus.client._client import Client


TIMEOUT_MINUTES = 20
POLL_INTERVAL_SECONDS = 60
INITIAL_SLEEP_SECONDS = 30
PEGASUS_HOME = "/usr"

# States that mean the workflow is still running
RUNNING_STATES = {"Running", "Unknown", ""}


def _extract_run_dir(output: str) -> str:
    """Parse the submit directory from sra-search.py stdout.

    pegasus-plan prints a line like:
        pegasus-remove /path/to/rundir
    We grab the path from that line.
    """
    match = re.search(r"pegasus-remove\s+(\S+)", output)
    if not match:
        raise RuntimeError(
            "Could not find run directory in sra-search.py output:\n" + output
        )
    return match.group(1)


class TestSraSearchWorkflow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Submit the workflow once for all tests and attach a Workflow object."""
        result = subprocess.run(
            ["./sra-search.py",
             "--sra-id-list", "examples/1/sra_ids.txt",
             "--reference", "examples/1/crassphage.fna"],
            capture_output=True,
            text=True,
        )
        combined = result.stdout + result.stderr
        if "pegasus-remove" not in combined:
            raise RuntimeError(
                "sra-search.py did not produce a pegasus-remove line; "
                f"stdout={result.stdout!r}  stderr={result.stderr!r}"
            )

        cls.run_dir = _extract_run_dir(combined)

        # Attach a Workflow object to the existing run directory
        cls.wf = Workflow("sra-search")
        cls.wf._submit_dir = cls.run_dir
        cls.wf._client = Client(PEGASUS_HOME)

    def _get_state(self) -> str:
        """Return the root DAG state string (e.g. 'Running', 'Success', 'Failure')."""
        status = self.wf.status(json=True, noqueue=True)
        return status.get("dags", {}).get("root", {}).get("state", "")

    def test_workflow_succeeds(self):
        """Workflow should reach 'Success' within TIMEOUT_MINUTES minutes."""
        print(f"\nRun directory: {self.run_dir}")

        time.sleep(INITIAL_SLEEP_SECONDS)

        state = self._get_state()
        print(f"Initial state: {state!r}")

        deadline = time.time() + TIMEOUT_MINUTES * 60

        while state in RUNNING_STATES:
            if time.time() >= deadline:
                self.wf.remove()
                time.sleep(60)
                self.fail(
                    f"Workflow did not finish within {TIMEOUT_MINUTES} minutes; "
                    f"called pegasus-remove on {self.run_dir}"
                )

            time.sleep(POLL_INTERVAL_SECONDS)
            state = self._get_state()
            print(f"State: {state!r}")

        self.assertEqual(
            state, "Success",
            msg=f"Workflow ended with state {state!r} instead of 'Success'",
        )
        print("*** Workflow finished successfully ***")

    def test_workflow_has_jobs(self):
        """After submission the workflow status should report at least one job."""
        status = self.wf.status(json=True, noqueue=True)
        total = status.get("totals", {}).get("total", 0)
        self.assertGreater(total, 0, msg="Expected at least one job in the workflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
