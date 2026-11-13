# workflow.py
import json
from enum import Enum, auto

from .handshake import (
    build_key_request,
    build_session_request,
    build_encrypted_request,
)
from .responses import parse_response, parse_encrypted_response, validate_camera_mac


class Stage(Enum):
    NEW = auto()
    WAIT_KEY = auto()
    WAIT_SESSION = auto()
    READY = auto()
    WAIT_JSON = auto()
    COMPLETE = auto()
    FAILED = auto()


class InitializationWorkflow:
    def __init__(self, camera_mac, client_mac, aes_key, aes_iv):
        self.camera_mac = camera_mac
        self.client_mac = client_mac
        self.aes_key = aes_key
        self.aes_iv = aes_iv
        self.stage = Stage.NEW
        self.camera_public_key = None
        self.pending_operation = None
        self.operation_index = 0

    def start(self):
        if self.stage != Stage.NEW:
            raise RuntimeError("Workflow already started")
        packet = build_key_request(self.camera_mac)
        self.stage = Stage.WAIT_KEY
        return packet

    def receive_key(self, packet):
        if self.stage != Stage.WAIT_KEY:
            raise RuntimeError("Unexpected key response")
        try:
            response = parse_response(packet, 9)
            self._validate_handshake(response)
            if not response.public_key:
                raise ValueError("Missing camera RSA public key")
            self.camera_public_key = response.public_key
            request = build_session_request(
                self.camera_mac,
                self.client_mac,
                "AES",
                self.aes_key,
                self.aes_iv,
                self.camera_public_key,
            )
            self.stage = Stage.WAIT_SESSION
            return request
        except Exception:
            self.stage = Stage.FAILED
            raise

    def receive_session(self, packet):
        if self.stage != Stage.WAIT_SESSION:
            raise RuntimeError("Unexpected session response")
        try:
            response = parse_response(packet, 11)
            self._validate_handshake(response)
            self.stage = Stage.READY
        except Exception:
            self.stage = Stage.FAILED
            raise

    OPERATIONS = (
        'get_language_capability',
        'get_sec_question_category',
        'set_password',
        'set_basic_settings',
    )

    def send_json(self, operation, payload):
        if self.stage != Stage.READY:
            raise RuntimeError("Workflow is not ready")
        if self.operation_index >= len(self.OPERATIONS):
            raise RuntimeError('All initialization operations completed')
        expected = self.OPERATIONS[self.operation_index]
        if operation != expected:
            raise RuntimeError(f'Expected {expected}, got {operation}')
        request = build_encrypted_request(
            self.camera_mac,
            self.client_mac,
            json.dumps(payload, separators=(",", ":")),
            self.aes_key,
            self.aes_iv,
        )
        self.pending_operation = operation
        self.stage = Stage.WAIT_JSON
        return request

    def receive_json(self, packet):
        if self.stage != Stage.WAIT_JSON:
            raise RuntimeError("No JSON response expected")
        try:
            result = parse_encrypted_response(
                packet,
                self.camera_mac,
                self.aes_key,
                self.aes_iv,
            )
            self.pending_operation = None
            self.operation_index += 1
            self.stage = Stage.READY
            return result
        except Exception:
            self.stage = Stage.FAILED
            raise

    def finish(self):
        if self.stage != Stage.READY:
            raise RuntimeError("Cannot finish with pending operation")
        if self.operation_index != len(self.OPERATIONS):
            raise RuntimeError('Initialization operations incomplete')
        self.stage = Stage.COMPLETE

    def _validate_handshake(self, response):
        validate_camera_mac(response.mac_address, self.camera_mac)
        if response.error_code != 0:
            raise ValueError(
                f"UDP protocol error: {response.error_code}"
            )
