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

    def test_partial_infrastructure_can_clean_unused_workload_without_creation_outputs(self):
        self.foundation()
        original = self.runner
        outputs_ready = False

        def runner(args, cwd, env, *, capture=False):
            result = original(args, cwd, env, capture=capture)
            if args[0].endswith('terraform'):
                if args[1:3] == ['output', '-json'] and Path(cwd).name in {'09-pod-identity', '10-ebs-storage'}:
                    # The failed infrastructure apply created its IAM role, but
                    # never produced the output required to start the exercise.
                    outputs = {'csi_role_arn': {'value': f'arn:aws:iam::{ACCOUNT}:role/learner-ebs'}}
                    if outputs_ready:
                        outputs.update(bucket_name={'value': 'learner-fixture'}, addon_version={'value': 'v1'})
                    result.stdout = json.dumps(outputs)
                if args[1] == 'apply' and args[-1].endswith('arcade-destroy.tfplan') and not result.returncode:
                    Path(cwd, 'terraform.tfstate').write_text(json.dumps({'version': 4, 'resources': []}))
            elif args[0] == 'aws' and 'describe-volumes' in args:
                result.stdout = json.dumps({'Volumes': []})
            return result

        self.runner = runner
        for alias in ('09', '10'):
            with self.subTest(alias=alias):
                outputs_ready = False
                infrastructure = self.session(alias, '.')
                infrastructure.perform('prepare', mode='guided')
                infrastructure.perform('configure', profile='learner', account_id=ACCOUNT)
                Path(infrastructure.runtime.path, 'terraform.tfstate').write_text(json.dumps({
                    'version': 4, 'resources': [{'mode': 'managed', 'type': 'aws_iam_role',
                    'name': 'partial', 'instances': [{'attributes': {'id': 'owned-partial-role'}}]}]}))
                infrastructure.runtime._save(status='failed')
                workload = self.session(alias, 'workload')
                with self.assertRaisesRegex(ValueError, 'output'):
                    workload.perform('configure', profile='learner', account_id=ACCOUNT)
                with self.assertRaisesRegex(ValueError, 'workload'):
                    infrastructure.perform('plan_destroy')
                self.assertFalse((workload.runtime.path / 'terraform.tfstate').exists())

                planned = workload.perform('plan_destroy')
                plan = planned['plan']
                self.assertEqual(plan['operation'], 'destroy')
                self.assertTrue(workload.runtime._read(lab_runtime.SETTINGS)['cleanupOnly'])
                self.assertEqual(planned['inventory']['absence'], 'unknown')
                self.assertFalse((workload.runtime.path / 'terraform.tfstate').exists())
                with self.assertRaisesRegex(ValueError, 'workload'):
                    infrastructure.perform('plan_destroy')
                with self.assertRaisesRegex(ValueError, 'cleanup|Configure'):
                    workload.perform('plan')
                with self.assertRaisesRegex(ValueError, 'output'):
                    workload.perform('configure', profile='learner', account_id=ACCOUNT)
                self.assertTrue(workload.runtime._read(lab_runtime.SETTINGS)['cleanupOnly'])

                before = len(original.calls)
                workload.perform('apply', approval='not approved', plan_digest=plan['digest'])
                self.assertFalse(any(c[0][1] == 'apply' for c in original.calls[before:]))

                original.fail_apply = True
                with self.assertRaisesRegex(ValueError, 'preserved'):
                    workload.perform('apply', approval=f'DESTROY {ACCOUNT}', plan_digest=plan['digest'])
                self.assertFalse((workload.runtime.path / 'terraform.tfstate').exists())
                with self.assertRaisesRegex(ValueError, 'workload'):
                    infrastructure.perform('plan_destroy')
                original.fail_apply = False
                workload.perform('apply', approval=f'DESTROY {ACCOUNT}', plan_digest=plan['digest'])
                self.assertEqual(workload.describe()['inventory']['absence'], 'unknown')
                self.assertEqual(infrastructure.perform('plan_destroy')['plan']['operation'], 'destroy')
                self.assertTrue(infrastructure.runtime.path.exists())
                outputs_ready = True
                workload.perform('configure', profile='learner', account_id=ACCOUNT)
                self.assertFalse(workload.runtime._read(lab_runtime.SETTINGS)['cleanupOnly'])
                self.assertEqual(workload.perform('plan')['plan']['operation'], 'apply')

    def test_cleanup_configuration_preserves_identity_and_live_context_guards(self):
        foundation = self.foundation()
        workload = self.session('10', 'workload')
        workload.perform('prepare', mode='guided')
        foreign = {'aws_profile': 'someone-else', 'expected_account_id': '999999999999'}
        lab_runtime.write_json(workload.runtime.path / lab_runtime.INPUTS, foreign)
        before = len(self.runner.calls)
        with self.assertRaisesRegex(ValueError, 'identity|inputs'):
            workload.perform('plan_destroy')
        self.assertEqual(workload.runtime._read(lab_runtime.INPUTS), foreign)
        self.assertFalse(any(c[0][1] == 'plan' for c in self.runner.calls[before:]))
        lab_runtime.write_json(workload.runtime.path / lab_runtime.INPUTS, {})
        self.runner.account = '999999999999'
        before = len(self.runner.calls)
        with self.assertRaisesRegex(ValueError, 'account'):
            workload.perform('plan_destroy')
        self.assertFalse(any(c[0][1] == 'plan' for c in self.runner.calls[before:]))
        self.runner.account = ACCOUNT
        lab_runtime.write_json(foundation.runtime.path / 'kubeconfig.json', {'unexpected': 'context'})
        before = len(self.runner.calls)
        with self.assertRaisesRegex(ValueError, 'context'):
            workload.perform('plan_destroy')
        self.assertFalse(any(c[0][1] == 'plan' for c in self.runner.calls[before:]))

    def test_applying_status_and_wait_take_precedence_over_plan_hints(self):
        session = self.session()
        session.perform('prepare', mode='guided')
        session.perform('plan')
        session.runtime._save(status='applying')
        self.assertEqual(session.describe()['status'], 'applying')
        self.assertEqual(session.describe()['nextAction'], 'wait for the current operation')
        record = session._record()
        record['appliedSourceFingerprint'] = 'an earlier applied revision'
        session._save(record)
        path = session.runtime.path / 'main.tf'
        path.write_text(path.read_text() + '\n# changed during observation\n')
        self.assertTrue(session.describe()['plan']['stale'])
        self.assertEqual(session.describe()['status'], 'applying')
        self.assertEqual(session.describe()['nextAction'], 'wait for the current operation')

    def test_real_terraform_destroy_of_unused_root_writes_empty_state(self):
        terraform = ROOT / '.tools/bin/terraform'
        if not terraform.is_file():
            terraform = shutil.which('terraform')
        if not terraform:
            self.skipTest('Terraform is unavailable')
        session = Session(self.root, '00')
        session.runtime.terraform = str(terraform)
        session.perform('prepare', mode='guided')
        state = session.runtime.path / 'terraform.tfstate'
        self.assertFalse(state.exists())
        plan = session.perform('plan_destroy')['plan']
        self.assertFalse(state.exists())
        session.perform('apply', approval='DESTROY LOCAL', plan_digest=plan['digest'])
        self.assertEqual(json.loads(state.read_text())['resources'], [])
        self.assertEqual(session.describe()['inventory']['absence'], 'unknown')

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
