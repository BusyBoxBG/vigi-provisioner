from .transport import transport_for_operation

def execute_read_only(workflow, transport, destination, operation, payload):
    if operation not in ("get_language_capability", "get_sec_question_category"):
        raise ValueError("State-changing operation requires explicit handling")
    packet = workflow.send_json(operation, payload)
    try:
        response = transport_for_operation(transport, operation).exchange(packet, destination)
        return workflow.receive_json(response)
    except Exception:
        workflow.stage = type(workflow.stage).FAILED
        raise

class UncertainOperationError(RuntimeError):
    def __init__(self, operation):
        self.operation = operation
        super().__init__("Outcome uncertain: " + operation)

def execute_state_change(workflow, transport, destination, operation, payload):
    if operation not in ("set_password", "set_basic_settings"):
        raise ValueError("Not a state-changing initialization operation")

    # Build the request before entering the uncertain-outcome section.
    packet = workflow.send_json(operation, payload)

    try:
        response = transport_for_operation(transport, operation).exchange(
            packet, destination
        )
        return workflow.receive_json(response)

    except Exception as exc:
        # Never retry a state-changing operation after an ambiguous failure.
        workflow.stage = type(workflow.stage).FAILED
        raise UncertainOperationError(operation) from exc
