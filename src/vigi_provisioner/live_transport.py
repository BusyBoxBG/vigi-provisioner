import socket
import time
from .packets import decode_packet
from .transport import validate_response_source


class LiveUdpTransport:
    EXPECTED_TYPES = {8: 9, 10: 11, 13: 14}

    def __init__(self, enabled=False, timeout=2.0):
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        self.enabled = enabled
        self.timeout = timeout

    def exchange(self, packet, destination):
        if not self.enabled:
            raise RuntimeError("Live UDP transmission disabled")

        if not isinstance(destination, tuple) or len(destination) != 2:
            raise ValueError("Invalid destination")

        request_type, _ = decode_packet(packet)
        expected_response = self.EXPECTED_TYPES.get(request_type)
        if expected_response is None:
            raise ValueError("Unsupported request packet type")

        deadline = time.monotonic() + self.timeout

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(packet, destination)

            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("UDP response timeout")

                sock.settimeout(remaining)

                try:
                    response, source = sock.recvfrom(65535)
                except socket.timeout as exc:
                    raise TimeoutError("UDP response timeout") from exc

                try:
                    validate_response_source(source, destination)
                    response_type, _ = decode_packet(response)
                except ValueError:
                    continue

                if response_type != expected_response:
                    continue

                return response
