"""Synthetic device binding metadata; never authenticate an unverified token."""
import base64,json,unittest
from leapmotor_cloud.session import session_device_id
from leapmotor_cloud.errors import ValidationError

def token(payload):
 p=base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
 return 'e30.'+p+'.synthetic'

class BindingTests(unittest.TestCase):
 def test_authenticated_server_binding_overrides_installation(self):
  self.assertEqual(session_device_id(token({'user_name':'a,b,server-device,d'}),'installation'),'server-device')
 def test_absent_optional_binding_retains_installation(self):
  self.assertEqual(session_device_id(token({}),'installation'),'installation')
 def test_header_injection_rejected_without_echo(self):
  with self.assertRaises(ValidationError) as e:
   session_device_id(token({'user_name':'a,b,PRIVATE\r\nheader,d'}),'installation')
  self.assertNotIn('PRIVATE',str(e.exception))
