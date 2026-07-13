"""
DAX query command against the Claude Usage Direct Lake semantic model.

Uses the Power BI Execute DAX Queries REST API, which returns results as
concatenated Apache Arrow IPC streams (LZ4 record batches, handled by
pyarrow). Query errors can arrive as HTTP 200 with an error rowset flagged in
the Arrow schema metadata, so every stream is checked for IsError.
"""
#region Imports
import io
import json
import time
import urllib.error
import urllib.request
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from src.config.user_config import get_sync_config
from src.storage.onelake_remote import _POWERBI_RESOURCE, _get_az_token

#endregion


#region Constants

_API_HOST = "https://api.powerbi.com/v1.0/myorg"

#endregion


#region Errors


class DaxQueryError(RuntimeError):
    """A DAX query failed (transport, auth, or an IsError rowset)."""


#endregion


#region Core


def parse_arrow_response(payload: bytes) -> list[Any]:
    """
    Split a response body into its concatenated Arrow IPC stream tables.

    Raises DaxQueryError on an IsError rowset (surfacing FaultCode and
    FaultString) and on any bytes that are not a well-formed Arrow stream;
    a format surprise must never be silently truncated.
    """
    import pyarrow as pa

    stream = io.BytesIO(payload)
    tables: list[Any] = []
    while stream.tell() < len(payload):
        try:
            reader = pa.ipc.open_stream(stream)
            table = reader.read_all()
        except pa.ArrowInvalid as exc:
            raise DaxQueryError(
                f"Response at byte {stream.tell()} is not an Arrow IPC stream: {exc}"
            ) from exc
        metadata = {
            k.decode(): v.decode()
            for k, v in (reader.schema.metadata or {}).items()
        }
        if metadata.get("IsError") == "true":
            raise DaxQueryError(
                f"Query error [{metadata.get('FaultCode', '?')}]: "
                f"{metadata.get('FaultString', 'unknown')} "
                f"(rows: {table.to_pylist()[:3]})"
            )
        tables.append(table)
    if not tables:
        raise DaxQueryError("Response contained no Arrow streams")
    return tables


def execute_dax(config: dict[str, Any], dax: str, limit: int | None) -> list[Any]:
    """
    POST the query to executeDaxQueries and return the parsed result tables.

    Honors one Retry-After pause on 429; a 401 maps to an actionable
    scope/tenant hint (the endpoint requires the Dataset.Read.All delegated
    scope, which a plain az CLI token does not carry).
    """
    workspace_id = config.get("workspace_id")
    model_id = config.get("semantic_model_id")
    if not workspace_id or not model_id:
        raise DaxQueryError(
            "onelake sync_config needs workspace_id and semantic_model_id. "
            "Run: ccg sync setup --provider onelake"
        )

    token = _get_az_token(_POWERBI_RESOURCE, config.get("tenant_id"))
    body: dict[str, Any] = {"query": dax}
    if limit is not None:
        body["resultSetRowCountLimit"] = limit

    request = urllib.request.Request(
        f"{_API_HOST}/groups/{workspace_id}/datasets/{model_id}/executeDaxQueries",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )

    for attempt in (0, 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return parse_arrow_response(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                time.sleep(float(exc.headers.get("Retry-After", "5") or "5"))
                continue
            if exc.code == 401:
                raise DaxQueryError(
                    "401 Unauthorized. This preview API requires a token with the "
                    "Dataset.Read.All scope; a plain `az` token (user_impersonation) "
                    "is rejected. Try: az login --scope "
                    "'https://analysis.windows.net/powerbi/api/Dataset.Read.All' "
                    "or query via the SQL endpoint instead."
                ) from exc
            detail = exc.read()[:300].decode(errors="replace")
            raise DaxQueryError(f"HTTP {exc.code}: {detail}") from exc
    raise DaxQueryError("throttled twice (429); try again later")


#endregion


#region Rendering


def render_csv(tables: list[Any]) -> str:
    import csv as csv_mod

    out = io.StringIO()
    for table in tables:
        writer = csv_mod.writer(out)
        writer.writerow(table.column_names)
        for row in table.to_pylist():
            writer.writerow([row[c] for c in table.column_names])
    return out.getvalue()


def render_json(tables: list[Any]) -> str:
    return json.dumps([t.to_pylist() for t in tables], indent=2, default=str)


def _render_rich(console: Console, tables: list[Any]) -> None:
    for i, table in enumerate(tables):
        rich_table = Table(title=f"Result {i + 1}" if len(tables) > 1 else None)
        for name in table.column_names:
            rich_table.add_column(name)
        for row in table.to_pylist():
            rich_table.add_row(*[str(row[c]) for c in table.column_names])
        console.print(rich_table)
        console.print(f"[dim]{table.num_rows:,} row(s)[/dim]")


#endregion


#region Command


def query_command(
    dax: str = typer.Option(..., "--query", "-q", help="DAX query (multiple EVALUATE statements allowed)"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, csv, or json"),
    limit: int | None = typer.Option(None, "--limit", help="Server-side row limit per result set"),
) -> None:
    """
    Run a DAX query against the Claude Usage semantic model.

    Uses the Execute DAX Queries REST API (Arrow). Requires the onelake
    provider configured with workspace_id and semantic_model_id, plus an
    az login session in the right tenant.
    """
    console = Console()
    config = get_sync_config("onelake")
    try:
        tables = execute_dax(config, dax, limit)
    except (DaxQueryError, RuntimeError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    if output == "csv":
        print(render_csv(tables), end="")
    elif output == "json":
        print(render_json(tables))
    else:
        _render_rich(console, tables)


#endregion
