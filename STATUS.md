# Implementation and release gates

Current version: 0.1.0a9 — Leapmotor cloud client with V3 commands, alpha. Not a complete login-only application.

## Implemented and tested offline

- Signing, explicit verified TLS transport and caller-supplied session models.
- Single-attempt login primitive with injected application/account material.
- Token-bound PIN encryption with no static-key fallback.
- PKCS12 decoding, certificate/key checks and private file generations.
- Command payload/permission validators for every model and command execution primitives.
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
- Independent Mate vehicle model, migrated command convenience methods and
  account-password derivation with explicitly injected private parameters.
- Lab web/poller API entry points and adapter constructor run with legacy SDK
  imports blocked. API wire signing no longer calls obsolete SDK header builders.
- Backup and restore on a private snapshot of the actual lab database preserved
  trip/charge/settings contents, position count/latest time, schema and integrity.
  The restored cached session was reused without cloud login; a different account
  could not reuse it. Temporary copies were removed after the check.
- The previous adapter and web entry point passed all 42 lab tests against the
  current package in a network-disabled rollback container.

## Integration evidence, not generic support claims

- B10 lab integration has retrieved telemetry/configuration, trip summaries and
  owner-account charge history. A shared account did not expose that charge history.
- Several B10 commands have user-confirmed physical trials. Not every command or
  sleeping-vehicle condition is validated.
- Commands are enabled for every model. What decides is the cloud's own per-vehicle
  data (abilities, rightList, moduleRights) and the cloud's refusal (result 40 for a
  command the car has not got). Physical actuation outside the B10 is still unproven,
  and cloud acceptance never proves it.
- The one payload difference measured between models is full climate off: bare
  {"operate":"off"} on the B10/C10, the full seven-field body with operate=off on the
  T03 (user-confirmed on-car by re-reading acSwitch, not from an ACK). Each model
  ignores the other's shape while answering code 0, so contracts validate the shape
  the caller supplies and never rewrite it.
- The lab API adapter no longer inherits the old SDK or uses its DTOs/password
  resolver. Existing application parameters were migrated locally into private
  storage, not published. This is not a fresh-install provisioning solution.
- Optional surrounding Mate image/diagnostic helpers are outside this API
  migration; the entire Mate application is not advertised as SDK-free.

## Required before stable release

- Legitimate automated application credential provisioning for fresh installs.
- Validate issuer-side revocation/recovery in a supervised environment. Automatic
  retirement is not enabled while live processes can retain certificate paths.
- Complete fresh-install cloud onboarding once legitimate provisioning exists.
  Local backup/restore, account-cache isolation and offline rollback are checked;
  a live login/account-switch sequence is not substituted with synthetic proof.
- Complete physical tests with a supervising user, including sleeping vehicles.
- Collect per-model/trim actuation evidence. Sending is open and fail-safe (the cloud
  refuses what a car has not got); what still needs a supervised trial per model is
  whether an accepted command physically executes.

Historical GPS routes and MQTT are not advertised as supported. Synthetic tests
on different model names are not hardware compatibility validation.

See FINAL_QUALIFICATION.md for the exact closed checks and external blockers.
