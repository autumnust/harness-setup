from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BROADCAST = REPO_ROOT / ".claude/skills/broadcast-harness/scripts/broadcast.sh"


@unittest.skipUnless(shutil.which("rsync"), "rsync is required")
class BroadcastHarnessTests(unittest.TestCase):
    def test_selected_profile_transfers_without_replacing_remote_local_profiles(self) -> None:
        rules = subprocess.run(
            [str(BROADCAST), "--print-rsync-rules", "--instance", "selected"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.splitlines()

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            destination = root / "destination"
            (source / "instances/selected.local/agent-skills/private").mkdir(parents=True)
            (source / "instances/selected.local.md").write_text("selected instructions\n")
            (source / "instances/selected.local/agent-skills/private/SKILL.md").write_text(
                "selected skill\n"
            )
            (source / "instances/other.local.md").write_text("do not transfer\n")
            (source / "instances/portable.md").write_text("do not transfer\n")
            (source / ".resolved-external-skills/unslop").mkdir(parents=True)
            (source / ".resolved-external-skills/unslop/SKILL.md").write_text(
                "resolved external skill\n"
            )
            (destination / "instances").mkdir(parents=True)
            remote_profile = destination / "instances/aws-bench.local.md"
            remote_profile.write_text("remote-only instructions\n")

            subprocess.run(
                ["rsync", "-a", "--delete", *rules, f"{source}/", f"{destination}/"],
                check=True,
            )

            self.assertEqual(remote_profile.read_text(), "remote-only instructions\n")
            self.assertEqual(
                (destination / "instances/selected.local.md").read_text(), "selected instructions\n"
            )
            self.assertEqual(
                (destination / "instances/selected.local/agent-skills/private/SKILL.md").read_text(),
                "selected skill\n",
            )
            self.assertFalse((destination / "instances/other.local.md").exists())
            self.assertFalse((destination / "instances/portable.md").exists())
            self.assertEqual(
                (destination / ".resolved-external-skills/unslop/SKILL.md").read_text(),
                "resolved external skill\n",
            )


if __name__ == "__main__":
    unittest.main()
