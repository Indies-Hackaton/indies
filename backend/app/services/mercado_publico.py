"""Async client wrapper for the Chilean government 'Mercado Publico' API.

The :class:`MercadoPublicoClient` is intentionally minimal and extensible:
every public method models exactly *one* business query and delegates all
networking to the private :meth:`MercadoPublicoClient._make_request` helper.
Adding a new endpoint/query is therefore a one-method change.
"""

from typing import Any

import httpx

from app.core.config import Settings


class MercadoPublicoError(RuntimeError):
    """Raised when Mercado Publico is unreachable or returns an HTTP error."""


class MercadoPublicoClient:
    """Thin async wrapper around the Mercado Publico REST API.

    Parameters
    ----------
    settings:
        Application settings holding the API ticket and base URL.
    client:
        A shared :class:`httpx.AsyncClient`. Sharing a single client across the
        app enables connection pooling and keep-alive.
    """

    # Every purchase-order query targets the same JSON resource; only the
    # query-string parameters differ between methods.
    ORDERS_ENDPOINT = "ordenesdecompra.json"

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._client = client
        self._base_url = settings.MERCADO_PUBLICO_BASE_URL.rstrip("/")
        self._ticket = settings.MERCADO_PUBLICO_TICKET

    async def _make_request(
        self, endpoint: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Perform an authenticated GET request and return the parsed JSON.

        The ``ticket`` is injected automatically, so callers only ever pass the
        parameters specific to their query. This keeps every public method free
        of authentication and error-handling boilerplate.

        Raises
        ------
        MercadoPublicoError
            If the API responds with an error status or cannot be reached.
        """
        url = f"{self._base_url}/{endpoint}"
        # The ticket is always required; merge it with the caller's params.
        query: dict[str, Any] = {"ticket": self._ticket, **params}

        try:
            response = await self._client.get(url, params=query)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MercadoPublicoError(
                f"Mercado Publico returned HTTP {exc.response.status_code} "
                f"for '{endpoint}'."
            ) from exc
        except httpx.HTTPError as exc:
            # Covers timeouts, connection errors, DNS failures, etc.
            raise MercadoPublicoError(
                f"Could not reach Mercado Publico for '{endpoint}': {exc}"
            ) from exc

        return response.json()

    # ------------------------------------------------------------------
    # Public business queries. To add a new query, simply define another
    # async method here that builds its ``params`` and calls ``_make_request``.
    # ------------------------------------------------------------------

    async def get_orders_by_org_and_date(
        self, codigoorg: str, fecha: str
    ) -> dict[str, Any]:
        """Method A - purchase orders for one organism on a specific date.

        Parameters
        ----------
        codigoorg:
            Code identifying the public organism (``CodigoOrganismo``).
        fecha:
            Date in ``ddmmyyyy`` format, as expected by Mercado Publico.
        """
        return await self._make_request(
            self.ORDERS_ENDPOINT,
            {"CodigoOrganismo": codigoorg, "fecha": fecha},
        )

    async def get_orders_by_date(self, fecha: str) -> dict[str, Any]:
        """Method B - every purchase order issued on a specific date.

        Parameters
        ----------
        fecha:
            Date in ``ddmmyyyy`` format, as expected by Mercado Publico.
        """
        return await self._make_request(self.ORDERS_ENDPOINT, {"fecha": fecha})
