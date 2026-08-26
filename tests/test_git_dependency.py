from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "prepare-git-dependency.py"
SPEC = importlib.util.spec_from_file_location("prepare_git_dependency", MODULE_PATH)
assert SPEC and SPEC.loader
dependency = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dependency)


class GitDependencyTests(unittest.TestCase):
    def test_prepares_the_exact_locked_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            subprocess.run(["git", "init", "--quiet", str(source)], check=True)
            (source / "tss").write_text("#!/bin/sh\necho tss\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", "tss"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "--quiet",
                    "-m",
                    "initial",
                ],
                check=True,
            )
            revision = subprocess.run(
                ["git", "-C", str(source), "rev-parse", "HEAD"],
                check=True,
                text=True,
                capture_output=True,
            ).stdout.strip()
            manifest = root / "dependency.json"
            manifest.write_text(
                json.dumps(
                    {
                        "name": "tss",
                        "repository": str(source),
                        "revision": revision,
                        "entrypoint": "tss",
                    }
                ),
                encoding="utf-8",
            )

            destination = root / "staged"
            result = dependency.prepare(manifest, destination)

            self.assertEqual(result["revision"], revision)
            self.assertEqual((destination / "tss").read_text(), "#!/bin/sh\necho tss\n")
            checked_out = subprocess.run(
                ["git", "-C", str(destination), "rev-parse", "HEAD"],
                check=True,
                text=True,
                capture_output=True,
            ).stdout.strip()
            self.assertEqual(checked_out, revision)

    def test_rejects_a_manifest_without_an_immutable_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / "dependency.json"
            manifest.write_text(
                json.dumps(
                    {
                        "name": "tss",
                        "repository": "https://example.invalid/tss.git",
                        "revision": "main",
                        "entrypoint": "tss",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "40-character"):
                dependency.load_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
