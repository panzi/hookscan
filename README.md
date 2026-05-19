hookscan.py
===========

Scan for hooks in `package.json` files and for Rust build scripts.

**NOTE:** It is of course too late to scan for these hooks if you have installed
the packages without passing `--ignore-scripts` to `npm`/`yarn`.

Usage
-----

```
usage: hookscan [-h] [--langs LANG[,LANG]] [-a ACTION[,ACTION ...] | -k
                HOOK[,HOOK ...]] [--print-npm-action-hooks] [-e] [-l]
                [--version]
                [paths ...]

positional arguments:
  paths                 Paths to recursively scan these paths for 
                        "package.json" files. The case of the file is ignored,
                        even on Linux.

options:
  -h, --help            show this help message and exit
  --langs LANG[,LANG]   Comma separated list. [default: js,rust]
  -a ACTION[,ACTION ...], --npm-actions ACTION[,ACTION ...]
                        Comma separated list.
                        
                        Supported actions:
                        
                          cache_add
                          ci
                          diff
                          install
                          pack
                          publish
                          rebuild
                          restart
                          start
                          stop
                          test
                          version
                          * (all npm hooks from above merged)
                        
                        [default: install,ci]
  -k HOOK[,HOOK ...], --npm-hooks HOOK[,HOOK ...]
                        Comma separated list. [default from action]
  --print-npm-action-hooks
                        Print the npm hooks of the given --npm-actions and 
                        exit.
  -e, --exit-on-error   Exit on error. [off by default]
  -l, --follow-links    Follow symbolic links. [off by default]
  --version             Print version and exit.
```

License
-------

[MIT](LICENSE)
