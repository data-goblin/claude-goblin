#region Imports
from datetime import datetime
from pathlib import Path

from rich.console import Console

from src.config.settings import get_claude_jsonl_files
from src.config.user_config import (
    get_device_id,
    get_extra_sources,
    get_storage_mode,
)
from src.data.codex_parser import parse_all_codex_files
from src.data.hermes_parser import parse_all_hermes_files
from src.data.jsonl_parser import parse_all_jsonl_files
from src.models.usage_record import UsageRecord
from src.storage import api, get_db_path

#endregion


#region Functions


def _parse_source_files(file_paths: list[Path], source_format: str) -> list[UsageRecord]:
    """Dispatch a configured source to its transcript parser."""
    if source_format == "codex":
        return parse_all_codex_files(file_paths)
    if source_format == "hermes":
        return parse_all_hermes_files(file_paths)
    return parse_all_jsonl_files(file_paths)


def ingest_token_usage(console: Console, force: bool = False, verbose: bool = True) -> int:
    """
    Parse stale JSONL files from all configured sources and save records.

    Sources are the main Claude projects directory plus any extra_sources
    config entries, each saved under its own device identity. Incremental:
    only files whose mtime/size changed since the last run are parsed
    (tracked in file_metadata); force reparses everything.

    Args:
        console: Rich console for output
        force: Reparse all files, ignoring the incremental cache
        verbose: Print per-source save counts and the no-op message

    Returns:
        Number of new records saved across all sources
    """
    # Each source is (jsonl files, device overrides); None overrides means
    # this device's identity from config.
    sources: list[tuple[list[Path], dict | None]] = []
    jsonl_files = get_claude_jsonl_files()
    if jsonl_files:
        sources.append((jsonl_files, None))
    for extra in get_extra_sources():
        extra_dir = Path(extra["path"])
        if extra_dir.is_dir():
            extra_files = list(extra_dir.rglob("*.jsonl"))
            if extra_files:
                sources.append((extra_files, extra))

    all_files = [f for files, _ in sources for f in files]
    if not all_files:
        return 0

    # One stale/deleted pass over the union of all sources: get_stale_files
    # marks tracked paths missing from its input as deleted, so separate
    # per-source calls would evict each other's file_metadata rows.
    if force:
        stale_files, deleted_files = all_files, []
    else:
        stale_files, deleted_files = api.get_stale_files(all_files)
    stale_set = {str(f) for f in stale_files}

    storage_mode = get_storage_mode()
    total_saved = 0
    for files, overrides in sources:
        source_stale = [f for f in files if str(f) in stale_set]
        if not source_stale:
            continue
        # A failing source must not block the others, so trap and report per
        # source. Metadata is updated only after a successful save; failed
        # files stay stale for retry. File stats are captured BEFORE parsing
        # so bytes appended mid-ingest stay stale for the next run.
        label = overrides["device_name"] if overrides else "this device"
        try:
            pre_stats: dict[str, tuple[int, int]] = {}
            for f in source_stale:
                try:
                    st = f.stat()
                    pre_stats[str(f)] = (st.st_mtime_ns, st.st_size)
                except OSError:
                    pass
            device_kwargs = {}
            if overrides:
                device_kwargs = {
                    "device_id": overrides["device_id"],
                    "device_name": overrides["device_name"],
                    "device_type": overrides["device_type"],
                }
            source_format = overrides.get("format", "claude") if overrides else "claude"
            if storage_mode == "aggregate":
                # Per-file delta accounting: each file's contribution is
                # tracked so a grown file's reparse adds only the difference
                saved_count = 0
                for f in source_stale:
                    records = _parse_source_files([f], source_format)
                    if records:
                        saved_count += api.save_file_aggregate(f, records, **device_kwargs)
            else:
                records = _parse_source_files(source_stale, source_format)
                saved_count = api.save_snapshot(
                    records,
                    storage_mode=storage_mode,
                    **device_kwargs,
                ) if records else 0
            total_saved += saved_count
            if verbose and saved_count:
                source_label = f" ({overrides['device_name']})" if overrides else ""
                console.print(f"[green]Saved {saved_count} new token records{source_label}[/green]")
            api.update_files_metadata(source_stale, record_count=0, stats=pre_stats)
        except Exception as e:
            console.print(f"[yellow]⚠ Source {label} failed, will retry next run: {e}[/yellow]")

    if deleted_files:
        api.remove_deleted_file_metadata(deleted_files)

    if verbose and not stale_files and not deleted_files:
        console.print("[dim]No new data to ingest[/dim]")

    return total_saved


def rebuild_token_usage(console: Console) -> int:
    """
    Recompute usage_records from surviving transcripts (repair command).

    Per-session replacement: every session still present on disk is deleted
    and re-ingested under the corrected billed-response identity; sessions
    whose transcripts aged out are untouched (their rows are the only
    surviving record). Backs up the database file first and sets the quack
    purge guard before any delete so a racing hook push cannot double the
    remote.

    Returns:
        Number of records saved by the re-ingest
    """
    import shutil

    from src.storage.duckdb_backend import (
        delete_session_rows,
        recompute_daily_snapshots,
        set_sync_state,
    )
    from src.storage.quack_remote import QUACK_PURGE_KEY

    if get_storage_mode() != "full":
        console.print("[red]--rebuild requires storage_mode 'full' (records are the repair source)[/red]")
        return 0

    db_path = get_db_path()
    if not db_path.exists():
        console.print("[yellow]No database to rebuild[/yellow]")
        return 0
    if db_path.suffix != ".duckdb":
        console.print("[red]--rebuild currently supports the DuckDB backend only[/red]")
        return 0

    backup = db_path.with_name(
        f"{db_path.name}.pre-rebuild-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
    shutil.copy2(db_path, backup)
    if not backup.exists():
        console.print("[red]Backup failed; aborting rebuild[/red]")
        return 0
    console.print(f"[dim]Backup: {backup}[/dim]")

    # Guard BEFORE any mutation: a hook-triggered quack push mid-rebuild (or
    # after it, before the remote purge) must refuse.
    set_sync_state(QUACK_PURGE_KEY, "1", db_path=db_path)

    sources: list[tuple[list[Path], dict | None]] = []
    jsonl_files = get_claude_jsonl_files()
    if jsonl_files:
        sources.append((jsonl_files, None))
    for extra in get_extra_sources():
        extra_dir = Path(extra["path"])
        if extra_dir.is_dir():
            extra_files = list(extra_dir.rglob("*.jsonl"))
            if extra_files:
                sources.append((extra_files, extra))

    total_saved = 0
    for files, overrides in sources:
        label = overrides["device_name"] if overrides else "this device"
        try:
            pre_stats: dict[str, tuple[int, int]] = {}
            for f in files:
                try:
                    st = f.stat()
                    pre_stats[str(f)] = (st.st_mtime_ns, st.st_size)
                except OSError:
                    pass
            source_format = overrides.get("format", "claude") if overrides else "claude"
            records = _parse_source_files(files, source_format)
            if not records:
                continue
            device_kwargs = {}
            device_id = None
            if overrides:
                device_kwargs = {
                    "device_id": overrides["device_id"],
                    "device_name": overrides["device_name"],
                    "device_type": overrides["device_type"],
                }
                device_id = overrides["device_id"]
            else:
                device_id = get_device_id()

            sessions = sorted({r.session_id for r in records})
            deleted_dates = delete_session_rows(sessions, device_id, db_path=db_path)
            saved_count = api.save_snapshot(records, storage_mode="full", **device_kwargs)
            affected = sorted(set(deleted_dates) | {r.date_key for r in records})
            recompute_daily_snapshots(affected, db_path=db_path, **device_kwargs)
            api.update_files_metadata(files, record_count=0, stats=pre_stats)
            total_saved += saved_count
            console.print(
                f"[green]Rebuilt {len(sessions)} sessions ({saved_count} records) for {label}[/green]"
            )
        except Exception as e:
            console.print(f"[yellow]⚠ Rebuild of {label} failed: {e}[/yellow]")

    console.print(
        "[yellow]Quack pushes are blocked until the remote is purged; "
        "then run: ccg sync push --quack-purged --full[/yellow]"
    )
    return total_saved


def run(console: Console) -> None:
    """
    Update usage database and fill in gaps with empty records.

    Incremental: only parses JSONL files whose mtime/size has changed since
    the last run (tracked in the file_metadata table). On a typical Stop-hook
    invocation, exactly one file is stale and a handful of new records get
    inserted.

    Args:
        console: Rich console for output
    """
    try:
        # Save current snapshot (tokens) -- incremental via get_stale_files
        ingest_token_usage(console)

        # Fill in date gaps so the heatmap is contiguous. Coverage comes from
        # a cheap count/min/max query, not the full stats aggregation.
        coverage = api.get_update_coverage()
        if coverage["total_records"] == 0:
            console.print("[yellow]No data to process.[/yellow]")
            return

        today = datetime.now().date().strftime("%Y-%m-%d")
        filled_count = api.fill_empty_daily_snapshots(coverage["oldest_date"], today)
        if filled_count > 0:
            console.print(f"[cyan]Filled {filled_count} empty days[/cyan]")

        console.print(
            f"[green]Complete! Coverage: {coverage['oldest_date']} to {coverage['newest_date']}[/green]"
        )

    except Exception as e:
        console.print(f"[red]Error updating usage: {e}[/red]")
        import traceback
        traceback.print_exc()


#endregion
