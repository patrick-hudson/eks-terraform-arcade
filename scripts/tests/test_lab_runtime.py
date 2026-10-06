"""Lifecycle proofs never contact AWS; only Game 00 uses real Terraform."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lab_runtime as runtime
import lab_manager

ROOT = Path(__file__).resolve().parents[2]
ACCOUNT = '123456789012'


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.account = ACCOUNT
        self.fail_apply = False
        self.interrupt = False
        self.http = 'arcade-10-v1'
        self.cluster = 'learner-arcade'

    def __call__(self, args, cwd, env, *, capture=False):
        self.calls.append((args, Path(cwd), dict(env)))
        out = ''
        if args[0].endswith('terraform'):
            command = args[1]
            if command == 'plan':
                Path(cwd, next(x[5:] for x in args if x.startswith('-out='))).write_bytes(b'reviewed-binary-' + str(len(self.calls)).encode())
            elif command == 'show' and '-json' in args:
                out = json.dumps({'format_version': '1.2', 'resource_changes': [], 'planned_values': {}, 'prior_state': {}, 'configuration': {}})
            elif command == 'apply':
                if self.interrupt:
                    raise KeyboardInterrupt
                if self.fail_apply:
                    return subprocess.CompletedProcess(args, 1, '', 'partial apply')
                Path(cwd, 'terraform.tfstate').write_text(json.dumps({'version': 4, 'serial': len(self.calls), 'lineage': 'same-state', 'resources': [{'mode': 'managed', 'instances': [{}]}]}))
            elif command == 'output' and '-json' in args:
                out = json.dumps({'cluster_name': {'value': self.cluster}, 'region': {'value': 'us-west-2'}})
            elif command == 'workspace':
                out = 'default\n'
        elif args[0].endswith('aws'):
            if 'get-caller-identity' in args:
                out = json.dumps({'Account': self.account, 'Arn': f'arn:aws:iam::{self.account}:user/learner'})
            elif 'describe-cluster' in args:
                out = json.dumps({'cluster': {'name': self.cluster, 'arn': f'arn:aws:eks:us-west-2:{ACCOUNT}:cluster/{self.cluster}', 'status': 'ACTIVE', 'endpoint': 'https://lab.example', 'certificateAuthority': {'data': 'Y2E='}}})
            elif 'describe-addon' in args:
                out = json.dumps({'addon': {'status': 'ACTIVE', 'health': {'issues': []}}})
        elif args[0].endswith('kubectl'):
            if 'nodes' in args:
                out = json.dumps({'items': [{'metadata': {'name': 'worker', 'labels': {'role': 'lab', 'node.kubernetes.io/instance-type': 't3.medium'}}, 'spec': {}, 'status': {'allocatable': {'cpu': '1930m'}, 'conditions': [{'type': 'Ready', 'status': 'True'}]}}]})
            elif 'exec' in args:
                out = self.http + '\n'
        return subprocess.CompletedProcess(args, 0, out, '')


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='arcade-runtime-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copy(ROOT / 'lab-recipes.json', self.root)
        shutil.copytree(ROOT / 'labs', self.root / 'labs')
        shutil.copytree(ROOT / 'modules', self.root / 'modules')
        self.runner = FakeRunner()
        self.stdout = contextlib.redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)

    def make(self, alias='01', mode='guided'):
        run = runtime.Runtime(self.root, alias, runner=self.runner)
        run.prepare(mode)
        if alias != '00':
            extra = {'admin_principal_arn': f'arn:aws:iam::{ACCOUNT}:user/learner', 'allowed_cidr': '198.51.100.8/32'} if alias == '07' else {}
            run.configure(profile='learner', account_id=ACCOUNT, lab_id='learner', **extra)
        return run

    def foundation(self):
        run = self.make('07', 'starter')
        run.plan()
        self.assertTrue(run.apply(confirm=lambda _: f'APPLY {ACCOUNT}'))
        return run

    def test_support_matrix_and_prerequisites_are_not_readiness(self):
        recipes = lab_manager.load_recipes(self.root)
        expected = {'00','01','03','04','05','07','08','09','10','13', *(f'11-{i:02}' for i in range(1,11))}
        self.assertEqual({r['alias'] for r in recipes if runtime.support(r)}, expected)
        self.make('07','starter')
        info = runtime.Runtime(self.root,'08',runner=self.runner).describe()
        self.assertIn('prepared', info['prerequisites'][0]['status'].lower())
        self.assertIn('not', info['prerequisites'][0]['status'].lower())
        complex_run = runtime.Runtime(self.root,'02',runner=self.runner)
        complex_run.prepare('guided')
        with self.assertRaisesRegex(ValueError,'runbook'):
            complex_run.plan()
        self.assertFalse(self.runner.calls)

    def test_environment_prerequisites_exclude_curriculum_only_missions(self):
        remote = runtime.Runtime(self.root, '02', runner=self.runner).describe()
        capstone = runtime.Runtime(self.root, '12', runner=self.runner).describe()
        self.assertEqual(remote['prerequisites'], [])
        self.assertEqual([item['alias'] for item in capstone['prerequisites']], ['07'])

    def test_missing_inputs_and_identity_refuse_before_terraform(self):
        run = runtime.Runtime(self.root,'01',runner=self.runner)
        run.prepare('guided')
        with self.assertRaisesRegex(ValueError,'input|Configure'):
            run.plan()
        run.configure(profile='learner',account_id=ACCOUNT,lab_id='learner')
        self.runner.account = '999999999999'
        with self.assertRaisesRegex(ValueError,'account'):
            run.plan()
        self.assertFalse(any(c[0][0].endswith('terraform') for c in self.runner.calls))

    def test_configured_account_is_pinned_while_state_is_active_or_unknown(self):
        run = self.make('04')
        run.plan()
        protected = [runtime.INPUTS, runtime.SETTINGS, runtime.PLAN_RECEIPT, 'arcade-apply.tfplan']
        before = {name: (run.path / name).read_bytes() for name in protected}
        for state in (None, '{malformed', json.dumps({'version': 4, 'resources': [
                {'mode': 'managed', 'instances': [{'attributes': {'id': 'role-with-account-local-name'}}]}]})):
            with self.subTest(state=state):
                if state is not None:
                    (run.path / 'terraform.tfstate').write_text(state)
                for changes in ({'account_id': '999999999999'}, {'region': 'us-east-1'}):
                    arguments = dict(profile='learner', account_id=ACCOUNT, lab_id='learner')
                    arguments.update(changes)
                    with self.assertRaisesRegex(ValueError, 'pinned|region'):
                        run.configure(**arguments)
                    self.assertEqual({name: (run.path / name).read_bytes() for name in protected}, before)
        run.configure(profile='learner', account_id=ACCOUNT, lab_id='another-lab')
        self.assertEqual(run._read(runtime.INPUTS)['lab_id'], 'another-lab')
        with self.assertRaisesRegex(ValueError, 'changed'):
            run.apply(confirm=lambda _: f'APPLY {ACCOUNT}')

    def test_profile_change_checks_pinned_account_before_writing(self):
        run = self.make('04')
        run.plan()
        names = [runtime.INPUTS, runtime.SETTINGS, runtime.PLAN_RECEIPT, 'arcade-apply.tfplan']
        before = {name: (run.path / name).read_bytes() for name in names}
        self.runner.account = '999999999999'
        with self.assertRaisesRegex(ValueError, 'account'):
            run.configure(profile='another-profile', account_id=ACCOUNT, lab_id='learner')
        self.assertEqual({name: (run.path / name).read_bytes() for name in names}, before)
        self.runner.account = ACCOUNT
        run.configure(profile='another-profile', account_id=ACCOUNT, lab_id='learner')
        self.assertEqual(run._read(runtime.SETTINGS)['profile'], 'another-profile')
        self.assertTrue(any('get-caller-identity' in args and args[args.index('--profile') + 1] == 'another-profile'
                            for args, _, _ in self.runner.calls))
        with self.assertRaisesRegex(ValueError, 'changed'):
            run.apply(confirm=lambda _: f'APPLY {ACCOUNT}')

    def test_initial_configuration_refuses_unowned_existing_state_and_configure_is_locked(self):
        run = runtime.Runtime(self.root, '04', runner=self.runner)
        run.prepare('guided')
        original = (run.path / runtime.INPUTS).read_bytes()
        for state in ('{malformed', json.dumps({'version': 4, 'resources': [
                {'mode': 'managed', 'instances': [{}]}]})):
            (run.path / 'terraform.tfstate').write_text(state)
            with self.assertRaisesRegex(ValueError, 'identity|configured'):
                run.configure(profile='learner', account_id=ACCOUNT, lab_id='learner')
            self.assertEqual((run.path / runtime.INPUTS).read_bytes(), original)
        (run.path / 'terraform.tfstate').unlink()
        with run._locked():
            with self.assertRaisesRegex(ValueError, 'Another lifecycle'):
                run.configure(profile='learner', account_id=ACCOUNT, lab_id='learner')
        run.configure(profile='learner', account_id=ACCOUNT, lab_id='learner')

    def test_rebinding_after_empty_state_still_checks_unknown_siblings_and_foundation_dependents(self):
        foundation = self.foundation()
        run = runtime.Runtime(self.root, '10', runner=self.runner)
        run.prepare('guided')
        run.configure(profile='learner', account_id=ACCOUNT)
        empty = json.dumps({'version': 4, 'resources': []})
        (foundation.path / 'terraform.tfstate').write_text(empty)
        (run.path / 'terraform.tfstate').write_text(empty)
        with self.assertRaisesRegex(ValueError, 'dependent|pinned'):
            foundation.configure(profile='learner', account_id='999999999999', lab_id='learner',
                                 admin_principal_arn='arn:aws:iam::999999999999:user/learner', allowed_cidr='198.51.100.8/32')
        # Model an independently recovered foundation in the new account to
        # prove that a sibling's unknown state still prevents root rebinding.
        foundation._save(account_id='999999999999')
        values = foundation._read(runtime.INPUTS)
        values['expected_account_id'] = '999999999999'
        runtime.write_json(foundation.path / runtime.INPUTS, values)
        with self.assertRaisesRegex(ValueError, 'pinned'):
            run.configure(profile='learner', account_id='999999999999')
        workload = runtime.Runtime(self.root, '10', runner=self.runner, terraform_root='workload')
        with self.assertRaisesRegex(ValueError, 'pinned'):
            workload.configure(profile='learner', account_id='999999999999')
        self.assertFalse((workload.path / runtime.INPUTS).exists())
        (run.path / 'workload/terraform.tfstate').write_text(empty)
        run.configure(profile='learner', account_id='999999999999')
        self.assertEqual(run._read(runtime.SETTINGS)['account_id'], '999999999999')

    def test_clients_cannot_change_a_foundation_and_dependent_concurrently(self):
        foundation = runtime.Runtime(self.root, '07', runner=self.runner)
        dependent = runtime.Runtime(self.root, '11-01', runner=self.runner)
        foundation.prepare('guided')
        dependent.prepare('starter')
        with foundation._locked():
            with self.assertRaisesRegex(ValueError, 'Another lifecycle'):
                with dependent._locked():
                    self.fail('Concurrent dependent operation acquired its lock')
        with dependent._locked():
            pass

    def test_saved_plan_apply_decline_and_exact_binary(self):
        run = self.make()
        receipt = run.plan()
        with self.assertRaisesRegex(ValueError, 'digest'):
            run.apply(confirm=lambda _: f'APPLY {ACCOUNT}', plan_digest='a different reviewed plan')
        self.assertFalse(run.apply(confirm=lambda _: 'no'))
        self.assertFalse(any(c[0][1] == 'apply' for c in self.runner.calls))
        self.assertTrue(run.apply(confirm=lambda _: f'APPLY {ACCOUNT}', plan_digest=receipt['digest']))
        argv = next(c[0] for c in self.runner.calls if len(c[0]) > 1 and c[0][1] == 'apply')
        self.assertEqual(argv[1:], ['apply','-input=false','-no-color',str(run.path / receipt['planFile'])])

    def test_changed_plan_source_and_input_refuse_apply(self):
        for changed in ('binary','source','input'):
            with self.subTest(changed=changed):
                run = self.make()
                receipt = run.plan()
                if changed == 'binary':
                    (run.path / receipt['planFile']).write_bytes(b'changed')
                elif changed == 'source':
                    with (run.path / 'main.tf').open('a') as f: f.write('\n# edit\n')
                else:
                    values = json.loads((run.path / runtime.INPUTS).read_text())
                    values['lab_id'] = 'different'
                    (run.path / runtime.INPUTS).write_text(json.dumps(values))
                before = len(self.runner.calls)
                with self.assertRaisesRegex(ValueError,'changed|digest|match'):
                    run.apply(confirm=lambda _: f'APPLY {ACCOUNT}')
                self.assertFalse(any(c[0][1] == 'apply' for c in self.runner.calls[before:]))

    def test_failed_and_interrupted_apply_keep_state_inputs_and_recovery(self):
        run = self.make()
        for interrupt in (False,True):
            (run.path / 'terraform.tfstate').write_text('{"owned":"preserve"}')
            run.plan()
            self.runner.fail_apply = not interrupt
            self.runner.interrupt = interrupt
            before = len(self.runner.calls)
            with self.assertRaisesRegex(ValueError,'state|Recover'):
                run.apply(confirm=lambda _: f'APPLY {ACCOUNT}')
            self.assertEqual((run.path / 'terraform.tfstate').read_text(),'{"owned":"preserve"}')
            self.assertTrue((run.path / runtime.INPUTS).exists())
            self.assertTrue(any(c[0][1] == 'apply' for c in self.runner.calls[before:]))

    def test_guided_iam_fault_persists_until_explicit_repair(self):
        run = self.make('04')
        self.assertEqual(json.loads((run.path/runtime.INPUTS).read_text())['policy_variant'], 'broken')
        values = json.loads((run.path/runtime.INPUTS).read_text())
        values['policy_variant'] = 'fixed'
        (run.path/runtime.INPUTS).write_text(json.dumps(values))
        run.prepare()
        run.configure(profile='learner', account_id=ACCOUNT, lab_id='learner')
        self.assertEqual(json.loads((run.path/runtime.INPUTS).read_text())['policy_variant'], 'fixed')

    def test_lab_id_matches_authored_input_length(self):
        for alias in ('01', '03', '07'):
            run = self.make(alias, 'starter' if alias == '07' else 'guided')
            with self.assertRaisesRegex(ValueError, '16'):
                run.configure(profile='learner', account_id=ACCOUNT, lab_id='a' * 17)

    def test_guided_counter_fault_persists_until_explicit_repair(self):
        run = self.make('05')
        self.assertEqual(json.loads((run.path/runtime.INPUTS).read_text())['table_environment_key'],'COUNTER_TABLE')
        first = run.plan()
        values = json.loads((run.path/runtime.INPUTS).read_text())
        values['table_environment_key'] = 'TABLE_NAME'
        (run.path/runtime.INPUTS).write_text(json.dumps(values))
        run.prepare()
        second = run.plan()
        self.assertNotEqual(first['fingerprint'],second['fingerprint'])
        self.assertEqual(json.loads((run.path/runtime.INPUTS).read_text())['table_environment_key'],'TABLE_NAME')

    def test_symlink_unregistered_region_and_profile_injection_refused(self):
        run = self.make()
        with self.assertRaisesRegex(ValueError,'region'):
            run.configure(profile='learner',account_id=ACCOUNT,region='us-east-1',lab_id='learner')
        with self.assertRaises(ValueError):
            run.configure(profile='x; touch bad',account_id=ACCOUNT,lab_id='learner')
        receipt = run.path / lab_manager.RECEIPT
        receipt.unlink()
        with self.assertRaisesRegex(ValueError,'unregistered'):
            run.plan()
        (self.root/'run/symlink').symlink_to(run.path,target_is_directory=True)
        real = self.root/'run'
        renamed = self.root/'original-run'
        real.rename(renamed)
        real.symlink_to(renamed,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):
            runtime.Runtime(self.root,'01',runner=self.runner).plan()

    def test_foundation_destroy_blocks_active_and_unknown_dependents(self):
        foundation = self.foundation()
        work = runtime.Runtime(self.root,'08',runner=self.runner)
        work.prepare('starter')
        for state in (None, {'version':4,'resources':[{'mode':'managed','instances':[{}]}]}):
            if state: (work.path/'terraform.tfstate').write_text(json.dumps(state))
            with self.assertRaisesRegex(ValueError,'dependent|08'):
                foundation.plan('destroy')
        (work.path/'terraform.tfstate').write_text(json.dumps({'version':4,'resources':[]}))
        foundation.plan('destroy')

    def test_activation_uses_isolated_kubeconfig_and_context(self):
        foundation = self.foundation()
        commands = foundation.activation()
        self.assertIn('export KUBECONFIG=',commands)
        self.assertIn('export LAB_KUBE_CONTEXT=',commands)
        self.assertIn(str(foundation.path),commands)
        self.assertTrue((foundation.path/'session-env.sh').is_file())
        shell = subprocess.run(['bash','-c','source "$1"; printf "%s\\n%s" "$KUBECONFIG" "$LAB_KUBE_CONTEXT"','bash',str(foundation.path/'session-env.sh')],capture_output=True,text=True)
        kube,context = shell.stdout.splitlines()
        self.assertEqual(Path(kube).parent,foundation.path)
        self.assertEqual(json.loads(Path(kube).read_text())['current-context'],context)

    def test_workload_refuses_missing_foundation_and_changed_context(self):
        work = runtime.Runtime(self.root,'08',runner=self.runner)
        work.prepare('starter')
        with self.assertRaisesRegex(ValueError,'07|foundation'):
            work.configure(profile='learner',account_id=ACCOUNT)
        foundation = self.foundation()
        work.configure(profile='learner',account_id=ACCOUNT)
        work.plan()
        config = foundation.path / 'kubeconfig.json'
        data = json.loads(config.read_text());data['current-context']='unexpected';config.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'context|changed'):
            work.apply(confirm=lambda _: f'APPLY {ACCOUNT}')

    def test_scenario_ten_baseline_http_before_broken_same_state(self):
        self.foundation()
        run = runtime.Runtime(self.root,'11-10',runner=self.runner)
        run.prepare('starter')
        run.configure(profile='learner',account_id=ACCOUNT)
        self.assertEqual((run.path/'candidate.yaml').read_text(),(run.path/'baseline.yaml').read_text())
        with self.assertRaisesRegex(ValueError,'baseline'):
            run.begin_broken_update()
        baseline = run.plan()
        self.assertEqual(baseline['phase'],'baseline')
        run.apply(confirm=lambda _: f'APPLY {ACCOUNT}')
        self.runner.http='wrong-version'
        with self.assertRaisesRegex(ValueError,'v1|HTTP'):
            run.verify()
        with self.assertRaisesRegex(ValueError,'baseline'):
            run.begin_broken_update()
        self.runner.http='arcade-10-v1'
        run.verify()
        state = (run.path/'terraform.tfstate').read_bytes()
        run.begin_broken_update()
        self.assertEqual(state,(run.path/'terraform.tfstate').read_bytes())
        update=run.plan()
        self.assertEqual(update['phase'],'incident')
        self.assertNotEqual(baseline['fingerprint'],update['fingerprint'])
        self.assertFalse(run.apply(confirm=lambda _: 'no'))
        run.apply(confirm=lambda _: f'APPLY {ACCOUNT}')
        applies = [c for c in self.runner.calls if c[0][1]=='apply' and c[1]==run.path]
        self.assertEqual(len(applies),2)

    def test_captured_cloud_failure_explains_actual_error(self):
        run = self.make()
        def denied(args, cwd, env, *, capture=False):
            return subprocess.CompletedProcess(args, 1, '', 'AccessDenied: session expired')
        run.runner = denied
        with self.assertRaisesRegex(ValueError, 'AccessDenied: session expired'):
            run.plan()

    def test_wrong_account_after_plan_and_changed_copied_module_refuse_apply(self):
        run = self.make()
        run.plan()
        self.runner.account = '999999999999'
        with self.assertRaisesRegex(ValueError, 'account'):
            run.apply(confirm=lambda _: f'APPLY {ACCOUNT}')
        self.assertFalse(any(c[0][1] == 'apply' for c in self.runner.calls))
        self.runner.account = ACCOUNT
        self.foundation()
        work = runtime.Runtime(self.root, '08', runner=self.runner)
        work.prepare('starter')
        work.configure(profile='learner', account_id=ACCOUNT)
        work.plan()
        module = work.path / 'workload-module/main.tf'
        module.write_text(module.read_text() + '\n# changed workload module\n')
        before = len(self.runner.calls)
        with self.assertRaisesRegex(ValueError, 'changed'):
            work.apply(confirm=lambda _: f'APPLY {ACCOUNT}')
        self.assertFalse(any(c[0][1] == 'apply' for c in self.runner.calls[before:]))

    def test_ambient_credentials_and_terraform_overrides_do_not_reach_runner(self):
        from unittest.mock import patch
        run = self.make()
        with patch.dict(os.environ, {'AWS_ACCESS_KEY_ID': 'unrelated', 'AWS_SECRET_ACCESS_KEY': 'secret',
                                    'TF_VAR_region': 'us-east-1', 'TF_CLI_ARGS_apply': '-auto-approve'}):
            run.plan()
        for _, _, env in self.runner.calls:
            self.assertNotIn('AWS_ACCESS_KEY_ID', env)
            self.assertNotIn('AWS_SECRET_ACCESS_KEY', env)
            self.assertNotIn('TF_VAR_region', env)
            self.assertNotIn('TF_CLI_ARGS_apply', env)
            self.assertEqual(env['AWS_PROFILE'], 'learner')
            self.assertEqual(env['AWS_REGION'], 'us-west-2')

    def test_real_local_game_zero_lifecycle(self):
        tf = ROOT/'.tools/bin/terraform'
        if not tf.is_file(): tf = shutil.which('terraform')
        if not tf: self.skipTest('Terraform is unavailable on PATH and in .tools/bin')
        run = runtime.Runtime(self.root,'00')
        run.terraform = str(tf)
        run.prepare('guided')
        run.plan()
        self.assertTrue(run.apply(confirm=lambda _: 'APPLY LOCAL'))
        observation = run.verify()
        self.assertIn('local',observation['scope'].lower())
        output = subprocess.run([str(tf),'output','-json','allocations'],cwd=run.path,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(output.stdout),{'api':256,'worker':512})
        run.plan('destroy')
        self.assertTrue(run.apply(confirm=lambda _: 'DESTROY LOCAL'))
        self.assertEqual(lab_manager.state_summary(run.path)['managedObjects'],0)


if __name__ == '__main__':
    unittest.main()
