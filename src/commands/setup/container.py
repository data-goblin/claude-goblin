"""
Setup container command.

Sets up devcontainer for safe Claude Code execution with --dangerously-skip-permissions.
"""
from typing import Optional
import typer
from rich.console import Console

from src.commands.init_container import run as _run_init_container


def setup_container_command(
    target: str = typer.Argument(
        ".",
        help="Target directory (default: current directory)"
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name", "-n",
        help="Project name (default: directory name)"
    ),
    domains: Optional[str] = typer.Option(
        None,
        "--domains", "-d",
        help="Extra domains to whitelist (comma-separated)"
    ),
    no_vscode: bool = typer.Option(
        False,
        "--no-vscode",
        help="Skip creating .vscode/settings.json"
    ),
) -> None:
    """
    Setup devcontainer for safe Claude Code execution.

    Creates .devcontainer/ with Docker + firewall setup for running
    Claude Code with --dangerously-skip-permissions in an isolated container.

    Network is restricted to: GitHub, Anthropic, PyPI, npm, MS Learn, MDN.

    Examples:
        ccg setup container                     Setup in current directory
        ccg setup container /path/to/project    Setup in specific directory
        ccg setup container -n myproject        Set custom project name
        ccg setup container -d "example.com,api.example.com"  Add extra domains

    After setup:
        devcontainer up --workspace-folder .
        devcontainer exec --workspace-folder . claude --dangerously-skip-permissions
    """
    console = Console()

    extra_domains = None
    if domains:
        extra_domains = [d.strip() for d in domains.split(",") if d.strip()]

    _run_init_container(
        console,
        target_dir=target,
        project_name=name,
        extra_domains=extra_domains,
        vscode_settings=not no_vscode,
    )
