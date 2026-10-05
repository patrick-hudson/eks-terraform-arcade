#!/usr/bin/env python3
"""Shared local session operations for CLI, TUI and the opt-in browser runner.

Session(project, lab, root=None, runner=None) accepts only registered recipes and
Terraform roots. describe() performs local reads only. perform() returns that same
projection after one fixed operation. Refusals raise ValueError (including the
runtime's RuntimeError); cloud tools run only for an explicit operation.
"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

import lab_manager
import lab_runtime
import verification

RECORD = '.arcade-session.json'
OPERATIONS = ('prepare', 'configure', 'plan', 'plan_destroy', 'apply', 'submit', 'verify', 'begin_incident')
EKS_HOURLY = 0.10 + 0.0416 + 20 * 0.08 / 730 + 0.005


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def costs(recipe):
    """Authored us-west-2 planning assumptions; never an account billing limit."""
    model = recipe.get('sessionEstimate', {})
    hourly = model.get('hourlyUsd', 0)
    shared = EKS_HOURLY if recipe['alias'] in {'08', '09', '10', '12', '13'} or recipe['alias'].startswith('11') else 0
    if recipe['alias'] == '07':
        hourly = EKS_HOURLY
    return {'currency': 'USD', 'region': 'us-west-2', 'asOf': '2026-10-04',
            'hourlyUsd': round(hourly + shared, 4), 'incrementalHourlyUsd': round(hourly, 4),
            'sharedHourlyUsd': round(shared, 4), 'oneHourUsd': round(hourly + shared, 4),
            'twoHoursUsd': round(2 * (hourly + shared), 4),
            'assumptions': model.get('assumptions', []) + ([
                'Shared Game 07: standard-support EKS $0.10/hour, one t3.medium $0.0416/hour, 20 GiB gp3 at $0.08/GiB-month (730 hours), one public IPv4 $0.005/hour.',
                'Count an existing EKS foundation once across simultaneous exercises.'
            ] if shared or recipe['alias'] == '07' else []),
            'activityBased': model.get('activityBased', 'Requests, transfer, storage and startup time can change the total.'),
            'notice': 'Estimate, not a billing cap. Resources can bill until cleanup finishes.',
            'description': recipe['cost']}


class ReadRunner:
    """Adapt the bounded verifier to the runtime's isolated credentials/context."""
    def __init__(self, runtime):
        self.runtime = runtime

    def run(self, argv):
        runtime = self.runtime
        try:
            if runtime.runner is not lab_runtime.command_runner:
                # Browser jobs provide a bounded read path distinct from long
                # Terraform operations. Injected test runners keep the same API.
                runner = getattr(runtime.runner, 'read', runtime.runner)
                result = runner(argv, runtime.path, runtime._env(), capture=True)
            else:
                result = subprocess.run(argv, cwd=runtime.path, env=runtime._env(), shell=False,
                                        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=35)
        except FileNotFoundError:
            return subprocess.CompletedProcess(argv, 127, '', 'ArcadeToolMissing')
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(argv, 124, '', 'ArcadeTimeout')
        except (OSError, UnicodeError):
            return subprocess.CompletedProcess(argv, 126, '', 'ArcadeProcessError')
        if len(result.stdout) + len(result.stderr) > verification.MAX_OUTPUT:
            return subprocess.CompletedProcess(argv, 126, '', 'ArcadeOutputLimit')
        return result


class Session:
    def __init__(self, project, lab, root=None, runner=None):
        self.runtime = lab_runtime.Runtime(project, lab, runner=runner, terraform_root=root)
        self.recipe = self.runtime.recipe

    def _record(self):
        return self.runtime._read(RECORD) if self.runtime.path and self.runtime.path.is_dir() else {}

    def _fingerprint(self):
        return self.runtime._fingerprint()

    def _inventory(self, previous=None):
        runtime = self.runtime
        saved = previous or {}
        resources = {(item['address'], item.get('id')): item for item in saved.get('resources', [])}
        status = 'no-local-state'
        if runtime.path and runtime.path.is_dir():
            status = lab_manager.state_summary(runtime.path)['status']
            path = lab_manager.contained_path(runtime.path, 'terraform.tfstate')
            if status == 'local' and path.exists():
                state = lab_manager.read_json(path)
                for resource in state.get('resources', []):
                    if resource.get('mode') != 'managed':
                        continue
                    prefix = resource.get('module', '')
                    address = '.'.join(x for x in (prefix, resource.get('type'), resource.get('name')) if x)
                    for instance in resource.get('instances', []):
                        attributes = instance.get('attributes', {})
                        selector = '[' + json.dumps(instance['index_key']) + ']' if 'index_key' in instance else ''
                        item = {'address': address + selector, 'type': resource.get('type', 'unknown'),
                                'root': runtime.terraform_root, 'id': attributes.get('id'), 'arn': attributes.get('arn')}
                        # IDs/ARNs are metadata; never copy arbitrary attributes,
                        # outputs, credentials, object bodies or entire state.
                        for key in ('id', 'arn'):
                            item[key] = item[key][:2048] if isinstance(item[key], str) else None
                        resources[(item['address'], item['id'])] = item
        return {'resources': list(resources.values()), 'stateStatus': status,
                'absence': saved.get('absence', 'unknown'),
                'scope': 'Retained Terraform resource identifiers, including prior observations. Empty state is not verified cloud absence.'}

    def _save(self, record):
        runtime = self.runtime
        if runtime.path and runtime.path.is_dir():
            runtime._workspace(supported=False)
            lab_runtime.write_json(runtime.path / RECORD, record)

    def _public_plan(self):
        runtime = self.runtime
        receipt = runtime._read(lab_runtime.PLAN_RECEIPT)
        if not receipt:
            return None
        try:
            stale = (receipt.get('fingerprint') != self._fingerprint()
                     or receipt.get('stateDigest') != runtime._state_digest()
                     or receipt.get('digest') != lab_runtime.digest(runtime.path / receipt['planFile']))
        except (OSError, ValueError, KeyError):
            stale = True
        identity = receipt.get('identity', {})
        from plan_review import format_review
        review = receipt.get('review')
        return {'operation': receipt.get('operation'), 'digest': receipt.get('digest'),
                'approval': receipt.get('operation', '').upper() + ' ' + identity.get('account', ''),
                'identity': identity, 'consumed': receipt.get('consumed', False), 'stale': stale,
                'sourceChanged': receipt.get('fingerprint') != self._fingerprint(),
                'review': review, 'reviewText': format_review(review) if review else 'Create a fresh plan to view its metadata summary.',
                'scope': 'Values and sensitive outputs are omitted. Review private plan details in the terminal when needed.'}

    def describe(self):
        runtime = self.runtime
        info = runtime.describe()
        record = self._record() if info['prepared'] else {}
        mode = (runtime._workspace(supported=False)['mode'] if info['prepared'] else next(iter(self.recipe['modes']), None))
        runbook = self.recipe['modes'].get(mode, {})
        settings = runtime._read(lab_runtime.SETTINGS) if info['prepared'] else {}
        status = settings.get('status', 'prepared' if info['prepared'] else 'not prepared')
        plan = self._public_plan() if info['prepared'] else None
        repair = record.get('repair')
        if repair:
            repair = dict(repair)
            try:
                repair['stale'] = (repair.get('sourceFingerprint') != self._fingerprint()
                                   or repair.get('stateDigest') != runtime._state_digest())
            except (OSError, ValueError):
                repair['stale'] = True
        if status != 'applying' and plan and not plan['consumed'] and not plan['stale']:
            status = 'planned'
        next_action = 'prepare' if not info['prepared'] else 'plan'
        if info['prepared'] and runtime.alias != '00' and not settings.get('profile'):
            next_action = 'configure'
        if status == 'planned':
            next_action = 'review and approve'
        elif status in {'applied', 'failed', 'interrupted', 'applying'}:
            next_action = 'submit repair or plan cleanup'
        elif status == 'destroyed':
            next_action = 'verify named-resource absence'
        if plan and not plan['consumed'] and plan['stale']:
            next_action = 'plan'
        applied_source = record.get('appliedSourceFingerprint')
        if info['prepared'] and applied_source and status != 'destroyed' and applied_source != self._fingerprint():
            next_action = 'plan'
        if not runtime.supported:
            next_action = 'follow the ordered runbook'
        if settings.get('cleanupOnly') and status not in {'planned', 'destroyed', 'applying'}:
            next_action = 'plan cleanup or configure for practice'
        if status == 'applying':
            next_action = 'wait for the current operation'
        capabilities = list(OPERATIONS[:-1]) if runtime.supported else (['prepare'] if runtime.path else [])
        if runtime.alias == '11-10':
            capabilities.append('begin_incident')
        cleanup = [{'lab': runtime.alias, 'root': root} for root in reversed(runtime.roots)]
        cleanup += [{'lab': item['alias'], 'root': '.'} for item in reversed(info['prerequisites'])]
        requirements = list(info['prerequisites'])
        if runtime.alias in lab_runtime.ROOT_ORDER:
            for parent in runtime.roots[:runtime.roots.index(runtime.terraform_root)]:
                sibling = runtime._sibling(parent)
                requirements.append({'recipeId': self.recipe['id'], 'alias': runtime.alias, 'root': parent,
                                     'title': 'Prerequisite Terraform root ' + parent,
                                     'path': str(sibling.path), 'status': 'Apply and verify this root before continuing.'})
        return {**info, 'id': self.recipe['id'], 'alias': runtime.alias, 'title': self.recipe['title'],
                'root': runtime.terraform_root, 'roots': list(runtime.roots), 'capabilities': capabilities,
                'status': status, 'nextAction': next_action, 'prerequisites': requirements,
                'cleanupOrder': cleanup, 'costs': costs(self.recipe),
                'inventory': self._inventory(record.get('inventory')),
                'lastOperation': record.get('lastOperation'), 'repair': repair, 'plan': plan,
                'runbookSteps': runbook.get('steps', []), 'runbookCleanup': runbook.get('cleanup', []),
                'runbookText': runtime.runbook.read_text(encoding='utf-8') if runtime.runbook.is_file() else '',
                'configuration': {key: (runtime._read(lab_runtime.INPUTS) if key in {'admin_principal_arn', 'allowed_cidr'} else settings).get(key)
                                  for key in ('profile', 'account_id', 'region', 'lab_id', 'admin_principal_arn', 'allowed_cidr')} if info['prepared'] else {},
                'modes': list(self.recipe['modes']), 'mode': mode}

    def _local_checks(self):
        runtime = self.runtime
        path = lab_manager.contained_path(runtime.path, 'terraform.tfstate')
        state = lab_manager.read_json(path) if path.exists() else {}
        allocations = state.get('outputs', {}).get('allocations', {}).get('value')
        services = []
        keyed = True
        for resource in state.get('resources', []):
            if resource.get('mode') == 'managed' and resource.get('type') == 'terraform_data' and resource.get('name') == 'service':
                for instance in resource.get('instances', []):
                    attributes = instance.get('attributes', {})
                    output = attributes.get('output', {}).get('value', {})
                    source = attributes.get('input', {}).get('value', {})
                    services.append(output)
                    keyed = keyed and isinstance(output, dict) and instance.get('index_key') == output.get('name') and source == output
        valid = bool(services) and all(isinstance(item, dict) and isinstance(item.get('name'), str)
                 and re.fullmatch(r'[a-z][a-z0-9-]+', item['name'])
                 and isinstance(item.get('memory_mib'), (int, float)) and not isinstance(item['memory_mib'], bool)
                 and 64 <= item['memory_mib'] <= 2048 and item['memory_mib'] % 64 == 0 for item in services)
        if valid:
            expected = {item['name']: item['memory_mib'] for item in services}
            valid = len(expected) == len(services) and sum(expected.values()) <= 4096 and allocations == expected and keyed
        return [{'id': 'local-contract', 'label': 'Applied service allocations', 'status': 'pass' if valid else 'fail',
                 'expected': 'Applied services use stable name keys, valid 64–2048 MiB requests, a 4096 MiB total budget, and matching allocations.',
                 'observed': 'Applied state and output satisfy the Game 00 contract.' if valid else 'Applied state/output does not establish the Game 00 contract. Plan and apply the Terraform repair.'}]

    def submit(self):
        runtime = self.runtime
        runtime._workspace()
        with runtime._locked():
            fingerprint = self._fingerprint()
            phase = 'cleanup' if runtime._read(lab_runtime.SETTINGS).get('status') == 'destroyed' else 'verify'
            scope = 'Point-in-time checks of this registered workspace; this is separate from self-reported study completion.'
            try:
                if runtime.alias == '00':
                    checks = self._local_checks() if phase == 'verify' else [
                        {'id': 'local-cleanup', 'label': 'Local Terraform state',
                         'status': 'pass' if lab_manager.state_summary(runtime.path)['managedObjects'] == 0 else 'fail',
                         'expected': 'No managed local objects.', 'observed': 'Local state inspected; no AWS resources are used by Game 00.'}]
                elif self.recipe['id'] in verification.LABS:
                    settings = runtime._settings()
                    options = verification.Options(self.recipe['id'], phase, settings['profile'], settings['account_id'],
                                                   settings['region'], settings.get('cluster_name', ''), settings.get('context', ''))
                    evidence = verification.collect_receipt(options, ReadRunner(runtime))
                    checks, scope = evidence['checks'], evidence['scope']
                    if phase == 'verify' and runtime.alias in {'08', '11-08'}:
                        checks.append({'id': 'functional-acceptance', 'label': 'Remaining behavioral acceptance', 'status': 'unknown',
                                       'expected': 'Complete the mission-specific functional runbook checks.',
                                       'observed': 'Read-only API checks do not execute HTTP, eviction, or mutation-based checks. These acceptance steps remain unverified.'})
                else:
                    checks = [{'id': 'behavior-not-automated', 'label': 'Behavioral acceptance', 'status': 'unknown',
                               'expected': 'Follow this mission\'s ordered runbook acceptance checks.',
                               'observed': 'This mission has no automated behavioral checker; a successful apply does not pass the exercise.'}]
            except (OSError, ValueError, KeyError) as exc:
                checks = [{'id': 'observation-unavailable', 'label': 'Read-only verification', 'status': 'unknown',
                           'expected': 'Successful bounded observations in the configured environment.',
                           'observed': 'The checks could not complete. Inspect identity, tools, context and the runbook; no repair was applied.'}]
            receipt = runtime._read(lab_runtime.PLAN_RECEIPT)
            applied_source = self._record().get('appliedSourceFingerprint')
            if not applied_source and receipt.get('consumed'):
                applied_source = receipt.get('fingerprint')
            if phase == 'verify' and applied_source and applied_source != fingerprint:
                checks.append({'id': 'applied-source', 'label': 'Deployed source matches submission', 'status': 'unknown',
                               'expected': 'Current source has a reviewed successful apply.',
                               'observed': 'Source changed since the applied plan. Plan and apply the Terraform repair before submitting again.'})
            status = 'fail' if any(c['status'] == 'fail' for c in checks) else 'unknown' if any(c['status'] in {'unknown', 'error'} for c in checks) else 'pass'
            result = {'schemaVersion': 1, 'kind': 'arcade-repair-check', 'labId': self.recipe['id'], 'root': runtime.terraform_root,
                      'generatedAt': now(), 'phase': phase, 'sourceFingerprint': fingerprint, 'stale': False,
                      'stateDigest': runtime._state_digest(),
                      'status': status, 'checks': checks, 'scope': scope}
            record = self._record()
            record['repair'] = result
            self._save(record)
            return result

    def perform(self, operation, **parameters):
        if operation not in self.describe()['capabilities']:
            raise ValueError('Operation is unavailable for this mission; use its ordered runbook.')
        runtime = self.runtime
        before = self._record()
        before['inventory'] = self._inventory(before.get('inventory'))
        if self.describe()['prepared']:
            self._save(before)
        result = None
        try:
            if operation == 'prepare':
                runtime.prepare(**parameters)
            elif operation == 'configure':
                result = runtime.configure(**parameters)
            elif operation in {'plan', 'plan_destroy'}:
                if parameters:
                    raise ValueError('Plan takes no additional parameters.')
                result = runtime.plan('destroy' if operation == 'plan_destroy' else 'apply')
            elif operation == 'apply':
                approval, requested_digest = parameters.pop('approval', None), parameters.pop('plan_digest', None)
                if parameters or not isinstance(approval, str):
                    raise ValueError('Apply requires the displayed approval phrase and plan digest.')
                receipt = runtime._read(lab_runtime.PLAN_RECEIPT)
                if not requested_digest or receipt.get('digest') != requested_digest:
                    raise ValueError('The saved plan digest differs from the reviewed plan. Review the current plan again.')
                result = runtime.apply(confirm=lambda _: approval, plan_digest=requested_digest)
            elif operation == 'submit':
                if parameters:
                    raise ValueError('Submit takes no additional parameters.')
                result = self.submit()
            elif operation == 'verify':
                if parameters:
                    raise ValueError('Verify takes no additional parameters.')
                # Preserve scenario 11-10\'s existing baseline phase gate.
                result = runtime.verify() if runtime.alias == '11-10' else self.submit()
            elif operation == 'begin_incident':
                if parameters:
                    raise ValueError('Begin incident takes no additional parameters.')
                result = runtime.begin_broken_update()
        except (KeyboardInterrupt, OSError, ValueError, TypeError):
            record = self._record()
            record['inventory'] = self._inventory(before.get('inventory'))
            record['lastOperation'] = {'operation': operation, 'status': 'failed', 'finishedAt': now(),
                                       'message': 'Operation did not finish. Workspace, state and prior inventory are retained; inspect the terminal and runbook.'}
            self._save(record)
            raise
        record = self._record()
        record['inventory'] = self._inventory(before.get('inventory'))
        if operation == 'apply' and result:
            record['appliedSourceFingerprint'] = self._fingerprint()
        record['lastOperation'] = {'operation': operation, 'status': 'cancelled' if result is False else 'succeeded', 'finishedAt': now()}
        self._save(record)
        return self.describe()


def main(argv=None, project=lab_runtime.ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['catalog', 'status', *OPERATIONS])
    parser.add_argument('lab', nargs='?')
    parser.add_argument('--root', help='Registered Terraform root, such as workload or access')
    parser.add_argument('--mode', choices=['starter', 'guided'])
    parser.add_argument('--profile')
    parser.add_argument('--account-id')
    parser.add_argument('--region', default='us-west-2')
    parser.add_argument('--lab-id')
    parser.add_argument('--admin-principal-arn')
    parser.add_argument('--allowed-cidr')
    parser.add_argument('--approval')
    parser.add_argument('--plan-digest')
    args = parser.parse_args(argv)
    try:
        if args.operation == 'catalog':
            result = [Session(project, recipe['id']).describe() for recipe in lab_manager.load_recipes(Path(project))]
        else:
            if not args.lab:
                parser.error('a lab ID is required')
            session = Session(project, args.lab, root=args.root)
            parameters = {}
            if args.operation == 'prepare':
                parameters['mode'] = args.mode
            elif args.operation == 'configure':
                parameters = {key: getattr(args, key) for key in ('profile', 'account_id', 'region', 'lab_id', 'admin_principal_arn', 'allowed_cidr')}
            elif args.operation == 'apply':
                parameters = {'approval': args.approval, 'plan_digest': args.plan_digest}
                if parameters['approval'] is None:
                    plan = session.describe()['plan'] or {}
                    print(plan.get('reviewText', 'Plan first.'), file=sys.stderr)
                    parameters['approval'] = input('Type ' + plan.get('approval', 'the displayed phrase') + ': ')
                    parameters['plan_digest'] = plan.get('digest')
            with contextlib.redirect_stdout(sys.stderr):
                result = session.describe() if args.operation == 'status' else session.perform(args.operation, **parameters)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f'Session stopped: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
