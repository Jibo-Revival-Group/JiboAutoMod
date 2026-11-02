import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
import conversion_plan as P


class Preparation(unittest.TestCase):
    def setUp(self):
        self.audit = {'schema': 'openjibo.conversion-inventory.v1',
                      'deviceFingerprintSha256': 'a' * 64, 'releaseFamily': 'v2',
                      'observedAtUtc': '2026-11-01T00:00:00Z', 'auditEvidenceSha256': 'b' * 64,
                      'backups': [{'kind': kind, 'sha256': char * 64, 'sizeBytes': 4096}
                                  for kind, char in [('calibration', 'c'), ('affected-storage', 'd')]]}
        self.target = {'schema': 'openjibo.conversion-target.v1', 'mode': 'isolated',
                       'providerId': 'self-hosted', 'apiOrigin': 'http://192.0.2.20:8080'}

    def test_deterministic_plan_never_enables_device_execution(self):
        p = P.plan(self.audit, self.target)
        self.assertTrue(p['suppliedPreparationFieldsComplete'])
        self.assertEqual(p, P.plan(copy.deepcopy(self.audit), copy.deepcopy(self.target)))
        for key in ('readyForApply', 'executionSupported', 'deviceWritesPerformed',
                    'networkRequestsPerformed', 'cloudOwnershipVerified', 'recoveryBytesVerified'):
            self.assertIs(p[key], False)
        self.assertFalse(p['managedMembershipRequiredForIsolatedMode'])

    def test_unknown_device_and_missing_backups_remain_blocked(self):
        self.audit.update(releaseFamily='unknown', backups=[])
        p = P.plan(self.audit, self.target)
        self.assertEqual(len(p['preparationBlockers']), 3)
        self.assertFalse(p['suppliedPreparationFieldsComplete'])

    def test_explicit_provider_and_https_for_networked_modes(self):
        for mode in ('hybrid', 'managed'):
            target = {**self.target, 'mode': mode, 'providerId': 'owner-selected', 'apiOrigin': 'https://provider.example'}
            self.assertTrue(P.plan(self.audit, target)['providerOnboardingRequired'])
            with self.assertRaises(ValueError):P.plan(self.audit, {**target, 'apiOrigin': 'http://provider.example'})
        with self.assertRaises(ValueError):P.plan(self.audit, {k: v for k, v in self.target.items() if k != 'providerId'})

    def test_rejects_credentials_non_origin_urls_and_loopback(self):
        for origin in ('https://user:secret@example.com', 'https://example.com?token=secret',
                       'https://example.com/#x', 'https://example.com/path', 'ftp://example.com',
                       'http://localhost', 'http://localhost.', 'http://robot.localhost',
                       'http://127.0.0.2', 'http://127.1', 'http://2130706433',
                       'http://[::1]', 'http://[::ffff:127.0.0.1]', 'http://example.com:',
                       'http://example.com:99999',
                       'https://example.com/%2e%2e', 'https://example.com\\foreign'):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                P.plan(self.audit, {**self.target, 'apiOrigin': origin})
        with self.assertRaises(ValueError):P.plan(self.audit, {**self.target, 'password': 'secret'})

    def test_rejects_duplicate_backup_kinds_invalid_hash_size_and_time(self):
        cases = [dict(backups=self.audit['backups'] * 2), dict(auditEvidenceSha256='bad'),
                 dict(observedAtUtc='2026-11-01T00:00:00'), dict(backups=[{'kind': 'calibration', 'sha256': 'c'*64, 'sizeBytes': True}])]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValueError):P.plan({**self.audit, **change}, self.target)

    def test_exclusive_export_does_not_overwrite_plan_or_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'plan.json'
            value = P.plan(self.audit, self.target)
            P.export(value, out)
            original = out.read_bytes()
            with self.assertRaises(FileExistsError):P.export(value, out)
            self.assertEqual(out.read_bytes(), original)
            self.assertEqual(json.loads(original), value)
            for private in ('password', 'privateKey', 'backupPath', 'serialNumber'):
                self.assertNotIn(private, original.decode())

    def test_json_rejects_duplicate_fields_and_oversize(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'input.json'
            for raw in (b'{"schema":1,"schema":2}', b' '*65537, b'{"n":NaN}'):
                source.write_bytes(raw)
                with self.assertRaises(ValueError):P.read_input(source)


if __name__ == '__main__':unittest.main()
