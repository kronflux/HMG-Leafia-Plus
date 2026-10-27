#!/usr/bin/env python3
"""Validate patch families and compile the data read by the head unit."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PATCHES = ROOT / 'patches'
TOKEN = re.compile(r'[A-Za-z0-9_.-]+\Z')
MD5 = re.compile(r'[0-9a-f]{32}\Z')
APPS = ('HKMC_GPM', 'HKMC_DiPO', 'Iap2ServerApp', 'HKMC_Navi_ExSL')
INPUTS = {f'/system/app/{a}.{ext}' for a in APPS for ext in ('apk', 'odex')}
INPUTS.add('/system/lib/libautoreceiver_infobank.so')
OUTPUTS = {('2_tbt', a) for a in APPS} | {
    ('2_tbt', 'libautoreceiver_infobank.so'), ('3_bridge', 'HKMC_DiPO'),
    ('3_bridge', 'Iap2ServerApp')}
CAPABILITIES = {'cluster-api', 'wifi-hardware'}


def token(value):
    if not isinstance(value, str) or not TOKEN.fullmatch(value) or value in ('.', '..'):
        raise ValueError(f'invalid identifier: {value!r}')


def group_id(family):
    """Fingerprint the content contract, independently of labels and storage paths."""
    contract = {
        'format': 'leafia-patch-set-1',
        'inputs': {'md5': family['inputs']},
        'revision': family['revision'],
        'capabilities': sorted(family['capabilities']),
        'requires': {part: sorted(deps) for part, deps in family['requires'].items()},
        'outputs': sorted(({
            key: out[key] for key in ('part', 'kind', 'name', 'md5', 'sha256')
        } for out in family['outputs']), key=lambda out: (out['part'], out['name'])),
    }
    raw = json.dumps(contract, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=True).encode('ascii')
    return 'set-' + hashlib.sha256(raw).hexdigest()


def validate_catalog(data):
    if data.get('version') != 1 or not data.get('families'):
        raise ValueError('expected catalog version 1 with families')
    ids, identities = set(), set()
    for family in data['families']:
        ident = family['id']; token(ident); token(family['revision'])
        if 'legacy_id' in family: token(family['legacy_id'])
        name = family['name']
        if not isinstance(name, str) or not name or any(ord(c) < 32 for c in name):
            raise ValueError(f'invalid display name: {ident}')
        if ident in ids: raise ValueError(f'duplicate family: {ident}')
        ids.add(ident)
        inputs = family['inputs']
        if set(inputs) != INPUTS or any(not MD5.fullmatch(h) for h in inputs.values()):
            raise ValueError(f'incomplete original bindings: {ident}')
        identity = tuple(sorted(inputs.items()))
        if identity in identities: raise ValueError(f'ambiguous original bindings: {ident}')
        identities.add(identity)
        if set(family['capabilities']) != CAPABILITIES:
            raise ValueError(f'unknown or incomplete capabilities: {ident}')
        if family['requires'] != {'2_tbt': [], '3_bridge': ['2_tbt']}:
            raise ValueError(f'incoherent feature dependencies: {ident}')
        for alias in family['aliases']: token(alias)
        seen = set()
        for out in family['outputs']:
            for key in ('part', 'kind', 'name'): token(out[key])
            key = out['part'], out['name']
            if key in seen: raise ValueError(f'duplicate output: {key}')
            seen.add(key)
            expected_kind = 'file' if out['name'].endswith('.so') else 'app'
            if out['kind'] != expected_kind or not MD5.fullmatch(out['md5']):
                raise ValueError(f'invalid output: {key}')
            path = out['patch']
            if not isinstance(path, str) or len(path.split('/')) != 2:
                raise ValueError('patch must be a relative family/file path')
            for part in path.split('/'): token(part)
            file = PATCHES / path
            if not file.is_file() or PATCHES.resolve() not in file.resolve().parents:
                raise ValueError(f'missing patch: {path}')
            raw = file.read_bytes()
            source = (f"/system/app/{out['name']}.odex" if out['kind'] == 'app'
                      else f"/system/lib/{out['name']}")
            if raw[:4] != b'LPD1' or raw[8:24].hex() != inputs.get(source):
                raise ValueError(f'delta original does not match family: {path}')
            if hashlib.sha256(raw).hexdigest() != out['sha256']:
                raise ValueError(f'patch identity changed: {path}')
        if seen != OUTPUTS: raise ValueError(f'incomplete output group: {ident}')
        if ident != group_id(family):
            raise ValueError(f'content identity changed: {ident}; expected {group_id(family)}')
    return data


def compile_catalog(data):
    validate_catalog(data)
    lines = ['catalog 1']
    for f in data['families']:
        ident = f['id']
        lines.append(f"family {ident} {f['revision']}")
        lines.append(f"name {ident} {f['name']}")
        for capability in f['capabilities']:
            lines.append(f'capability {ident} {capability}')
        for part, dependencies in f['requires'].items():
            for dependency in dependencies:
                lines.append(f'requires {ident} {part} {dependency}')
        for path, digest in sorted(f['inputs'].items()):
            lines.append(f'input {ident} {path} {digest}')
        for o in f['outputs']:
            lines.append('output ' + ident + ' ' + ' '.join(
                o[k] for k in ('part', 'kind', 'name', 'patch', 'md5')))
    return '\n'.join(lines) + '\n'


def refresh_identities(data, compat):
    """Keep compatibility references attached when a content contract changes."""
    mapping = {f['id']: group_id(f) for f in data['families']}
    for f in data['families']:
        f['id'] = mapping[f['id']]
    for variant in compat['variants']:
        if 'patch_families' in variant:
            variant['patch_families'] = [mapping.get(ident, ident)
                                         for ident in variant['patch_families']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--refresh-identities', action='store_true',
                      help='recalculate group identities and their compatibility bindings')
    args = parser.parse_args()
    data = json.loads((PATCHES / 'catalog.json').read_text(encoding='utf-8'))
    if args.refresh_identities:
        compat_path = ROOT / 'docs/data/compat.json'
        compat = json.loads(compat_path.read_text(encoding='utf-8'))
        refresh_identities(data, compat)
    compiled = compile_catalog(data)
    if args.refresh_identities:
        for target, value in ((PATCHES / 'catalog.json', data), (compat_path, compat)):
            target.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n',
                              encoding='utf-8', newline='\n')
    path = PATCHES / 'catalog'
    if args.check:
        if not path.exists() or path.read_text(encoding='utf-8') != compiled:
            parser.exit(1, 'patches/catalog is out of date: run tools/patch-catalog.py\n')
        print('patch catalog is valid and up to date')
    else:
        path.write_text(compiled, encoding='utf-8', newline='\n')
        print('updated patches/catalog')


if __name__ == '__main__': main()
