"""Shared-client session contracts; fake cloud commands only."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab_session import Session
import lab_runtime
from test_lab_runtime import FakeRunner, ROOT, ACCOUNT


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='arcade-session-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copy(ROOT / 'lab-recipes.json', self.root)
        for folder in ('labs', 'modules'):
            shutil.copytree(ROOT / folder, self.root / folder)
        self.runner = FakeRunner()
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def session(self, alias='00', root=None):
        return Session(self.root, alias, root=root, runner=self.runner)

    def foundation(self):
        session = self.session('07')
        session.perform('prepare', mode='guided')
        session.perform('configure', profile='learner', account_id=ACCOUNT, lab_id='learner',
                        admin_principal_arn=f'arn:aws:iam::{ACCOUNT}:user/learner', allowed_cidr='198.51.100.8/32')
        plan = session.perform('plan')['plan']
        session.perform('apply', approval=f'APPLY {ACCOUNT}', plan_digest=plan['digest'])
        return session

    def test_catalog_costs_and_manual_runbook(self):
        info = self.session('13').describe()
        self.assertEqual(info['roots'], ['workload', 'access'])
        self.assertEqual(info['cleanupOrder'][0]['root'], 'access')
        self.assertGreater(info['costs']['twoHoursUsd'], info['costs']['oneHourUsd'])
        self.assertGreater(info['costs']['sharedHourlyUsd'], 0)
        manual = self.session('02').describe()
        self.assertFalse(manual['supported'])
        self.assertNotIn('apply', manual['capabilities'])
        self.assertTrue(manual['runbookSteps'])
        self.assertFalse(self.runner.calls)

    def test_apply_requires_current_digest_and_preserves_state_when_source_changes(self):
        session = self.session()
        session.perform('prepare', mode='guided')
        plan = session.perform('plan')['plan']
        with self.assertRaisesRegex(ValueError, 'digest|review'):
            session.perform('apply', approval='APPLY LOCAL', plan_digest='wrong')
        path = Path(session.describe()['path'])
        (path / 'main.tf').write_text((path / 'main.tf').read_text() + '\n# learner edit\n')
        self.assertTrue(session.describe()['plan']['stale'])
        with self.assertRaisesRegex(ValueError, 'changed'):
            session.perform('apply', approval='APPLY LOCAL', plan_digest=plan['digest'])
        self.assertFalse(any(call[0][1] == 'apply' for call in self.runner.calls))

    def test_failed_apply_and_destroy_retain_only_inventory_metadata(self):
        session = self.session()
        session.perform('prepare', mode='guided')
        path = Path(session.describe()['path'])
        state = {'version': 4, 'resources': [{'mode': 'managed', 'type': 'terraform_data', 'name': 'service',
                    'instances': [{'index_key': 'api', 'attributes': {'id': 'owned-id', 'arn': 'arn:example:owned', 'secret': 'never-publish'}}]}]}
        (path / 'terraform.tfstate').write_text(json.dumps(state))
        plan = session.perform('plan')['plan']
        self.runner.fail_apply = True
        with self.assertRaises(ValueError):
            session.perform('apply', approval='APPLY LOCAL', plan_digest=plan['digest'])
        first = session.describe()
        self.assertEqual(first['lastOperation']['status'], 'failed')
        self.assertEqual(first['inventory']['resources'][0]['id'], 'owned-id')
        self.assertNotIn('never-publish', json.dumps(first))
        self.runner.fail_apply = False
        plan = session.perform('plan_destroy')['plan']
        self.runner.fail_apply = True
        with self.assertRaises(ValueError):
            session.perform('apply', approval='DESTROY LOCAL', plan_digest=plan['digest'])
        self.assertEqual(session.describe()['inventory']['resources'][0]['id'], 'owned-id')
        self.runner.fail_apply = False
        session.perform('apply', approval='DESTROY LOCAL', plan_digest=plan['digest'])
        (path / 'terraform.tfstate').write_text(json.dumps({'version': 4, 'resources': []}))
        final = session.describe()
        self.assertEqual(final['inventory']['resources'][0]['id'], 'owned-id')
        self.assertEqual(final['inventory']['absence'], 'unknown')

    def test_submit_missing_contract_is_failed_and_edits_make_receipt_stale(self):
        session = self.session()
        session.perform('prepare', mode='guided')
        receipt = session.perform('submit')['repair']
        self.assertEqual(receipt['status'], 'fail')
        self.assertFalse(receipt['stale'])
        path = Path(session.describe()['path'])
        (path / 'main.tf').write_text((path / 'main.tf').read_text() + '\n# repaired source\n')
        self.assertTrue(session.describe()['repair']['stale'])
        unknown = self.session('05')
        unknown.perform('prepare', mode='guided')
        self.assertEqual(unknown.perform('submit')['repair']['status'], 'unknown')

    def test_multi_root_blocks_missing_outputs_and_reverse_cleanup(self):
        self.foundation()
        workload = self.session('09', 'workload')
        workload.perform('prepare', mode='guided')
        with self.assertRaisesRegex(ValueError, 'infrastructure|output'):
            workload.perform('configure', profile='learner', account_id=ACCOUNT)
        infrastructure = self.session('09', '.')
        infrastructure.perform('configure', profile='learner', account_id=ACCOUNT)
        with self.assertRaisesRegex(ValueError, 'workload|dependent'):
            infrastructure.perform('plan_destroy')
        with self.assertRaises(ValueError):
            self.session('09', '../07-eks-foundation')

    def test_multi_root_output_wiring_and_fixed_commands(self):
        self.foundation()
        original = self.runner
        def runner(args, cwd, env, *, capture=False):
            result = original(args, cwd, env, capture=capture)
            if args[0].endswith('terraform') and args[1:3] == ['output', '-json'] and Path(cwd).name in {'09-pod-identity', '10-ebs-storage'}:
                result.stdout = json.dumps({'bucket_name': {'value': 'learner-fixture'}, 'addon_version': {'value': 'v1'},
                                            'csi_role_arn': {'value': f'arn:aws:iam::{ACCOUNT}:role/learner-ebs'}})
            return result
        self.runner = runner
        for alias in ('09', '10'):
            infrastructure = self.session(alias, '.')
            infrastructure.perform('prepare', mode='guided')
            infrastructure.perform('configure', profile='learner', account_id=ACCOUNT)
            plan = infrastructure.perform('plan')['plan']
            infrastructure.perform('apply', approval=f'APPLY {ACCOUNT}', plan_digest=plan['digest'])
            workload = self.session(alias, 'workload')
            workload.perform('configure', profile='learner', account_id=ACCOUNT)
            result = workload.perform('plan')
            self.assertEqual(result['plan']['operation'], 'apply')
            self.assertFalse(result['plan']['stale'])
            self.assertTrue(any(call[1] == Path(result['path']) and call[0][1] == 'plan' for call in original.calls))
            if alias == '09':
                fixture = json.loads((Path(result['path']) / 'fixture.yaml').read_text())
                self.assertEqual(fixture['data']['bucket'], 'learner-fixture')
                values = json.loads((Path(result['path']) / lab_runtime.INPUTS).read_text())
                self.assertEqual(values['extra_manifest_paths'], ['fixture.yaml'])
        self.assertFalse(any(call[0][0] in {'bash', 'sh'} for call in original.calls))

    def test_broken_service_fails_even_when_pods_are_ready(self):
        from test_verification import FakeRunner as VerifyRunner, FIXTURES
        self.foundation()
        session = self.session('11-01')
        session.perform('prepare', mode='starter')
        session.perform('configure', profile='learner', account_id=ACCOUNT)
        cloud = VerifyRunner({('eks', 'describe-cluster', '--name', 'learner-arcade'):
                                  FIXTURES[('eks', 'describe-cluster', '--name', 'tfeks-arcade')],
                              ('get', 'endpointslices', '-l', 'kubernetes.io/service-name=app', '-o', 'json'): {'items': []}})
        def runner(args, cwd, env, *, capture=False):
            return cloud.run(args)
        session.runtime.runner = runner
        repair = session.perform('submit')['repair']
        self.assertEqual(repair['status'], 'fail')
        self.assertTrue(any(c['id'] == 'pods' and c['status'] == 'pass' for c in repair['checks']))
        self.assertTrue(any(c['id'] == 'endpoints' and c['status'] == 'fail' for c in repair['checks']))
        cloud.overrides.pop(('get', 'endpointslices', '-l', 'kubernetes.io/service-name=app', '-o', 'json'))
        self.assertEqual(session.perform('submit')['repair']['status'], 'pass')
        self.assertFalse(any(set(call) & {'apply', 'create', 'delete', 'exec', 'patch'} for call in cloud.calls))

    def test_public_access_uses_registered_worker_and_reverses_roots(self):
        self.foundation()
        original = self.runner
        def runner(args, cwd, env, *, capture=False):
            result = original(args, cwd, env, capture=capture)
            if args[0] == 'kubectl' and 'nodes' in args:
                data = json.loads(result.stdout)
                data['items'][0]['spec']['providerID'] = 'aws:///us-west-2a/i-0123456789abcdef0'
                result.stdout = json.dumps(data)
            return result
        self.runner = runner
        workload = self.session('13', 'workload')
        workload.perform('prepare', mode='guided')
        workload.perform('configure', profile='learner', account_id=ACCOUNT)
        plan = workload.perform('plan')['plan']
        workload.perform('apply', approval=f'APPLY {ACCOUNT}', plan_digest=plan['digest'])
        access = self.session('13', 'access')
        result = access.perform('configure', profile='learner', account_id=ACCOUNT, allowed_cidr='198.51.100.8/32')
        values = json.loads((Path(result['path']) / lab_runtime.INPUTS).read_text())
        self.assertEqual(values['node_instance_id'], 'i-0123456789abcdef0')
        self.assertEqual(values['lab_id'], 'learner')
        self.assertFalse(access.perform('plan')['plan']['stale'])
        with self.assertRaisesRegex(ValueError, 'access'):
            workload.perform('plan_destroy')

    def test_real_local_session_submit_and_cli_projection(self):
        terraform = ROOT / '.tools/bin/terraform'
        if not terraform.is_file():
            terraform = shutil.which('terraform')
        if not terraform:
            self.skipTest('Terraform is unavailable')
        session = Session(self.root, '00')
        session.runtime.terraform = str(terraform)
        session.perform('prepare', mode='guided')
        plan = session.perform('plan')['plan']
        session.perform('apply', approval='APPLY LOCAL', plan_digest=plan['digest'])
        repaired = session.perform('submit')
        self.assertEqual(repaired['repair']['status'], 'pass')
        from lab_session import main
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(['status', '00'], project=self.root), 0)
        self.assertEqual(json.loads(output.getvalue()), repaired)
        source = Path(repaired['path']) / 'main.tf'
        source.write_text(source.read_text() + '\n# a learner change after deployed evidence\n')
        self.assertEqual(session.describe()['nextAction'], 'plan')
        session.perform('plan')
        self.assertEqual(session.perform('submit')['repair']['status'], 'unknown')
        plan = session.perform('plan_destroy')['plan']
        final = session.perform('apply', approval='DESTROY LOCAL', plan_digest=plan['digest'])
        self.assertEqual(final['status'], 'destroyed')
        self.assertEqual(len(final['inventory']['resources']), 2)


if __name__ == '__main__':
    unittest.main()
