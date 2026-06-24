from typing import List, Optional
import typer
from rich.console import console
from rich.table import Table 
import db
from api import search_movie
from models import MovieSchema

app = typer.Typer(
  help="Track watched movies, search real-time movie data with Groq",
  no_args_is_help=True,
)
console = Console()

def _query(words: List[str]) -> str:
  text = " ".join(words).strip()
  if not text:
    raise typer.BadParameter("Please provide a movie title, slug, or
  search query.")
  return text

def _movie_table(title: str, rows: list[dict]) -> None:
  table = Table(title=title)
  table.add_column("Slug", overflow="fold")
  table.add_column("Title")
  table.add_column("Year", justify="right")
  table.add_column("Genre", overflow="fold")
  table.add_column("IMDb", justify="right")
  table.add_column("Watched", justify="right")
  table.add_column("Last Watched", overflow="fold")

  for row in rows:
    table.add_row(
       str(row.get("slug", "")),
       str(row.get("title", "")),
       str(row.get("year", "")),
       str(row.get("genre", "")),
       f"{float(row.get('imdb_rating', 0)):.1f}",
       str(row.get("times_watched", 0) or 0),
       str(row.get("last_watched_at") or "—"),
    )
    console.print(table)

def _print_movie(movie: MovieSchema, prefix: str = "Found") -> None:
  console.print("f[bold green]{prefix}:[/bold green] {movie.title}
  ({movie.year})")
  console.print(f"[bold]Slug:[/bold] {movie.slug}")
  console.print(f"[bold]Genre:[/bold] {movie.genre}")
  console.print(f"[bold]IMDb:[/bold] {movie.imdb_rating:.1f}/10")

def _handle_error(exc: Exception) -> None:
  console.print(f"[bold red]Error:[/bold red] {exc}")
  raise typer.Exit(code=1)


@app.callback()
def startup() -> None:
  """Initialize the SQLite database before every command."""
  db.init_db()