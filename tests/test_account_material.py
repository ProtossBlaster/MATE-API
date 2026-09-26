import base64,os,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from test_certificates import CertificateTests
from leapmotor_cloud.account_material import AccountMaterialProvider,AccountMaterialUnavailable

class AccountMaterialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'private'
        self.fixture=CertificateTests();self.fixture.setUp();self.fixture.now=datetime.now(timezone.utc)
        bundle,self.password=self.fixture.bundle()
        self.data={'base64Cert':base64.b64encode(bundle).decode()}
        self.provider=AccountMaterialProvider(self.root,lambda data:[self.password])

    def test_private_generations_and_preservation(self):
        first=self.provider(self.data);second=self.provider(self.data)
        self.assertNotEqual(first,second)
        for p in first+second:
            self.assertTrue(p.is_file())
            if os.name!='nt':self.assertEqual(os.stat(p).st_mode&0o777,0o600)
        if os.name!='nt':self.assertEqual(os.stat(self.root).st_mode&0o777,0o700)

    def test_invalid_bundle_keeps_previous(self):
        first=self.provider(self.data)
        with self.assertRaises(AccountMaterialUnavailable):self.provider({'base64Cert':'invalid'})
        self.assertTrue(all(p.exists() for p in first))

    def test_password_candidates(self):
        provider=AccountMaterialProvider(self.root,lambda data:[b'wrong',self.password])
        self.assertTrue(all(p.exists() for p in provider(self.data)))

    def test_wrong_password_is_sanitized(self):
        provider=AccountMaterialProvider(self.root,lambda data:[b'private-password'])
        with self.assertRaises(AccountMaterialUnavailable) as caught:provider(self.data)
        self.assertNotIn('private-password',str(caught.exception))

    def test_expired_material_rejected_and_cleaned(self):
        bundle,password=self.fixture.bundle(days=-0.5)
        with self.assertRaises(AccountMaterialUnavailable):self.provider({'base64Cert':base64.b64encode(bundle).decode()})
        self.assertEqual(list(self.root.iterdir()),[])

    @unittest.skipIf(os.name=='nt','Windows storage is protected by a DACL')
    def test_permissive_root_rejected(self):
        self.root.mkdir(mode=0o755);self.root.chmod(0o755)
        with self.assertRaises(AccountMaterialUnavailable):self.provider(self.data)
