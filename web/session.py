"""Opt-in local session jobs. No browser-supplied command or filesystem path."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
import time

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

OPERATIONS = {
    'prepare': {'mode'},
    'configure': {'profile', 'account_id', 'region', 'lab_id', 'admin_principal_arn', 'allowed_cidr'},
    'plan': set(), 'plan_destroy': set(),
    'apply': {'approval', 'plan_digest'},
    'submit': set(), 'verify': set(), 'begin_incident': set(),
}
READ_TIMEOUT = 35


def session_factory(*args, **kwargs):
    from lab_session import Session
    return Session(*args, **kwargs)


def now():
    return datetime.now(timezone.utc).isoformat()


class Busy(RuntimeError):
    pass


class JobCoordinator:
    def __init__(self, project, *, enabled=False, factory=None):
        self.project = Path(project)
        self.enabled = enabled
        self.token = secrets.token_urlsafe(32) if enabled else None
        self.factory = factory or session_factory
        self._lock = threading.RLock()
        self._jobs = OrderedDict()
        self._threads = {}
        self._active = None

    def describe(self, lab, root=None):
        with self._lock:
            if self._active:
                active = self._jobs[self._active]
                # Avoid reading state while Terraform is writing it. The last
                # receipt remains visible until the operation ends.
                if lab in {active['lab'], active['before'].get('id'), active['before'].get('alias')} and root in {None, active['root'], active['before'].get('root')}:
                    return active['before']
            return self.factory(self.project, lab, root=root).describe()

    @staticmethod
    def validate(request):
        if not isinstance(request, dict) or set(request) - {'lab', 'root', 'operation', 'parameters'}:
            raise ValueError('Supply a mission, operation and its named parameters.')
        if not isinstance(request.get('lab'), str) or not 1 <= len(request['lab']) <= 100:
            raise ValueError('Choose a mission from the catalog.')
        root = request.get('root')
        if root is not None and (not isinstance(root, str) or root not in {'.', 'workload', 'access'}):
            raise ValueError('Choose one of this mission’s Terraform roots.')
        operation = request.get('operation')
        if not isinstance(operation, str) or operation not in OPERATIONS:
            raise ValueError('Unknown session operation.')
        parameters = request.get('parameters', {})
        if not isinstance(parameters, dict) or set(parameters) - OPERATIONS[operation]:
            raise ValueError('Unknown operation parameter.')
        if any(not isinstance(v, str) or len(v) > 512 or '\x00' in v for v in parameters.values()):
            raise ValueError('Operation parameters must be short text values.')
        if operation == 'apply' and not all(parameters.get(k) for k in ('approval', 'plan_digest')):
            raise ValueError('Review a saved plan and supply its exact approval and digest.')
        return request['lab'], root, operation, parameters

    def start(self, request):
        if not self.enabled:
            raise PermissionError('Start arcade serve --runner to enable local operations.')
        lab, root, operation, parameters = self.validate(request)
        with self._lock:
            if self._active:
                raise Busy('An operation is already running. Wait for its result before starting another.')
            before = self.factory(self.project, lab, root=root).describe()
            job_id = secrets.token_hex(12)
            job = {'id':job_id, 'lab':lab, 'root':root, 'operation':operation,
                   'status':'running', 'startedAt':now(), 'finishedAt':None,
                   'events':[f'{operation.replace("_", " ").capitalize()} started.'],
                   'before':before, 'result':None, 'error':None}
            self._jobs[job_id] = job
            self._active = job_id
            while len(self._jobs) > 30:
                old, _ = self._jobs.popitem(last=False)
                self._threads.pop(old, None)
            worker = threading.Thread(target=self._execute, args=(job_id, parameters), daemon=False)
            self._threads[job_id] = worker
            worker.start()
            return self.get(job_id)

    def _event(self, job_id, text):
        with self._lock:
            self._jobs[job_id]['events'].append(text[:300])
            self._jobs[job_id]['events'] = self._jobs[job_id]['events'][-100:]

    def _runner(self, job_id):
        def run(args, cwd, env, *, capture=False, timeout=None, max_output=16 * 1024 * 1024, raw_diagnostics=False):
            tool = Path(args[0]).name
            command = args[1] if len(args) > 1 and not args[1].startswith('-') else 'check'
            self._event(job_id, f'Running {tool} {command}…')
            # Terraform plan/state JSON can contain secrets. Tool output never
            # enters a browser job log; only the shared metadata projection does.
            with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
                process = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
                def stop():
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                        process.wait(timeout=10)
                    except (subprocess.TimeoutExpired, ProcessLookupError):
                        pass
                    finally:
                        # Include descendants that outlive the main process.
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait()
                try:
                    if timeout is None:
                        process.wait()
                    else:
                        deadline = time.monotonic() + timeout
                        while True:
                            if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > max_output:
                                stop()
                                self._event(job_id, f'{tool} {command}: observation output limit reached.')
                                return subprocess.CompletedProcess(args, 126, '', 'ArcadeOutputLimit')
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                raise subprocess.TimeoutExpired(args, timeout)
                            try:
                                process.wait(timeout=min(0.1, remaining))
                                break
                            except subprocess.TimeoutExpired:
                                continue
                except BaseException:
                    stop()
                    raise
                stdout, stderr = '', ''
                if capture:
                    out.seek(0)
                    data = out.read(max_output + 1)
                    err.seek(0)
                    errors = err.read(max_output + 1) if raw_diagnostics else b''
                    if len(data) + len(errors) > max_output:
                        if raw_diagnostics:
                            return subprocess.CompletedProcess(args, 126, '', 'ArcadeOutputLimit')
                        raise RuntimeError('Tool output exceeded the local reader limit. Inspect the workspace in a terminal.')
                    stdout = data.decode('utf-8', errors='replace')
                    stderr = errors.decode('utf-8', errors='replace')
                self._event(job_id, f'{tool} {command}: ' + ('finished.' if process.returncode == 0 else f'exit {process.returncode}.'))
                diagnostic = stderr if raw_diagnostics else '' if process.returncode == 0 else 'Inspect this registered workspace in the terminal for tool diagnostics; state is preserved.'
                return subprocess.CompletedProcess(args, process.returncode, stdout, diagnostic)
        def read(args, cwd, env, *, capture=True):
            import verification
            # Raw errors stay inside the bounded verifier, which maps them to
            # fixed public messages (including named-resource absence).
            return run(args, cwd, env, capture=capture, timeout=READ_TIMEOUT,
                       max_output=verification.MAX_OUTPUT, raw_diagnostics=True)
        run.read = read
        return run

    def _execute(self, job_id, parameters):
        job = self._jobs[job_id]
        try:
            session = self.factory(self.project, job['lab'], root=job['root'], runner=self._runner(job_id))
            result = session.perform(job['operation'], **parameters)
            with self._lock:
                job['result'] = result
                job['status'] = 'succeeded'
        except Exception as exc:
            with self._lock:
                job['status'] = 'failed'
                job['error'] = str(exc)[:2000] if isinstance(exc, (ValueError, RuntimeError, OSError)) else 'Operation failed. Inspect the workspace and retain its state.'
        finally:
            with self._lock:
                job['finishedAt'] = now()
                self._active = None

    def get(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise ValueError('Job not found in this server session.')
            return {**job, 'events':list(job['events'])}

    def active(self):
        with self._lock:
            return self.get(self._active) if self._active else None

    def latest(self, lab):
        with self._lock:
            return next((self.get(key) for key, value in reversed(self._jobs.items()) if value['lab'] == lab), None)

    def wait(self, job_id, timeout=None):
        self._threads[job_id].join(timeout)
