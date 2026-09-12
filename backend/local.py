"""Start locally with literal values from the ignored .env file (no shell execution)."""
import os
import re
from pathlib import Path


def load_env(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#'):
            continue
        key,separator,value=line.partition('=')
        key=key.strip();value=value.strip()
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*',key):
            raise ValueError('Invalid .env entry; use NAME=value')
        if len(value)>=2 and value[0]==value[-1] and value[0] in ('"', "'"):
            value=value[1:-1]
        os.environ.setdefault(key,value)


if __name__=='__main__':
    load_env(Path(__file__).resolve().parent.parent / '.env')
    from backend.server import run
    run()
