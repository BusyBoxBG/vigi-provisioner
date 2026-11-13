from .vigi_activation import build_activation_request
from .vigi_activation_safety import DeviceObservation, activation_allowed


def prepare_activation(device, password):
    allowed, reason = activation_allowed(device)

    if not allowed:
        return None, reason

    return build_activation_request(password), reason
