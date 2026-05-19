hookscan.py
===========

Scan for hooks in `package.json` files.

**NOTE:** It is of course too late to scan for these hooks if you have installed
the packages without passing `--ignore-scripts` to `npm`/`yarn`.

Usage
-----

```
usage: hookscan.py [-h] [-a ACTION[,ACTION ...] | -k HOOK[,HOOK ...]]
                   [--print-action-hooks] [-e] [-l] [--version]
                   [paths ...]

positional arguments:
  paths                 Paths to recursively scan these paths for 
                        "package.json" files. The case of the file is ignored,
                        even on Linux.

options:
  -h, --help            show this help message and exit
  -a ACTION[,ACTION ...], --actions ACTION[,ACTION ...]
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
                          * (all hooks from above merged)
                        
                        [default: install,ci]
  -k HOOK[,HOOK ...], --hooks HOOK[,HOOK ...]
                        Comma separated list. [default from action]
  --print-action-hooks  Print the hooks of the given --actions and exit.
  -e, --exit-on-error   Exit on error. [off by default]
  -l, --follow-links    Follow symbolic links. [off by default]
  --version             Print version and exit.
```

License
-------

[MIT](LICENSE)
