"""Real PTY keyboard/resize proof plus stream-suspension failure tests."""
import contextlib
import fcntl
import io
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import sys
import termios
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import arcade_tui as tui
ROOT = Path(__file__).resolve().parents[2]


class TuiTests(unittest.TestCase):
    def desk(self):
        screen = Mock()
        screen.getmaxyx.return_value = (30, 110)
        with patch.object(tui.curses, 'has_colors', return_value=False), \
             patch.object(tui.curses, 'curs_set'), patch.object(tui.curses, 'set_escdelay'):
            return tui.Desk(screen, ROOT)

    def test_catalog_search_matches_symptoms_and_preserves_return_position(self):
        desk = self.desk()
        desk.queries['missions'] = 'imagepullbackoff'
        matches = desk.choices()
        self.assertIn('11-01', [value['alias'] for _, (_, value) in matches])
        desk.queries['missions'] = 'public path'
        self.assertEqual(desk.choices()[0][1][1]['alias'], '13')
        desk.activate()
        self.assertEqual(desk.selected['alias'], '13')
        desk.back()
        self.assertEqual(desk.queries['missions'], 'public path')
        self.assertEqual(desk.choices()[desk.index][1][1]['alias'], '13')
        desk.queries['missions'] = 'no-such-symptom-ever'
        self.assertEqual(desk.choices(), [])
        desk.activate()  # An empty search never starts a command.

    def test_search_editing_keeps_shortcuts_as_text_and_cancels_cleanly(self):
        desk = self.desk()
        desk.searching = True
        desk.search_before = 'eks'
        for character in 'query backoff':
            desk.search_key(ord(character))
        self.assertTrue(desk.running)
        self.assertEqual(desk.queries['missions'], 'query backoff')
        desk.search_key(27)
        self.assertFalse(desk.searching)
        self.assertEqual(desk.queries['missions'], 'eks')
        desk.searching = True
        desk.search_key(21)
        desk.search_key(ord('0'))
        desk.search_key(ord('7'))
        desk.search_key(10)
        self.assertEqual(desk.choices()[0][1][1]['alias'], '07')

    def test_roots_and_prerequisites_target_the_registered_workspace(self):
        desk = self.desk()
        desk.push('mission', tui.lab_manager.find_recipe(desk.recipes, '13'))
        self.assertEqual(desk.session().describe()['root'], 'workload')
        desk.push('roots', desk.selected)
        desk.index = 1
        desk.activate()
        self.assertEqual(desk.view, 'mission')
        self.assertEqual(desk.session().describe()['root'], 'access')
        desk.index = next(i for i, (_, (action, value)) in enumerate(desk.choices())
                          if action == 'prerequisite' and value['alias'] == '07')
        desk.activate()
        self.assertEqual(desk.selected['alias'], '07')
        self.assertEqual(desk.session().describe()['root'], '.')
        desk.back()
        self.assertEqual(desk.session().describe()['root'], 'access')

    def test_apply_binds_explicit_approval_to_displayed_plan(self):
        session = Mock()
        plan = {'digest': 'reviewed-digest', 'approval': 'APPLY 123456789012',
                'stale': False, 'consumed': False, 'reviewText': 'Create two owned resources.',
                'scope': 'Metadata only; inspect values in the terminal.'}
        session.describe.return_value = {'plan': plan}
        with contextlib.redirect_stdout(io.StringIO()) as output:
            tui.apply_session(session, input_fn=lambda _: 'APPLY 123456789012')
        session.perform.assert_called_once_with('apply', approval='APPLY 123456789012',
                                                plan_digest='reviewed-digest')
        self.assertIn('Create two owned resources.', output.getvalue())
        for invalid in (None, {**plan, 'stale': True}, {**plan, 'consumed': True}):
            session.reset_mock()
            session.describe.return_value = {'plan': invalid}
            with self.assertRaises(ValueError):
                tui.apply_session(session, input_fn=Mock(side_effect=AssertionError('must not prompt')))
            session.perform.assert_not_called()

    def test_repair_costs_and_inventory_keep_the_shared_result_meaning(self):
        repair = {'status': 'unknown', 'stale': True, 'generatedAt': '2026-10-04T12:00:00Z',
                  'phase': 'verify', 'scope': 'HTTP remains unchecked.',
                  'checks': [{'label': 'HTTP request', 'status': 'unknown',
                              'expected': 'Returns 200', 'observed': 'Not observed'}]}
        text = '\n'.join(tui.repair_lines({'repair': repair}))
        for token in ('STALE', 'UNKNOWN', 'HTTP remains unchecked.', 'Not observed'):
            self.assertIn(token, text)
        self.assertIn('No repair', '\n'.join(tui.repair_lines({'repair': None})))
        inventory = {'absence': 'unknown', 'stateStatus': 'empty',
                     'scope': 'Empty state is not verified cloud absence.',
                     'resources': [{'address': 'aws_thing.demo', 'root': '.', 'type': 'aws_thing',
                                    'id': 'owned-id', 'arn': 'arn:aws:example:owned'}]}
        text = '\n'.join(tui.inventory_lines({'inventory': inventory, 'lastOperation':
                                            {'operation': 'apply', 'status': 'failed', 'finishedAt': 'now'}}))
        for token in ('owned-id', 'arn:aws:example:owned', 'unknown', 'failed', inventory['scope']):
            self.assertIn(token, text)
        costs = tui.Session(ROOT, '13').describe()['costs']
        text = '\n'.join(tui.cost_lines(costs))
        self.assertIn(f"${costs['oneHourUsd']:.3f}", text)
        self.assertIn(f"${costs['twoHoursUsd']:.3f}", text)
        self.assertIn(costs['notice'], text)

    def test_configure_and_cleanup_use_shared_session_operations(self):
        session = Mock()
        session.runtime.workload = True
        session.describe.return_value = {'alias': '13', 'root': 'access', 'configuration':
                                         {'profile': 'sandbox', 'account_id': '123456789012',
                                          'region': 'us-west-2', 'allowed_cidr': '203.0.113.4/32'}}
        with contextlib.redirect_stdout(io.StringIO()):
            tui.configure_session(session, input_fn=lambda _: '')
        session.perform.assert_called_once_with('configure', profile='sandbox', account_id='123456789012',
                                                region='us-west-2', allowed_cidr='203.0.113.4/32')
        desk = self.desk()
        desk.push('mission', tui.lab_manager.find_recipe(desk.recipes, '13'))
        facade = tui.Session(ROOT, '13')
        with patch.object(desk, 'session', return_value=facade), \
             patch.object(facade, 'perform') as perform, \
             patch.object(tui, 'run_external', side_effect=lambda screen, operation: operation()):
            desk.index = next(i for i, (_, (action, _)) in enumerate(desk.choices()) if action == 'plan_destroy')
            desk.activate()
        perform.assert_called_once_with('plan_destroy')

    def test_ordered_runbook_keeps_commands_and_cleanup_for_manual_missions(self):
        for alias in ('02', '06', '12', '13'):
            details = tui.Session(ROOT, alias).describe()
            lines = '\n'.join(tui.runbook_lines(details))
            self.assertIn('Cleanup order', lines)
            for step in details['runbookSteps'] + details['runbookCleanup']:
                self.assertIn(step['title'], lines)
                self.assertIn(step['command'], lines)
            self.assertIn(Path(details['runbook']).read_text().strip(), lines)

    def test_non_tty_returns_actionable_help_without_waiting(self):
        output = io.StringIO()
        with patch('sys.stdin.isatty', return_value=False), contextlib.redirect_stdout(output):
            self.assertEqual(tui.main([],root=ROOT),2)
        self.assertIn('terminal',output.getvalue().lower())
        self.assertIn('drill',output.getvalue().lower())

    def test_missing_curses_returns_help_without_waiting(self):
        output=io.StringIO()
        with patch.object(tui,'curses',None), patch('sys.stdin.isatty',return_value=True), patch('sys.stdout.isatty',return_value=True),contextlib.redirect_stdout(output):
            self.assertEqual(tui.main([],root=ROOT),2)
        self.assertIn('curses',output.getvalue().lower())

    def test_streamed_command_failure_and_interrupt_restore_terminal(self):
        for failure in (ValueError('fake terraform failed'),KeyboardInterrupt()):
            screen=Mock()
            with patch.object(tui.curses,'def_prog_mode') as save,patch.object(tui.curses,'endwin') as end,patch.object(tui.curses,'reset_prog_mode') as reset,contextlib.redirect_stdout(io.StringIO()):
                message=tui.run_external(screen,Mock(side_effect=failure),input_fn=lambda _: '')
            save.assert_called_once();end.assert_called_once();reset.assert_called_once()
            self.assertEqual(screen.keypad.call_args_list[-1].args,(True,))
            screen.clear.assert_called_once();screen.refresh.assert_called_once()
            self.assertIn('failed' if isinstance(failure,ValueError) else 'Interrupted',message)

    def test_actual_pty_streamed_failure_and_interrupt_return_to_curses(self):
        for exception in ('ValueError("fake Terraform failure")', 'KeyboardInterrupt()'):
            with self.subTest(exception=exception):
                master, slave = pty.openpty()
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 90, 0, 0))
                before = termios.tcgetattr(slave)
                code = """import curses, subprocess, sys
from arcade_tui import run_external

def main(screen):
    def operation():
        subprocess.run([sys.executable, '-c', 'print("FAKE TERRAFORM STREAM")'], check=True)
        raise EXCEPTION
    run_external(screen, operation)
    screen.addstr(0, 0, 'CURSES DISPLAY RESTORED')
    screen.refresh()
    screen.getch()
curses.wrapper(main)
print('NORMAL TERMINAL RESTORED')
""".replace('EXCEPTION', exception)
                env = {**os.environ, 'TERM': 'xterm-256color', 'PYTHONDONTWRITEBYTECODE': '1',
                       'PYTHONPATH': str(ROOT / 'scripts')}
                process = subprocess.Popen([sys.executable, '-c', code], stdin=slave, stdout=slave,
                                           stderr=slave, env=env, start_new_session=True)
                data = bytearray()
                def until(text):
                    deadline = time.monotonic() + 4
                    while text.encode() not in data and time.monotonic() < deadline:
                        if select.select([master], [], [], 0.1)[0]:
                            data.extend(os.read(master, 65536))
                    self.assertIn(text.encode(), data)
                try:
                    until('Press Enter to return')
                    self.assertIn(b'FAKE TERRAFORM STREAM', data)
                    self.assertTrue(termios.tcgetattr(slave)[3] & termios.ECHO)
                    os.write(master, b'\n')
                    until('CURSES DISPLAY RESTORED')
                    self.assertFalse(termios.tcgetattr(slave)[3] & termios.ECHO)
                    os.write(master, b'q')
                    until('NORMAL TERMINAL RESTORED')
                    process.wait(timeout=4)
                    self.assertEqual(process.returncode, 0)
                    self.assertEqual(termios.tcgetattr(slave)[3], before[3])
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                    os.close(master)
                    os.close(slave)

    def test_actual_pty_arrows_enter_back_help_purple_resize_and_drill(self):
        master,slave=pty.openpty()
        self.addCleanup(os.close,master);self.addCleanup(os.close,slave)
        def size(rows,columns):
            fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',rows,columns,0,0))
        size(30,110)
        env={**os.environ,'TERM':'xterm-256color','PYTHONDONTWRITEBYTECODE':'1'}
        process=subprocess.Popen([sys.executable,str(ROOT/'scripts/arcade_tui.py')],stdin=slave,stdout=slave,stderr=slave,env=env,cwd='/tmp',start_new_session=True)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        chunks=bytearray()
        def read_until(text,timeout=4):
            start=len(chunks);deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                ready,_,_=select.select([master],[],[],0.1)
                if ready:
                    try: chunks.extend(os.read(master,65536))
                    except OSError: break
                    if text.encode() in chunks[start:]: return bytes(chunks[start:])
                if process.poll() is not None: break
            self.fail(f'Missing PTY text {text!r}: {bytes(chunks[-5000:])!r}')
        first=read_until('Practice desk')
        self.assertTrue(b'35m' in first or b'45m' in first or b'38;5;' in first or b'48;5;' in first,first)
        os.write(master,b'\x1bOB\r')
        read_until('Read mission runbook')
        os.write(master,b'?')
        read_until('Keyboard help')
        os.write(master,b'b')
        read_until('Read mission runbook')
        os.write(master,b'b')
        read_until('Live missions')
        os.write(master,b'\x1bOH' + b'\x1bOB' * 8 + b'\r')
        read_until('Prerequisite 07')
        os.write(master,b'\x1bOB\r')
        read_until('Build the short-lived EKS arena')
        os.write(master,b'bb\t')
        read_until('No AWS or tools required')
        os.write(master,b'\r')
        read_until('Reveal:')
        os.write(master,b'\x1bOB\r')
        read_until('Simulated observation')
        os.write(master,b'b')
        read_until('Reveal:')
        size(8,35);os.kill(process.pid,signal.SIGWINCH)
        read_until('Terminal too small')
        size(30,110);os.kill(process.pid,signal.SIGWINCH)
        read_until('Reveal:')
        os.write(master,b'q')
        process.wait(timeout=4)
        self.assertEqual(process.returncode,0,bytes(chunks[-2000:]))

    def test_actual_pty_search_cloud_roots_evidence_cleanup_and_empty_results(self):
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 32, 120, 0, 0))
        env = {**os.environ, 'TERM': 'xterm-256color', 'PYTHONDONTWRITEBYTECODE': '1'}
        process = subprocess.Popen([sys.executable, str(ROOT / 'scripts/arcade_tui.py')],
                                   stdin=slave, stdout=slave, stderr=slave, env=env,
                                   cwd='/tmp', start_new_session=True)
        chunks = bytearray()
        def until(text):
            start = len(chunks)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if select.select([master], [], [], 0.1)[0]:
                    chunks.extend(os.read(master, 65536))
                    if text.encode() in chunks[start:]:
                        return
                if process.poll() is not None:
                    break
            self.fail(f'Missing PTY text {text!r}: {bytes(chunks[-5000:])!r}')
        try:
            until('Practice desk')
            os.write(master, b'/ImagePullBackOff\r')
            until('11-01')
            os.write(master, b'/\x15public path\r\r')
            until('Game 13')
            self.assertIn(b'1 hour', chunks)
            self.assertIn(b'2 hours', chunks)
            os.write(master, b'\x1bOB\x1bOB\r')
            until('Select Terraform root')
            os.write(master, b'\x1bOB\r')
            until('Root: access')
            os.write(master, b'r')
            until('Repair evidence / Game 13 / access')
            os.write(master, b'bi')
            until('Resource inventory / last operation')
            os.write(master, b'bc')
            until('Cleanup order and commands')
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 18, 60, 0, 0))
            os.kill(process.pid, signal.SIGWINCH)
            until('Lines ')
            os.write(master, b'bb/\x15no-such-mission\r')
            until('No matches.')
            os.write(master, b'/\x15\r')
            until('Terraform contract clinic')
            os.write(master, b'q')
            process.wait(timeout=4)
            self.assertEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
            os.close(slave)


if __name__=='__main__': unittest.main()
