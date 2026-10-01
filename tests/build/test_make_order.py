"""Exercise the real Make dependency graph without compiling Exim or touching spools."""

from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class MakeOrderTests(unittest.TestCase):
    def run_make(self, fail_build):
        with tempfile.TemporaryDirectory(prefix="observer-make-order-") as directory:
            temporary = Path(directory)
            log = temporary / "steps"
            quoted_log = shlex.quote(str(log))
            override = temporary / "override.mk"
            build = "false" if fail_build else f"printf 'build\\n' >> {quoted_log}"
            override.write_text(
                "check-protocol:\n\t@:\n"
                f"build:\n\t@{build}\n"
                f"integration:\n\t@printf 'integration\\n' >> {quoted_log}\n"
            )
            result = subprocess.run(
                [
                    "make",
                    "--no-print-directory",
                    "-k",
                    "-j2",
                    "-f",
                    str(ROOT / "Makefile"),
                    "-f",
                    str(override),
                    "build",
                    "integration",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=10,
            )
            return result, log.read_text().splitlines() if log.exists() else []

    def test_build_precedes_integration_and_runs_once(self):
        result, steps = self.run_make(fail_build=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(steps, ["build", "integration"])

    def test_failed_build_never_runs_integration_even_with_keep_going(self):
        result, steps = self.run_make(fail_build=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(steps, [], result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
