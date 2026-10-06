"""The loopback job boundary: fixed actions, one operation, recoverable receipts."""
import threading
import unittest
from pathlib import Path
import json
import os
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch
from web.session import JobCoordinator, Busy


class FakeSession:
    gate = None
    calls = []
    def __init__(self, project, lab, root=None, runner=None):
        if lab != '00':
            raise ValueError('Unknown mission')
        self.lab, self.root = lab, root
    def describe(self):
        return {'id':self.lab,'root':self.root,'supported':True,'capabilities':['plan']}
    def perform(self, operation, **parameters):
        self.calls.append((operation, parameters))
        if self.gate:
            self.gate.wait(2)
        return {'status':'planned'}


class JobsTests(unittest.TestCase):
    def setUp(self):
        FakeSession.calls=[]
        FakeSession.gate=None
        self.jobs=JobCoordinator(Path('/tmp'), enabled=True, factory=FakeSession)
    def test_disabled_rejects_before_session_execution(self):
        jobs=JobCoordinator(Path('/tmp'),enabled=False,factory=FakeSession)
        with self.assertRaises(PermissionError):jobs.start({'lab':'00','operation':'plan'})
        self.assertEqual(FakeSession.calls,[])
    def test_request_cannot_supply_shell_path_or_arbitrary_parameters(self):
        for request in ({'lab':'00','operation':'shell'}, {'lab':'00','operation':'plan','path':'/tmp'}, {'lab':'00','operation':'plan','parameters':{'command':'touch /tmp/nope'}}, {'lab':'00','operation':'configure','parameters':{'account_id':4}}):
            with self.subTest(request=request),self.assertRaises(ValueError):self.jobs.start(request)
        self.assertEqual(FakeSession.calls,[])
    def test_one_operation_at_a_time_and_polling_retains_completion(self):
        FakeSession.gate=threading.Event()
        job=self.jobs.start({'lab':'00','operation':'plan'})
        with self.assertRaises(Busy):self.jobs.start({'lab':'00','operation':'plan_destroy'})
        self.assertEqual(self.jobs.active()['id'],job['id'])
        FakeSession.gate.set();self.jobs.wait(job['id'],3)
        result=self.jobs.get(job['id'])
        self.assertEqual(result['status'],'succeeded');self.assertEqual(result['result']['status'],'planned')
        self.assertEqual(FakeSession.calls,[('plan',{})])
    def test_apply_requires_both_human_approval_and_plan_binding(self):
        for params in ({},{'approval':'APPLY LOCAL'},{'plan_digest':'abc'}):
            with self.assertRaises(ValueError):self.jobs.start({'lab':'00','operation':'apply','parameters':params})


class BoundedReadTests(unittest.TestCase):
    def setUp(self):
        from lab_session import ReadRunner
        self.jobs=JobCoordinator(Path('/tmp'),enabled=True)
        self.jobs._jobs['read-test']={'events':[]}
        runtime=SimpleNamespace(runner=self.jobs._runner('read-test'),path=Path('/tmp'),_env=lambda:dict(os.environ))
        self.reader=ReadRunner(runtime)

    def test_cleanup_classifies_not_found_without_publishing_raw_provider_error(self):
        import verification
        raw='An error occurred (ResourceNotFoundException): private-provider-detail'
        observed=self.reader.run([sys.executable,'-c',f'import sys; sys.stderr.write({raw!r}); sys.exit(254)'])
        class Observations:
            def run(self,argv):
                return subprocess.CompletedProcess(argv,0,'{"Account":"123456789012"}','') if 'get-caller-identity' in argv else observed
        collector=verification.Collector(verification.Options('07-eks-foundation','cleanup','test','123456789012','us-west-2','owned-test'),Observations())
        collector.identity_and_cluster()
        absence=next(item for item in collector.checks if item['id']=='cluster-absent')
        self.assertEqual(absence['status'],'pass')
        self.assertNotIn('private-provider-detail',json.dumps(collector.checks))
        self.assertNotIn('private-provider-detail',json.dumps(self.jobs._jobs['read-test']['events']))

    def test_browser_observation_has_a_real_process_timeout(self):
        started=time.monotonic()
        with patch('web.session.READ_TIMEOUT',0.05,create=True):
            result=self.reader.run([sys.executable,'-c','import time; time.sleep(5)'])
        self.assertEqual(result.returncode,124)
        self.assertEqual(result.stderr,'ArcadeTimeout')
        self.assertLess(time.monotonic()-started,2)

    def test_browser_observation_bounds_combined_stdout_and_stderr(self):
        started=time.monotonic()
        with patch('verification.MAX_OUTPUT',64):
            result=self.reader.run([sys.executable,'-c','import sys,time; sys.stdout.write("x"*40); sys.stderr.write("y"*40); sys.stdout.flush(); sys.stderr.flush(); time.sleep(5)'])
        self.assertEqual(result.returncode,126)
        self.assertEqual(result.stderr,'ArcadeOutputLimit')
        self.assertEqual(result.stdout,'')
        self.assertLess(time.monotonic()-started,2)

    def test_missing_executable_remains_a_safe_verifier_result(self):
        result=self.reader.run(['/arcade-test-executable-that-does-not-exist'])
        self.assertEqual(result.returncode,127)
        self.assertEqual(result.stderr,'ArcadeToolMissing')

    def test_ordinary_tool_failures_do_not_expose_provider_stderr(self):
        runner=self.jobs._runner('read-test')
        result=runner([sys.executable,'-c','import sys; sys.stderr.write("private-provider-detail"); sys.exit(1)'],Path('/tmp'),dict(os.environ),capture=True)
        self.assertEqual(result.returncode,1)
        self.assertNotIn('private-provider-detail',result.stderr)
        self.assertNotIn('private-provider-detail',json.dumps(self.jobs._jobs['read-test']['events']))

class RunnerHTTPTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from web.server import create_server
        from web.tests.test_catalog import write_fixture
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        write_fixture(self.root, {'README.md':'# Kit','labs/00-example/README.md':'# Example'})
        (self.root/'web').mkdir()
        (self.root/'web/playbooks.json').write_text('{}')
        self.server=create_server(self.root,port=0,runner=True,session_factory=FakeSession)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.port=self.server.server_port
        FakeSession.gate=None;FakeSession.calls=[]
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(3);self.tmp.cleanup()
    def request(self,method,path,body=None,headers=None):
        import http.client,json
        connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3)
        connection.request(method,path,body=json.dumps(body) if body is not None else None,headers=headers or {})
        response=connection.getresponse();result=response.status,json.loads(response.read());connection.close();return result
    def headers(self):
        return {'Origin':f'http://127.0.0.1:{self.port}','Content-Type':'application/json','X-Arcade-Token':self.server.sessions.token}
    def test_token_origin_and_host_all_required_before_execution(self):
        body={'lab':'00','operation':'plan'}
        for change in ({'X-Arcade-Token':'bad'},{'Origin':'https://attacker.invalid'},{'Host':'attacker.invalid'},{'Origin':''}):
            headers=self.headers();headers.update(change)
            self.assertEqual(self.request('POST','/api/session/operation',body,headers)[0],403)
        self.assertEqual(FakeSession.calls,[])
    def test_valid_job_can_be_polled_after_reload(self):
        status,data=self.request('GET','/api/session?id=00')
        self.assertEqual(status,200);self.assertTrue(data['runnerEnabled'])
        status,job=self.request('POST','/api/session/operation',{'lab':'00','operation':'plan'},self.headers())
        self.assertEqual(status,202)
        self.server.sessions.wait(job['id'],3)
        status,data=self.request('GET','/api/session?id=00')
        self.assertEqual(data['job']['id'],job['id']);self.assertEqual(data['job']['status'],'succeeded')
    def test_invalid_operation_parameters_never_run(self):
        status,_=self.request('POST','/api/session/operation',{'lab':'00','operation':'plan','parameters':{'command':'whoami'}},self.headers())
        self.assertEqual(status,400);self.assertEqual(FakeSession.calls,[])


if __name__ == '__main__':
    unittest.main()
