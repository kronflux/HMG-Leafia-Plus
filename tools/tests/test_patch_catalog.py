"""Catalog contract and preservation of the existing patch families."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CatalogContract(unittest.TestCase):
    def test_all_groups_have_content_identities(self):
        for family in self.data['families']:
            self.assertRegex(family['id'], r'^set-[0-9a-f]{64}$')

    def test_release_has_current_catalog(self):
        result = subprocess.run([sys.executable, str(ROOT / 'tools/patch-catalog.py'),
                                 '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def setUp(self):
        path = ROOT / 'tools/patch-catalog.py'
        if not path.exists():
            return
        spec = importlib.util.spec_from_file_location('catalog', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.data = json.loads((ROOT / 'patches/catalog.json').read_text(encoding='utf-8'))

    def test_group_identity_ignores_labels_paths_and_order(self):
        original = self.data['families'][0]
        changed = copy.deepcopy(original)
        changed.update(id='different', legacy_id='another', name='Another release',
                       aliases=['UNRELATED.'])
        changed['inputs'] = dict(reversed(list(changed['inputs'].items())))
        changed['outputs'].reverse()
        changed['capabilities'].reverse()
        for out in changed['outputs']:
            out['patch'] = 'relocated/' + Path(out['patch']).name
        self.assertEqual(self.module.group_id(original), self.module.group_id(changed))

    def test_group_identity_tracks_content_and_behavior(self):
        original = self.data['families'][0]
        def source(f): f['inputs']['/system/app/HKMC_GPM.apk'] = '0' * 32
        def patch(f): f['outputs'][0]['sha256'] = '0' * 64
        def output(f): f['outputs'][0]['md5'] = '0' * 32
        def revision(f): f['revision'] += '-changed'
        def dependency(f): f['requires']['3_bridge'] = []
        def capability(f): f['capabilities'].append('another')
        for mutate in (source, patch, output, revision, dependency, capability):
            with self.subTest(case=mutate.__name__):
                changed = copy.deepcopy(original); mutate(changed)
                self.assertNotEqual(self.module.group_id(original), self.module.group_id(changed))

    def test_rejects_stale_group_identity(self):
        changed = copy.deepcopy(self.data)
        changed['families'][0]['revision'] += '-changed'
        with self.assertRaisesRegex(ValueError, 'content identity changed'):
            self.module.validate_catalog(changed)

    def test_refresh_preserves_compatibility_bindings_and_text(self):
        changed = copy.deepcopy(self.data)
        original_id = changed['families'][0]['id']
        compat = {'variants': [{'patch_families': [original_id],
                                'verified': 'This firmware\u2019s files'}]}
        changed['families'][0]['revision'] += '-changed'
        self.module.refresh_identities(changed, compat)
        self.assertNotEqual(changed['families'][0]['id'], original_id)
        self.assertEqual(compat['variants'][0]['patch_families'],
                         [changed['families'][0]['id']])
        self.assertEqual(compat['variants'][0]['verified'], 'This firmware\u2019s files')
        self.module.validate_catalog(changed)

    def test_preserves_every_supported_stock_and_output_binding(self):
        if not hasattr(self, 'data'):
            self.skipTest('catalog not implemented')
        for f in self.data['families']:
            legacy = f['legacy_id']
            stock = dict(line.split() for line in
                         (ROOT / 'patches' / legacy / 'stock').read_text().splitlines())
            self.assertEqual({Path(p).name: h for p, h in f['inputs'].items()}, stock)
            outputs = [line.split() for line in
                       (ROOT / 'patches' / legacy / 'manifest').read_text().splitlines()]
            self.assertEqual([[o[k] for k in ('part', 'kind', 'name', 'patch', 'md5')]
                              for o in f['outputs']], outputs)
        legacy = {line.split()[1] for line in (ROOT / 'patches/cars').read_text().splitlines()
                  if line and not line.startswith('#')}
        self.assertTrue(legacy <= {f['legacy_id'] for f in self.data['families']})

    def test_rejects_invalid_contracts(self):
        if not hasattr(self, 'data'):
            self.skipTest('catalog not implemented')
        def duplicate(d): d['families'].append(copy.deepcopy(d['families'][0]))
        def ambiguous(d):
            f = copy.deepcopy(d['families'][0]); f['id'] = 'another'; d['families'].append(f)
        def traversal(d): d['families'][0]['outputs'][0]['patch'] = '../outside.lpd'
        def missing(d): d['families'][0]['outputs'][0]['patch'] = 'absent/missing.lpd'
        def whitespace(d): d['families'][0]['id'] = 'two words'
        def dependency(d): d['families'][0]['requires']['3_bridge'] = ['absent']
        def partial(d): del d['families'][0]['inputs']['/system/app/HKMC_GPM.apk']
        def digest(d): d['families'][0]['outputs'][0]['sha256'] = '0' * 64
        for mutate in (duplicate, ambiguous, traversal, missing, whitespace, dependency, partial, digest):
            with self.subTest(case=mutate.__name__):
                d = copy.deepcopy(self.data); mutate(d)
                with self.assertRaises(ValueError): self.module.validate_catalog(d)

    def test_compilation_is_deterministic_and_plain_data(self):
        if not hasattr(self, 'data'):
            self.skipTest('catalog not implemented')
        out = self.module.compile_catalog(self.data)
        self.assertEqual(out, self.module.compile_catalog(copy.deepcopy(self.data)))
        self.assertTrue(out.startswith('catalog 1\n'))
        self.assertEqual(out, (ROOT / 'patches/catalog').read_text())
        self.assertNotIn('$', out)


if __name__ == '__main__': unittest.main()
