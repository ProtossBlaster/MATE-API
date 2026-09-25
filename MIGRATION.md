# Integration and rollout boundaries

This repository is a protocol library, not a preconfigured Mate Docker image.
Version 0.1.0a6 is an experimental compatibility boundary, not a stable release.

## Existing installation

1. Preserve the database, encryption key, application TLS material and deployed
   adapter revision in private backup storage. Never attach them to an issue.
2. Use a separate lab instance and an account that does not evict production.
3. Inject valid application certificate/key and private password-derivation
   parameters through deployment-managed storage. Do not bake them into an image.
4. Keep the cross-process session coordinator. Never let web and poller perform
   independent login loops. Expiry/rejection must not replay vehicle commands.
5. Test model metadata, permission presence, data units and native command shapes
   offline. Cloud acceptance alone never proves physical actuation.
6. Verify database integrity/history and ordinary telemetry after deployment.
   Distinguish vehicle frame timestamp from cloud collection/receipt timestamps.
7. Retain the previous adapter and private parameters for rollback. Do not erase
   certificate generations while a process may still hold their paths.

## Verified scope

The lab's migrated API path uses independent vehicle models, password derivation,
command convenience methods, signing, login and TLS transport. Web and poller
API imports and adapter initialization were exercised with legacy SDK imports
blocked. These checks do not cover optional image decoder/diagnostic integrations
elsewhere in Mate. Those are not endpoints of this client.

The database schema is not changed by this adapter substitution. Offline tests
cover cache isolation, concurrent login, backup/restore, legacy table readability
and rejected-session invalidation. Keep deployment-level backup and encryption
key restoration separate from a library unit test.

## Deliberately incompatible or unavailable

- Typed status uses TelemetrySnapshot; consumers expecting legacy VehicleStatus
  must adapt explicitly or use raw status, as the Mate poller does.
- Unknown commands, unverified models and sentinel commands are not enabled.
- Pictures/binary downloads were not migrated; there is no hidden legacy route.
- App password parameters are required external inputs, not published secrets.
- Fresh installs still require legitimate application credential provisioning.
- Historical GPS tracks and MQTT remain outside verified support.

## Remaining external qualification

Issuer-side revocation, end-to-end fresh-account provisioning, physical command
trials while awake/asleep and other model/trim validation require external
evidence. Do not close those gates using only synthetic responses or model names.
