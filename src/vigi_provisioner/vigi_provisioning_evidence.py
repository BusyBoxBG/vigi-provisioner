
from .vigi_inventory import normalize_mac
from .vigi_static_ip_verification import verify_static_ip_readback

OPERATIONS = (
    "SetNetworkDefaultGateway",
    "SetNetworkInterfaces",
)

class ProvisioningEvidenceError(ValueError):
    pass

def validate_application_evidence(*, plan, execution):
    if not isinstance(plan, dict) or not isinstance(execution, dict):
        raise ProvisioningEvidenceError("Invalid evidence structure")

    history = execution.get("history")
    if not isinstance(history, list) or len(history) != 2:
        raise ProvisioningEvidenceError("Incomplete execution history")

    if execution.get("status") != "acknowledged":
        raise ProvisioningEvidenceError("Execution not acknowledged")

    if execution.get("failed_or_unknown_operation") is not None:
        raise ProvisioningEvidenceError("Unresolved operation")

    for entry, operation in zip(history, OPERATIONS):
        if not isinstance(entry, dict):
            raise ProvisioningEvidenceError("Invalid history entry")
        if entry.get("operation") != operation:
            raise ProvisioningEvidenceError("Wrong operation sequence")
        if entry.get("confirmed") is not True:
            raise ProvisioningEvidenceError("Unconfirmed operation")
        if entry.get("status") != "success":
            raise ProvisioningEvidenceError("Operation not confirmed")

    return {
        "accepted": True,
        "mac": normalize_mac(plan["mac"]),
        "target_ip": plan["target_ip"],
        "stage": "applied",
    }

def validate_readback_evidence(
    *,
    plan,
    discovered_device,
    interfaces,
    gateways,
):
    if not isinstance(plan, dict):
        raise ProvisioningEvidenceError("Invalid plan")

    result = verify_static_ip_readback(
        plan=plan,
        discovered_device=discovered_device,
        interfaces=interfaces,
        gateways=gateways,
    )

    if result.get("verified") is not True:
        raise ProvisioningEvidenceError(
            "Readback failed: " + ",".join(result["failures"])
        )

    if result.get("failures") != []:
        raise ProvisioningEvidenceError("Inconsistent verification result")

    if normalize_mac(result["mac"]) != normalize_mac(plan["mac"]):
        raise ProvisioningEvidenceError("Verification MAC mismatch")

    if result["target_ip"] != plan["target_ip"]:
        raise ProvisioningEvidenceError("Verification IP mismatch")

    return {
        "accepted": True,
        "mac": normalize_mac(plan["mac"]),
        "target_ip": plan["target_ip"],
        "stage": "verified",
        "verification": result,
    }


def validate_bound_application_evidence(
    *,
    plan,
    evidence,
    approved_assignment,
):
    """
    Validate an execution envelope against the requested plan
    and a separately retrieved approved assignment.

    This validates consistency, not the authenticity of the
    evidence source. The calling workflow must obtain evidence
    from its trusted execution path.
    """
    if not isinstance(plan, dict):
        raise ProvisioningEvidenceError("Invalid plan")

    if not isinstance(evidence, dict):
        raise ProvisioningEvidenceError("Invalid evidence envelope")

    if not isinstance(approved_assignment, dict):
        raise ProvisioningEvidenceError("Invalid approved assignment")

    try:
        plan_mac = normalize_mac(plan["mac"])
        evidence_mac = normalize_mac(evidence["mac"])
        approved_mac = normalize_mac(approved_assignment["mac"])

        fields = ("target_ip", "prefix_length", "gateway")

        for field in fields:
            expected = plan[field]

            if evidence[field] != expected:
                raise ProvisioningEvidenceError(
                    "Evidence-to-plan mismatch: " + field
                )

            if approved_assignment[field] != expected:
                raise ProvisioningEvidenceError(
                    "Approval-to-plan mismatch: " + field
                )

        if not (
            plan_mac == evidence_mac == approved_mac
        ):
            raise ProvisioningEvidenceError(
                "Camera MAC binding mismatch"
            )

        execution = evidence["execution"]

    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ProvisioningEvidenceError):
            raise
        raise ProvisioningEvidenceError(
            "Incomplete or invalid evidence binding"
        ) from exc

    validated = validate_application_evidence(
        plan=plan,
        execution=execution,
    )

    if validated["mac"] != plan_mac:
        raise ProvisioningEvidenceError(
            "Validated MAC mismatch"
        )

    if validated["target_ip"] != plan["target_ip"]:
        raise ProvisioningEvidenceError(
            "Validated target mismatch"
        )

    return {
        **validated,
        "assignment_bound": True,
        "execution_bound": True,
    }
