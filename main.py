from typing import List, Optional
import typer
from rich.console import Console
from rich.table import Table
import db
from api import search_movie
from models import MovieSchema
from datetime import datetime

app = typer.Typer(
    help="Track watched movies, search real-time movie data with Groq",
    no_args_is_help=True,
)
console = Console()

def format_timestamp(iso_str: Optional[str]) -> str:
  if not iso_str:
    return "-"
  parsed = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")
  return parsed.strftime("%Y-%m-%d %H:%M")

def query(words: List[str]) -> str:
    text = " ".join(words).strip()
    if not text:
        raise typer.BadParameter("Please provide a movie title, slug, or search query.")
    return text


def movie_table(title: str, rows: list[dict]) -> None:
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
            format_timestamp(row.get("last_watched_at"))
        )
    console.print(table)


def print_movie(movie: MovieSchema, prefix: str = "Found") -> None:
    console.print(f"[bold green]{prefix}:[/bold green] {movie.title} ({movie.year})")
    console.print(f"[bold]Slug:[/bold] {movie.slug}")
    console.print(f"[bold]Genre:[/bold] {movie.genre}")
    console.print(f"[bold]IMDb:[/bold] {movie.imdb_rating:.1f}/10")


def handle_error(exc: Exception) -> None:
    console.print(f"[bold red]Error:[/bold red] {exc}")
    raise typer.Exit(code=1)

@app.callback()
def startup() -> None:
    db.init_db()


@app.command()
def search(
    query_words: List[str] = typer.Argument(..., help="Movie Query, e.g. Inception"),
    save_result: bool = typer.Option(False, "--save", "-s", help="Save the found movie."),
) -> None:
   
    try:
        movie = search_movie(query(query_words))
        print_movie(movie)
        if save_result:
            slug = db.save_movie_to_db(movie)
            console.print(f"[green]Saved as[/green] {slug}")
    except (RuntimeError, ValueError) as exc:
        handle_error(exc)


@app.command()
def save(query_words: List[str] = typer.Argument(..., help="Movie query to search and save.")) -> None:
    try:
        movie = search_movie(query(query_words))
        slug = db.save_movie_to_db(movie)
        print_movie(movie, prefix="Saved")
        console.print(f"[bold]Primary key:[/bold] {slug}")
    except (RuntimeError, ValueError) as exc:
        handle_error(exc)


@app.command("list")
def list_saved(
    watched_only: bool = typer.Option(False, "--watched", "-w", help="Only show movies with watch logs."),
) -> None:
    """List saved movies."""
    rows = db.get_saved_movies(watched_only=watched_only)
    if not rows:
        console.print("No movies found yet. Try: [bold]python main.py save inception 2010[/bold]")
        return
    movie_table("Saved Movies", rows)


def resolve_saved_slug_or_fetch(query_text: str) -> tuple[str, str]:
    exact = db.get_movie(query_text)
    if exact:
        return exact["slug"], exact["title"]

    matches = db.find_saved_movies(query_text, limit=2)
    if len(matches) == 1:
        return matches[0]["slug"], matches[0]["title"]

    movie = search_movie(query_text)
    slug = db.save_movie_to_db(movie)
    return slug, movie.title


@app.command()
def watched(
    movie_words: List[str] = typer.Argument(
        ...,
        help="Saved slug, title, or search query. If not saved, it will be fetched and saved.",
    ),
) -> None:
    try:
        slug, title = resolve_saved_slug_or_fetch(query(movie_words))
        db.mark_as_watched(slug)
        console.print(f"[green]Logged watched:[/green] {title} ({slug})")
    except (RuntimeError, ValueError) as exc:
        handle_error(exc)


@app.command()
def find(query_words: List[str] = typer.Argument(..., help="Search inside your saved movies.")) -> None:
    rows = db.find_saved_movies(query(query_words))
    if not rows:
        console.print("No saved movies matched that search.")
        return
    movie_table("Matching Saved Movies", rows)


@app.command()
def stats() -> None:
    data = db.get_stats_data()
    table = Table(title="Movie Tracker Stats")
    table.add_column("Metric")
    table.add_column("Value", justify="right")

    labels = {
        "total_saved": "Total saved movies",
        "total_watches": "Total watch logs",
        "unique_watched": "Unique movies watched",
        "average_imdb_rating": "Average IMDb rating",
        "top_genre": "Most common genre",
    }

    for key, label in labels.items():
        value = data.get(key)
        table.add_row(label, str(value if value is not None else "—"))
    console.print(table)


@app.command()
def top(limit: int = typer.Option(10, "--limit", "-n", min=1, max=50, help="Number of movies to show.")) -> None:
    """Show top-rated saved movies."""
    rows = db.get_top_rated_movies(limit=limit)
    if not rows:
        console.print("No movies saved yet.")
        return
    movie_table(f"Top {limit} Saved Movies", rows)


if __name__ == "__main__":
    app()
