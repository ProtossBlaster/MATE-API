# MATE-API (experimental)

Unofficial Python protocol package for Leapmotor. Distribution version `0.1.0a6`.
This is not an official Leapmotor SDK and is not ready for a production release.
No certificate, private key, account, vehicle identifier or location fixture is
provided. Publishing this package does not provision application credentials.

## Current boundary

The `leapmotor_cloud` package is independent of Mate and the legacy
`leapmotor_api` SDK. It provides signing, verified TLS transport, caller-supplied
sessions, cloud reads/history, capability models, telemetry interpretation,
certificate lifecycle primitives and explicit B10 command execution primitives.

`command_contracts` now contains the payload/permission validators used by the
4004 adapter. It covers command IDs 110, 120, 130, 160, 170, 171, 180, 190, 192,
193, 230, 240, 301, 320, 360, 361, 370 and 440. A contract is not evidence of
permission or physical execution. Sentinel 220/400 is not enabled. ID 193 is
not authorized on the shared B10 account examined in the lab.

The separate Mate `api_v2_bridge` uses this package for vehicle DTOs, migrated
command convenience methods, PKCS12 password derivation, login, PIN protection
and account-certificate decoding. The cross-process coordinator and database
integration remain in the lab, not this standalone distribution. Optional Mate
image/diagnostic helpers outside the API path are not part of this replacement.

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

The planner and contracts share permission rules. CapabilitySnapshot carries
explicit rights_present/module_rights_present flags: an empty supplied list is
not an omitted field. Only an authenticated B10 owner binding may use the
omission exception. Operating policy is shared, with allow_stale_parked=False
by default; the lab explicitly opts in. Last-known parked state is not proof of
the current vehicle state. Planner payload coverage remains deliberately smaller
than the full contracts and does not authorize untested physical combinations.

## Safety and compatibility

- Acceptance by the cloud is not physical execution confirmation.
- Ambiguous command outcomes must not be retried automatically.
- Timestamp age alone does not prove sleep; an old parked state is not current
  evidence that a vehicle remains stationary.
- The lab currently permits stale-but-valid parked readings for remote
  commands, retaining the last-known speed/ON3 gates. Physical sleeping-car
  tests remain outstanding.
- B10 is the only model enabled by the migrated command adapter.
- Scheduled commands require an explicit IANA timezone. DST gaps and ambiguous
  wall times are rejected. The lab supplies its configured TZ.
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

Before a stable release: settle application provisioning, validate real revocation recovery,
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
errors omit remote response bodies/secrets and expose only bounded stage/status/code
metadata. Each explicit login call makes at most one login request; the package does
not retry it automatically. Cross-process serialization and throttling belong to the
caller. The Mate adapter serializes attempts and defers repeated failures for 60 seconds.

The Mate coordinator now delegates to this primitive under its process lock.
PKCS12 password resolution and application provisioning remain explicit
integration dependencies; this is not a certificate-free solution.

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

Since 0.1.0a6 the lab uses independent password derivation and vehicle models.
Application-specific parameters and optional password candidates are private
configuration supplied by the installation, not constants shipped by this repo.
The standalone LoginClient is called by, rather than replacing, the lab's
cross-process coordinator.

## Independent Mate interface (0.1.0a6)

mate_compat.MateClientCompatibility is a narrow adapter superclass, not a full
replacement for every historical SDK method. It never sends HTTP itself. Its
reads and command methods delegate to the coordinated adapter, which validates
permissions, payloads, TLS and signing. Unknown commands fail closed.
get_vehicle_status returns this package's TelemetrySnapshot, not a legacy
VehicleStatus. The Mate poller uses get_vehicle_raw_status.

Vehicle.from_dict handles comma-separated permission lists and preserves unknown
capability IDs and raw model metadata. It does not infer battery capacity or
hardware support from a model name. The lab's UI uses the same vehicle parser.

AccountPasswordResolver implements the reconstructed derivation using injected
SM4 round parameters and substitution table. Neither those application parameters
nor private fallback passwords are included. The existing lab migrated them into
private local storage once; subsequent client execution does not import the SDK.
Twelve synthetic input pairs matched the old derivation. This establishes local
algorithm parity, not a new issuer authorization or certificate-free bootstrap.

See [MIGRATION.md](MIGRATION.md) for rollout and rollback boundaries.

## Recovery and material retirement (0.1.0a5)

CloudReadClient invalidates a rejected session on HTTP 401 without replaying the
request. A late response cannot invalidate a newer session. HTTP 403 preserves
the session; proprietary API codes are not guessed to mean revocation.
AccountCertificateManager.invalidate rejects fallback to an explicitly rejected
lease. This requires caller-supplied revocation evidence, not a local CRL claim.

material_cleanup.retire_generations requires an explicit retired-generation
manifest, active paths and quiescent=True. Stop all readers before using it.
It refuses active generations, symlinks, hard links, unexpected files and paths
outside the private root. It is not scheduled automatically in the live lab.
Telemetry observed_at now refers only to vehicle signal 1; cloud_collected_at
is separate and cannot turn an old vehicle frame into a fresh one.

## Public project

Repository: https://github.com/ProtossBlaster/MATE-API

See [STATUS.md](STATUS.md) for the release gates and
[SECURITY.md](SECURITY.md) before contributing. Source code is MIT licensed;
this does not license or distribute Leapmotor credentials, keys or APK assets.
The repository deliberately excludes the vehicle-specific lab database and
application integration. No automatic vehicle commands run in CI.


## September 2026 migration verification

[Migration notes](MIGRATION_NOTES.md) document the verified history schema, command
mapping corrections, server-bound session device metadata, and remaining physical
and provisioning qualifications. The current source has passed the canonical
suite; obsolete experimental test copies are not the release gate. Laboratory
read success is not evidence of physical command execution or vehicle wake-up.
