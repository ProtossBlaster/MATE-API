# MATE-API (experimental)

Unofficial Python protocol package for Leapmotor. Distribution version `0.1.0a3`.
This is not an official Leapmotor SDK and is not ready for a production release.
No certificate, private key, account, vehicle identifier or location fixture is
provided. Publishing this package does not provision application credentials.

## Current boundary

The `leapmotor_cloud` package is independent of Mate and the legacy
`leapmotor_api` SDK. It provides signing, verified TLS transport, caller-supplied
sessions, cloud reads/history, capability models, telemetry interpretation,
certificate lifecycle primitives and explicit B10 command execution primitives.

`command_contracts` now contains the payload/permission validators used by the
4001 adapter. It covers command IDs 110, 120, 130, 160, 170, 171, 180, 190, 192,
193, 230, 240, 301, 320, 360, 361, 370 and 440. A contract is not evidence of
permission or physical execution. Sentinel 220/400 is not enabled. ID 193 is
not authorized on the shared B10 account examined in the lab.

The separate 4001 `api_v2_bridge` still uses legacy local vehicle DTOs, PIN
cryptography and account-certificate decoding. Those dependencies have NOT yet
been eliminated. Its coordinated login/database implementation is not part of
this standalone package. Do not confuse extraction of validators with complete
migration of authentication or replacement of every Mate integration.

## Installation and tests

Python >=3.11. Certificate helpers additionally require cryptography >=42:

```sh
pip install '.[certificates]'
python -m unittest discover -s tests -v
```

Tests are offline with synthetic data. One reference-catalog test may skip when
an external diagnostic fixture is unavailable. No real car command is sent.
Other-model simulations do not establish physical compatibility.

## B10 contracts

```python
from leapmotor_cloud.command_contracts import prepare

# vehicle must represent a fresh authenticated vehicle-list entry, not an
# arbitrary untrusted dictionary. See below for the compatibility protocol.
state = prepare('240', {'value': '10'}, vehicle)
```

The compatibility object supplies `vin`, `car_type`, `is_shared`, `raw`,
`has_right(code)`, `has_module_right(code)` and `has_ability(code)`. Seat mapping
uses `rudder` (`left` or `right`). The existing default is left-hand drive;
callers must provide known driving-side metadata for right-hand-drive vehicles.
Never use these examples to invent a vehicle's rights or hardware abilities.

The raw binding includes `vin`, `carType`, `rightList`, `moduleRights` and
`abilities`. For a verified B10 owner binding, absent permission lists may be
resolved from declared capabilities; explicitly empty permission lists remain
a denial. Shared vehicles require explicit permission/module rights.

The generic conservative `capabilities.evaluate` and older `b10_planner` remain
separate APIs; they do not automatically inherit the lab's newer owner and
sleeping-vehicle policies. Unifying these APIs is a release blocker.

## Safety and compatibility

- Acceptance by the cloud is not physical execution confirmation.
- Ambiguous command outcomes must not be retried automatically.
- Timestamp age alone does not prove sleep; an old parked state is not current
  evidence that a vehicle remains stationary.
- The lab currently permits stale-but-valid parked readings for remote
  commands, retaining the last-known speed/ON3 gates. Physical sleeping-car
  tests remain outstanding.
- B10 is the only model enabled by the migrated command adapter.
- Scheduled command date validation currently assumes Europe/Rome. This is a
  lab limitation, not global timezone support.
- Imported cloud trip summaries do not include a verified historical GPS track.
- Charge history was available to the owner but not the shared account in the
  observed case; this is not a universal claim about every account or model.
- Unknown raw signals retain their identifiers; meanings are not inferred.

## Application bootstrap and publication

The app's built-in application certificate matches the certificate already
used in the lab, and its matching private key was verified offline. Neither is
included here. Redistribution permission has not been established. A private
key embedded in a public image would be extractable.

Account certificate validation/renewal is distinct from provisioning the
application certificate required for initial login. A new-install login-only
wizard still needs a legitimate distribution-side provisioning mechanism.
Existing installations can reuse valid application material.

Before a public release: complete independent authentication/PIN/DTO support,
unify command APIs and policies, settle application provisioning, choose a
license after reviewing reused code, validate account switching/revocation,
complete physical trials, and document a tested installation/rollback matrix.
This repository publishes experimental source only; no stable release is claimed.

## Independent login (0.1.0a2)

`leapmotor_cloud.authentication.LoginClient` implements the reconstructed login
request without the legacy SDK. It requires the certificates extra, an explicit
transport, application certificate/key, device identity, clock, nonce source and
an account-certificate provider. The provider consumes the authenticated login
response and returns private local PEM paths. No credential files are bundled.

The result is an immutable `CloudSession`. Application/account certificate pairs
are checked locally; token/signing material is validated before invoking the
provider, and expiry is checked again afterwards. Requests are single-attempt,
errors omit remote response bodies/secrets, and one instance rate-limits login
attempts to one per minute. Cross-process coordination remains the caller's job.

This primitive is verified with synthetic offline transport, not yet substituted
for the coordinated login running on 4001. PKCS12 password resolution/provisioning
and PIN encryption remain explicit integration work; the module must not be
presented as a complete fresh-install or certificate-free solution.

## PIN and account material (0.1.0a3)

`pin.encrypt_operate_password` implements token-bound AES-CBC/PKCS7 PIN
protection and rejects missing/short tokens instead of a static-key fallback.
The lab adapter now uses this function. Twelve synthetic cases match the
previous SDK output; no real PIN or vehicle command was used in the comparison.

`account_material.AccountMaterialProvider` decodes the authenticated PKCS12
response, preserves its certificate chain, validates the pair and writes a new
private generation (directory 0700, files 0600). Failure never removes a prior
generation. Retired generations require explicit coordinated garbage collection.
The lab uses this provider instead of the old SDK's decoding/file writer.

The password-candidate resolver in the lab still uses compatibility helpers
from the old SDK. Therefore password derivation/fallback removal and vehicle DTO
replacement remain incomplete; do not advertise the whole lab adapter as SDK-free.
The standalone LoginClient is still not the coordinator used by the live lab.

## Public project

Repository: https://github.com/ProtossBlaster/MATE-API

See [STATUS.md](STATUS.md) for the release gates and
[SECURITY.md](SECURITY.md) before contributing. Source code is MIT licensed;
this does not license or distribute Leapmotor credentials, keys or APK assets.
The repository deliberately excludes the vehicle-specific lab database and
application integration. No automatic vehicle commands run in CI.
