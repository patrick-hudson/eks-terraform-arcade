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
from lab_session import Session
from scripts import drill_engine

HELP = [
    'Up / Down: move through missions, actions or observations.',
    'Enter: open the selected item or run the selected action.',
    'Tab: switch between live missions and offline drills from the desk.',
    '/: search mission titles, symptoms and runbooks. Enter keeps the filter; Escape cancels.',
    'c: cleanup steps from a mission. r: repair evidence. i: retained resource inventory.',
    'b / Left / Escape: back. q: quit. ? / h: this help.',
    'Page Up / Page Down: scroll long text. Home / End: jump.',
    'Resize the terminal at any time; a minimum of 60 columns by 18 rows is needed.',
    '',
    'Offline drills are authored simulations and never use AWS credentials.',
    'Prepare copies registered working files; it does not prove live readiness.',
    'Plan initializes, validates, saves and displays a Terraform plan.',
    'Apply saved plan requires a typed operation and account confirmation.',
    'Select a Terraform root for missions with separate infrastructure / workload states.',
    'Submit repair records bounded observations; UNKNOWN or STALE does not mean passed.',
    'Plan destroy creates a separate reviewed deletion plan; Apply saved plan executes it.',
    'Commands stream outside this screen. Enter returns here after success or failure.',
    'Repairs belong in the workspace Terraform inputs, source or candidate.yaml.',
    'Keep state after failures. Re-plan before retrying; use the mission runbook for acceptance.',
    'The $20 allowance is total practice budget, not a price guarantee.',
]


def cost_lines(costs):
    return [f"1 hour ≈ ${costs['oneHourUsd']:.3f}  |  2 hours ≈ ${costs['twoHoursUsd']:.3f} USD",
            f"Estimate for {costs['region']} · checked {costs['asOf']}",
            f"This mission: ${costs['incrementalHourlyUsd']:.3f}/h; shared foundation: ${costs['sharedHourlyUsd']:.3f}/h.",
            costs['description'], '', *costs['assumptions'], costs['activityBased'], '', costs['notice']]


def repair_lines(data):
    repair = data.get('repair')
    if not repair:
        return ['No repair checks recorded.', 'Submit repair after applying your Terraform change.',
                'A successful apply alone does not pass the exercise.']
    lines = [('STALE — source changed; submit again after applying the repair.' if repair['stale']
              else 'Point-in-time repair evidence'),
             f"Result: {repair['status'].upper()} | {repair['phase']} | {repair['generatedAt']}",
             repair['scope'], '', 'This evidence is separate from self-reported study completion.', '']
    for check in repair['checks']:
        lines.extend([f"[{check['status'].upper()}] {check['label']}",
                      'Expected: ' + check['expected'], 'Observed: ' + check['observed'], ''])
    return lines


def inventory_lines(data):
    inventory = data['inventory']
    operation = data.get('lastOperation')
    lines = ['Retained resource identifiers', inventory['scope'],
             f"State: {inventory['stateStatus']} | Cloud absence: {inventory['absence']}", '']
    if operation:
        lines.extend([f"Last operation: {operation['operation']} — {operation['status']}",
                      operation.get('finishedAt', ''), operation.get('message', ''), ''])
    for item in inventory['resources']:
        lines.extend([f"{item['root']} / {item['address']}", 'Type: ' + item['type'],
                      'ID: ' + (item.get('id') or 'not recorded'),
                      'ARN: ' + (item.get('arn') or 'not recorded'), ''])
    if not inventory['resources']:
        lines.append('No identifiers recorded. This is not proof that AWS resources are absent.')
    return lines


def cleanup_lines(data):
    order = ' → '.join(f"Game {item['lab']} ({item['root']})" for item in data['cleanupOrder'])
    lines = ['Cleanup order: ' + (order or 'Follow the mission runbook.'),
             'Review a destroy plan, explicitly apply it, then confirm the named resources are absent.',
             'Keep the workspace and state until cleanup is verified. Empty state alone is not cloud absence.', '']
    for number, step in enumerate(data['runbookCleanup'], 1):
        lines.extend([f"{number}. {step['title']}", step['command'], ''])
    if not data['runbookCleanup']:
        lines.extend(['Use the complete mission runbook for the cleanup steps.', data['runbook']])
    return lines


def runbook_lines(data):
    lines = ['Workspace: ' + (data['path'] or 'Use the runbook directories'),
             'Commands below are reference text; this viewer does not execute shell recipes.', '']
    for number, step in enumerate(data['runbookSteps'], 1):
        lines.extend([f"{number}. {step['title']}", step['command'], ''])
    lines.extend(cleanup_lines(data))
    lines.extend(['', 'Full mission brief, acceptance checks and hints', '',
                  data.get('runbookText') or Path(data['runbook']).read_text()])
    return lines


def apply_session(session, *, input_fn=input):
    plan = session.describe()['plan']
    if not plan or plan['stale'] or plan['consumed']:
        raise ValueError('Create and review a fresh saved plan before applying it.')
    print(plan['reviewText'])
    print(plan['scope'])
    print('Saved plan digest: ' + plan['digest'])
    approval = input_fn('Type ' + plan['approval'] + ' to apply this reviewed plan: ')
    return session.perform('apply', approval=approval, plan_digest=plan['digest'])


def configure_session(session, *, input_fn=input):
    data = session.describe()
    if data['alias'] == '00':
        print('Game 00 needs no AWS credentials or cloud inputs.')
        return session.perform('configure')
    previous = data['configuration']
    fields = [('profile', 'AWS profile'), ('account_id', 'Intended AWS account (12 digits)'),
              ('region', 'AWS region')]
    if not session.runtime.workload:
        fields.append(('lab_id', 'Distinctive lab ID'))
    if data['alias'] == '07':
        fields.append(('admin_principal_arn', 'Permanent IAM role/user ARN'))
    if data['alias'] == '07' or (data['alias'] == '13' and data['root'] == 'access'):
        fields.append(('allowed_cidr', 'Your public IPv4 /32'))
    values = {}
    for key, label in fields:
        old = previous.get(key) or ('us-west-2' if key == 'region' else '')
        values[key] = input_fn(label + (f' [{old}]' if old else '') + ': ').strip() or old
    return session.perform('configure', **values)


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
        self.terraform_root = None
        self.queries = {'missions': '', 'drills': ''}
        self.searching = False
        self.search_before = ''
        self.search_text = {}
        self.text_title = ''
        self.text_lines = []
        self.notice = 'Inspect a cloud mission, or Tab for offline practice. / searches symptoms.'
        self.running = True
        self.purple, self.selected_style, self.muted = curses.A_BOLD, curses.A_REVERSE, curses.A_DIM
        if curses.has_colors():
            curses.start_color()
            # A deliberate dark canvas also stays readable in light terminals.
            background = 234 if curses.COLORS >= 256 else curses.COLOR_BLACK
            purple = 183 if curses.COLORS >= 256 else curses.COLOR_MAGENTA
            highlight = 54 if curses.COLORS >= 256 else curses.COLOR_MAGENTA
            curses.init_pair(1, purple, background)
            curses.init_pair(2, curses.COLOR_WHITE, highlight)
            curses.init_pair(3, 250 if curses.COLORS >= 256 else curses.COLOR_CYAN, background)
            curses.init_pair(4, 253 if curses.COLORS >= 256 else curses.COLOR_WHITE, background)
            self.screen.bkgd(' ', curses.color_pair(4))
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
        self.history.append((self.view, self.index, self.scroll, self.selected, self.text_title, self.text_lines, self.terraform_root))
        self.view, self.index, self.scroll = view, 0, 0
        self.selected = selected
        if view == 'mission':
            self.terraform_root = None

    def back(self):
        if self.history:
            self.view, self.index, self.scroll, self.selected, self.text_title, self.text_lines, self.terraform_root = self.history.pop()
        else:
            self.notice = 'Tab switches missions / offline drills. q quits.'

    def show_text(self, title, lines):
        self.push('text', self.selected)
        self.text_title = title
        entries = [lines] if isinstance(lines, str) else lines
        self.text_lines = [line for entry in entries for line in (str(entry).splitlines() or [''])]

    def session(self):
        return Session(self.root, self.selected['id'], root=self.terraform_root)

    def matches(self, item):
        query = self.queries[self.section].casefold().split()
        if not query:
            return True
        cache_key = (self.section, item['id'])
        if cache_key not in self.search_text:
            if self.section == 'missions':
                # Index authored symptoms once; no AWS calls or workspace writes.
                runbook = lab_runtime.Runtime(self.root, item['id']).runbook
                text = runbook.read_text() if runbook.exists() else ''
                text += ' '.join(mode.get('description', '') for mode in item['modes'].values())
            else:
                text = item['summary'] + ' ' + ' '.join(item['skills'])
            self.search_text[cache_key] = ' '.join((item['id'], item['title'], text)).casefold()
        return all(token in self.search_text[cache_key] for token in query)

    def choices(self):
        if self.view == 'desk':
            items = self.recipes if self.section == 'missions' else self.drills
            matches = [item for item in items if self.matches(item)]
            query = self.queries[self.section].casefold().strip()
            if query:
                # Titles and exact game numbers lead; runbook symptom matches
                # remain available without burying the mission a learner named.
                matches.sort(key=lambda item: (
                    item.get('alias', '').casefold() != query,
                    not all(word in item['title'].casefold() for word in query.split())))
            if self.section == 'missions':
                return [(f"{item['alias']:5} {item['title']}", ('mission', item)) for item in matches]
            return [(f"{item['kind']:13} {item['title']}", ('drill', item)) for item in matches]
        if self.view == 'roots':
            details = self.session().describe()
            return [(root + ('  / current' if root == details['root'] else ''), ('root', root))
                    for root in details['roots']]
        if self.view == 'mission':
            description = self.session().describe()
            choices = [('Read mission runbook', ('runbook', None))]
            for item in description['prerequisites']:
                choices.append((f"Prerequisite {item['alias']}" + (f" / {item['root']}" if item.get('root') else '')
                                + ': ' + item['status'], ('prerequisite', item)))
            if len(description['roots']) > 1:
                choices.append((f"Select Terraform root / {description['root']}", ('roots', None)))
            if 'prepare' in description['capabilities']:
                if description['prepared']:
                    choices.append(('Resume prepared workspace (preserve edits and state)', ('prepare', None)))
                else:
                    for mode, data in self.selected['modes'].items():
                        choices.append((f"Prepare {mode}: {data['label']}", ('prepare', mode)))
            actions = [('configure', 'Configure account, profile and required inputs'),
                       ('plan', 'Plan changes and review saved plan'),
                       ('apply', 'Review / apply saved plan (typed confirmation)'),
                       ('submit', 'Submit repair / check observed behavior'),
                       ('plan_destroy', 'Plan destroy / review cleanup before applying')]
            choices.extend((label, (operation, None)) for operation, label in actions
                           if operation in description['capabilities'])
            if description['supported']:
                if self.selected['alias'] == '07' or self.session().runtime.workload:
                    choices.append(('Show / save shell activation for isolated context', ('activation', None)))
                if self.selected['alias'] == '11-10':
                    choices.append(('Verify healthy baseline before broken update', ('verify', None)))
                if 'begin_incident' in description['capabilities']:
                    choices.append(('Prepare broken update after baseline HTTP proof', ('begin_incident', None)))
            else:
                choices.append(('Environment operations: explicit runbook handoff', ('handoff', None)))
            choices.extend([('Repair evidence / failed, unknown or stale checks', ('repair', None)),
                            ('Resource inventory / IDs, ARNs and last operation', ('inventory', None)),
                            ('Cost estimate / 1 hour, 2 hours and assumptions', ('costs', None)),
                            ('Cleanup order and exact runbook commands', ('cleanup', None))])
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
        help_text = ('Type to filter  Enter Keep  Esc Cancel  Backspace Delete' if self.searching else
                     '↑↓ Move  Enter Open  / Search  Tab Drills  ? Help  q Quit' if self.view == 'desk' else
                     '↑↓ Move  Enter Run  c Cleanup  r Evidence  i IDs  b Back  ? Help' if self.view == 'mission' else
                     '↑↓ Move  Enter Open  b Back  ? Help  q Quit')
        self.put(rows - 1, 2, help_text, self.purple)

    def draw(self):
        try:
            size = os.get_terminal_size(sys.stdout.fileno())
        except OSError:
            size = os.terminal_size(self.screen.getmaxyx()[::-1])
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
                self.put(4, 2, 'Terraform & AWS foundations / EKS workloads / Incident practice' if self.section == 'missions' else 'Authored simulations. Request one observation, then choose an answer.')
                query = self.queries[self.section]
                self.put(5, 2, ('Search: ' + query + ('▏' if self.searching else '') if query or self.searching else
                               '/ Search by title or symptom, e.g. ImagePullBackOff'), self.purple if self.searching else self.muted)
            elif self.view == 'mission':
                data = self.session().describe()
                self.header(f"Game {self.selected['alias']}  /  {self.selected['title']}")
                self.put(4, 2, ('Session controls' if data['supported'] else 'Ordered runbook') +
                         f" | {data['status']} | Root: {data['root']}", self.purple)
                self.put(5, 2, 'Next: ' + data['nextAction'])
                self.put(6, 2, cost_lines(data['costs'])[0] + ' · estimate', self.muted)
                top = 8
                if data['prerequisites']:
                    self.put(7, 2, 'Setup first: ' + ' → '.join(item['alias'] +
                             ('/' + item['root'] if item.get('root') else '') for item in data['prerequisites']), self.muted)
                    top = 9
            elif self.view == 'roots':
                self.header('Select Terraform root / Game ' + self.selected['alias'])
                self.put(4, 2, 'Each root keeps its own plan and state. Follow setup order.', self.muted)
                self.put(5, 2, 'Switching roots only changes this view; it runs no cloud commands.')
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
            split = int(columns * 0.55) if self.view in {'desk', 'mission'} and columns >= 105 else None
            for offset, (label, _) in enumerate(choices[self.scroll:self.scroll + height]):
                selected = self.scroll + offset == self.index
                self.put(top + offset, 2, ('› ' if selected else '  ') + label,
                         self.selected_style if selected else 0, width=split - 4 if split else None)
            if not choices:
                self.put(top, 2, 'No matches. Press / to change the search.', self.muted)
            elif split is not None and self.view == 'desk':
                self.preview(split, top, rows - 4, choices[self.index][1][1])
            elif split is not None and self.view == 'mission':
                self.session_preview(split, top, rows - 4, data)
            self.put(rows - 3, 2, f'{self.index + 1 if choices else 0} / {len(choices)}' +
                     ('  (more below)' if self.scroll + height < len(choices) else '') +
                     ('  |  c Cleanup · r Evidence · i IDs' if self.view == 'mission' else ''), self.muted)
        self.screen.refresh()

    def preview(self, column, top, bottom, item):
        """Wide terminals keep a selected mission brief beside the keyboard list."""
        width = self.screen.getmaxyx()[1] - column - 4
        for row in range(top, bottom + 1):
            self.put(row, column - 2, '│', self.purple)
        if self.section == 'missions':
            details = Session(self.root, item['id']).describe()
            group = ('LOCAL CONTRACT' if item['alias'] == '00' else 'EKS INCIDENT' if item['alias'].startswith('11')
                     else 'EKS MISSION' if item['alias'] in {'07', '08', '09', '10', '12', '13'} else 'AWS & TERRAFORM')
            blocks = [
                (f"GAME {item['alias']} / {group}", self.purple),
                (item['title'], curses.A_BOLD),
                ('', 0),
                ('Lifecycle available' if details['supported'] else 'Runbook handoff', self.purple),
                ('Prepared files: ' + ('yes' if details['prepared'] else 'no'), 0),
                ('Next: ' + details['nextAction'], 0),
                ('', 0),
                ('Setup order', self.purple),
                (' → '.join([p['alias'] for p in details['prerequisites']] + [item['alias']]), 0),
                ('', 0),
                (cost_lines(details['costs'])[0], 0),
                ('Costs are estimates; see mission assumptions.', self.muted),
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

    def session_preview(self, column, top, bottom, data):
        width = self.screen.getmaxyx()[1] - column - 4
        for row in range(top, bottom + 1):
            self.put(row, column - 2, '│', self.purple)
        repair = data['repair']
        result = ('No repair checks yet' if not repair else
                  ('STALE / ' if repair['stale'] else '') + repair['status'].upper())
        inventory = data['inventory']
        cleanup = ' → '.join(item['lab'] + '/' + item['root'] for item in data['cleanupOrder'])
        blocks = [('REPAIR EVIDENCE', self.purple), (result, curses.A_BOLD),
                  ('Apply alone is not a passed exercise.', self.muted), ('', 0),
                  ('WORKSPACE', self.purple), (data['path'] or 'Runbook directories', 0), ('', 0),
                  ('CLEANUP', self.purple), (cleanup or 'Use the complete runbook.', 0),
                  (f"{len(inventory['resources'])} retained IDs · absence: {inventory['absence']}", self.muted)]
        operation = data['lastOperation']
        if operation:
            blocks += [('', 0), ('LAST OPERATION', self.purple),
                       (operation['operation'] + ' / ' + operation['status'], 0)]
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
            self.push('mission', lab_manager.find_recipe(self.recipes, value['recipeId']))
            self.terraform_root = value.get('root')
        elif action == 'roots':
            self.push('roots', self.selected)
        elif action == 'root':
            self.back()
            self.terraform_root = value
            self.index = self.scroll = 0
            self.notice = 'Selected root ' + value + '. Review its prerequisites before planning.'
        elif action in {'runbook', 'handoff'}:
            data = self.session().describe()
            self.show_text(f"Game {data['alias']} runbook", runbook_lines(data))
        elif action in {'repair', 'inventory', 'costs', 'cleanup'}:
            self.details(action)
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
            session = self.session()
            operations = {
                'prepare': lambda: session.perform('prepare', mode=value),
                'configure': lambda: configure_session(session),
                'apply': lambda: apply_session(session),
                'activation': lambda: print(session.runtime.activation()),
            }
            self.notice = run_external(self.screen, operations.get(action, lambda: session.perform(action)))
            if action in {'submit', 'verify'}:
                self.details('repair')

    def details(self, kind):
        data = self.session().describe()
        title, lines = {
            'repair': ('Repair evidence', lambda: repair_lines(data)),
            'inventory': ('Resource inventory / last operation', lambda: inventory_lines(data)),
            'costs': ('Cost assumptions', lambda: cost_lines(data['costs'])),
            'cleanup': ('Cleanup order and commands', lambda: cleanup_lines(data)),
        }[kind]
        self.show_text(title + ' / Game ' + data['alias'] + ' / ' + data['root'], lines())

    def search_key(self, key):
        """Search owns keystrokes until accepted, so q/b remain searchable text."""
        if key in (10, 13, curses.KEY_ENTER):
            self.searching = False
        elif key == 27:
            self.queries[self.section] = self.search_before
            self.searching = False
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            self.queries[self.section] = self.queries[self.section][:-1]
        elif key == 21:  # Ctrl-U clears a previous filter in one keystroke.
            self.queries[self.section] = ''
        elif 32 <= key <= 126 and len(self.queries[self.section]) < 120:
            self.queries[self.section] += chr(key)
        self.index = self.scroll = 0

    def loop(self):
        while self.running:
            try:
                self.draw()
                key = self.screen.getch()
                if self.searching:
                    self.search_key(key)
                elif key == ord('/') and self.view == 'desk':
                    self.search_before = self.queries[self.section]
                    self.searching = True
                elif key in (ord('q'), ord('Q')):
                    self.running = False
                elif key in (ord('b'), 27, curses.KEY_LEFT):
                    self.back()
                elif key in (ord('?'), ord('h')):
                    self.show_text('Keyboard help', HELP)
                elif key == 9 and self.view == 'desk':
                    self.section = 'drills' if self.section == 'missions' else 'missions'
                    self.index = self.scroll = 0
                elif self.view == 'mission' and key in (ord('c'), ord('r'), ord('i')):
                    self.details({ord('c'): 'cleanup', ord('r'): 'repair', ord('i'): 'inventory'}[key])
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
