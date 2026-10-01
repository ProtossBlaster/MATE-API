# Protocol and integration reference

Unofficial Python protocol package for Leapmotor. Current package version: `0.1.0a9` (alpha).
This is not an official Leapmotor SDK and is not ready for a production release.
No certificate, private key, account, vehicle identifier or location fixture is
provided. Publishing this package does not provision application credentials.

## Current boundary

The `leapmotor_cloud` package is independent of Mate and of the
third-party SDK Mate used before it. It provides signing, verified TLS transport, caller-supplied
sessions, cloud reads/history, capability models, telemetry interpretation,
certificate lifecycle primitives and explicit command execution primitives.

`command_contracts` now contains the payload/permission validators used by the
4004 adapter. It covers command IDs 110, 120, 130, 160, 170, 171, 180, 190, 192,
193, 220, 230, 240, 301, 320, 360, 361, 370 and 440. A contract is not evidence of
permission or physical execution. ID 220 (sentry mode) carries the contract the
original V1 client used — `{"value":"1"|"0"}`, right 220 — with no ability code
identified in the app, so the account right, the control module and the cloud's own
refusal are its only gate; its actuation is unverified on every model. ID 400 stays
disabled by the examined official-app availability path. ID 193 is not authorized on
the shared B10 account examined in the lab.

Ability codes are documentation, and `ABILITY_NOT_GATED` names the ones that are not a usable
gate because a model was measured to under-declare them: climate (170/171), because the European
T03 omits AC_ON (6) and cools anyway (Mate #67). An id joins that set only with a measurement.

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

## Command contracts

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
`abilities`. For a verified owner binding — on any model — absent permission lists
may be resolved from declared capabilities; explicitly empty permission lists remain
a denial. Shared vehicles require explicit permission/module rights. `carType` is
carried for the caller's payload choices; it never grants or withholds a command.

The planner and contracts share permission rules. CapabilitySnapshot carries
explicit rights_present/module_rights_present flags: an empty supplied list is
not an omitted field. Only an authenticated owner binding may use the
omission exception, on any model. Operating policy is shared, with allow_stale_parked=False
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
- Every model is enabled by the migrated command adapter; the cloud's per-vehicle
  data decides what is permitted, and its refusal is the safety net.
- Physical actuation is proven only on the B10. Payload shapes that were measured to
  differ per model (full climate off) are the caller's to supply.
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

## Session renewal (0.1.0a11)

`LoginClient.refresh(session, device_id=…)` renews a session from its refresh token:
`POST /base/base-user/token/v1/refresh` with `{"refreshToken": …}`, signed as an
authenticated request. Measured against the live cloud on 27 September 2026: it answers
`code 0` with a complete new session — access token, refresh token and signing
parameters — and does **not** re-issue the account certificate, so the renewed session
keeps the pair it already holds and the certificate provider is never called. A refresh
token the cloud will not take answers `302010219 Token refresh error`; that surfaces as
`LoginUnavailable`, never as a session silently left unchanged.

The login response states both lifetimes: `tokenExpireTime` (7200 s measured) and
`refreshTokenExpireTime` (604799 s). Sessions are bounded by the stated value where the
cloud gives one, and by the previous 30-minute default where it does not. A stated
lifetime that is not a plain positive number within a month is refused rather than
guessed at. `CloudSession.renewable(now)` says whether a renewal is possible at all;
deciding WHEN to renew belongs to the caller, as does serialization.

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
private generation (POSIX directory 0700, files 0600; Windows protected
current-user DACL inherited by new generations and files). Windows ACLs are read
back and checked; unsupported storage fails closed.
`private_storage.validate_private_directory(path)` validates an existing root
without changing it, while `ensure_private_directory(path)` creates/protects it.
`validate_private_file(path)` checks file permissions separately, including explicit
Windows file ACEs that could expose a file despite its protected parent.
Existing Windows generations are not rewritten; retire old references explicitly
once readers are quiescent. Failure never removes a prior
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
