"""A folder that does not keep permission bits is used, and the log says so (leapmotor-mate #401).

On storage that does not keep modes - a FAT disk does not, and a NAS shared folder that maps its own
ACLs onto the mode may not - a directory made 0700 reads back 0777, and chmod does not change that.
Since 4.0.0 Mate refused such a /data at startup - «Private directory permissions required» - and
on a Synology the container stopped, where 3.19.2 had run. Who may read such a folder is decided by
the storage, not by the bits, so refusing protects nothing.
A probe made private by tempfile tells the two storages apart: on storage that keeps modes it reads
back private, and an exposed path is refused exactly as before.
"""
import logging
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from leapmotor_cloud import private_storage


@contextmanager
def acl_share(root):
    """Everything under `root` reads back 0777, whatever was asked: storage that keeps no modes."""
    real_stat, real_fstat = os.stat, os.fstat

    def widen(result):
        return os.stat_result((result.st_mode | 0o777,) + tuple(result)[1:])

    def stat(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        return widen(result) if os.fspath(path).startswith(os.fspath(root)) else result

    with patch('os.stat', stat), patch('os.fstat', lambda fd: widen(real_fstat(fd))):
        yield


@unittest.skipIf(os.name == 'nt', 'POSIX permission bits')
class FolderThatDoesNotKeepModesTests(unittest.TestCase):
    def setUp(self):
        private_storage._MODES_KEPT.clear()

    def test_the_private_folders_are_made_and_the_log_says_why_once(self):
        with tempfile.TemporaryDirectory() as tmp, acl_share(tmp):
            root = Path(tmp) / 'migration-backups'
            with self.assertLogs('leapmotor_cloud.private_storage', logging.WARNING) as said:
                self.assertEqual(private_storage.ensure_private_directory(root), root)
                private_storage.ensure_private_directory(root)
                private_storage.validate_private_directory(root)
            self.assertEqual(len(said.records), 1)
            self.assertIn('does not keep file permissions', said.output[0])
            secret = root / 'parameters.json'
            secret.write_bytes(b'synthetic')
            private_storage.validate_private_file(secret)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['parameters.json'],
                             'the probe leaves nothing behind')

    def test_an_exposed_folder_where_modes_are_kept_is_still_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'private'
            root.mkdir(mode=0o755)
            root.chmod(0o755)
            with self.assertRaises(ValueError):
                private_storage.ensure_private_directory(root)
            secret = Path(tmp) / 'parameters.json'
            secret.write_bytes(b'synthetic')
            secret.chmod(0o644)
            with self.assertRaises(ValueError):
                private_storage.validate_private_file(secret)

    def test_a_probe_that_cannot_be_made_proves_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, acl_share(tmp):
            root = Path(tmp) / 'private'
            with patch('tempfile.mkdtemp', side_effect=PermissionError(13, 'denied')):
                with self.assertRaises(ValueError):
                    private_storage.ensure_private_directory(root)


if __name__ == '__main__':
    unittest.main()
