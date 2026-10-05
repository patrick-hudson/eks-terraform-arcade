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


if __name__=='__main__': unittest.main()
