import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    'compat_built', Path(__file__).with_name('compat-built.py'))
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)


class CompatibilityBuilds(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patches = self.root / 'patches'
        self.patches.mkdir()
        self.db = self.root / 'compat.json'

    def write_catalog(self, general_first=False):
        families = [
            {'id': 'v014', 'aliases': ['CVEV.CAN.0000.V014.'], 'outputs': [
                dict(part='2_tbt', kind='app', name='GPM', patch='v014/GPM.lpd', md5='1' * 32)]},
            {'id': 'v015', 'aliases': ['CVEV.CAN.', 'ALIAS.CAN.'], 'outputs': [
                dict(part='2_tbt', kind='app', name='GPM', patch='v015/GPM.lpd', md5='2' * 32)]}]
        if general_first: families.reverse()
        (self.patches / 'catalog.json').write_text(json.dumps({'version': 1, 'families': families}))

    def write_variants(self, *prefixes):
        self.write_catalog()
        self.db.write_text(json.dumps({'variants': [
            {'id': str(i), 'product_prefix': p} for i, p in enumerate(prefixes)
        ]}))

    def run_generator(self, check=False):
        argv = ['compat-built.py'] + (['--check'] if check else [])
        with patch.object(compat, 'PATCHES', str(self.patches)), \
                patch.object(compat, 'COMPAT', str(self.db)), \
                patch('sys.argv', argv), contextlib.redirect_stdout(io.StringIO()):
            compat.main()
        return json.loads(self.db.read_text())['variants']

    def test_firmware_specific_and_general_rows_keep_separate_outputs(self):
        self.write_variants('CVEV.CAN.0000.V014.', 'CVEV.CAN.')
        rows = self.run_generator()
        self.assertEqual(rows[0]['built']['/system/app/GPM.apk'], ['1' * 32])
        self.assertEqual(rows[1]['built']['/system/app/GPM.apk'], ['2' * 32])

    def test_alias_order_for_legacy_display_rows(self):
        self.write_variants('CVEV.CAN.0000.V014.')
        self.write_catalog(general_first=True)
        self.assertEqual(self.run_generator()[0]['built']['/system/app/GPM.apk'],
                         ['2' * 32])

    def test_aliases_for_one_family_share_outputs(self):
        self.write_variants(['CVEV.CAN.', 'ALIAS.CAN.'])
        self.assertEqual(self.run_generator()[0]['built']['/system/app/GPM.apk'],
                         ['2' * 32])

    def test_aliases_for_different_families_refuse_without_writing(self):
        self.write_variants(['CVEV.CAN.0000.V014.', 'ALIAS.CAN.'])
        before = self.db.read_bytes()
        with self.assertRaisesRegex(SystemExit, 'several patch sets'):
            self.run_generator()
        self.assertEqual(self.db.read_bytes(), before)

    def test_explicit_binding_can_combine_firmware_families(self):
        self.write_variants('CVEV.CAN.')
        data = json.loads(self.db.read_text())
        data['variants'][0]['patch_families'] = ['v014', 'v015']
        self.db.write_text(json.dumps(data))
        self.assertEqual(self.run_generator()[0]['built']['/system/app/GPM.apk'],
                         ['1' * 32, '2' * 32])

    def test_unknown_prefix_does_not_inherit_a_known_family(self):
        self.write_variants('UNKNOWN.')
        self.assertNotIn('built', self.run_generator()[0])

    def test_check_detects_stale_outputs_without_writing(self):
        self.write_variants('ALIAS.CAN.')
        before = self.db.read_bytes()
        with self.assertRaisesRegex(SystemExit, 'out of date'):
            self.run_generator(check=True)
        self.assertEqual(self.db.read_bytes(), before)
        self.run_generator()
        self.run_generator(check=True)


if __name__ == '__main__':
    unittest.main()
