#!/usr/bin/env python3
"""Explicit, saved-plan lifecycle for registered arcade workspaces.

Recipe shell text is documentation, never an execution source. Cloud tests use
injected command runners; Game 00 uses only Terraform's built-in provider.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import tempfile

import lab_manager

ROOT = Path(__file__).resolve().parents[1]
INPUTS = 'arcade.auto.tfvars.json'
SETTINGS = '.arcade-runtime.json'
PLAN_RECEIPT = '.arcade-plan.json'
SUPPORTED = {'00', '01', '03', '04', '05', '07', '08', '09', '10', '13', *(f'11-{i:02}' for i in range(1, 11))}
ROOT_ORDER = {'09': ['.', 'workload'], '10': ['.', 'workload'], '13': ['workload', 'access']}
ADDONS = ('vpc-cni', 'kube-proxy', 'coredns', 'eks-pod-identity-agent')


class RuntimeError(ValueError):
    """An actionable refusal or recoverable lifecycle error."""


def support(recipe):
    return recipe['alias'] in SUPPORTED


def prerequisites(root, recipe):
    """Ordered prerequisites, with local preparation explicitly distinguished."""
    catalog = lab_manager.load_recipes(root)
    result, seen = [], set()

    def visit(identifier):
        if identifier in seen:
            return
        seen.add(identifier)
        item = lab_manager.find_recipe(catalog, identifier)
        for prerequisite in lab_manager.environment_prerequisites(item):
            visit(prerequisite)
        path = None
        status = 'Runbook prerequisite; complete its acceptance checks'
        if item['runDirectory']:
            path = lab_manager.contained_path(root, 'run/' + item['runDirectory'])
            status = 'Not prepared; live readiness not checked'
            if path.exists():
                try:
                    lab_manager.session_receipt(path, item)
                    status = 'Prepared files; live readiness not checked'
                except (OSError, ValueError):
                    status = 'Unregistered or invalid; inspect before proceeding'
        result.append({'recipeId': item['id'], 'alias': item['alias'], 'title': item['title'],
                       'status': status, 'path': str(path) if path else None})

    for identifier in lab_manager.environment_prerequisites(recipe):
        visit(identifier)
    return result


def command_runner(args, cwd, env, *, capture=False):
    """Stream normal tools outside curses; capture only machine observations."""
    process = subprocess.Popen(args, cwd=cwd, env=env, text=True,
                               stdout=subprocess.PIPE if capture else None,
                               stderr=subprocess.PIPE if capture else None,
                               start_new_session=True)
    try:
        stdout, stderr = process.communicate()
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        except ProcessLookupError:
            pass
        raise
    return subprocess.CompletedProcess(args, process.returncode, stdout or '', stderr or '')


def digest(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f'Refusing missing or symlink file: {path.name}')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    if path.is_symlink():
        raise RuntimeError(f'Refusing symlink file: {path.name}')
    # A unique temporary file permits recovery after an interrupted earlier write.
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    temp = Path(temporary)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2)
            stream.write('\n')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)



class Runtime:
    def __init__(self, root, identifier, runner=None, terraform_root=None):
        self.root = Path(root).absolute()
        if self.root.is_symlink():
            raise RuntimeError('Refusing symlink repository root.')
        self.recipes = lab_manager.load_recipes(self.root)
        self.recipe = lab_manager.find_recipe(self.recipes, identifier)
        self.alias = self.recipe['alias']
        self.supported = support(self.recipe)
        self.workspace = (lab_manager.contained_path(self.root, 'run/' + self.recipe['runDirectory'])
                     if self.recipe['runDirectory'] else None)
        self.roots = ROOT_ORDER.get(self.alias, next(iter(self.recipe['modes'].values()), {}).get('terraformRoots', ['.']))
        self.terraform_root = self.roots[0] if terraform_root is None else terraform_root
        if self.terraform_root not in self.roots:
            raise RuntimeError('Choose a registered Terraform root: ' + ', '.join(self.roots))
        self.path = (lab_manager.contained_path(self.workspace, self.terraform_root)
                     if self.workspace is not None else None)
        self.runner = runner or command_runner
        bundled = self.root / '.tools/bin/terraform'
        self.terraform = str(bundled) if bundled.is_file() else 'terraform'

    @property
    def workload(self):
        return self.alias in {'08', '09', '10', '13'} or self.alias.startswith('11-')

    def _workspace(self, *, supported=True):
        if supported and not self.supported:
            raise RuntimeError(f'Environment operations for Game {self.alias} use its runbook: {self.runbook}')
        if self.path is None:
            raise RuntimeError(f'This is a runbook mission: {self.runbook}')
        lab_manager.contained_path(self.root, 'run/' + self.recipe['runDirectory'])
        if not self.path.is_dir():
            raise RuntimeError(f'Prepare Game {self.alias} first.')
        session = lab_manager.session_receipt(self.workspace, self.recipe)
        for local_path in ('.terraform', 'terraform.tfstate', 'terraform.tfstate.backup', INPUTS, SETTINGS, PLAN_RECEIPT):
            lab_manager.contained_path(self.path, local_path)
        if supported:
            roots = self.recipe['modes'][session['mode']].get('terraformRoots', ['.'])
            if self.terraform_root not in roots:
                raise RuntimeError('This Terraform root is not registered for the prepared mode.')
        return session

    @property
    def runbook(self):
        return self.root / 'labs' / self.recipe['id'] / 'README.md'

    def _read(self, name, default=None):
        path = lab_manager.contained_path(self.path, name)
        value = lab_manager.read_json(path) if path.exists() else ({} if default is None else default)
        if not isinstance(value, dict):
            raise RuntimeError(f'Expected a JSON object in {name}; preserve the workspace and inspect this file.')
        return value

    def _save(self, **values):
        settings = self._read(SETTINGS)
        settings.update(values)
        write_json(self.path / SETTINGS, settings)
        return settings

    @contextmanager
    def _locked(self):
        self._workspace()
        # Serialize the dependency graph across CLI, TUI and browser processes.
        # A per-workspace lock alone permits foundation deletion while another
        # client is creating a dependent workload whose state is still empty.
        lockpath = lab_manager.contained_path(self.root, 'run/.arcade-runtime.lock')
        with lockpath.open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError('Another lifecycle operation owns this project. Wait for it to finish.') from exc
            yield

    def describe(self):
        prepared, phase = False, 'not prepared'
        if self.path and self.path.exists():
            try:
                self._workspace(supported=False)
                prepared = True
                phase = self._read(SETTINGS).get('phase', 'practice')
            except (OSError, ValueError):
                phase = 'unregistered or invalid workspace'
        return {'supported': self.supported, 'runbook': str(self.runbook),
                'path': str(self.path) if self.path else None, 'prepared': prepared,
                'phase': phase, 'prerequisites': prerequisites(self.root, self.recipe),
                'scope': 'Prepared files and Terraform state do not prove live readiness.'}

    def prepare(self, mode=None):
        if self.path is None:
            raise RuntimeError(f'Follow this runbook; it has no standalone workspace: {self.runbook}')
        _, selected, created = lab_manager.prepare(self.root, self.recipe, mode)
        path = self.path
        if self.supported:
            values = self._read(INPUTS)
            faults = {'04': ('policy_variant', 'broken'), '05': ('table_environment_key', 'COUNTER_TABLE')}
            if selected == 'guided' and self.alias in faults:
                key, initial = faults[self.alias]
                if key not in values:
                    values[key] = initial
                    write_json(path / INPUTS, values)
            settings = self._read(SETTINGS)
            if not settings:
                phase = 'practice'
                if self.alias == '11-10':
                    # Only initialize an untouched empty session. Existing edits/state
                    # must never be silently replaced by an authored fixture.
                    candidate = lab_manager.contained_path(path, 'candidate.yaml')
                    source = lab_manager.contained_path(self.root, 'labs/' + self.recipe['id'] + '/starter/broken.yaml')
                    if not created and ((path / 'terraform.tfstate').exists() or digest(candidate) != digest(source)):
                        raise RuntimeError('Existing scenario 11-10 edits/state preserved. Follow the baseline runbook in this workspace before using guided phases.')
                    baseline = lab_manager.contained_path(path, 'baseline.yaml')
                    candidate.write_bytes(baseline.read_bytes())
                    phase = 'baseline'
                self._save(schemaVersion=1, phase=phase, status='prepared')
        print(f'Prepared files: {path}\nLive readiness has not been established. Runbook: {self.runbook}')
        return path

    def configure(self, *, profile=None, account_id=None, region='us-west-2', lab_id=None,
                  admin_principal_arn=None, allowed_cidr=None):
        self._workspace()
        if self.alias == '00':
            return self._read(SETTINGS)
        if not isinstance(profile, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@+-]{0,127}', profile):
            raise RuntimeError('Configure an explicit named AWS profile (letters, digits, _, ., @, +, -).')
        if not isinstance(account_id, str) or not re.fullmatch(r'[0-9]{12}', account_id):
            raise RuntimeError('Configure the intended 12-digit AWS account ID.')
        if region != 'us-west-2':
            raise RuntimeError('This terminal workflow requires region us-west-2. Use the runbook for a different region.')
        inputs = self._read(INPUTS)
        inputs.update(expected_account_id=account_id, region=region)
        settings = {'profile': profile, 'account_id': account_id, 'region': region}
        if self.workload:
            foundation = self._foundation()
            parent = foundation._settings()
            if (parent['profile'], parent['account_id'], parent['region']) != (profile, account_id, region):
                raise RuntimeError('Workload identity must match the registered Game 07 foundation.')
            if not parent.get('cluster_name') or not parent.get('context'):
                raise RuntimeError('Apply Game 07 and configure its isolated context first.')
            inputs.update(aws_profile=profile, cluster_name=parent['cluster_name'])
            settings.update({key: parent[key] for key in ('cluster_name', 'context', 'kubeconfig')})
            if self.alias in ROOT_ORDER and self.terraform_root != 'workload':
                inputs['lab_id'] = parent['lab_id']
                settings['lab_id'] = parent['lab_id']
            if self.alias == '13' and self.terraform_root == 'access':
                try:
                    network = ipaddress.ip_network(allowed_cidr, strict=True)
                    if network.version != 4 or network.prefixlen != 32:
                        raise ValueError()
                except (ValueError, TypeError) as exc:
                    raise RuntimeError('Provide your allowed public IPv4 /32 CIDR for the public access root.') from exc
                inputs['allowed_cidr'] = str(network)
                nodes = foundation._ready()
                if len(nodes) != 1:
                    raise RuntimeError('Public access requires exactly one registered Game 07 worker.')
                provider = nodes[0].get('spec', {}).get('providerID', '')
                match = re.fullmatch(r'aws:///[a-z0-9-]+/(i-[0-9a-f]+)', provider)
                if not match:
                    raise RuntimeError('The registered worker has no valid EC2 provider identity.')
                inputs['node_instance_id'] = match.group(1)
            if self.alias in {'09', '10'} and self.terraform_root == 'workload':
                self._wire_infrastructure(inputs, settings)
        else:
            maximum = 16 if self.alias in {'01', '03', '07'} else 20
            if not isinstance(lab_id, str) or not re.fullmatch(r'[a-z][a-z0-9-]{2,' + str(maximum - 1) + '}', lab_id):
                raise RuntimeError(f'Configure a distinctive lab_id: 3–{maximum} lowercase letters, digits or hyphens, starting with a letter.')
            inputs['lab_id'] = lab_id
            settings['lab_id'] = lab_id
        if self.alias == '07':
            if not isinstance(admin_principal_arn, str) or not re.fullmatch(r'arn:aws:iam::' + account_id + r':(?:role|user)/[A-Za-z0-9+=,.@_/-]+', admin_principal_arn):
                raise RuntimeError('Provide a permanent IAM role/user ARN in the intended account, never an STS session ARN.')
            try:
                network = ipaddress.ip_network(allowed_cidr, strict=True)
                if network.version != 4 or network.prefixlen != 32:
                    raise ValueError()
            except (ValueError, TypeError) as exc:
                raise RuntimeError('Provide your allowed public IPv4 /32 CIDR.') from exc
            inputs.update(admin_principal_arn=admin_principal_arn, allowed_cidr=str(network))
        write_json(self.path / INPUTS, inputs)
        return self._save(**settings)

    def configure_interactive(self, input_fn=input):
        self._workspace()
        if self.alias == '00':
            print('Game 00 needs no AWS credentials or cloud inputs.')
            return self._read(SETTINGS)
        previous, values = self._read(SETTINGS), self._read(INPUTS)
        def ask(label, old=''):
            answer = input_fn(f'{label}' + (f' [{old}]' if old else '') + ': ').strip()
            return answer or old
        data = {'profile': ask('AWS profile', previous.get('profile', '')),
                'account_id': ask('Intended AWS account (12 digits)', previous.get('account_id', '')),
                'region': ask('AWS region', previous.get('region', 'us-west-2'))}
        if not self.workload:
            data['lab_id'] = ask('Distinctive lab ID', previous.get('lab_id', ''))
        if self.alias == '07':
            data['admin_principal_arn'] = ask('Permanent IAM role/user ARN', values.get('admin_principal_arn', ''))
        if self.alias == '07' or (self.alias == '13' and self.terraform_root == 'access'):
            data['allowed_cidr'] = ask('Your public IPv4 /32', values.get('allowed_cidr', ''))
        result = self.configure(**data)
        print(f'Inputs saved in {self.path / INPUTS}. Edit this Terraform input file for mission repairs.')
        return result

    def _settings(self):
        self._workspace()
        settings = self._read(SETTINGS)
        if self.alias == '00':
            return settings
        if not all(settings.get(key) for key in ('profile', 'account_id', 'region')):
            raise RuntimeError('Configure missing identity inputs before planning.')
        if settings['region'] != 'us-west-2':
            raise RuntimeError('Unexpected region; configure us-west-2 before planning.')
        if (not isinstance(settings['profile'], str) or not isinstance(settings['account_id'], str)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@+-]{0,127}', settings['profile'])
                or not re.fullmatch(r'[0-9]{12}', settings['account_id'])):
            raise RuntimeError('Invalid saved identity inputs; configure this workspace again.')
        values = self._read(INPUTS)
        for variable, expected in [('region', settings['region']), ('expected_account_id', settings['account_id'])]:
            if values.get(variable) != expected:
                raise RuntimeError('Terraform identity inputs changed; configure and review a fresh plan.')
        if self.workload:
            if values.get('aws_profile') != settings['profile'] or values.get('cluster_name') != settings.get('cluster_name'):
                raise RuntimeError('Workload context inputs changed; configure and review a fresh plan.')
        elif values.get('lab_id') != settings.get('lab_id'):
            raise RuntimeError('Terraform lab identity input changed; configure and review a fresh plan.')
        if self.alias == '07' and not all(values.get(k) for k in ('admin_principal_arn', 'allowed_cidr')):
            raise RuntimeError('Missing Game 07 IAM principal or allowed /32 input.')
        return settings

    def _env(self):
        data = self._settings()
        env = {k: v for k, v in os.environ.items() if not k.startswith(('AWS_', 'TF_')) and k not in {'KUBECONFIG', 'LAB_KUBE_CONTEXT'}}
        env.update(TF_IN_AUTOMATION='1', TF_INPUT='0', AWS_EC2_METADATA_DISABLED='true', AWS_PAGER='')
        env['PATH'] = str(self.root / '.tools/bin') + os.pathsep + env.get('PATH', '')
        if self.alias != '00':
            env.update(AWS_PROFILE=data['profile'], AWS_REGION=data['region'], AWS_DEFAULT_REGION=data['region'])
        if data.get('kubeconfig'):
            env.update(KUBECONFIG=data['kubeconfig'], LAB_KUBE_CONTEXT=data['context'])
        return env

    def _invoke(self, args, *, capture=False):
        if self.runner is command_runner and not capture:
            print('> ' + shlex.join(args), flush=True)
        result = self.runner(args, self.path, self._env(), capture=capture)
        if result.returncode:
            diagnostic = ''.join(c if c.isprintable() or c == '\n' else ' ' for c in (result.stderr or '')[-2000:]).strip()
            detail = (' ' + diagnostic) if capture and diagnostic else ' Inspect the streamed error.'
            raise RuntimeError(f'{Path(args[0]).name} {args[1]} failed (exit {result.returncode}).{detail} Retain this workspace: {self.path}')
        return result.stdout

    def _tf(self, *args, capture=False):
        return self._invoke([self.terraform, *args], capture=capture)

    def _aws(self, *args):
        data = self._settings()
        raw = self._invoke(['aws', '--profile', data['profile'], '--region', data['region'], '--no-cli-pager', '--output', 'json', *args], capture=True)
        try:
            return json.loads(raw)
        except ValueError as exc:
            raise RuntimeError('AWS returned invalid JSON; no operation was approved.') from exc

    def _identity(self):
        data = self._settings()
        if self.alias == '00':
            return {'account': 'LOCAL', 'profile': None, 'region': None}
        actual = self._aws('sts', 'get-caller-identity')
        if actual.get('Account') != data['account_id']:
            raise RuntimeError('AWS account does not match the intended account. Stop and check the named profile.')
        return {'account': actual['Account'], 'profile': data['profile'], 'region': data['region']}

    def _foundation(self):
        foundation = Runtime(self.root, '07', runner=self.runner)
        try:
            foundation._workspace()
        except (OSError, ValueError) as exc:
            raise RuntimeError('Prepare, apply and verify prerequisite Game 07 first.') from exc
        return foundation

    def _sibling(self, root):
        return Runtime(self.root, self.alias, runner=self.runner, terraform_root=root)

    def _wire_infrastructure(self, inputs, settings):
        infrastructure = self._sibling('.')
        infrastructure._workspace()
        if not infrastructure._state_digest():
            raise RuntimeError('Apply this mission\'s infrastructure root first; its outputs are required by workload.')
        data = infrastructure._settings()
        if any(data.get(key) != settings.get(key) for key in ('profile', 'account_id', 'region', 'cluster_name')):
            raise RuntimeError('Infrastructure and workload must use the same foundation identity.')
        outputs = json.loads(infrastructure._tf('output', '-json', capture=True))
        if self.alias == '09':
            bucket = outputs.get('bucket_name', {}).get('value')
            if not isinstance(bucket, str) or not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', bucket):
                raise RuntimeError('Infrastructure output bucket_name is missing or invalid; apply infrastructure first.')
            fixture = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'fixture', 'namespace': 'arcade-identity'},
                       'data': {'bucket': bucket, 'region': settings['region']}}
            target = lab_manager.contained_path(self.path, 'fixture.yaml')
            previous = self._read(SETTINGS).get('fixtureDigest')
            if target.exists() and digest(target) != previous:
                # A manually authored fixture remains the learner's file.
                try:
                    same = json.loads(target.read_text()) == fixture
                except ValueError:
                    same = False
                if not same:
                    raise RuntimeError('Existing fixture.yaml edits preserved. Review the infrastructure outputs and fixture before configuring.')
            write_json(target, fixture)
            settings['fixtureDigest'] = digest(target)
            paths = inputs.get('extra_manifest_paths', [])
            if not isinstance(paths, list):
                raise RuntimeError('extra_manifest_paths must remain a list; preserve and inspect learner inputs.')
            inputs['extra_manifest_paths'] = list(dict.fromkeys([*paths, 'fixture.yaml']))
        elif not outputs.get('addon_version', {}).get('value') or not outputs.get('csi_role_arn', {}).get('value'):
            raise RuntimeError('Infrastructure outputs addon_version and csi_role_arn are required before the storage workload.')
        settings['infrastructureStateDigest'] = infrastructure._state_digest()

    def _root_dependencies(self, operation):
        order = ROOT_ORDER[self.alias]
        index = order.index(self.terraform_root)
        if operation == 'destroy':
            for later in order[index + 1:]:
                observation = lab_manager.state_summary(self._sibling(later).path)
                if observation['managedObjects'] != 0:
                    raise RuntimeError(f'Destroy dependent root {later} first; its state is active or unknown.')
            if self.alias == '10' and self.terraform_root == '.':
                self._storage_absence()
            return
        if index == 0:
            return
        parent = self._sibling(order[index - 1])
        if lab_manager.state_summary(parent.path)['managedObjects'] in (None, 0):
            raise RuntimeError(f'Apply prerequisite root {parent.terraform_root} first; infrastructure outputs/state are missing.')
        settings, parent_settings = self._settings(), parent._settings()
        if any(settings.get(key) != parent_settings.get(key) for key in ('profile', 'account_id', 'region', 'cluster_name')):
            raise RuntimeError('Prerequisite roots must use the same foundation identity. Configure and review again.')
        if self.alias in {'09', '10'}:
            if self._settings().get('infrastructureStateDigest') != parent._state_digest():
                raise RuntimeError('Infrastructure outputs/state changed. Configure workload again, then review a fresh plan.')
            if self.alias == '10':
                data = self._settings()
                addon = self._aws('eks', 'describe-addon', '--cluster-name', data['cluster_name'], '--addon-name', 'aws-ebs-csi-driver').get('addon', {})
                if addon.get('status') != 'ACTIVE' or addon.get('health', {}).get('issues'):
                    raise RuntimeError('The EBS CSI driver is not healthy; complete the infrastructure acceptance checks first.')

    def _storage_absence(self):
        # Keep the controller alive until Kubernetes has released the disk. This
        # is an observation only; never delete a volume discovered by tag search.
        for args in [('get', 'namespace', 'arcade-storage', '--ignore-not-found', '-o', 'name'),
                     ('get', 'storageclass', 'arcade-gp3', '--ignore-not-found', '-o', 'name')]:
            if self._kubectl(*args, capture=True).strip():
                raise RuntimeError('Storage workload still exists; retain the CSI infrastructure until its cleanup completes.')
        volumes = self._aws('ec2', 'describe-volumes', '--filters',
                            'Name=tag:Project,Values=aws-interview-arcade', 'Name=tag:Lab,Values=10').get('Volumes')
        if volumes is None or volumes:
            raise RuntimeError('Storage volume absence is not established. Inspect Game 10 volume ownership; retain the controller and foundation.')

    def _cluster(self):
        data = self._settings()
        name = data.get('cluster_name')
        if not name or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', name):
            raise RuntimeError('Missing or invalid Game 07 cluster identity; apply/verify Game 07 first.')
        cluster = self._aws('eks', 'describe-cluster', '--name', name).get('cluster', {})
        if cluster.get('arn') != f"arn:aws:eks:{data['region']}:{data['account_id']}:cluster/{name}" or cluster.get('status') != 'ACTIVE':
            raise RuntimeError('The intended EKS cluster is not ACTIVE in the expected account and region.')
        if not str(cluster.get('endpoint', '')).startswith('https://') or not cluster.get('certificateAuthority', {}).get('data'):
            raise RuntimeError('Cluster connection information is incomplete.')
        return cluster

    def _kube_document(self, cluster, data):
        return {'apiVersion': 'v1', 'kind': 'Config', 'current-context': data['context'],
                'clusters': [{'name': data['cluster_name'], 'cluster': {'server': cluster['endpoint'], 'certificate-authority-data': cluster['certificateAuthority']['data']}}],
                'contexts': [{'name': data['context'], 'context': {'cluster': data['cluster_name'], 'user': 'arcade'}}],
                'users': [{'name': 'arcade', 'user': {'exec': {'apiVersion': 'client.authentication.k8s.io/v1beta1',
                    'command': 'aws', 'args': ['--profile', data['profile'], '--region', data['region'], 'eks', 'get-token', '--cluster-name', data['cluster_name'], '--output', 'json'],
                    'interactiveMode': 'Never'}}}]}

    def _context(self):
        data = self._settings()
        foundation = self._foundation() if self.workload else self
        parent = foundation._settings()
        for key in ('profile', 'account_id', 'region', 'cluster_name', 'context', 'kubeconfig'):
            if not parent.get(key) or data.get(key) != parent[key]:
                raise RuntimeError('Unexpected Kubernetes context or foundation identity. Configure this workspace again.')
        path = lab_manager.contained_path(foundation.path, 'kubeconfig.json')
        if data['kubeconfig'] != str(path):
            raise RuntimeError('Kubernetes context must use the registered foundation kubeconfig.')
        cluster = self._cluster()
        if foundation._read('kubeconfig.json') != self._kube_document(cluster, data):
            raise RuntimeError('Isolated Kubernetes context changed or no longer matches the intended EKS cluster.')
        return digest(path)

    def _kubectl(self, *args, capture=False):
        data = self._settings()
        return self._invoke(['kubectl', '--kubeconfig', data['kubeconfig'], '--context', data['context'], *args], capture=capture)

    def _ready(self):
        self._context()
        data = self._settings()
        for addon in ADDONS:
            observation = self._aws('eks', 'describe-addon', '--cluster-name', data['cluster_name'], '--addon-name', addon).get('addon', {})
            if observation.get('status') != 'ACTIVE' or observation.get('health', {}).get('issues'):
                raise RuntimeError(f'Game 07 addon {addon} is not healthy; inspect its runbook before starting a workload.')
        nodes = json.loads(self._kubectl('get', 'nodes', '-o', 'json', capture=True)).get('items', [])
        if not nodes or not all(any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in node.get('status', {}).get('conditions', [])) for node in nodes):
            raise RuntimeError('Game 07 has no usable Ready workers; preparation is not readiness.')
        return nodes

    def _configure_kubeconfig(self):
        outputs = json.loads(self._tf('output', '-json', capture=True))
        name, region = outputs.get('cluster_name', {}).get('value'), outputs.get('region', {}).get('value')
        data = self._settings()
        if region != data['region'] or name != data['lab_id'] + '-arcade':
            raise RuntimeError('Game 07 outputs do not match the configured cluster identity.')
        context = f"arcade-{data['account_id']}-{name}"
        data = self._save(cluster_name=name, context=context, kubeconfig=str(self.path / 'kubeconfig.json'))
        cluster = self._cluster()
        write_json(lab_manager.contained_path(self.path, 'kubeconfig.json'), self._kube_document(cluster, data))
        print(self.activation())

    def activation(self):
        self._workspace()
        data = self._settings()
        if not data.get('kubeconfig') or not data.get('context'):
            raise RuntimeError('Apply Game 07 first to create its isolated Kubernetes context.')
        variables = {'KUBECONFIG': data['kubeconfig'], 'LAB_KUBE_CONTEXT': data['context'],
                     'AWS_PROFILE': data['profile'], 'AWS_REGION': data['region'], 'AWS_DEFAULT_REGION': data['region'],
                     'TF_VAR_expected_account_id': data['account_id'], 'TF_VAR_region': data['region'],
                     'TF_VAR_aws_profile': data['profile'], 'TF_VAR_cluster_name': data['cluster_name']}
        if data.get('lab_id'):
            variables['TF_VAR_lab_id'] = data['lab_id']
        text = '\n'.join(f'export {key}={shlex.quote(value)}' for key, value in variables.items()) + '\n'
        file = lab_manager.contained_path(self.path, 'session-env.sh')
        file.write_text(text)
        file.chmod(0o600)
        return text + '\n# Activate this same isolated session in your current shell:\nsource ' + shlex.quote(str(file))

    def _fingerprint(self):
        entries = {}
        excluded = {SETTINGS, PLAN_RECEIPT, '.arcade-session.json', 'kubeconfig.json', 'session-env.sh'}
        for directory, dirs, files in os.walk(self.path, followlinks=False):
            dirs[:] = sorted(name for name in dirs if name not in {'.terraform', '.git', '__pycache__'})
            if Path(directory) == self.path and self.terraform_root == '.' and self.alias in ROOT_ORDER:
                dirs[:] = [name for name in dirs if name not in self.roots]
            for name in dirs:
                if (Path(directory) / name).is_symlink():
                    raise RuntimeError('Refusing symlinked configuration directory.')
            for name in sorted(files):
                path = Path(directory) / name
                if name in excluded or name.endswith(('.tfstate', '.tfstate.backup')):
                    continue
                if path.suffix in {'.tf', '.json', '.tfvars', '.hcl', '.yaml', '.yml', '.py', '.sh'}:
                    entries[str(path.relative_to(self.path))] = digest(path)
        entries['runtimeIdentity'] = self._read(SETTINGS)
        # Status is operational bookkeeping, not reviewed Terraform input.
        entries['runtimeIdentity'] = {k: v for k, v in entries['runtimeIdentity'].items() if k not in {'status', 'baselineProof', 'baselineState'}}
        return hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()

    def _state_digest(self):
        path = lab_manager.contained_path(self.path, 'terraform.tfstate')
        return digest(path) if path.exists() else None

    def _local_backend(self):
        state = lab_manager.state_summary(self.path)
        if state['status'] not in {'local', 'no-local-state', 'invalid'}:
            raise RuntimeError('Unexpected Terraform backend/workspace; this workflow requires the registered default local state.')
        # invalid state is left to Terraform to diagnose; never overwrite it.
        workspace = self._tf('workspace', 'show', capture=True).strip()
        if workspace != 'default':
            raise RuntimeError('Unexpected Terraform workspace; select the registered default workspace before planning.')

    def _dependents(self):
        def depends(recipe, visited=None):
            visited = set() if visited is None else visited
            for identifier in lab_manager.environment_prerequisites(recipe):
                if identifier == self.recipe['id']:
                    return True
                if identifier not in visited:
                    visited.add(identifier)
                    if depends(lab_manager.find_recipe(self.recipes, identifier), visited):
                        return True
            return False
        blocked = []
        for recipe in self.recipes:
            if recipe['runDirectory'] and depends(recipe):
                try:
                    path = lab_manager.contained_path(self.root, 'run/' + recipe['runDirectory'])
                    if not path.exists():
                        continue
                    session = lab_manager.session_receipt(path, recipe)
                    observation = lab_manager.workspace_state(path, recipe, session['mode'])
                    if observation['managedObjects'] != 0:
                        blocked.append(recipe['alias'])
                except (OSError, ValueError):
                    blocked.append(recipe['alias'])
        if blocked:
            raise RuntimeError('Foundation destroy blocked by active or unknown dependent workspaces: ' + ', '.join(blocked) + '. Complete their Terraform cleanup and inspect disks first.')

    def _preflight(self, operation):
        identity = self._identity()
        context = None
        if self.alias in ROOT_ORDER:
            self._root_dependencies(operation)
        if self.workload:
            context = self._context()
            if operation != 'destroy':
                nodes = self._ready()
                if self.alias == '11-10' and self._read(SETTINGS).get('phase') == 'baseline':
                    node = nodes[0]
                    labels = node.get('metadata', {}).get('labels', {})
                    cpu = str(node.get('status', {}).get('allocatable', {}).get('cpu', '0'))
                    millicpu = float(cpu[:-1]) if cpu.endswith('m') else float(cpu) * 1000
                    if (len(nodes) != 1 or labels.get('role') != 'lab' or labels.get('node.kubernetes.io/instance-type') != 't3.medium'
                            or node.get('spec', {}).get('unschedulable') or not 1000 < millicpu < 2000):
                        raise RuntimeError('Scenario 11-10 baseline requires one Ready t3.medium worker with the authored CPU capacity.')
                    self._kubectl('get', 'pods', '-A', '-o', 'wide')
                    self._kubectl('describe', 'node', node['metadata']['name'])
                    print('Review requested-resource totals above. Clean other exercise workloads through their own Terraform before baseline apply.')
        elif self.alias == '07' and operation == 'destroy':
            self._dependents()
        return identity, context

    def plan(self, operation='apply'):
        if operation not in {'apply', 'destroy'}:
            raise RuntimeError('Operation must be apply or destroy.')
        with self._locked():
            identity, context = self._preflight(operation)
            settings = self._settings()
            if self.alias == '11-10' and settings.get('phase') == 'baseline' and operation == 'apply':
                if digest(self.path / 'candidate.yaml') != digest(self.path / 'baseline.yaml'):
                    raise RuntimeError('Scenario 11-10 must apply the healthy baseline before the broken update. Restore candidate.yaml from baseline.yaml explicitly.')
            print(f"\nOperation: {operation.upper()} | Account: {identity['account']} | Profile: {identity['profile'] or 'none'} | Region: {identity['region'] or 'local'}\nWorkspace: {self.path}\n{self.recipe['cost']}\nReview ownership and estimates before approval; estimates are not a billing cap.")
            init = ['init', '-input=false', '-no-color']
            if (self.path / '.terraform.lock.hcl').exists():
                init.append('-lockfile=readonly')
            self._tf(*init)
            self._local_backend()
            self._tf('validate', '-no-color')
            plan_name = 'arcade-destroy.tfplan' if operation == 'destroy' else 'arcade-apply.tfplan'
            plan_path = lab_manager.contained_path(self.path, plan_name)
            args = ['plan', '-input=false', '-no-color', f'-out={plan_path}']
            if operation == 'destroy':
                args.append('-destroy')
            if (self.path / INPUTS).exists():
                args.append(f'-var-file={self.path / INPUTS}')
            self._tf(*args)
            self._tf('show', '-no-color', str(plan_path))
            # The machine plan stays in process memory. Only the coach's allowlist
            # is displayed; JSON values are never stored as an extra artifact.
            from plan_review import review_plan, format_review
            document = json.loads(self._tf('show', '-json', str(plan_path), capture=True))
            review = review_plan(document)
            print(format_review(review))
            receipt = {'schemaVersion': 1, 'labId': self.recipe['id'], 'workspace': str(self.path),
                       'operation': operation, 'phase': settings.get('phase', 'practice'), 'planFile': plan_name,
                       'digest': digest(plan_path), 'fingerprint': self._fingerprint(),
                       'stateDigest': self._state_digest(), 'identity': identity, 'contextDigest': context, 'consumed': False,
                       'review': review}
            write_json(self.path / PLAN_RECEIPT, receipt)
            print(f'Reviewed plan saved. Apply saved plan requires typing {operation.upper()} {identity["account"]}.')
            return receipt

    def _check_plan(self, receipt):
        if (receipt.get('schemaVersion') != 1 or receipt.get('labId') != self.recipe['id']
                or receipt.get('workspace') != str(self.path) or receipt.get('consumed')
                or receipt.get('operation') not in {'apply', 'destroy'}):
            raise RuntimeError('Missing, used or mismatched saved plan. Plan again in this workspace.')
        expected = 'arcade-destroy.tfplan' if receipt['operation'] == 'destroy' else 'arcade-apply.tfplan'
        if receipt.get('planFile') != expected or digest(self.path / expected) != receipt.get('digest'):
            raise RuntimeError('Saved plan digest changed. Review a fresh plan before applying.')
        if self._fingerprint() != receipt.get('fingerprint') or self._state_digest() != receipt.get('stateDigest'):
            raise RuntimeError('Source, inputs, context or state changed after review. Plan again; existing state is preserved.')
        identity, context = self._preflight(receipt['operation'])
        if identity != receipt.get('identity') or context != receipt.get('contextDigest'):
            raise RuntimeError('Account, region or context changed after plan review. Plan again.')
        return identity

    def apply(self, confirm=input, *, plan_digest=None):
        with self._locked():
            receipt = self._read(PLAN_RECEIPT)
            if plan_digest is not None and receipt.get('digest') != plan_digest:
                raise RuntimeError('Saved plan digest differs from the reviewed plan. Review the current plan again.')
            identity = self._check_plan(receipt)
            phrase = receipt['operation'].upper() + ' ' + identity['account']
            print(f"Workspace: {self.path}\nProfile: {identity['profile'] or 'none'} | Region: {identity['region'] or 'local'}\nSaved operation: {receipt['operation']} | Account: {identity['account']}")
            if confirm(f'Type {phrase} to apply the reviewed binary (anything else cancels): ').strip() != phrase:
                print('Cancelled; no apply was run.')
                return False
            self._check_plan(receipt)
            self._local_backend()
            try:
                self._save(status='applying')
                self._tf('apply', '-input=false', '-no-color', str(self.path / receipt['planFile']))
                receipt['consumed'] = True
                write_json(self.path / PLAN_RECEIPT, receipt)
                self._save(status='destroyed' if receipt['operation'] == 'destroy' else 'applied')
                if receipt['operation'] == 'destroy':
                    if self.alias == '11-10':
                        self._save(phase='baseline', baselineProof=False, baselineState=None)
                    print(f'Terraform destroy completed. This does not prove AWS is empty. Complete named-resource/API absence and disk checks: {self.runbook}')
                elif self.alias == '07':
                    self._configure_kubeconfig()
                elif self.alias == '11-10' and receipt['phase'] == 'baseline':
                    self._save(baselineProof=False, baselineState=self._state_digest())
                    print('Baseline apply completed. Choose Verify for readiness and v1 HTTP proof before the broken update.')
                return True
            except (KeyboardInterrupt, OSError, ValueError) as exc:
                self._save(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed')
                raise RuntimeError(f'Operation did not complete all steps; state and inputs are preserved at {self.path}. Recover: inspect Terraform state and the runbook, then choose Plan (or Plan destroy) and review a fresh saved plan. Do not delete the workspace.') from exc

    def _baseline_http(self):
        self._kubectl('-n', 'arcade-incident-10', 'rollout', 'status', 'deployment/app', '--timeout=180s')
        self._kubectl('-n', 'arcade-incident-10', 'wait', '--for=condition=Ready', 'pod/arcade-diagnostics', '--timeout=180s')
        body = self._kubectl('-n', 'arcade-incident-10', 'exec', 'arcade-diagnostics', '--', 'wget', '-T', '3', '-O', '-', 'http://app:8080/', capture=True).strip()
        if body != 'arcade-10-v1':
            raise RuntimeError('Baseline HTTP proof failed: expected exactly arcade-10-v1. Keep this state and investigate; do not inject the update.')
        return body

    def begin_broken_update(self):
        with self._locked():
            if self.alias != '11-10':
                raise RuntimeError('This phase transition belongs only to scenario 11-10.')
            settings = self._settings()
            if (settings.get('phase') != 'baseline' or not settings.get('baselineProof')
                    or settings.get('baselineState') != self._state_digest()):
                raise RuntimeError('Apply and verify the healthy baseline first, retaining the same Terraform state.')
            self._preflight('apply')
            self._baseline_http()
            candidate = lab_manager.contained_path(self.path, 'candidate.yaml')
            if digest(candidate) != digest(self.path / 'baseline.yaml'):
                raise RuntimeError('Baseline candidate has learner edits; preserve them and follow the runbook explicitly.')
            source = lab_manager.contained_path(self.root, 'labs/' + self.recipe['id'] + '/starter/broken.yaml')
            candidate.write_bytes(source.read_bytes())
            self._save(phase='incident', baselineProof=True)
            print('Authored broken update prepared in the SAME Terraform state. Plan and approve it separately; no apply has run.')

    def verify(self):
        with self._locked():
            self._identity()
            self._tf('state', 'list')
            self._tf('output', '-no-color')
            result = {'scope': 'Local Terraform observations: state and outputs. These alone do not prove live health or cleanup.',
                      'runbook': str(self.runbook), 'liveChecks': []}
            settings = self._settings()
            if self.alias == '07' and settings.get('status') != 'destroyed':
                if not settings.get('context'):
                    self._configure_kubeconfig()
                self._ready()
                result['liveChecks'].append('EKS ACTIVE, four addons ACTIVE without reported issues, workers Ready at observation time')
            elif self.workload and settings.get('status') != 'destroyed':
                self._context()
                namespace = {'08': 'arcade-app', '09': 'arcade-identity', '10': 'arcade-storage',
                             '13': 'arcade-public'}.get(self.alias, 'arcade-incident-' + self.alias[-2:])
                self._kubectl('-n', namespace, 'get', 'pods', '-o', 'wide')
                result['liveChecks'].append('Kubernetes pod listing from the explicit lab context; not HTTP acceptance')
                if self.alias == '11-10' and settings.get('phase') == 'baseline':
                    if settings.get('status') != 'applied' or settings.get('baselineState') != self._state_digest():
                        raise RuntimeError('The baseline must be successfully applied in this same state before readiness proof.')
                    self._ready()
                    self._baseline_http()
                    self._save(baselineProof=True)
                    result['liveChecks'].append('BASELINE PASS: rollout ready and internal Service HTTP returned arcade-10-v1; not internet proof')
            print(json.dumps(result, indent=2))
            print(f'Complete the mission-specific live/API/HTTP acceptance and absence checks: {self.runbook}')
            return result
