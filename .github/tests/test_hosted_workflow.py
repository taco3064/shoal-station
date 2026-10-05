"""Actual inline scripts + mocked Hosted Action/broker boundaries.

GitHub scheduler, live OIDC, Copilot and artifact/attestation proof remain hosted gates.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
CALLER_BYTES = (ROOT / '.github/workflows/reviewer-summary.yml').read_bytes()
CALLER = yaml.load(CALLER_BYTES, Loader=yaml.BaseLoader)
HOSTED_BYTES = (ROOT / '.github/workflows/hosted-review.yml').read_bytes()
HOSTED = yaml.load(HOSTED_BYTES, Loader=yaml.BaseLoader)
STEPS = {s['id']: s for s in HOSTED['jobs']['hosted']['steps']}


def run_mode(value):
    selected = CALLER['jobs']['mode']['steps'][0]
    with tempfile.TemporaryDirectory() as path:
        output = Path(path) / 'outputs'
        result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', selected['run']],
                                env={'AUTOMATED_REVIEW': value, 'GITHUB_OUTPUT': str(output)},
                                text=True, capture_output=True, check=True)
        return output.read_text().strip().split('=', 1)[1], result.stdout + result.stderr


def run_hosted(mode, summary_result='success', **faults):
    result = subprocess.run(['node', str(ROOT / '.github/tests/hosted_harness.mjs')],
                            input=json.dumps({'caller': CALLER, 'hosted': HOSTED, 'mode': mode, 'faults': faults,
                                              'summaryResult': summary_result}),
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


class HostedWorkflowTests(unittest.TestCase):
    def test_exact_modes_and_untrusted_configuration(self):
        for value, expected in [('', 'none'), ('none', 'none'), ('review', 'review'),
                                ('re-review', 're-review'), ('all', 'all'), ('ALL', 'none'),
                                (' review', 'none'), ('review\nall', 'none'),
                                ('$(touch /tmp/should-never-run)', 'none')]:
            with self.subTest(value=value):
                actual, log = run_mode(value)
                self.assertEqual(actual, expected)
                if value and value not in ['none', 'review', 're-review', 'all']:
                    self.assertIn('Invalid SHOAL_AUTOMATED_REVIEW', log)
                    self.assertNotIn(value, log)

    def test_modes_route_only_authorized_operations(self):
        for mode, expected in [('review', ['review']), ('re-review', ['re-review']), ('all', ['review', 're-review'])]:
            with self.subTest(mode=mode):
                result = run_hosted(mode)
                self.assertEqual(result['operations'], expected)
                self.assertEqual(result['result']['stop_semantic_work'], 'false')
                self.assertEqual([r['operation'] for r in json.loads(result['result']['result'])['results']], expected)
        for mode in ['none', '', 'invalid']:
            result = run_hosted(mode)
            self.assertEqual(result['operations'], [])
            self.assertEqual(result['calls'], [])

    def test_missing_authority_configuration_never_requests_oidc_or_mutates(self):
        for fault in ['brokerMissing', 'audienceMissing']:
            result = run_hosted('all', **{fault: True})
            self.assertEqual(result['operations'], [])
            self.assertEqual(result['calls'], [])
            self.assertEqual(result['authority']['ready'], 'false')
            self.assertEqual(result['result']['stop_semantic_work'], 'true')

    def test_broker_and_oidc_failure_are_classified_without_raw_diagnostics(self):
        for fault in ['oidc', 'brokerNetwork', 'brokerDenied', 'brokerMalformed', 'brokerOversized']:
            with self.subTest(fault=fault):
                result = run_hosted('all', **{fault: True})
                self.assertEqual(result['operations'], [])
                self.assertEqual(result['authority']['ready'], 'false')
                self.assertNotIn('FAIL', result['result']['result'])

    def test_authority_response_binding_and_expiry(self):
        for patch in [{'repositoryId': 'other'}, {'reviewerId': 'other'}, {'formatVersion': 2},
                      {'reviewerToken': 'bad\n::warning::injection'}, {'reviewerToken': ''},
                      {'expiresAt': '2000-01-01T00:00:00Z'}, {'expiresAt': '2999-01-01T00:00:00Z'},
                      {'expiresAt': 'invalid'}]:
            with self.subTest(patch=patch):
                result = run_hosted('review', brokerResult=patch)
                self.assertEqual(result['operations'], [])
                self.assertEqual(result['authority']['code'], 'BROKER_RESULT_REFUSED')

    def test_broker_request_is_bound_and_redirects_forbidden(self):
        result = run_hosted('review')
        self.assertEqual(result['calls'][0], {'kind': 'oidc', 'audience': 'shoal-hosted-review'})
        broker = result['calls'][1]
        self.assertEqual(broker['redirect'], 'error')
        self.assertEqual(broker['body'], {'formatVersion': 1, 'repositoryId': '17', 'reviewerId': '42',
                         'workflowRef': 'owner/station/.github/workflows/reviewer-summary.yml@refs/heads/main',
                         'workflowSha': 'a' * 40, 'runId': '1234', 'runAttempt': '1'})
        self.assertEqual(result['calls'][2]['persistCredentials'], 'false')
        for url in ['http://broker.example/', 'https://user:pass@broker.example/',
                    'https://broker.example/?token=secret', 'https://broker.example/#fragment']:
            refused = run_hosted('all', brokerUrl=url)
            self.assertEqual(refused['operations'], [])
            self.assertEqual(refused['calls'], [])

    def test_all_stops_on_quota_authority_refusal_and_result_faults(self):
        for failure in ['COPILOT_BUDGET_UNAVAILABLE', 'COPILOT_ENTITLEMENT_UNAVAILABLE',
                        'REVIEWER_AUTHORITY_UNAVAILABLE', 'RUNTIME_COMPATIBILITY_REFUSED']:
            result = run_hosted('all', review={'status': 'REFUSED', 'failures': [failure], 'stop': True})
            self.assertEqual(result['operations'], ['review'])
            self.assertEqual(result['result']['stop_semantic_work'], 'true')
            self.assertNotIn('FAIL"', result['result']['result'])
        for fault in [{'malformed': True}, {'infrastructure': True}, {'stop': True},
                      {'outputStop': 'true'}, {'outputStatus': 'PARTIAL'},
                      {'status': 'REFUSED'}, {'failures': ['COPILOT_PROCESS_UNAVAILABLE']}]:
            with self.subTest(fault=fault):
                result = run_hosted('all', review=fault)
                self.assertEqual(result['operations'], ['review'])
                self.assertEqual(result['result']['stop_semantic_work'], 'true')

    def test_checkout_failure_never_invokes_hosted_runtime(self):
        result = run_hosted('all', checkout=True)
        self.assertEqual(result['operations'], [])
        self.assertIn('STATION_CHECKOUT_UNAVAILABLE', result['result']['result'])

    def test_summary_order_and_failure_isolation(self):
        summary = CALLER['jobs']['summary']
        self.assertEqual(summary['needs'], ['mode', 'hosted'])
        self.assertEqual(summary['if'], '${{ always() }}')
        self.assertEqual(CALLER['jobs']['publish']['needs'], 'summary')
        self.assertEqual(CALLER['jobs']['publish']['if'], "${{ always() && needs.summary.result == 'success' }}")
        self.assertEqual(HOSTED['jobs']['hosted']['continue-on-error'], 'true')
        for identity in ['checkout', 'review', 're_review']:
            self.assertEqual(STEPS[identity]['continue-on-error'], 'true')
        self.assertEqual(STEPS['result']['if'], '${{ always() }}')

    def test_summary_byte_chain_after_disabled_or_refused_semantic_work(self):
        from test_summary_workflow import WorkflowTests, step, PUBLISH
        cases = [('none', {}), ('all', {'brokerMissing': True}),
                 ('all', {'review': {'status': 'REFUSED', 'stop': True, 'failures': ['COPILOT_BUDGET_UNAVAILABLE']}}),
                 ('all', {'review': {'infrastructure': True}})]
        for mode, faults in cases:
            with self.subTest(mode=mode, faults=faults):
                result = run_hosted(mode, **faults)
                self.assertTrue(result['publishAllowed'])
                self.assertEqual(result['result']['stop_semantic_work'], 'true')
                summary = WorkflowTests()
                summary.setUp()
                try:
                    for selected in [step('produced'), step('integrity'), step('correspondence'), PUBLISH]:
                        completed = summary.run_script(selected)
                        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                finally:
                    summary.doCleanups()

    def test_publication_status_guard_requires_successful_summary(self):
        # Evaluate the actual condition. Hosted scheduler behavior is a separate live gate.
        for status in ['failure', 'cancelled', 'skipped']:
            result = run_hosted('none', summary_result=status)
            self.assertFalse(result['publishAllowed'])
        for mode, faults in [('none', {}), ('all', {'review': {'infrastructure': True}})]:
            result = run_hosted(mode, summary_result='success', **faults)
            self.assertTrue(result['publishAllowed'])

    def test_canonical_schedule_and_repository_lock(self):
        self.assertEqual(set(CALLER['on']), {'schedule', 'workflow_dispatch'})
        self.assertEqual(CALLER['on']['schedule'], [{'cron': '25 3 * * 0'}])
        self.assertEqual(set(HOSTED['on']), {'workflow_call'})
        self.assertEqual(CALLER['concurrency'], {'group': 'shoal-station-${{ github.repository_id }}',
                         'cancel-in-progress': 'false', 'queue': 'max'})
        self.assertNotIn('concurrency', HOSTED)
        self.assertEqual(CALLER['jobs']['hosted']['uses'], './.github/workflows/hosted-review.yml')

    def test_immutable_pin_cycle_is_broken(self):
        self.assertNotIn(b'shoal-action/hosted-review@', CALLER_BYTES)
        for step in STEPS.values():
            self.assertRegex(step['uses'], r'@[0-9a-f]{40}$')
        review_pin = STEPS['review']['uses']
        self.assertEqual(review_pin, STEPS['re_review']['uses'])
        replaced = HOSTED_BYTES.replace(review_pin.encode(), b'taco3064/shoal-action/hosted-review@' + b'f' * 40)
        self.assertNotEqual(hashlib.sha256(HOSTED_BYTES).digest(), hashlib.sha256(replaced).digest())
        self.assertEqual(CALLER_BYTES, (ROOT / '.github/workflows/reviewer-summary.yml').read_bytes())

    def test_read_role_endpoint_permissions_at_both_workflow_boundaries(self):
        # hosted-review/github.go reads Git contents/refs and Issue/comment endpoints.
        # Repository metadata and public user enumeration require no extra scope.
        required = {'contents': 'read', 'issues': 'read'}
        for boundary in [CALLER, HOSTED]:
            permissions = boundary['jobs']['hosted']['permissions']
            for scope, level in required.items():
                with self.subTest(boundary=boundary['name'], scope=scope):
                    self.assertEqual(permissions.get(scope), level)
                    # Removing either permission must invalidate this contract.
                    missing = dict(permissions)
                    missing.pop(scope)
                    self.assertFalse(all(missing.get(key) == value
                                         for key, value in required.items()))
            self.assertNotEqual(permissions.get('contents'), 'write')
            self.assertNotEqual(permissions.get('issues'), 'write')

    def test_authority_roles_and_no_credential_persistence(self):
        expected = {'contents': 'read', 'issues': 'read', 'copilot-requests': 'write', 'id-token': 'write'}
        self.assertEqual(CALLER['jobs']['hosted']['permissions'], expected)
        self.assertEqual(HOSTED['jobs']['hosted']['permissions'], expected)
        for identity in ['review', 're_review']:
            inputs = STEPS[identity]['with']
            for role in ['copilot_token', 'read_token']:
                self.assertEqual(inputs[role], '${{ github.token }}')
            self.assertEqual(inputs['lifecycle_token'], '${{ steps.authority.outputs.lifecycle_token }}')
            self.assertEqual(inputs['reviewer_token'], '${{ steps.authority.outputs.reviewer_token }}')
            self.assertEqual(inputs['max_ai_credits'], '30')
            self.assertEqual(inputs['timeout_seconds'], '180')
        self.assertNotIn('reviewer_token', json.dumps(HOSTED['jobs']['hosted']['outputs']))
        self.assertNotIn('reviewer_token', json.dumps(HOSTED['on']['workflow_call']['outputs']))
        self.assertNotIn('secrets.', HOSTED_BYTES.decode())
        self.assertNotIn('upload-artifact', HOSTED_BYTES.decode())
        self.assertNotIn('writeFile', HOSTED_BYTES.decode())
        self.assertEqual(STEPS['checkout']['with']['persist-credentials'], 'false')

    def test_lifecycle_authority_is_required_and_distinct(self):
        for token in ['', None, 'bad token', 'ghu_SYNTHETIC_PERSONAL_TOKEN']:
            result = run_hosted('all', brokerResult={'lifecycleToken': token})
            self.assertEqual(result['operations'], [])
            self.assertEqual(result['authority']['ready'], 'false')
            self.assertEqual(result['authority']['code'], 'BROKER_RESULT_REFUSED')
        for outputs in [HOSTED['jobs']['hosted']['outputs'], HOSTED['on']['workflow_call']['outputs']]:
            self.assertNotIn('lifecycle_token', json.dumps(outputs))

    def test_managed_surface_and_policy_are_not_rewritten(self):
        # Station does not implement its own migration; gh shoal init owns it.
        text = CALLER_BYTES.decode() + HOSTED_BYTES.decode()
        self.assertNotIn('gh shoal init', text)
        self.assertNotIn('git commit', text)
        self.assertNotIn('git push', text)
        self.assertNotIn('npm', text)
        self.assertNotIn('copilot --', text)
        self.assertNotIn('README.md', HOSTED_BYTES.decode())


if __name__ == '__main__':
    unittest.main()
