"""Single-use transport ownership lease.

This module performs no network operations.
A lease is not independently authenticated TLS evidence.
"""

from .vigi_initialization_execution_plan import (
    InitializationExecutionPlan,
)


class GatewayTransportLeaseError(RuntimeError):
    pass


class GatewayTransportLease:
    __slots__ = (
        "__plan",
        "__transport",
        "__claimed",
        "__closed",
    )

    def __init__(self, plan, transport):
        if not isinstance(
            plan,
            InitializationExecutionPlan,
        ):
            raise TypeError(
                "Expected InitializationExecutionPlan"
            )

        if transport is None:
            raise ValueError(
                "Transport reference is required"
            )

        if not callable(
            getattr(transport, "close", None)
        ):
            raise TypeError(
                "Transport must support close()"
            )

        self.__plan = plan
        self.__transport = transport
        self.__claimed = False
        self.__closed = False

    @property
    def execution_plan(self):
        return self.__plan

    @property
    def claimed(self):
        return self.__claimed

    @property
    def closed(self):
        return self.__closed

    def claim(self, expected_plan):
        if self.__closed:
            raise GatewayTransportLeaseError(
                "Transport lease already closed"
            )

        if self.__claimed:
            raise GatewayTransportLeaseError(
                "Transport lease already claimed"
            )

        if expected_plan != self.__plan:
            raise GatewayTransportLeaseError(
                "Transport lease identity mismatch"
            )

        self.__claimed = True
        transport = self.__transport
        self.__transport = None

        return transport

    def close(self):
        if self.__closed:
            return

        self.__closed = True

        transport = self.__transport
        self.__transport = None

        if transport is not None:
            transport.close()


def create_gateway_transport_lease(
    plan,
    transport,
):
    """Wrap a supplied transport without connecting."""
    return GatewayTransportLease(
        plan,
        transport,
    )
