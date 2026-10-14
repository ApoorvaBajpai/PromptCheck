import httpx
import typer
from rich.console import Console

app = typer.Typer(
    name="promptcheck",
    help="PromptCheck CLI - Test and evaluate prompts with continuous confidence.",
    add_completion=False,
)
console = Console()


@app.command()
def version():
    """Show PromptCheck CLI version."""
    console.print("[bold green]PromptCheck CLI[/bold green] version [bold cyan]0.1.0[/bold cyan]")


@app.command()
def ping(
    url: str = typer.Option(
        "http://localhost:8000",
        "--url",
        "-u",
        help="PromptCheck API base URL",
    ),
):
    """Ping PromptCheck backend API /healthz endpoint."""
    endpoint = f"{url.rstrip('/')}/healthz"
    console.print(f"Connecting to [bold]{endpoint}[/bold]...")
    try:
        response = httpx.get(endpoint, timeout=5.0)
        if response.status_code == 200:
            console.print("[bold green][OK] Success:[/bold green] PromptCheck backend is healthy!")
            console.print(response.json())
        else:
            console.print(
                f"[bold red][FAIL] Unhealthy status code:[/bold red] {response.status_code}"
            )
            console.print(response.text)
            raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red][FAIL] Connection failed:[/bold red] {exc}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
