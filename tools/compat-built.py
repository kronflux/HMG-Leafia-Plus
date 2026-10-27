#!/usr/bin/env python3
"""Keep docs/data/compat.json's "built" lists in step with the patch sets.

usage: compat-built.py [--check]

For each car on the compatibility page, "built" lists the md5 of every file our
package installs on it (from patches/catalog.json and patches/common/optional),
so the page can tell a unit that already runs Leafia from one with unknown files.
Explicit patch_families bind display rows to the catalog; aliases cover older rows.
With --check nothing is written; it exits 1 if compat.json is out of date (CI).
"""
import json, os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
COMPAT = os.path.join(ROOT, 'docs', 'data', 'compat.json')
PATCHES = os.path.join(ROOT, 'patches')


def manifest_lines(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for l in f:
            p = l.split()
            if len(p) == 5 and not p[0].startswith('#'):
                out.append(p)
    return out


def built_for(patch_set):
    built = {}
    with open(os.path.join(PATCHES, 'catalog.json'), encoding='utf-8') as f:
        catalog = json.load(f)
    family = next((f for f in catalog['families'] if f['id'] == patch_set), None)
    if family is None:
        raise ValueError('unknown patch family: ' + patch_set)
    lines = [[o[k] for k in ('part', 'kind', 'name', 'patch', 'md5')]
             for o in family['outputs']]
    lines += manifest_lines(os.path.join(PATCHES, 'common', 'optional'))
    for part, kind, name, _patch, md5 in lines:
        f = '/system/app/%s.apk' % name if kind == 'app' else '/system/lib/%s' % name
        if md5 not in built.setdefault(f, []):
            built[f].append(md5)
    return {f: sorted(v) for f, v in sorted(built.items())}


def main():
    check = '--check' in sys.argv[1:]
    sets = {}
    with open(os.path.join(PATCHES, 'catalog.json'), encoding='utf-8') as f:
        catalog = json.load(f)
    for family in catalog['families']:
        for alias in family['aliases']:
            sets[alias] = family['id']
    with open(COMPAT, encoding='utf-8') as f:
        raw = f.read()
    db = json.loads(raw)
    for v in db['variants']:
        prefixes = v['product_prefix'] if isinstance(v['product_prefix'], list) else [v['product_prefix']]
        # Legacy display rows use ordered aliases; explicit bindings can list several families.
        found = set()
        for p in prefixes:
            for c in sets:
                if p.startswith(c):
                    found.add(sets[c])
                    break
        if len(found) > 1 and 'patch_families' not in v:
            sys.exit('%s: product prefixes map to several patch sets %s' % (v['id'], sorted(found)))
        bindings = v.get('patch_families', sorted(found))
        combined = {}
        for family in bindings:
            for path, digests in built_for(family).items():
                combined.setdefault(path, set()).update(digests)
        b = {path: sorted(digests) for path, digests in sorted(combined.items())}
        if b:
            v['built'] = b
        else:
            v.pop('built', None)
    new = json.dumps(db, indent=2, ensure_ascii=False) + '\n'
    if new == raw:
        print('compat.json built lists are up to date')
        return
    if check:
        sys.exit('docs/data/compat.json "built" lists are out of date: run tools/compat-built.py')
    with open(COMPAT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new)
    print('updated docs/data/compat.json')


if __name__ == '__main__':
    main()
