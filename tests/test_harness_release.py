from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts/harness-release.py"
SPEC = importlib.util.spec_from_file_location("harness_release", MODULE_PATH)
assert SPEC and SPEC.loader
harness_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness_release)


class HarnessReleaseTests(unittest.TestCase):
    @staticmethod
    def make_installer(home: Path, release_id: str, exit_status: int) -> Path:
        source = home / "releases" / release_id / "source"
        source.mkdir(parents=True)
        installer = source / "install.sh"
        installer.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$*\" > {str(source / 'args.log')!r}\n"
            f"exit {exit_status}\n",
            encoding="utf-8",
        )
        installer.chmod(0o755)
        return source

    def test_content_id_is_stable_and_changes_with_payload(self) -> None:
        first = harness_release.content_id(REPO_ROOT)
        second = harness_release.content_id(REPO_ROOT)
        self.assertEqual(first, second)

        with tempfile.TemporaryDirectory() as temp:
            copy = Path(temp) / "source"
            copy.mkdir()
            for relative in harness_release.PAYLOAD:
                source = REPO_ROOT / relative
                destination = copy / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    import shutil

                    shutil.copytree(source, destination)
                else:
                    destination.write_bytes(source.read_bytes())
            target = copy / "README.md"
            target.write_text(target.read_text() + "\ntest change\n")
            self.assertNotEqual(first, harness_release.content_id(copy))

    def test_register_reuses_release_and_switches_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = root / "staged"
            home = root / "home"
            release_id = harness_release.stage_release(REPO_ROOT, staged)

            self.assertEqual(
                harness_release.register_release(staged, home),
                release_id,
            )
            self.assertEqual(harness_release.current_release(home), release_id)
            self.assertEqual(len(harness_release.list_releases(home)), 1)

            harness_release.register_release(staged, home)
            self.assertEqual(len(harness_release.list_releases(home)), 1)
            self.assertEqual(
                (home / "current").resolve(),
                (home / "releases" / release_id).resolve(),
            )

    def test_release_contains_resolved_external_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            resolved = root / "resolved"
            skill = resolved / "unslop"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("upstream skill\n", encoding="utf-8")
            staged = root / "staged"

            first_id = harness_release.stage_release(REPO_ROOT, staged, resolved)
            self.assertEqual(
                (staged / "source/.resolved-external-skills/unslop/SKILL.md").read_text(),
                "upstream skill\n",
            )

            (skill / "SKILL.md").write_text("new upstream skill\n", encoding="utf-8")
            self.assertNotEqual(
                first_id,
                harness_release.content_id(REPO_ROOT, resolved),
            )

    def test_rollback_switches_only_after_successful_install(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            first_id = "1111111111111111"
            second_id = "2222222222222222"
            broken_id = "3333333333333333"
            self.make_installer(home, first_id, 0)
            second = self.make_installer(home, second_id, 0)
            self.make_installer(home, broken_id, 7)
            harness_release.switch_current(home, first_id)

            harness_release.rollback(home, second_id)
            self.assertEqual(harness_release.current_release(home), second_id)
            self.assertEqual(
                (second / "args.log").read_text().strip(),
                "--update --no-release",
            )

            with self.assertRaises(subprocess.CalledProcessError):
                harness_release.rollback(home, broken_id)
            self.assertEqual(harness_release.current_release(home), second_id)

            with self.assertRaisesRegex(ValueError, "invalid release ID"):
                harness_release.rollback(home, "../outside")


if __name__ == "__main__":
    unittest.main()
