# Implementation and release gates

Current version: 0.1.0a5, experimental. Not a complete login-only application.

## Implemented and tested offline

- Signing, explicit verified TLS transport and caller-supplied session models.
- Single-attempt login primitive with injected application/account material.
- Token-bound PIN encryption with no static-key fallback.
- PKCS12 decoding, certificate/key checks and private file generations.
- B10 command payload/permission validators and command execution primitives.
- Cloud history reads, pagination and preservation of unknown/raw data.
- Cross-platform Python package and offline synthetic regression suite.
- Explicit IANA timezone and injected clock for appointments; DST gaps and
  ambiguous wall times are rejected instead of silently shifted.
- Planner capability IDs derive from the command contracts (one source).
- Lab login delegates to LoginClient under its existing process lock/cooldown.
- Shared permission rules distinguish omitted owner permissions from explicit
  denial; shared accounts do not receive the owner exception.
- Shared operating policy defaults to fresh state. The lab explicitly opts into
  last-known parked state; neither mode proves physical execution.
- Vehicle timestamp and cloud collection timestamp remain distinct.
- HTTP 401 invalidates only the rejected session, never a newer replacement;
  HTTP 403 does not trigger session invalidation. No request is replayed.
- Explicit certificate invalidation and quiescent-generation retirement helpers.
- Synthetic fresh-cache, backup/restore, account isolation and legacy-schema
  readability checks. These do not replace end-to-end fresh cloud provisioning.

## Integration evidence, not generic support claims

- B10 lab integration has retrieved telemetry/configuration, trip summaries and
  owner-account charge history. A shared account did not expose that charge history.
- Several B10 commands have user-confirmed physical trials. Not every command or
  sleeping-vehicle condition is validated.
- The Mate integration still has legacy DTO/password-resolution dependencies.

## Required before stable release

- Legitimate automated application credential provisioning for fresh installs.
- Remove residual legacy DTO/password-resolution dependencies.
- Validate issuer-side revocation/recovery in a supervised environment. Automatic
  retirement is not enabled while live processes can retain certificate paths.
- Test new install, backup/restore, account switch and rollback end to end.
- Complete physical tests with a supervising user, including sleeping vehicles.
- Obtain per-model/trim evidence before enabling models beyond B10.

Historical GPS routes and MQTT are not advertised as supported. Synthetic tests
on different model names are not hardware compatibility validation.
