"""Conservative capability/permission layer, not a remote-execution permit."""

from datetime import datetime, timedelta

from .errors import ValidationError
from .models import Availability as A, CapabilitySnapshot, Decision, require_aware


def evaluate(snapshot: CapabilitySnapshot, *, ability: int, right: int,
             now: datetime, max_age: timedelta) -> Decision:
    if not isinstance(snapshot, CapabilitySnapshot):
        raise ValidationError("Invalid capability snapshot")
    if any(type(code) is not int or code <= 0 for code in (ability, right)):
        raise ValidationError("Invalid capability requirement")
    require_aware(now)
    if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
        raise ValidationError("A positive freshness limit is required")
    age = now - snapshot.observed_at
    if age < timedelta(0):
        return Decision(A.UNKNOWN, "snapshot_from_future")
    if age > max_age:
        return Decision(A.UNKNOWN, "snapshot_expired")
    if not snapshot.complete:
        return Decision(A.UNKNOWN, "snapshot_incomplete")
    if ability not in snapshot.abilities:
        return Decision(A.UNSUPPORTED, "ability_absent")
    if snapshot.owner is None:
        return Decision(A.UNKNOWN, "ownership_unknown")
    if snapshot.owner:
        if right not in snapshot.rights:
            return Decision(A.UNKNOWN, "owner_rule_not_reconstructed")
        if 200 not in snapshot.module_rights:
            return Decision(A.UNKNOWN, "owner_module_rule_not_reconstructed")
    else:
        if 200 not in snapshot.module_rights:
            return Decision(A.FORBIDDEN, "control_module_denied")
        if right not in snapshot.rights:
            return Decision(A.FORBIDDEN, "account_right_denied")
    return Decision(A.AVAILABLE, "explicit_ability_and_permission")

