import http.client

from .vigi_camera_gateway import connect_inventory_camera


class CameraHTTPError(RuntimeError):
    pass


def get_camera_homepage(
    mac,
    camera_ip,
    *,
    source_ip="192.168.0.10",
    operator_confirmed=False,
    timeout=5,
    max_body_bytes=8192,
):
    """
    Retrieve GET / through the authorized pinned TLS gateway.

    No authentication credentials or configuration commands
    are transmitted.
    """

    if operator_confirmed is not True:
        raise CameraHTTPError(
            "Explicit operator confirmation required"
        )

    if (
        not isinstance(max_body_bytes, int)
        or isinstance(max_body_bytes, bool)
        or not 0 < max_body_bytes <= 65536
    ):
        raise CameraHTTPError(
            "Invalid response body limit"
        )

    connection = connect_inventory_camera(
        mac=mac,
        camera_ip=camera_ip,
        source_ip=source_ip,
        operator_confirmed=True,
        timeout=timeout,
    )

    try:
        request = (
            "GET / HTTP/1.1\r\n"
            f"Host: {camera_ip}\r\n"
            "Accept: text/html\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("ascii")

        connection.sendall(request)

        response = http.client.HTTPResponse(
            connection
        )

        response.begin()

        body = response.read(
            max_body_bytes + 1
        )

        if len(body) > max_body_bytes:
            raise CameraHTTPError(
                "Camera HTTP response exceeds size limit"
            )

        if response.status != 200:
            raise CameraHTTPError(
                f"Unexpected HTTP status: {response.status}"
            )

        return {
            "status": response.status,
            "reason": response.reason,
            "content_type": response.getheader(
                "Content-Type"
            ),
            "body_bytes": len(body),
            "body": body,
        }

    finally:
        connection.close()
