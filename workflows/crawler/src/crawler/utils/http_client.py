"""HTTP client factory for creating configured httpx.AsyncClient instances."""

import httpx


def create_http_client(
    base_url: str = "",
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    max_connections: int = 100,
    max_keepalive_connections: int = 20,
    keepalive_expiry: float = 5.0,
) -> httpx.AsyncClient:
    """Create a configured httpx.AsyncClient instance.

    Args:
        base_url: Base URL for all requests
        headers: Default headers to include in all requests
        timeout: Request timeout in seconds
        max_connections: Maximum number of concurrent connections
        max_keepalive_connections: Maximum number of keep-alive connections
        keepalive_expiry: Keep-alive expiry time in seconds

    Returns:
        Configured AsyncClient instance
    """
    limits = httpx.Limits(
        max_connections=max_connections,
        max_keepalive_connections=max_keepalive_connections,
        keepalive_expiry=keepalive_expiry,
    )
    return httpx.AsyncClient(
        base_url=base_url,
        headers=headers or {},
        timeout=timeout,
        limits=limits,
    )
