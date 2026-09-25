# Final qualification of the experimental client

Version: 0.1.0a6. Status: experimental, not approved for a stable production release.

## Closed software checks

- Package: 183 passing tests, one optional reference-fixture skip.
- Lab integration: 42 passing offline tests.
- Previous adapter/web entry point: 42 passing tests against the current package
  in an isolated container with networking disabled.
- GitHub build/test matrix: Python 3.11, 3.12, 3.13 and 3.14 passed.
- API entry points and constructor: exercised with legacy SDK imports blocked.
- Account password algorithm: twelve synthetic cases matched the previous
  implementation; no private parameters are distributed in this repository.
- Actual lab database: read-only source, private SQLite backup/restore, integrity
  check, trip/charge/settings content equality, position count/latest timestamp
  equality and preserved schema. Private temporary copies were removed.
- Restored session: reused with its matching account without cloud login.
- Different account: restored session refused; no real login executed.
- Empty session cache: requires authentication provider rather than accepting
  an unrelated cached session. This is not end-to-end first-account onboarding.

No production data was modified and no vehicle command was issued for these
qualification checks. Raw databases, identifiers, credentials and locations are
deliberately excluded from this public report.

## External blockers, not unfinished unit tests

### Application credential provisioning

The client needs valid application TLS material and private password-derivation
parameters. Reusing an already configured installation is not fresh provisioning.
No verified issuer enrollment endpoint or authorized distributable credential
bundle has been established. Do not expose a login-only setup as ready until
the distribution has a legitimate way to supply those inputs.

Closure evidence: provision a genuinely fresh installation through that mechanism,
complete a coordinated login and a read-only vehicle request, and verify renewal
and failure behavior. Publishing an extracted private key does not qualify.

### Issuer-side revocation

The examined application leaf has neither Authority Information Access nor CRL
Distribution Points extensions. This does not prove the certificate is unrevoked
or that the issuer offers no separate revocation service. It means no such service
can be discovered from that leaf alone. No certificate was revoked during testing.

Closure evidence: issuer-supported status/replacement semantics and a supervised
test using disposable authorized material. Local invalidation and HTTP rejection
handling are implemented, but are not evidence of issuer-side revocation recovery.

### Physical and model qualification

No unsupervised command trials were performed. B10 trials already confirmed by
the owner do not establish all commands, sleeping-vehicle behavior or other trims.

Closure evidence: for each enabled model/trim and command, record capability data,
request acceptance, independent physical observation and safe restoration of the
initial state. Keep unsupported combinations disabled until those checks exist.

## Release decision

Keep 0.1.0a6 experimental. The checks above are completed; the external gates are
blocked on their required evidence, not on further blanket authorization to code.
Do not relabel them as passed or issue a stable release solely because CI is green.
