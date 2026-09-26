# Mate migration findings — September 2026

This update concerns protocol interoperability and source verification. It does not
ship application private material or claim a stable, universally compatible release.

## Sessions and authentication

The installation device ID and a server-bound session device ID can differ.
`session_device_id` reads optional `user_name` metadata from a token that the caller
already received through authenticated TLS. It is not JWT signature verification.
Absent binding preserves the installation ID; malformed/header-control metadata
is rejected without echoing it. The installation ID must remain stable for login.

`LoginUnavailable` exposes bounded `stage`, `http_status`, and `api_code`; it never
returns response bodies, credentials, or transport exception strings. One explicit
LoginClient call sends at most one login request. Caller-side locking and cooldown
are needed across processes. A successful live login, vehicle-list read, telemetry
read and configuration read have been observed in the independent lab. Stale
telemetry can be returned successfully; do not label that as a current parked or
sleeping state.

## Command compatibility

The installed original SDK and Mate's actual web/MQTT generators were inspected.
Mate overrides several SDK defaults, so copying defaults alone is insufficient.

Corrected capability IDs: lock 10, find vehicle 11, climate 6, climate appointment 9,
navigation 52, charge limit 35, steering heat 15, mirror heat 19. Connector unlock
uses 48; 53 denotes BLE key restart. Sunshade's account right is 161 and battery
preheat's account right is 190. Rights and abilities are separate namespaces.

32 synthetic original web-generator cases produce equivalent command IDs/payloads
with the independent Mate interface. This includes preserving an existing charge
plan when only the SoC target changes. Mate's driver-seat quick buttons use level
3; the web integration was aligned accordingly. Seat names are subsequently
normalized to physical positions by the B10 contract. Other input values, models
and complete physical actuation remain separate qualifications.

The independent transport still signs and sends the reconstructed v3 request. It
does not import the old SDK, download its credentials, or fall back to its HTTP
endpoint. Explicitly denied shared-account permissions remain denied even where
the old SDK would only log a warning. Commands with ambiguous results are not
resent automatically. B10 remains the only enabled command model.

## History and energy

Observed mileage records use `routeStartTs` and `routeEndTs` as epoch milliseconds,
`totalMileage` in km and `totalEnergy` in kWh. Those are distinct from request
startTime/endTime filters (epoch seconds). Do not look for record fields named
startTime/endTime/mileage or infer missing energy from missing SoC.

Cloud microtrips may have zero distance and zero energy. Zero is a supplied value;
missing is unknown. Preserve both the original cloud payload and later independent
getEC measurements. An importer should be optional, idempotent and conservative
about overlap, keep local GPS/SoC intact, and never turn off an option by deleting
previously imported records. The Mate integration now exposes that preference.

EV display selection prioritizes conservatively matched cloud-trip energy, then
stable getEC, then the existing estimate. List, detail and period totals must use
the same selection without rewriting historical telemetry. REEV remains unchanged.

## Remaining release boundaries

A successful clone migration does not prove permission to redistribute APK-derived
application credentials, real revocation recovery, other-model actuation, physical
sleep/wake behavior, or every desktop installation. New installations require
operator-supplied application material. No private certificates/keys, real account
fixtures, vehicle identifiers or locations are included in this update.
