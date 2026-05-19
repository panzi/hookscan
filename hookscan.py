#!/usr/bin/env python3

from typing import Generator, NamedTuple, Sequence, Mapping, Final, Literal, Callable

import json
import tomllib
import os
import sys

from os.path import join as join_path, exists

__version__ = '1.0.0'

type Lang = Literal['js', 'rust']

class Match(NamedTuple):
    type: Lang
    file: str
    npm_hooks: dict[str, str]|None = None
    build_rs: str|None = None

# https://docs.npmjs.com/cli/v8/using-npm/scripts

NPM_HOOKS: Final[Mapping[str, Sequence[str]]] = {
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

def hookscan(
        dirs: Sequence[str],
        npm_hooks: Sequence[str] = (),
        build_rs: bool = True,
        follow_links: bool = False,
        on_error: Callable[[str, Exception], None] = lambda path, error: None,
        on_warning: Callable[[str, Warning], None] = lambda path, warning: None,
) -> Generator[Match, None, None]:
    visited: set[str] = set()

    def onerror(error: OSError) -> None:
        on_error(error.filename, error)

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

            if npm_hooks:
                alts = folded.get('package.json', ())
                for file in alts:
                    path = join_path(root, file)
                    try:
                        with open(path, 'rt') as fp:
                            pkg = json.load(fp)

                        scripts = pkg.get('scripts')
                        if scripts is not None:
                            actual_hooks: dict[str, str] = {}
                            for hook in npm_hooks:
                                if hook in scripts:
                                    actual_hooks[hook] = scripts[hook]

                            if actual_hooks:
                                yield Match(
                                    type = 'js',
                                    file = path,
                                    npm_hooks = actual_hooks,
                                )

                    except Exception as error:
                        on_error(path, error)

            if build_rs:
                alts = folded.get('cargo.toml', ())
                for file in alts:
                    path = join_path(root, file)
                    try:
                        with open(path, 'rb') as fp:
                            crate = tomllib.load(fp)

                        pkg = crate.get('package')
                        if pkg and 'build' in pkg:
                            build = pkg['build']

                            if build != False:
                                yield Match(
                                    type = 'rust',
                                    file = path,
                                    build_rs = join_path(root, str(build)),
                                )
                            elif exists(join_path(root, "build.rs")):
                                on_warning(path, Warning(f'build deactivated, but build.rs exists anyway!'))

                        else:
                            build = "build.rs"
                            if build in folded:
                                yield Match(
                                    type = 'rust',
                                    file = path,
                                    build_rs = join_path(root, build),
                                )

                    except Exception as error:
                        on_error(path, error)

DEFAULT_ACTIONS: Final[list[str]] = ['install', 'ci']
DEFAULT_LANGS: Final[list[str]] = ['js', 'rust']

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

    ap.add_argument('--langs', default=None, metavar='LANG[,LANG]',
        help=f'Comma separated list. [default: {",".join(DEFAULT_LANGS)}]'
    )

    grp = ap.add_mutually_exclusive_group()

    grp.add_argument('-a', '--npm-actions', default=None,
        metavar='ACTION[,ACTION ...]',
        help=f'Comma separated list.\n'
             f'\n'
             f'Supported actions:\n'
             f'\n'
             f"{''.join(f'  {action}\n' for action in NPM_HOOKS)}"
             f'  * (all npm hooks from above merged)\n'
             f'\n'
             f'[default: {",".join(DEFAULT_ACTIONS)}]'
    )

    grp.add_argument('-k', '--npm-hooks', default=None, metavar='HOOK[,HOOK ...]',
        help=f'Comma separated list. [default from action]'
    )

    ap.add_argument('--print-npm-action-hooks', action='store_true', default=False,
        help='Print the npm hooks of the given --npm-actions and exit.'
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

    npm_actions_str: str|None = args.npm_actions
    npm_hooks_str: str|None = args.npm_hooks
    paths: list[str] = args.paths or ['.']
    print_npm_action_hooks: bool = args.print_npm_action_hooks
    exit_on_error: bool = args.exit_on_error
    follow_links: bool = args.follow_links
    langs: set[str] = set(args.langs) if args.langs is not None else set(DEFAULT_LANGS)

    if print_npm_action_hooks:
        actions: set[str] = set()
        if npm_actions_str is None:
            actions.update(DEFAULT_ACTIONS)
        elif npm_actions_str:
            for action in npm_actions_str:
                action = action.strip().casefold().replace(' ', '_')
                if action == '*':
                    actions.update(NPM_HOOKS)
                else:
                    actions.add(action)

        for action in actions:
            action_hooks = NPM_HOOKS.get(action)
            if action_hooks is None:
                print(f'Unknown action: {action}', file=sys.stderr)
            else:
                print(f'{action}:')
                for hook in action_hooks:
                    print(f'  {hook}')
                print()

        sys.exit()

    npm_hooks: set[str] = set()

    if 'js' in langs:
        if npm_actions_str is None and npm_hooks_str is None:
            for action in DEFAULT_ACTIONS:
                npm_hooks.update(NPM_HOOKS[action])
        else:
            if npm_actions_str:
                for action in npm_actions_str.split(','):
                    norm_action = action.strip().casefold().replace(' ', '_')

                    if norm_action == '*':
                        for action_hooks in NPM_HOOKS.values():
                            npm_hooks.update(action_hooks)
                    else:
                        action_hooks = NPM_HOOKS.get(norm_action)
                        if action_hooks is None:
                            print(f'unknown action: {action}')
                            sys.exit(1)

                        npm_hooks.update(action_hooks)

            if npm_hooks_str:
                npm_hooks.update(npm_hooks_str.split(','))

    ok = True

    def on_error(path: str, error: Exception) -> None:
        nonlocal ok
        ok = False
        print(f'{path}: {error}', file=sys.stderr)
        if exit_on_error:
            sys.exit(1)

    def on_warning(path: str, warning: Warning) -> None:
        print(f'{path}: Warning: {warning}', file=sys.stderr)

    scanner = hookscan(
        dirs = paths,
        npm_hooks = list(npm_hooks),
        build_rs = 'rust' in langs,
        follow_links = follow_links,
        on_error = on_error,
        on_warning = on_warning,
    )

    for match in scanner:
        print(f'{match.file}:')

        if hooks := match.npm_hooks:
            for hook, script in hooks.items():
                print(f'  {hook}: {json.dumps(script)}')

        if build_rs := match.build_rs:
            print(f'  build: {json.dumps(build_rs)}')

        print()

    if not ok:
        sys.exit(1)

if __name__ == '__main__':
    main()
