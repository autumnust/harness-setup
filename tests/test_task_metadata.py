from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'scripts/task-catalog.py'
TASK = ROOT / 'scripts/agent-task.py'
WORKSPACE = ROOT / 'scripts/agent-workspace.py'
CHECKER = ROOT / 'agent-skills/execution-notes/scripts/check_work_structure.py'


class TaskMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.folder = self.root / 'task'
        self.folder.mkdir()
        self.harness = self.root / 'harness'
        self.env = {**os.environ, 'AGENT_HARNESS_HOME': str(self.harness)}

    def run_cli(self, script, *args):
        return subprocess.run([sys.executable, str(script), *map(str, args)],
                              env=self.env, capture_output=True, text=True)

    def write(self, metadata):
        text = '---\n' + metadata + '\n---\n\n# Existing work\n\nPreserve this content.\n'
        (self.folder / 'README.md').write_text(text)
        return text

    def validate(self):
        result = self.run_cli(TASK, 'validate', '--task-dir', self.folder, '--format', 'json')
        return result.returncode, json.loads(result.stdout)

    def test_validation_is_read_only_and_does_not_create_catalog(self):
        content = self.write('agent_task: 1\nid: existing-task\nstatus: paused')
        code, payload = self.validate()
        self.assertEqual(code, 0, payload)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['record']['id'], 'existing-task')
        self.assertEqual((self.folder / 'README.md').read_text(), content)
        self.assertFalse(self.harness.exists())

    def test_rejects_missing_or_invalid_metadata_with_repair_instructions(self):
        cases = [
            '# Ordinary research README\n',
            '---\nagent_task: 1\nid: one\nstatus: active\n',
            '---\nid: one\nstatus: active\n---\n',
            '---\nagent_task: 2\nid: one\nstatus: active\n---\n',
            '---\nagent_task: 1\nworkspace_task: 1\nid: one\nstatus: active\n---\n',
            '---\nagent_task: 1\nstatus: active\n---\n',
            '---\nagent_task: 1\nid: " "\nstatus: active\n---\n',
            '---\nagent_task: 1\nid: [TASK_ID]\nstatus: active\n---\n',
            '---\nagent_task: 1\nid: one\n---\n',
            '---\nagent_task: 1\nid: \"unterminated\nstatus: active\n---\n',
            '---\nworkspace_task: 1\nid: one\nstatus: active\nworkspace_id: \" \"\n---\n',
            '---\nagent_task: 1\nid: one\nstatus: finished\n---\n',
            '---\nagent_task: 1\nid: one\nid: two\nstatus: active\n---\n',
            '---\nworkspace_task: 1\nid: one\nstatus: active\n---\n',
        ]
        for content in cases:
            with self.subTest(content=content):
                (self.folder / 'README.md').write_text(content)
                code, payload = self.validate()
                self.assertEqual(code, 1, payload)
                self.assertFalse(payload['ok'])
                self.assertTrue(payload['errors'])
                self.assertIn('Do not rerun init', payload['repair'])
                self.assertEqual((self.folder / 'README.md').read_text(), content)
                self.assertFalse(self.harness.exists())

    def test_workspace_reference_and_mismatch(self):
        workspace = self.root / 'workspace'
        workspace.mkdir()
        (workspace / 'workspace.yaml').write_text('schema_version: 2\nworkspace:\n  id: workspace-one\n  name: Example\nrepositories: []\n')
        metadata = 'workspace_task: 1\nid: existing-task\nstatus: active\nworkspace_path: ../workspace'
        self.write(metadata)
        code, payload = self.validate()
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload['record']['workspace_id'], 'workspace-one')
        self.write(metadata + '\nworkspace_id: wrong-workspace')
        code, payload = self.validate()
        self.assertEqual(code, 1, payload)
        self.assertIn('does not match', payload['error'])

    def test_metadata_check_does_not_require_local_workspace_when_id_is_known(self):
        self.write('workspace_task: 1\nid: existing-task\nstatus: unknown\nworkspace_id: portable-workspace')
        code, payload = self.validate()
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload['record']['status'], 'unknown')

    def test_layout_check_requires_identity_only_when_task_is_selected(self):
        (self.folder / 'README.md').write_text('# Existing notes\n')
        (self.folder / 'progress.html').write_text('<h1>Progress</h1>')
        # A document folder has no task identity requirement.
        plain = self.run_cli(CHECKER, self.folder, '--mode', 'full', '--json')
        self.assertEqual(plain.returncode, 0, plain.stdout + plain.stderr)
        checked = self.run_cli(CHECKER, self.folder, '--mode', 'full', '--task', '--json')
        self.assertEqual(checked.returncode, 1)
        findings = json.loads(checked.stdout)
        self.assertEqual([f['rule'] for f in findings], ['T1'])
        self.write('agent_task: 1\nid: repaired-existing-id\nstatus: unknown')
        checked = self.run_cli(CHECKER, self.folder, '--mode', 'full', '--task', '--json')
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertFalse(self.harness.exists())

    def test_installed_commands_and_both_creation_paths_validate(self):
        (self.harness / 'bin').mkdir(parents=True)
        (self.harness / 'current').mkdir()
        (self.harness / 'current/source').symlink_to(ROOT, target_is_directory=True)
        for name in ['agent-task', 'agent-workspace', 'task-catalog']:
            shutil.copy2(ROOT / 'scripts' / (name + '.py'), self.harness / 'bin' / name)
        task_cli = self.harness / 'bin/agent-task'
        created = self.run_cli(task_cli, 'init', '--name', 'created', '--destination', self.root, '--format', 'json')
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        workspace = self.root / 'workspace'
        workspace.mkdir()
        (workspace / 'workspace.yaml').write_text('schema_version: 2\nworkspace:\n  id: workspace-one\n  name: Example\nrepositories: []\n')
        created = self.run_cli(self.harness / 'bin/agent-workspace', 'start-task', '--workspace', workspace,
                               '--name', 'member', '--execution-root', self.root, '--format', 'json')
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        database = self.harness / 'state/task-catalog/catalog.sqlite3'
        before = database.read_bytes()
        for name, kind in [('created', 'agent-task'), ('member', 'workspace-task')]:
            result = self.run_cli(task_cli, 'validate', '--task-dir', self.root / name, '--format', 'json')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['record']['kind'], kind)
        self.assertEqual(database.read_bytes(), before)
        # The copied skill checker resolves the deployed catalog command.
        installed = self.harness / 'skills/execution-notes/scripts/check_work_structure.py'
        installed.parent.mkdir(parents=True)
        shutil.copy2(CHECKER, installed)
        self.write('agent_task: 1\nid: existing-task\nstatus: done')
        (self.folder / 'progress.html').write_text('<h1>Progress</h1>')
        result = self.run_cli(installed, self.folder, '--mode', 'full', '--task', '--json')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
