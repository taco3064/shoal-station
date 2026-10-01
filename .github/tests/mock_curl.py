#!/usr/bin/env python3
"""Local-only Git API/raw transport boundary for the actual workflow Bash."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
state_path = Path(os.environ['MOCK_STATE'])
state = json.loads(state_path.read_text()) if state_path.exists() else {'objects': {}, 'refs': {}, 'calls': []}
url = next(a for a in args if a.startswith('https://'))
output = args[args.index('--output') + 1]
mode = os.environ.get('MOCK_FAILURE', '')
if '-X' in args:
    kind = url.rsplit('/', 1)[1]
    payload = json.loads(args[args.index('-d') + 1])
    state['calls'].append({'kind': kind, 'payload': payload})
    status, response = '201', {}
    if kind == mode:
        status, response = '503', {'message': 'untrusted response SECRET must not be logged'}
    elif kind == 'refs':
        ref = payload['ref']
        if ref in state['refs']:
            status, response = '422', {'message': 'Reference already exists'}
        else:
            state['refs'][ref] = payload['sha']
            response = {'ref': ref, 'object': {'sha': payload['sha']}}
    else:
        if kind == 'blobs':
            raw = base64.b64decode(payload['content'])
            sha = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        else:
            sha = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        state['objects'][sha] = {'kind': kind, 'payload': payload}
        response = {'sha': sha}
    Path(output).write_text(json.dumps(response))
    state_path.write_text(json.dumps(state))
    print(status, end='')
else:
    assert not any('Authorization:' in a for a in args), 'Public retrieval must be anonymous'
    state['calls'].append({'kind': 'anonymous', 'url': url})
    state_path.write_text(json.dumps(state))
    if mode == 'retrieval':
        sys.exit(22)
    tag = url.split('/')[-2]
    commit = state['objects'][state['refs']['refs/tags/' + tag]]['payload']
    tree = state['objects'][commit['tree']]['payload']
    blob = state['objects'][tree['tree'][0]['sha']]['payload']
    raw = base64.b64decode(blob['content'])
    Path(output).write_bytes(raw + (b' ' if mode == 'mismatch' else b''))
