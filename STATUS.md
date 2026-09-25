# Implementation and release gates

Current version: 0.1.0a3, experimental. Not a complete login-only application.

## Implemented and tested offline

- Signing, explicit verified TLS transport and caller-supplied session models.
- Single-attempt login primitive with injected application/account material.
- Token-bound PIN encryption with no static-key fallback.
- PKCS12 decoding, certificate/key checks and private file generations.
- B10 command payload/permission validators and command execution primitives.
- Cloud history reads, pagination and preservation of unknown/raw data.
- Cross-platform Python package and offline synthetic regression suite.

## Integration evidence, not generic support claims

- B10 lab integration has retrieved telemetry/configuration, trip summaries and
  owner-account charge history. A shared account did not expose that charge history.
- Several B10 commands have user-confirmed physical trials. Not every command or
  sleeping-vehicle condition is validated.
- The Mate integration still has legacy DTO/password-resolution dependencies.

## Required before stable release

- Legitimate automated application credential provisioning for fresh installs.
- Integrate the independent login into the shared cross-process coordinator.
- Remove residual legacy DTO/password-resolution dependencies.
- Unify the generic planner and lab command permission/freshness policies.
- Replace Europe/Rome-specific scheduled-command validation with an explicit,
  tested timezone contract.
- Validate revoked-session/certificate recovery and retired-material cleanup.
- Test new install, backup/restore, account switch and rollback end to end.
- Complete physical tests with a supervising user, including sleeping vehicles.
- Obtain per-model/trim evidence before enabling models beyond B10.

Historical GPS routes and MQTT are not advertised as supported. Synthetic tests
on different model names are not hardware compatibility validation.
