"""Execute canonical workflow scripts; replace only hosted Action/API boundaries.

These tests are not OIDC, GitHub artifact, or GitHub rerun runtime evidence.
Run: python -m unittest discover -s .github/tests -v
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / '.github/workflows/reviewer-summary.yml'
WORKFLOW_BYTES = WORKFLOW_PATH.read_bytes()
WORKFLOW = yaml.load(WORKFLOW_BYTES, Loader=yaml.BaseLoader)
SUMMARY = WORKFLOW['jobs']['summary']['steps']
PUBLISH = WORKFLOW['jobs']['publish']['steps'][-1]
RAW = b'{\r\n  "example": "opaque bytes", "spaces": [1, 2]\r\n}\r\n'
DIGEST = hashlib.sha256(RAW).hexdigest()


def step(identity):
    return next(s for s in SUMMARY if s.get('id') == identity)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        (self.path / 'reviewer-summary.json').write_bytes(RAW)
        statement = {'subject': [{'name': 'reviewer-summary.json', 'digest': {'sha256': DIGEST}}]}
        self.bundle(statement)
        self.env = dict(os.environ, EXPECTED_DIGEST=DIGEST, BUNDLE_PATH=str(self.path / 'bundle.json'),
                        ARTIFACT_ID='artifact-1', ATTESTATION_ID='attestation-1',
                        GITHUB_RUN_ID='100', GITHUB_RUN_ATTEMPT='1', GITHUB_SHA='a' * 40,
                        GITHUB_REPOSITORY='owner/station', GITHUB_API_URL='https://api.github.com',
                        GITHUB_OUTPUT=str(self.path / 'outputs'), GH_TOKEN='SECRET',
                        MOCK_STATE=str(self.path / 'state.json'))
        bindir = self.path / 'bin'
        bindir.mkdir()
        mock = ROOT / '.github/tests/mock_curl.py'
        (bindir / 'curl').symlink_to(mock)
        self.env['PATH'] = str(bindir) + os.pathsep + self.env['PATH']

    def bundle(self, statement):
        payload = base64.b64encode(json.dumps(statement).encode()).decode()
        (self.path / 'bundle.json').write_text(json.dumps({'dsseEnvelope': {'payload': payload}}))

    def run_script(self, selected, **env):
        script = selected['run'].replace('${{ github.repository_id }}', '1234')
        result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script],
                                cwd=self.path, env=self.env | env, text=True, capture_output=True)
        self.assertNotIn('SECRET', result.stdout + result.stderr)
        return result

    def publish(self, **env):
        return self.run_script(PUBLISH, **env)

    def state(self):
        return json.loads((self.path / 'state.json').read_text())

    def test_exact_bytes_across_all_local_boundaries(self):
        for selected in [step('produced'), step('integrity'), step('correspondence'), PUBLISH]:
            result = self.run_script(selected)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual((self.path / 'reviewer-summary.json').read_bytes(), RAW)
        self.assertEqual((self.path / 'published-reviewer-summary.json').read_bytes(), RAW)
        self.assertEqual((self.path / 'outputs').read_text(), 'digest=' + DIGEST + '\n')
        state = self.state()
        tree = next(o['payload'] for o in state['objects'].values() if o['kind'] == 'trees')
        self.assertEqual([e['path'] for e in tree['tree']], ['reviewer-summary.json'])
        commit = next(o['payload'] for o in state['objects'].values() if o['kind'] == 'commits')
        self.assertEqual(commit['parents'], [])
        self.assertEqual(set(state['refs']), {'refs/tags/shoal-summary-1234-100-1'})

    def test_missing_generation(self):
        (self.path / 'reviewer-summary.json').unlink()
        self.assertNotEqual(self.run_script(step('produced')).returncode, 0)
        self.assertFalse((self.path / 'outputs').exists())
        self.assertNotEqual(self.publish().returncode, 0)
        self.assertFalse((self.path / 'state.json').exists())

    def test_changed_summary_after_generation_rejected(self):
        (self.path / 'reviewer-summary.json').write_bytes(RAW + b' ')
        self.assertNotEqual(self.run_script(step('integrity')).returncode, 0)

    def test_wrong_attested_digest_rejected(self):
        self.bundle({'subject': [{'name': 'reviewer-summary.json', 'digest': {'sha256': '0' * 64}}]})
        self.assertNotEqual(self.run_script(step('integrity')).returncode, 0)

    def test_wrong_subject_name_multiple_subjects_and_malformed_bundle(self):
        for subjects in [[], [{'name': 'other', 'digest': {'sha256': DIGEST}}],
                         [{'name': 'reviewer-summary.json', 'digest': {'sha256': DIGEST}}] * 2]:
            with self.subTest(subjects=subjects):
                self.bundle({'subject': subjects})
                self.assertNotEqual(self.run_script(step('integrity')).returncode, 0)
        (self.path / 'bundle.json').write_text('{}')
        self.assertNotEqual(self.run_script(step('integrity')).returncode, 0)

    def test_changed_archival_source_rejected(self):
        (self.path / 'reviewer-summary.json').write_bytes(RAW + b' ')
        self.assertNotEqual(self.run_script(step('correspondence')).returncode, 0)

    def test_missing_artifact_or_attestation_identity_rejected(self):
        for key in ['ARTIFACT_ID', 'ATTESTATION_ID']:
            with self.subTest(key=key):
                self.assertNotEqual(self.run_script(step('correspondence'), **{key: ''}).returncode, 0)

    def test_changed_downloaded_archive_rejected_before_publication(self):
        (self.path / 'reviewer-summary.json').write_bytes(RAW + b' ')
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('archival-byte-integrity', result.stdout)
        self.assertFalse((self.path / 'state.json').exists())

    def test_transport_creation_failures(self):
        for kind in ['blobs', 'trees', 'commits', 'refs']:
            with self.subTest(kind=kind):
                (self.path / 'state.json').unlink(missing_ok=True)
                result = self.publish(MOCK_FAILURE=kind)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('creation failed (HTTP 503)', result.stderr)
                self.assertEqual(self.state()['refs'], {})

    def test_collision_preserves_existing_bytes(self):
        self.assertEqual(self.publish().returncode, 0)
        prior = self.state()['refs'].copy()
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('identity collision', result.stderr)
        self.assertEqual(self.state()['refs'], prior)

    def test_anonymous_retrieval_failure_and_mismatch_do_not_claim_success(self):
        for mode, stage in [('retrieval', 'anonymous-transport-retrieval'),
                            ('mismatch', 'published-byte-mismatch')]:
            with self.subTest(mode=mode):
                (self.path / 'state.json').unlink(missing_ok=True)
                result = self.publish(MOCK_FAILURE=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(stage, result.stdout)
                self.assertNotIn('Transport SHA-256:', result.stdout)
                self.assertEqual(len(self.state()['refs']), 1)

    def test_new_failed_attempt_preserves_prior_success_then_recovery(self):
        self.assertEqual(self.publish().returncode, 0)
        prior = self.state()['refs'].copy()
        prior_objects = self.state()['objects'].copy()
        result = self.publish(GITHUB_RUN_ATTEMPT='2', MOCK_FAILURE='retrieval')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.publish(GITHUB_RUN_ATTEMPT='3', ARTIFACT_ID='artifact-3',
                                     ATTESTATION_ID='attestation-3').returncode, 0)
        state = self.state()
        for ref, sha in prior.items():
            self.assertEqual(state['refs'][ref], sha)
        for sha, obj in prior_objects.items():
            self.assertEqual(state['objects'][sha], obj)
        self.assertEqual(set(state['refs']), {f'refs/tags/shoal-summary-1234-100-{n}' for n in [1, 2, 3]})
        # Re-read the older immutable locator through the same anonymous boundary.
        subprocess.run(['curl', '--output', 'old.json',
                        'https://raw.githubusercontent.com/owner/station/shoal-summary-1234-100-1/reviewer-summary.json'],
                       cwd=self.path, env=self.env, check=True)
        self.assertEqual((self.path / 'old.json').read_bytes(), RAW)

    def test_nonsemantic_byte_change_is_new_identity(self):
        for changed in [WORKFLOW_BYTES + b'\n# comment\n', WORKFLOW_BYTES.replace(b'\n', b'\r\n'),
                        b'\xef\xbb\xbf' + WORKFLOW_BYTES]:
            self.assertNotEqual(hashlib.sha256(changed).digest(), hashlib.sha256(WORKFLOW_BYTES).digest())

    def test_workflow_gates_and_authority(self):
        self.assertEqual(WORKFLOW['permissions'], {})
        self.assertEqual(set(WORKFLOW['on']), {'schedule', 'workflow_dispatch'})
        self.assertEqual(WORKFLOW['jobs']['publish']['needs'], 'summary')
        self.assertNotIn('if', WORKFLOW['jobs']['publish'])
        self.assertEqual(WORKFLOW['jobs']['summary']['outputs']['digest'], '${{ steps.produced.outputs.digest }}')
        order = [s.get('id') for s in SUMMARY if s.get('id')]
        self.assertEqual(order, ['compute', 'produced', 'attest', 'integrity', 'artifact', 'correspondence'])
        for job in WORKFLOW['jobs'].values():
            for selected in job['steps']:
                self.assertNotIn('continue-on-error', selected)
                if 'uses' in selected:
                    self.assertRegex(selected['uses'], r'@([0-9a-f]{40})$')
                if selected.get('id'):
                    self.assertNotIn('if', selected)
        self.assertEqual(step('attest')['with'], {'subject-path': 'reviewer-summary.json'})
        self.assertEqual(step('artifact')['with']['if-no-files-found'], 'error')
        self.assertIn('${{ github.run_attempt }}', step('artifact')['with']['name'])
        self.assertEqual(WORKFLOW['jobs']['summary']['permissions'],
                         {'contents': 'read', 'issues': 'read', 'id-token': 'write', 'attestations': 'write'})
        self.assertEqual(WORKFLOW['jobs']['publish']['permissions'], {'contents': 'write'})
        self.assertNotRegex(PUBLISH['run'], r'\b(PATCH|PUT|DELETE)\b|refs/heads/|--force')
        self.assertNotIn('secrets.', WORKFLOW_BYTES.decode())
        self.assertNotIn('checkout', WORKFLOW_BYTES.decode())

    def test_failed_stage_diagnostics_remain_failed(self):
        diagnostic = SUMMARY[-1]
        self.assertEqual(diagnostic['if'], '${{ failure() }}')
        for failed in ['COMPUTE', 'PRODUCED', 'ATTEST', 'INTEGRITY', 'ARTIFACT', 'CORRESPONDENCE']:
            with self.subTest(failed=failed):
                outcomes = {k: 'success' for k in diagnostic['env']}
                outcomes[failed] = 'failure'
                result = self.run_script(diagnostic, **outcomes)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('failure', result.stdout)


if __name__ == '__main__':
    unittest.main()
