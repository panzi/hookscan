#!/usr/bin/env python3

from typing import Generator, NamedTuple, Sequence, Mapping, Final, Literal, Callable

import json
import tomllib
import os
import sys

from os.path import join as join_path, exists, realpath
from collections import defaultdict

__version__ = '1.0.0'

type Lang = Literal['js', 'rust']

class Match(NamedTuple):
    type: Lang
    file: str
    hooks: dict[str, str|list[str]]

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

# PHP composer: https://getcomposer.org/doc/articles/scripts.md
# TODO: per-command grouping?
COMPOSER_EVENTS: Final[Mapping[str, Sequence[str]]] = {
    'command': [
        'pre-install-cmd',
        'post-install-cmd',
        'pre-update-cmd',
        'post-update-cmd',
        'pre-status-cmd',
        'post-status-cmd',
        'pre-archive-cmd',
        'post-archive-cmd',
        'pre-autoload-dump',
        'post-autoload-dump',
        'post-root-package-install',
        'post-create-project-cmd',
    ],
    'installer': [
        'pre-operations-exec',
    ],
    'package': [
        'pre-package-install',
        'post-package-install',
        'pre-package-update',
        'post-package-update',
        'pre-package-uninstall',
        'post-package-uninstall',
    ],
    'plugin': [
        'init',
        'command',
        'pre-file-download',
        'post-file-download',
        'pre-command-run',
        'pre-pool-create',
    ],
}

def hookscan(
        dirs: Sequence[str],
        npm_hooks: Sequence[str] = (),
        build_rs: bool = True,
        composer_events: Sequence[str] = (),
        follow_links: bool = False,
        on_error: Callable[[str, Exception], None] = lambda path, error: None,
        on_warning: Callable[[str, Warning], None] = lambda path, warning: None,
) -> Generator[Match, None, None]:
    visited: set[str] = set()

    for top in dirs:
        for root, dirs, files in os.walk(top, followlinks = follow_links, onerror = lambda error: on_error(error.filename, error)):
            root = realpath(root)

            if root in visited:
                continue

            visited.add(root)

            # folded in order to ignore case just in case for Windows
            folded: defaultdict[str, list[str]] = defaultdict(list)
            for file in files:
                folded_file = file.casefold()
                folded[folded_file].append(file)

            if npm_hooks:
                alts = folded.get('package.json', ())
                for file in alts:
                    path = join_path(root, file)
                    try:
                        with open(path, 'rt') as fp:
                            pkg = json.load(fp)

                        scripts = pkg.get('scripts')
                        if scripts is not None:
                            actual_hooks: dict[str, str|list[str]] = {}
                            for hook in npm_hooks:
                                if hook in scripts:
                                    actual_hooks[hook] = scripts[hook]

                            if actual_hooks:
                                yield Match(
                                    type = 'js',
                                    file = path,
                                    hooks = actual_hooks,
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
                                    hooks = { 'build': join_path(root, str(build)) },
                                )
                            elif exists(join_path(root, "build.rs")):
                                on_warning(path, Warning(f'build deactivated, but build.rs exists anyway!'))

                        else:
                            build = "build.rs"
                            if build in folded:
                                yield Match(
                                    type = 'rust',
                                    file = path,
                                    hooks = { 'build': join_path(root, str(build)) },
                                )

                    except Exception as error:
                        on_error(path, error)

            if composer_events:
                alts = folded.get('composer.json', ())
                for file in alts:
                    path = join_path(root, file)
                    try:
                        with open(path, 'rt') as fp:
                            pkg = json.load(fp)

                        scripts = pkg.get('scripts')
                        if scripts is not None:
                            actual_events: dict[str, str|list[str]] = {}
                            for event in composer_events:
                                if event in scripts:
                                    actual_events[event] = scripts[event]

                            if actual_events:
                                yield Match(
                                    type = 'js',
                                    file = path,
                                    hooks = actual_events,
                                )

                    except Exception as error:
                        on_error(path, error)

DEFAULT_NPM_ACTIONS: Final[list[str]] = ['install', 'ci']
DEFAULT_COMPOSER_EVENTS: Final[list[str]] = ['command', 'installer']
DEFAULT_LANGS: Final[list[str]] = ['js', 'rust', 'php']

def comma_list(value: str) -> list[str]:
    value = value.strip()

    return [item.strip() for item in value.split(',')] if value else []

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

    ap.add_argument('--langs', default=DEFAULT_LANGS, type=comma_list, metavar='LANG[,LANG]',
        help=f'Comma separated list. [default: {",".join(DEFAULT_LANGS)}]'
    )

    grp = ap.add_mutually_exclusive_group()

    grp.add_argument('-a', '--npm-actions', default=None,
        type=comma_list,
        metavar='ACTION[,ACTION ...]',
        help=f'Comma separated list.\n'
             f'\n'
             f'Supported actions:\n'
             f'\n'
             f"{''.join(f'  {action}\n' for action in NPM_HOOKS)}"
             f'  * (all npm hooks from above merged)\n'
             f'\n'
             f'[default: {",".join(DEFAULT_NPM_ACTIONS)}]'
    )

    grp.add_argument('-k', '--npm-hooks', default=None,
        type=comma_list,
        metavar='HOOK[,HOOK ...]',
        help=f'Comma separated list. [default from --npm-action]'
    )

    grp = ap.add_mutually_exclusive_group()

    grp.add_argument('--composer-event-groups', default=None, metavar='GROUP[,GROUP ...]',
        type=comma_list,
        help=f'Comma separeted list.\n'
             f'\n'
             f'Supported groups:\n'
             f'\n'
             f"{''.join(f'  {group}\n' for group in COMPOSER_EVENTS)}"
             f'  * (all composer events from above merged)\n'
             f'\n'
             f'[default: {",".join(DEFAULT_COMPOSER_EVENTS)}]'
    )

    grp.add_argument('--composer-events', default=None, metavar='EVENT[,EVENT ...]',
        type=comma_list,
        help=f"Comma separated list. [default from --composer-event-groups]"
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

    npm_actions: list[str]|None = args.npm_actions
    npm_hooks: list[str]|None = args.npm_hooks
    print_npm_action_hooks: bool = args.print_npm_action_hooks

    composer_event_groups: list[str]|None = args.composer_event_groups
    composer_events: list[str]|None = args.composer_events

    exit_on_error: bool = args.exit_on_error
    follow_links: bool = args.follow_links
    langs: set[str] = set(args.langs)

    paths: list[str] = args.paths or ['.']

    if print_npm_action_hooks:
        actions: set[str] = set()
        if npm_actions is None:
            actions.update(DEFAULT_NPM_ACTIONS)
        elif npm_actions:
            for action in npm_actions:
                action = action.casefold().replace(' ', '_')
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

    npm_hooks_set: set[str] = set()

    if 'js' in langs:
        langs.remove('js')
        if npm_actions is None and npm_hooks is None:
            for action in DEFAULT_NPM_ACTIONS:
                npm_hooks_set.update(NPM_HOOKS[action])
        else:
            if npm_actions:
                for action in npm_actions:
                    norm_action = action.casefold().replace(' ', '_')

                    if norm_action == '*':
                        for action_hooks in NPM_HOOKS.values():
                            npm_hooks_set.update(action_hooks)
                    else:
                        action_hooks = NPM_HOOKS.get(norm_action)
                        if action_hooks is None:
                            print(f'unknown npm action: {action}')
                            sys.exit(1)

                        npm_hooks_set.update(action_hooks)

            if npm_hooks:
                npm_hooks_set.update(npm_hooks)

    composer_events_set: set[str] = set()

    if 'php' in langs:
        langs.remove('php')
        if composer_event_groups is None and composer_events is None:
            for event in DEFAULT_COMPOSER_EVENTS:
                composer_events_set.update(COMPOSER_EVENTS[event])
        else:
            if composer_event_groups:
                for group in composer_event_groups:
                    norm_group = group.casefold().replace(' ', '_')

                    if norm_group == '*':
                        for events in COMPOSER_EVENTS.values():
                            composer_events_set.update(events)
                    else:
                        events = COMPOSER_EVENTS.get(norm_group)
                        if events is None:
                            print(f'unknown composer event group: {group}')
                            sys.exit(1)

                        composer_events_set.update(events)

            if composer_events:
                composer_events_set.update(composer_events)

    build_rs = 'rust' in langs
    if build_rs:
        langs.remove('rust')

    if langs:
        print(f'illegal value(s) for --langs: {', '.join(langs)}', file=sys.stderr)
        sys.exit(1)

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
        npm_hooks = list(npm_hooks_set),
        composer_events = list(composer_events_set),
        build_rs = build_rs,
        follow_links = follow_links,
        on_error = on_error,
        on_warning = on_warning,
    )

    for match in scanner:
        print(f'{match.file}:')

        if hooks := match.hooks:
            was_array = False
            for hook, script in hooks.items():
                if isinstance(script, (list, tuple)):
                    if was_array:
                        print()
                    print(f'  {hook}:')
                    for entry in script:
                        print(f'  - {json.dumps(entry)}')
                    was_array = True
                else:
                    print(f'  {hook}: {json.dumps(script)}')
                    was_array = False

        print()

    if not ok:
        sys.exit(1)

if __name__ == '__main__':
    main()
