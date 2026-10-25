#!/usr/bin/env python3
"""Propagate SHA-256 pins after deliberate source edits, using the committed tree as the reference.

Every tracked file whose bytes differ from HEAD has its old digest replaced by the new one in
every other tracked file that pins it, repeated until stable so chained pins (codec source ->
SOURCE_MANIFEST.json -> headless_runtime.py -> Skill entry) all follow. Historical evidence
and Markdown notes are never rewritten. Compiled codec digests are untouched: rebuild with
tools/build_native_codec.py and update those by hand.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
FROZEN_PREFIXES = ('docs/evidence/',)
FROZEN_SUFFIXES = ('.md',)
MAX_ROUNDS = 10


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True).stdout


def tracked():
    return [name for name in git('ls-files', '-z').decode().split('\0') if name]


def committed_digest(name):
    try:
        return hashlib.sha256(git('show', 'HEAD:' + name)).hexdigest()
    except subprocess.CalledProcessError:
        return None


def holder(name):
    return not name.startswith(FROZEN_PREFIXES) and not name.endswith(FROZEN_SUFFIXES)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='report stale pins without writing')
    args = parser.parse_args()
    names = tracked()
    known = {name: committed_digest(name) for name in names}
    texts = {}
    for name in filter(holder, names):
        try:
            texts[name] = (ROOT / name).read_bytes().decode('utf-8')
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    changes = []
    for _ in range(MAX_ROUNDS):
        progressed = False
        for name in names:
            path = ROOT / name
            if not path.is_file() or known[name] is None:
                continue
            current = (hashlib.sha256(texts[name].encode('utf-8')).hexdigest() if name in texts
                       else hashlib.sha256(path.read_bytes()).hexdigest())
            if current == known[name]:
                continue
            for other, text in texts.items():
                if other != name and known[name] in text:
                    texts[other] = text.replace(known[name], current)
                    changes.append({'pinned': name, 'in': other, 'old': known[name][:12], 'new': current[:12]})
            # A file can change more than once while its own pins settle; always chase the latest digest.
            known[name] = current
            progressed = True
        if not progressed:
            break
    else:
        raise SystemExit('Pins did not settle; look for a file that pins itself')
    if not args.check:
        for other in {change['in'] for change in changes}:
            (ROOT / other).write_bytes(texts[other].encode('utf-8'))
    print(json.dumps({'status': 'stale' if args.check and changes else 'ok',
                      'written': not args.check and bool(changes), 'changes': changes},
                     ensure_ascii=False, indent=2))
    raise SystemExit(1 if args.check and changes else 0)


if __name__ == '__main__':
    main()
