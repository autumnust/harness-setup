from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "external-skills.py"
SPEC = importlib.util.spec_from_file_location("external_skills", MODULE_PATH)
assert SPEC and SPEC.loader
external_skills = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(external_skills)


class ExternalSkillTests(unittest.TestCase):
    @staticmethod
    def commit(repository: Path, message: str) -> str:
        subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                message,
            ],
            check=True,
        )
        return subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()

    def make_repository(self, root: Path) -> tuple[Path, str]:
        repository = root / "upstream"
        repository.mkdir()
        subprocess.run(
            ["git", "-C", str(repository), "init", "--quiet", "-b", "main"],
            check=True,
        )
        skill = repository / "pstack/skills/unslop"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: unslop\ndescription: Test prose cleanup.\n---\n\n# Unslop\n\nVersion one.\n",
            encoding="utf-8",
        )
        (repository / "pstack/LICENSE").write_text(
            "MIT test license\n", encoding="utf-8"
        )
        return repository, self.commit(repository, "initial skill")

    @staticmethod
    def entry(repository: Path, revision: str, content_hash: str) -> dict[str, str]:
        return {
            "name": "unslop",
            "repository": str(repository),
            "tracking_ref": "refs/heads/main",
            "revision": revision,
            "source_path": "pstack/skills/unslop",
            "license_path": "pstack/LICENSE",
            "content_sha256": content_hash,
        }

    def write_manifest(
        self, path: Path, repository: Path, revision: str
    ) -> dict[str, str]:
        entry = self.entry(repository, revision, "0" * 64)
        with tempfile.TemporaryDirectory() as temp:
            calculated = external_skills.materialize_skill(
                entry, Path(temp) / "unslop", verify_hash=False
            )
        entry["content_sha256"] = calculated
        path.write_text(
            json.dumps({"schema_version": 1, "skills": [entry]}, indent=2) + "\n",
            encoding="utf-8",
        )
        return entry

    def test_materializes_the_exact_revision_and_license(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository, revision = self.make_repository(root)
            manifest = root / "external-skills.json"
            self.write_manifest(manifest, repository, revision)

            skill_file = repository / "pstack/skills/unslop/SKILL.md"
            skill_file.write_text(skill_file.read_text() + "Version two.\n")
            self.commit(repository, "newer skill")

            resolved = root / "resolved"
            external_skills.materialize_manifest(manifest, resolved)

            self.assertIn("Version one.", (resolved / "unslop/SKILL.md").read_text())
            self.assertNotIn("Version two.", (resolved / "unslop/SKILL.md").read_text())
            self.assertEqual(
                (resolved / "unslop/LICENSE.upstream").read_text(),
                "MIT test license\n",
            )
            external_skills.verify_resolved(manifest, resolved)

    def test_rejects_modified_resolved_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository, revision = self.make_repository(root)
            manifest = root / "external-skills.json"
            self.write_manifest(manifest, repository, revision)
            resolved = root / "resolved"
            external_skills.materialize_manifest(manifest, resolved)
            skill_file = resolved / "unslop/SKILL.md"
            skill_file.write_text(skill_file.read_text() + "changed after resolution\n")

            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                external_skills.verify_resolved(manifest, resolved)

    def test_refresh_ignores_unrelated_commits_then_updates_changed_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository, revision = self.make_repository(root)
            manifest = root / "external-skills.json"
            original = self.write_manifest(manifest, repository, revision)

            (repository / "README.md").write_text("unrelated\n", encoding="utf-8")
            self.commit(repository, "unrelated change")
            self.assertEqual(external_skills.refresh_lock(manifest, write=True), 0)
            self.assertEqual(
                json.loads(manifest.read_text())["skills"][0]["revision"],
                original["revision"],
            )

            skill_file = repository / "pstack/skills/unslop/SKILL.md"
            skill_file.write_text(skill_file.read_text() + "Upstream change.\n")
            changed_revision = self.commit(repository, "update skill")
            report = root / "report.md"
            self.assertEqual(
                external_skills.refresh_lock(manifest, write=True, report=report), 1
            )
            updated = json.loads(manifest.read_text())["skills"][0]
            self.assertEqual(updated["revision"], changed_revision)
            self.assertNotEqual(updated["content_sha256"], original["content_sha256"])
            self.assertIn("unslop", report.read_text())

            resolved = root / "updated"
            external_skills.materialize_manifest(manifest, resolved)
            self.assertIn("Upstream change.", (resolved / "unslop/SKILL.md").read_text())

    def test_adds_and_materializes_a_skill_from_another_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository, revision = self.make_repository(root)
            manifest = root / "external-skills.json"
            manifest.write_text(
                json.dumps({"schema_version": 1, "skills": []}) + "\n",
                encoding="utf-8",
            )

            other_repository = root / "other-upstream"
            other_repository.mkdir()
            subprocess.run(
                ["git", "-C", str(other_repository), "init", "--quiet", "-b", "main"],
                check=True,
            )
            other_skill = other_repository / "skills/plain-language"
            other_skill.mkdir(parents=True)
            (other_skill / "SKILL.md").write_text(
                "---\nname: plain-language\ndescription: Prefer plain language.\n---\n\n# Plain language\n",
                encoding="utf-8",
            )
            (other_repository / "LICENSE").write_text(
                "Apache test license\n", encoding="utf-8"
            )
            other_revision = self.commit(other_repository, "add plain-language skill")

            added = external_skills.add_skill(
                manifest,
                "plain-language",
                str(other_repository),
                "refs/heads/main",
                "skills/plain-language",
                "LICENSE",
            )
            external_skills.add_skill(
                manifest,
                "unslop",
                str(repository),
                "refs/heads/main",
                "pstack/skills/unslop",
                "pstack/LICENSE",
            )

            self.assertEqual(added["revision"], other_revision)
            self.assertEqual(
                external_skills.load_manifest(manifest)["skills"][1]["revision"],
                revision,
            )
            locked = external_skills.load_manifest(manifest)["skills"]
            self.assertEqual([skill["name"] for skill in locked], ["plain-language", "unslop"])
            resolved = root / "resolved"
            external_skills.materialize_manifest(manifest, resolved)
            self.assertTrue((resolved / "plain-language/SKILL.md").is_file())
            self.assertTrue((resolved / "unslop/SKILL.md").is_file())
            self.assertEqual(
                (resolved / "plain-language/LICENSE.upstream").read_text(),
                "Apache test license\n",
            )

            with self.assertRaisesRegex(ValueError, "already exists"):
                external_skills.add_skill(
                    manifest,
                    "plain-language",
                    str(other_repository),
                    "refs/heads/main",
                    "skills/plain-language",
                    "LICENSE",
                )

    def test_rejects_a_moving_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository, _ = self.make_repository(root)
            manifest = root / "external-skills.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "skills": [self.entry(repository, "main", "0" * 64)],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "40-character"):
                external_skills.load_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
