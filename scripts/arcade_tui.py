#!/usr/bin/env python3
"""Full-screen terminal practice desk and explicit Terraform lifecycle."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import textwrap

try:
    import curses
except ImportError:
    curses = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import lab_manager
import lab_runtime
from scripts import drill_engine

HELP = [
    'Up / Down: move through missions, actions or observations.',
    'Enter: open the selected item or run the selected action.',
    'Tab: switch between live missions and offline drills from the desk.',
    'b / Left / Escape: back. q: quit. ? / h: this help.',
    'Page Up / Page Down: scroll long text. Home / End: jump.',
    'Resize the terminal at any time; a minimum of 60 columns by 18 rows is needed.',
    '',
    'Offline drills are authored simulations and never use AWS credentials.',
    'Prepare copies registered working files; it does not prove live readiness.',
    'Plan initializes, validates, saves and displays a Terraform plan.',
    'Apply saved plan requires a typed operation and account confirmation.',
    'Plan destroy creates a separate reviewed deletion plan; Apply saved plan executes it.',
    'Commands stream outside this screen. Enter returns here after success or failure.',
    'Repairs belong in the workspace Terraform inputs, source or candidate.yaml.',
    'Keep state after failures. Re-plan before retrying; use the mission runbook for acceptance.',
    'The $20 allowance is total practice budget, not a price guarantee.',
]


def run_external(screen, operation, *, input_fn=input):
    """Always put curses back, even if Terraform or the learner interrupts."""
    curses.def_prog_mode()
    screen.keypad(False)
    curses.endwin()
    message = 'Operation finished. Read the output and required runbook checks.'
    try:
        try:
            operation()
        except KeyboardInterrupt:
            message = 'Interrupted. Preserve workspace state; inspect it and review a fresh plan before retrying.'
            print('\n' + message)
        except (OSError, ValueError) as exc:
            message = 'Operation failed: ' + str(exc)
            print('\n' + message)
        try:
            input_fn('\nPress Enter to return to the practice desk...')
        except (KeyboardInterrupt, EOFError):
            pass
    finally:
        curses.reset_prog_mode()
        screen.keypad(True)
        screen.clear()
        screen.refresh()
    return message


class Desk:
    def __init__(self, screen, root):
        self.screen, self.root = screen, Path(root)
        self.recipes = lab_manager.load_recipes(self.root)
        self.drills = drill_engine.list_drills(root=self.root)['drills']
        self.section = 'missions'
        self.view = 'desk'
        self.index = 0
        self.scroll = 0
        self.history = []
        self.selected = None
        self.text_title = ''
        self.text_lines = []
        self.notice = 'Choose an offline drill or inspect a mission before provisioning.'
        self.running = True
        self.purple, self.selected_style, self.muted = curses.A_BOLD, curses.A_REVERSE, curses.A_DIM
        if curses.has_colors():
            curses.start_color()
            try:
                curses.use_default_colors()
                background = -1
            except curses.error:
                background = curses.COLOR_BLACK
            purple = 141 if curses.COLORS >= 256 else curses.COLOR_MAGENTA
            curses.init_pair(1, purple, background)
            curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_MAGENTA)
            curses.init_pair(3, curses.COLOR_CYAN, background)
            self.purple = curses.color_pair(1) | curses.A_BOLD
            self.selected_style = curses.color_pair(2) | curses.A_BOLD
            self.muted = curses.color_pair(3)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        self.screen.keypad(True)
        # SIGWINCH can be consumed by refresh before a blocking getch. A bounded
        # read also redraws resizes received between those two curses calls.
        self.screen.timeout(250)
        if hasattr(curses, 'set_escdelay'):
            curses.set_escdelay(35)

    def push(self, view, selected=None):
        self.history.append((self.view, self.index, self.scroll, self.selected, self.text_title, self.text_lines))
        self.view, self.index, self.scroll = view, 0, 0
        self.selected = selected

    def back(self):
        if self.history:
            self.view, self.index, self.scroll, self.selected, self.text_title, self.text_lines = self.history.pop()
        else:
            self.notice = 'Tab switches missions / offline drills. q quits.'

    def show_text(self, title, lines):
        self.push('text', self.selected)
        self.text_title = title
        entries = [lines] if isinstance(lines, str) else lines
        self.text_lines = [line for entry in entries for line in (str(entry).splitlines() or [''])]

    def runtime(self):
        return lab_runtime.Runtime(self.root, self.selected['id'])

    def choices(self):
        if self.view == 'desk':
            if self.section == 'missions':
                return [(f"{item['alias']:5} {item['title']}", ('mission', item)) for item in self.recipes]
            return [(f"{item['kind']:13} {item['title']}", ('drill', item)) for item in self.drills]
        if self.view == 'mission':
            run = self.runtime()
            description = run.describe()
            choices = [('Read mission runbook', ('runbook', None))]
            for item in description['prerequisites']:
                choices.append((f"Prerequisite {item['alias']}: {item['status']}", ('prerequisite', item['recipeId'])))
            if self.selected['modes']:
                if description['prepared']:
                    choices.append(('Resume prepared workspace (preserve edits and state)', ('prepare', None)))
                else:
                    for mode, data in self.selected['modes'].items():
                        choices.append((f"Prepare {mode}: {data['label']}", ('prepare', mode)))
            if description['supported']:
                choices.extend([
                    ('Configure account, profile and required inputs', ('configure', None)),
                    ('Plan changes and review saved plan', ('plan', 'apply')),
                    ('Apply saved plan (typed confirmation)', ('apply', None)),
                    ('Verify local observations and required live checks', ('verify', None)),
                    ('Plan destroy (review deletion first)', ('plan', 'destroy')),
                ])
                if self.selected['alias'] == '07' or run.workload:
                    choices.append(('Show / save shell activation for isolated context', ('activation', None)))
                if self.selected['alias'] == '11-10':
                    choices.append(('Prepare broken update after baseline HTTP proof', ('broken', None)))
            else:
                choices.append(('Environment operations: explicit runbook handoff', ('handoff', None)))
            return choices
        if self.view == 'drill':
            public = drill_engine.public_drill(self.selected['id'], root=self.root)
            return [('Read full brief and answer choices', ('brief', None))] + [(f"Reveal: {entry['label']}", ('evidence', entry['id'])) for entry in public['observations']] + [
                (f"Answer: {entry['text']}", ('answer', entry['id'])) for entry in public['question']['options']]
        return []

    def put(self, row, col, text, style=0, width=None):
        rows, columns = self.screen.getmaxyx()
        if 0 <= row < rows and col < columns - 1:
            # Control characters in authored labels never become terminal controls.
            safe = ''.join(c if c.isprintable() else ' ' for c in str(text))
            try:
                self.screen.addnstr(row, col, safe, max(0, min(columns - col - 1, width if width is not None else columns)), style)
            except curses.error:
                pass

    def header(self, subtitle):
        rows, columns = self.screen.getmaxyx()
        self.put(0, 0, ' ' * (columns - 1), self.selected_style)
        self.put(0, 2, 'ARCADE  /  Practice desk', self.selected_style)
        self.put(2, 2, subtitle, self.purple)
        self.put(rows - 2, 2, self.notice, self.muted)
        self.put(rows - 1, 2, '↑↓ Move  Enter Open  Tab Desk tabs  b Back  ? Help  q Quit', self.purple)

    def draw(self):
        size = os.get_terminal_size(sys.stdout.fileno())
        if size.lines > 0 and size.columns > 0 and self.screen.getmaxyx() != (size.lines, size.columns):
            curses.resizeterm(size.lines, size.columns)
        self.screen.erase()
        rows, columns = self.screen.getmaxyx()
        if rows < 18 or columns < 60:
            self.put(0, 0, 'Terminal too small', self.purple)
            self.put(2, 0, 'Resize to at least 60 x 18.')
            self.put(min(rows - 1, 4), 0, 'q Quit | b Back')
            self.screen.refresh()
            return
        if self.view == 'text':
            self.header(self.text_title)
            wrapped = []
            for line in self.text_lines:
                wrapped.extend(textwrap.wrap(str(line), width=columns - 5, replace_whitespace=False) or [''])
            height = rows - 7
            self.scroll = max(0, min(self.scroll, max(0, len(wrapped) - height)))
            for offset, line in enumerate(wrapped[self.scroll:self.scroll + height]):
                self.put(4 + offset, 2, line)
            self.put(rows - 3, 2, f'Lines {self.scroll + 1}–{min(len(wrapped), self.scroll + height)} / {len(wrapped)}  |  PgUp / PgDn scroll', self.muted)
        else:
            choices = self.choices()
            self.index = min(self.index, max(0, len(choices) - 1))
            top = 7
            if self.view == 'desk':
                self.header('Live missions  |  Offline drills' if self.section == 'missions' else 'Offline drills  |  No AWS or tools required')
                self.put(4, 2, 'Missions: prepare, review and manage supported environments.' if self.section == 'missions' else 'Authored simulations. Request one observation, then choose an answer.')
                self.put(5, 2, 'Terraform repairs stay in your workspace. Total practice allowance: $20.' if self.section == 'missions' else 'Results are practice feedback; they do not prove cloud health or mastery.', self.muted)
            elif self.view == 'mission':
                run = self.runtime()
                data = run.describe()
                self.header(f"Game {self.selected['alias']}  /  {self.selected['title']}")
                self.put(4, 2, ('Lifecycle supported' if data['supported'] else 'Runbook handoff for environment operations') + f" | Phase: {data['phase']}")
                self.put(5, 2, 'Prepared files ≠ live readiness. ' + self.selected['cost'], self.muted)
                if data['prerequisites']:
                    self.put(6, 2, 'Setup order: ' + ' → '.join(item['alias'] for item in data['prerequisites']) + ' → ' + self.selected['alias'], self.purple)
                    top = 8
            else:
                public = drill_engine.public_drill(self.selected['id'], root=self.root)
                self.header('Offline drill / ' + public['title'])
                lines = textwrap.wrap(public['brief'], width=columns - 5)
                for offset, line in enumerate(lines[:4]):
                    self.put(4 + offset, 2, line)
                top = 5 + min(len(lines), 4)
                self.put(top, 2, public['question']['prompt'], self.muted)
                top += 2
            height = max(1, rows - top - 4)
            if self.index < self.scroll:
                self.scroll = self.index
            if self.index >= self.scroll + height:
                self.scroll = self.index - height + 1
            split = int(columns * 0.55) if self.view == 'desk' and columns >= 105 else None
            for offset, (label, _) in enumerate(choices[self.scroll:self.scroll + height]):
                selected = self.scroll + offset == self.index
                self.put(top + offset, 2, ('› ' if selected else '  ') + label,
                         self.selected_style if selected else 0, width=split - 4 if split else None)
            if split is not None:
                self.preview(split, top, rows - 4, choices[self.index][1][1])
            self.put(rows - 3, 2, f'{self.index + 1} / {len(choices)}' + ('  (more below)' if self.scroll + height < len(choices) else ''), self.muted)
        self.screen.refresh()

    def preview(self, column, top, bottom, item):
        """Wide terminals keep a selected mission brief beside the keyboard list."""
        width = self.screen.getmaxyx()[1] - column - 4
        for row in range(top, bottom + 1):
            self.put(row, column - 2, '│', self.purple)
        if self.section == 'missions':
            run = lab_runtime.Runtime(self.root, item['id'])
            details = run.describe()
            blocks = [
                (f"GAME {item['alias']}", self.purple),
                (item['title'], curses.A_BOLD),
                ('', 0),
                ('Lifecycle available' if details['supported'] else 'Runbook handoff', self.purple),
                ('Prepared files: ' + ('yes' if details['prepared'] else 'no'), 0),
                ('Phase: ' + details['phase'], 0),
                ('', 0),
                ('Setup order', self.purple),
                (' → '.join([p['alias'] for p in details['prerequisites']] + [item['alias']]), 0),
                ('', 0),
                (item['cost'], 0),
                ('', 0),
                ('Files and local state do not prove live readiness.', self.muted),
                ('', 0),
                ('Enter: read mission and manage workspace', self.purple),
            ]
        else:
            blocks = [(item['kind'].upper() + ' / OFFLINE', self.purple),
                      (item['title'], curses.A_BOLD), ('', 0), (item['summary'], 0),
                      ('', 0), (f"{item['minutes']} minutes", self.muted),
                      ('Skills: ' + ', '.join(item['skills']), 0), ('', 0),
                      ('Authored simulation; no cloud commands run.', self.muted), ('', 0),
                      ('Enter: read brief and request evidence', self.purple)]
        row = top
        for text, style in blocks:
            for line in textwrap.wrap(text, width=width) or ['']:
                if row > bottom:
                    return
                self.put(row, column, line, style, width=width)
                row += 1

    def activate(self):
        choices = self.choices()
        if not choices:
            return
        action, value = choices[self.index][1]
        if action in {'mission', 'drill'}:
            self.push(action, value)
        elif action == 'prerequisite':
            self.push('mission', lab_manager.find_recipe(self.recipes, value))
        elif action in {'runbook', 'handoff'}:
            run = self.runtime()
            prefix = '' if action == 'runbook' else 'This mission has multiple states, imperative steps or a runbook workflow. The terminal prepares its authored files but does not execute recipe shell text. Follow the runbook below.\n\n'
            self.show_text(f"Game {run.alias} runbook", prefix + run.runbook.read_text())
        elif action == 'brief':
            public = drill_engine.public_drill(self.selected['id'], root=self.root)
            self.show_text('Drill brief / ' + public['title'],
                           [public['brief'], '', public['question']['prompt'], ''] +
                           [item['text'] for item in public['question']['options']] + ['', public['provenance']])
        elif action == 'evidence':
            evidence = drill_engine.evidence(self.selected['id'], value, root=self.root)
            self.show_text('Simulated observation / ' + evidence['label'],
                           ['Command description (display only): ' + evidence['command'], '', evidence['output']])
        elif action == 'answer':
            feedback = drill_engine.answer(self.selected['id'], value, root=self.root)
            lines = [('Supported by the evidence.' if feedback['correct'] else 'Reconsider the decisive evidence.'), '']
            for key, label in [('explanation', 'Explanation'), ('decisiveEvidence', 'Decisive observations'), ('repair', 'Terraform repair'), ('verification', 'Recovery proof'), ('cleanup', 'Cleanup'), ('followUp', 'Changed-constraint interview')]:
                lines += [label + ':', ', '.join(feedback[key]) if isinstance(feedback[key], list) else feedback[key], '']
            self.show_text('Simulated feedback', lines)
        else:
            run = self.runtime()
            operations = {
                'prepare': lambda: run.prepare(value), 'configure': run.configure_interactive,
                'plan': lambda: run.plan(value), 'apply': run.apply, 'verify': run.verify,
                'activation': lambda: print(run.activation()), 'broken': run.begin_broken_update,
            }
            self.notice = run_external(self.screen, operations[action])

    def loop(self):
        while self.running:
            try:
                self.draw()
                key = self.screen.getch()
                if key in (ord('q'), ord('Q')):
                    self.running = False
                elif key in (ord('b'), 27, curses.KEY_LEFT):
                    self.back()
                elif key in (ord('?'), ord('h')):
                    self.show_text('Keyboard help', HELP)
                elif key == 9 and self.view == 'desk':
                    self.section = 'drills' if self.section == 'missions' else 'missions'
                    self.index = self.scroll = 0
                elif key == curses.KEY_RESIZE:
                    self.screen.clear()
                elif key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE, curses.KEY_HOME, curses.KEY_END):
                    change = -1 if key == curses.KEY_UP else 1
                    if key in (curses.KEY_PPAGE, curses.KEY_NPAGE):
                        change = (-1 if key == curses.KEY_PPAGE else 1) * max(1, self.screen.getmaxyx()[0] - 8)
                    if self.view == 'text':
                        self.scroll = (0 if key == curses.KEY_HOME else 10**9 if key == curses.KEY_END else max(0, self.scroll + change))
                    else:
                        maximum = max(0, len(self.choices()) - 1)
                        self.index = (0 if key == curses.KEY_HOME else maximum if key == curses.KEY_END else max(0, min(maximum, self.index + change)))
                elif key in (10, 13, curses.KEY_ENTER):
                    if min(self.screen.getmaxyx()) >= 18 and self.screen.getmaxyx()[1] >= 60:
                        self.activate()
            except (OSError, ValueError) as exc:
                self.notice = 'Workspace needs attention; files and state are preserved.'
                self.show_text('Workspace needs attention', [str(exc), '', 'Back returns to the previous view. q quits.'])
            except KeyboardInterrupt:
                self.notice = 'Interrupted. q quits; all workspaces are preserved.'


def main(argv=None, *, root=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    if curses is None:
        print('Python curses is unavailable. Use a Python build with curses in a Linux/WSL terminal, or ./arcade drill list and ./arcade labs.')
        return 2
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print('The full-screen practice desk needs an interactive terminal. Run ./arcade tui there. Without a TTY, use ./arcade drill list or ./arcade labs; no input will be requested.')
        return 2
    try:
        curses.wrapper(lambda screen: Desk(screen, root or ROOT).loop())
    except (curses.error, OSError, ValueError) as exc:
        print(f'Unable to open the terminal desk: {exc}. Check TERM and terminal size; ./arcade drill list works without curses.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
