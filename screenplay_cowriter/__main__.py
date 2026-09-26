import sys

from .cli import main

if __name__ == "__main__":
    # The CLI copy is written for a human terminal and carries em dashes and
    # arrows that a legacy code page cannot encode: without this, `--help` dies
    # printing its own text. Pin the streams this process writes to, whatever
    # the launching console claims. tests/test_cli_output_encoding.py.
    for _stream in (sys.stdout, sys.stderr):
        _stream.reconfigure(encoding="utf-8")
    main()
