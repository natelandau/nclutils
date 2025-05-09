"""Network utilities."""

import socket


def network_available(address: str = "8.8.4.4", port: int = 53, timeout: int = 5) -> bool:
    """Check network connectivity by attempting a TCP connection to a remote server.

    Attempt to establish a TCP connection to a remote server (defaults to Google DNS 8.8.4.4:53) to verify network connectivity. The connection is not a DNS lookup, just a plain TCP socket connection.

    Args:
        address (str): The remote server IP address to connect to. Defaults to "8.8.4.4".
        port (int): The remote server port to connect to. Defaults to 53.
        timeout (int): Maximum time in seconds to wait for connection. Defaults to 5.

    Returns:
        bool: True if connection succeeds, False if connection fails or times out.

    Examples:
        >>> network_available()
        True
        >>> network_available("1.1.1.1", 53, 10)
        True
        >>> network_available("10.10.10000.10000", 53, 1)
        False
    """
    try:
        conn = socket.create_connection((address, port), timeout=timeout)
        conn.close()
    except Exception:  # noqa: BLE001
        return False

    return True
