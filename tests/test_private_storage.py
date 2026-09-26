import os
from pathlib import Path
import tempfile
import unittest

class PrivateStorageTests(unittest.TestCase):
    def test_private_directory_and_account_generation(self):
        from leapmotor_cloud.private_storage import ensure_private_directory
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'private'
            ensure_private_directory(root)
            self.assertTrue(root.is_dir())
            if os.name!='nt':self.assertEqual(root.stat().st_mode&0o777,0o700)
            ensure_private_directory(root)

    @unittest.skipIf(os.name=='nt','POSIX permission bits do not describe Windows ACLs')
    def test_existing_permissive_directory_is_rejected(self):
        from leapmotor_cloud.private_storage import ensure_private_directory
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'private';root.mkdir(mode=0o755);root.chmod(0o755)
            with self.assertRaises(ValueError):ensure_private_directory(root)

    def test_validation_does_not_create_directory(self):
        from leapmotor_cloud.private_storage import validate_private_directory
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'missing'
            with self.assertRaises(ValueError):validate_private_directory(root)
            self.assertFalse(root.exists())

    @unittest.skipUnless(os.name=='nt','Native Windows ACL inspection')
    def test_windows_dacl_excludes_other_users_and_rejects_tampering(self):
        from leapmotor_cloud.private_storage import ensure_private_directory, validate_private_directory
        import json, subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root=ensure_private_directory(Path(tmp)/'private')
            validate_private_directory(root)
            child=Path(tempfile.mkdtemp(prefix='generation-',dir=root))
            ensure_private_directory(child)
            key=child/'key.pem';key.write_bytes(b'synthetic-test-only')
            script = """
$ErrorActionPreference = 'Stop'
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$paths = @($env:PRIVATE_TEST_ROOT, $env:PRIVATE_TEST_GENERATION, (Join-Path $env:PRIVATE_TEST_GENERATION 'key.pem'))
@($paths | ForEach-Object {
    $acl = Get-Acl -LiteralPath $_
    $rules = @($acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]))
    [pscustomobject]@{ Protected = $acl.AreAccessRulesProtected; Count = $rules.Count;
        OnlyCurrentUser = (@($rules | Where-Object { $_.IdentityReference.Value -ne $sid -or $_.AccessControlType -ne 'Allow' }).Count -eq 0);
        FullControl = (@($rules | Where-Object { ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::FullControl) -ne [System.Security.AccessControl.FileSystemRights]::FullControl }).Count -eq 0) }
}) | ConvertTo-Json -Compress
"""
            env=dict(os.environ,PRIVATE_TEST_ROOT=str(root),PRIVATE_TEST_GENERATION=str(child))
            result=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',script],env=env,check=True,capture_output=True,text=True)
            entries=json.loads(result.stdout)
            self.assertTrue(entries[0]['Protected'])
            for entry in entries:
                self.assertEqual(entry['Count'],1)
                self.assertTrue(entry['OnlyCurrentUser'])
                self.assertTrue(entry['FullControl'])
            # Explicitly introduce Everyone read access; read-only validation
            # must reject it, and protecting again must remove that ACE.
            subprocess.run(['icacls',str(root),'/grant','*S-1-1-0:(R)'],check=True,capture_output=True)
            with self.assertRaises(ValueError):validate_private_directory(root)
            ensure_private_directory(root)
            validate_private_directory(root)

    def test_explicit_generation_retirement_uses_platform_protection(self):
        from leapmotor_cloud.private_storage import ensure_private_directory
        from leapmotor_cloud.material_cleanup import retire_generations
        with tempfile.TemporaryDirectory() as tmp:
            root=ensure_private_directory(Path(tmp)/'private')
            old=root/'generation-old';old.mkdir(mode=0o700)
            (old/'key.pem').write_bytes(b'synthetic-only')
            self.assertEqual(retire_generations(root,[old],active_paths=[],quiescent=True),1)
            self.assertFalse(old.exists())
