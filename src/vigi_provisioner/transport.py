class UdpTransport:
    def __init__(self, enabled=False):
        self.enabled = enabled

    def exchange(self, packet, destination):
        if not self.enabled:
            raise RuntimeError("UDP transmission disabled")
        raise NotImplementedError("Live UDP transport not implemented")

class MockUdpTransport(UdpTransport):
    def __init__(self, responses):
        super().__init__(enabled=False)
        self.responses = iter(responses)
        self.sent_packets = []

    def exchange(self, packet, destination):
        self.sent_packets.append((packet, destination))
        try:
            response = next(self.responses)
        except StopIteration:
            raise TimeoutError("Simulated UDP timeout")
        if response is None:
            raise TimeoutError("Simulated UDP timeout")
        if isinstance(response, tuple) and len(response) == 2:
            response, source = response
            validate_response_source(source, destination)
        return response

class RetryTransport:
    def __init__(self, transport, max_attempts=3):
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.transport = transport
        self.max_attempts = max_attempts

    def exchange(self, packet, destination):
        for attempt in range(self.max_attempts):
            try:
                return self.transport.exchange(packet, destination)
            except TimeoutError:
                if attempt == self.max_attempts - 1:
                    raise

RETRY_ATTEMPTS = {
    "get_language_capability": 3,
    "get_sec_question_category": 3,
    "set_password": 1,
    "set_basic_settings": 1
}

def transport_for_operation(transport, operation):
    if operation not in RETRY_ATTEMPTS:
        raise ValueError("Unknown initialization operation")
    return RetryTransport(transport, RETRY_ATTEMPTS[operation])

def validate_response_source(source, destination):
    if not isinstance(source, tuple) or len(source) != 2:
        raise ValueError('Invalid UDP response source')
    if not isinstance(destination, tuple) or len(destination) != 2:
        raise ValueError('Invalid UDP destination')
    if source != destination:
        raise ValueError('UDP response source mismatch')
    return True
