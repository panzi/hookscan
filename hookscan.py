#!/usr/bin/env python3

from typing import Generator, NamedTuple, Sequence, Mapping, Final

import json
import os
import sys

from os.path import join as join_path

__version__ = '1.0.0'

class Match(NamedTuple):
    file: str
    hooks: dict[str, str]

# https://docs.npmjs.com/cli/v8/using-npm/scripts

HOOKS: Final[Mapping[str, Sequence[str]]] = {
    'cache_add': [
        'prepare'
    ],
    'ci': [
        'preinstall',
        'install',
        'postinstall',
        'prepublish',
        'preprepare',
        'prepare',
        'postprepare',
    ],
    'diff': [
        'prepare',
    ],
    'install': [
        'preinstall',
        'install',
        'postinstall',
        'prepublish',
        'preprepare',
        'prepare',
        'postprepare',
    ],
    'pack': [
        'prepack',
        'prepare',
        'postpack',
    ],
    'publish': [
        'prepublishOnly',
        'prepack',
        'prepare',
        'postpack',
        'publish',
        'postpublish',
    ],
    'rebuild': [
        'preinstall',
        'install',
        'postinstall',
        'prepare',
    ],
    'restart': [
        'prerestart',
        'restart',
        'postrestart',
    ],
    'start': [
        'prestart',
        'start',
        'poststart',
    ],
    'stop': [
        'prestop',
        'stop',
        'poststop',
    ],
    'test': [
        'pretest',
        'test',
        'posttest',
    ],
    'version': [
        'preversion',
        'version',
        'postversion',
    ],
}

def hookscan(dirs: Sequence[str], hooks: Sequence[str], follow_links: bool = False, exit_on_error: bool = False) -> Generator[Match, None, None]:
    visited: set[str] = set()

    def onerror(error: OSError) -> None:
        print(f'{error.filename}: {error}', file=sys.stderr)
        if exit_on_error:
            sys.exit(1)

    for top in dirs:
        for root, dirs, files in os.walk(top, followlinks = follow_links, onerror = onerror):
            if root in visited:
                continue

            visited.add(root)

            # folded in order to ignore case just in case for Windows
            folded: dict[str, list[str]] = {}
            for file in files:
                folded_file = file.casefold()
                alts = folded.get(folded_file)
                if alts is None:
                    folded[folded_file] = [file]
                else:
                    alts.append(file)

            alts = folded.get('package.json', ())
            for file in alts:
                path = join_path(root, file)
                try:
                    with open(path, 'rt') as fp:
                        pkg = json.load(fp)

                    scripts = pkg.get('scripts')
                    if scripts is not None:
                        actual_hooks: dict[str, str] = {}
                        for hook in hooks:
                            if hook in scripts:
                                actual_hooks[hook] = scripts[hook]

                        if actual_hooks:
                            yield Match(path, actual_hooks)

                except BaseException as exc:
                    print(f'{path}: {exc}', file=sys.stderr)

                    if exit_on_error:
                        sys.exit(1)

DEFAULT_ACTIONS: Final[list[str]] = ['install', 'ci']

def main() -> None:
    import argparse
    import re

    SPACE = re.compile(r'\s')
    NON_SPACE = re.compile(r'\S')

    # SmartFormatter always copy-pasted from:
    # https://gist.github.com/panzi/b4a51b3968f67b9ff4c99459fb9c5b3d
    class SmartFormatter(argparse.HelpFormatter):
        def _split_lines(self, text: str, width: int) -> list[str]:
            lines: list[str] = []
            for line_str in text.split('\n'):
                match = NON_SPACE.search(line_str)
                if not match:
                    lines.append('')
                    continue

                prefix = line_str[:match.start()]

                if len(prefix) >= width:
                    lines.append('')
                    prefix = ''

                line_len = prefix_len = len(prefix)
                line: list[str] = [prefix]
                pos = match.start()

                while pos < len(line_str):
                    match = NON_SPACE.search(line_str, pos)
                    if not match:
                        break

                    next_pos = match.start()
                    space = line_str[pos:next_pos]
                    line_len += len(space)

                    if line_len >= width:
                        lines.append(''.join(line))
                        line.clear()
                        line.append(prefix)
                        line_len = prefix_len
                    else:
                        line.append(space)

                    pos = next_pos
                    match = SPACE.search(line_str, pos)
                    if not match:
                        next_pos = len(line_str)
                    else:
                        next_pos = match.start()

                    word = line_str[pos:next_pos]
                    word_len = len(word)
                    line_len += word_len
                    if line_len > width:
                        lines.append(''.join(line))
                        line.clear()
                        line.append(prefix)
                        line_len = prefix_len + word_len
                    elif word_len >= 3:
                        if all(c == '.' for c in word) and line_str[next_pos:next_pos + 1].isspace():
                            prefix_len = line_len + 1
                            prefix = ' ' * prefix_len
                        elif all(c == ' ' for c in word):
                            prefix_len = line_len
                            prefix = ' ' * prefix_len
                    line.append(word)
                    pos = next_pos

                lines.append(''.join(line))
            return lines

        def _fill_text(self, text: str, width: int, indent: str) -> str:
            return '\n'.join(indent + line for line in self._split_lines(text, width - len(indent)))

    ap = argparse.ArgumentParser(formatter_class=SmartFormatter)

    grp = ap.add_mutually_exclusive_group()

    grp.add_argument('-a', '--actions', default=None,
        metavar='ACTION[,ACTION ...]',
        help=f'Comma separated list.\n'
             f'\n'
             f'Supported actions:\n'
             f'\n'
             f"{''.join(f'  {action}\n' for action in HOOKS)}"
             f'  * (all hooks from above merged)\n'
             f'\n'
             f'[default: {",".join(DEFAULT_ACTIONS)}]'
    )

    grp.add_argument('-k', '--hooks', default=None, metavar='HOOK[,HOOK ...]',
        help=f'Comma separated list. [default from action]'
    )

    ap.add_argument('--print-action-hooks', action='store_true', default=False,
        help='Print the hooks of the given --actions and exit.'
    )

    ap.add_argument('-e', '--exit-on-error', action='store_true', default=False,
        help='Exit on error. [off by default]'
    )

    ap.add_argument('-l', '--follow-links', action='store_true', default=False,
        help='Follow symbolic links. [off by default]'
    )

    ap.add_argument('--version', action='store_true', default=False,
        help='Print version and exit.'
    )

    ap.add_argument('paths', nargs='*',
        help='Paths to recursively scan these paths for "package.json" files. The case of the file is ignored, even on Linux.'
    )

    args = ap.parse_args()

    if args.version:
        print(__version__)
        sys.exit()

    actions_str: str|None = args.actions
    hooks_str: str|None = args.hooks
    paths: list[str] = args.paths or ['.']
    print_action_hooks: bool = args.print_action_hooks
    exit_on_error: bool = args.exit_on_error
    follow_links: bool = args.follow_links

    if print_action_hooks:
        actions: set[str] = set()
        if actions_str is None:
            actions.update(DEFAULT_ACTIONS)
        elif actions_str:
            for action in actions_str:
                action = action.strip().casefold().replace(' ', '_')
                if action == '*':
                    actions.update(HOOKS)
                else:
                    actions.add(action)

        for action in actions:
            action_hooks = HOOKS.get(action)
            if action_hooks is None:
                print(f'Unknown action: {action}', file=sys.stderr)
            else:
                print(f'{action}:')
                for hook in action_hooks:
                    print(f'  {hook}')
                print()

        sys.exit()

    hooks: set[str] = set()

    if actions_str is None and hooks_str is None:
        for action in DEFAULT_ACTIONS:
            hooks.update(HOOKS[action])
    else:
        if actions_str:
            for action in actions_str.split(','):
                norm_action = action.strip().casefold().replace(' ', '_')

                if norm_action == '*':
                    for action_hooks in HOOKS.values():
                        hooks.update(action_hooks)
                else:
                    action_hooks = HOOKS.get(norm_action)
                    if action_hooks is None:
                        print(f'unknown action: {action}')
                        sys.exit(1)

                    hooks.update(action_hooks)

        if hooks_str:
            hooks.update(hooks_str.split(','))

    for match in hookscan(paths, list(hooks), follow_links = follow_links, exit_on_error = exit_on_error):
        print(f'{match.file}:')
        for hook, script in match.hooks.items():
            print(f'  {hook}: {json.dumps(script)}')
        print()

if __name__ == '__main__':
    main()
