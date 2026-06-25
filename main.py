from typing import List, Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import db
from api import search_movie
from models import MovieSchema
import os
from openai import OpenAI


app = typer.Typer(
    help="Track watched movies, search real-time movie data with Groq",
    no_args_is_help=True,
)
console = Console()

WELCOME_TEXT = """[bold cyan]Commands[/bold cyan]

  [green]search[/green]     Find a movie via AI
  [green]save[/green]       Save a movie to your list
  [green]watched[/green]    Log that you watched a movie
  [green]rate[/green]       Rate + review a watched movie
  [green]list[/green]       List all saved movies
  [green]find[/green]       Search your saved movies locally
  [green]top[/green]        Show top-rated saved movies
  [green]stats[/green]      View your stats and breakdowns
  [green]recommend[/green]  Get AI recommendations

  [dim]quit / exit / q   Exit interactive mode[/dim]"""


def _query(words: List[str]) -> str:
    text = " ".join(words).strip()
    if not text:
        raise typer.BadParameter("Please provide a movie title, slug, or search query.")
    return text


def _movie_table(title: str, rows: list[dict]) -> None:
    table = Table(title=title)
    table.add_column("Slug", overflow="fold")
    table.add_column("Title")
    table.add_column("Year", justify="right")
    table.add_column("Genre", overflow="fold")
    table.add_column("IMDb", justify="right")
    table.add_column("Your Rating", justify="right")
    table.add_column("Watched", justify="right")
    table.add_column("Last Watched", overflow="fold")

    for row in rows:
        user_rating = row.get("user_rating")
        table.add_row(
            str(row.get("slug", "")),
            str(row.get("title", "")),
            str(row.get("year", "")),
            str(row.get("genre", "")),
            f"{float(row.get('imdb_rating', 0)):.1f}",
            f"{user_rating}/10" if user_rating else "—",
            str(row.get("times_watched", 0) or 0),
            str(row.get("last_watched_at") or "—"),
        )
    console.print(table)


def _print_movie(movie: MovieSchema, prefix: str = "Found") -> None:
    console.print(f"[bold green]{prefix}:[/bold green] {movie.title} ({movie.year})")
    console.print(f"[bold]Slug:[/bold] {movie.slug}")
    console.print(f"[bold]Genre:[/bold] {movie.genre}")
    console.print(f"[bold]IMDb:[/bold] {movie.imdb_rating:.1f}/10")


def _handle_error(exc: Exception) -> None:
    console.print(f"[bold red]Error:[/bold red] {exc}")
    raise typer.Exit(code=1)


def _resolve_saved_slug_or_fetch(query_text: str) -> tuple[str, str]:
    exact = db.get_movie(query_text)
    if exact:
        return exact["slug"], exact["title"]

    matches = db.find_saved_movies(query_text, limit=2)
    if len(matches) == 1:
        return matches[0]["slug"], matches[0]["title"]

    movie = search_movie(query_text)
    slug = db.save_movie_to_db(movie)
    return slug, movie.title


@app.callback()
def startup() -> None:
    """Initialize the SQLite database before every command."""
    db.init_db()


@app.command()
def search(
    query_words: List[str] = typer.Argument(..., help="Movie Query, e.g. Inception"),
    save_result: bool = typer.Option(False, "--save", "-s", help="Save the found movie."),
) -> None:
    """Search for a movie via AI."""
    try:
        movie = search_movie(_query(query_words))
        _print_movie(movie)
        if save_result:
            slug = db.save_movie_to_db(movie)
            console.print(f"[green]Saved as[/green] {slug}")
    except (RuntimeError, ValueError) as exc:
        _handle_error(exc)


@app.command()
def save(query_words: List[str] = typer.Argument(..., help="Movie query to search and save.")) -> None:
    """Search and save a movie."""
    try:
        movie = search_movie(_query(query_words))
        slug = db.save_movie_to_db(movie)
        _print_movie(movie, prefix="Saved")
        console.print(f"[bold]Primary key:[/bold] {slug}")
    except (RuntimeError, ValueError) as exc:
        _handle_error(exc)


@app.command("list")
def list_saved(
    watched_only: bool = typer.Option(False, "--watched", "-w", help="Only show movies with watch logs."),
) -> None:
    """List saved movies."""
    rows = db.get_saved_movies(watched_only=watched_only)
    if not rows:
        console.print("No movies found yet. Try: [bold]save inception 2010[/bold]")
        return
    _movie_table("Saved Movies", rows)


@app.command()
def watched(
    movie_words: List[str] = typer.Argument(
        ...,
        help="Saved slug, title, or search query. If not saved, it will be fetched and saved.",
    ),
) -> None:
    """Log that you watched a movie."""
    try:
        slug, title = _resolve_saved_slug_or_fetch(_query(movie_words))
        db.mark_as_watched(slug)
        console.print(f"[green]Logged watched:[/green] {title} ({slug})")
    except (RuntimeError, ValueError) as exc:
        _handle_error(exc)


@app.command()
def rate(
    movie_words: List[str] = typer.Argument(..., help="Movie slug or title to rate."),
    score: int = typer.Option(..., "--score", "-s", min=1, max=10, help="Your rating out of 10."),
    review: Optional[str] = typer.Option(None, "--review", "-r", help="Optional one-line review."),
) -> None:
    """Rate and optionally review a watched movie."""
    try:
        query = _query(movie_words)
        exact = db.get_movie(query)
        if not exact:
            matches = db.find_saved_movies(query, limit=2)
            if not matches:
                console.print(f"[red]Movie '{query}' not found in your saved list.[/red]")
                raise typer.Exit(code=1)
            exact = matches[0]

        slug = exact["slug"]
        title = exact["title"]

        success = db.rate_movie(slug, score, review)
        if not success:
            console.print(
                f"[yellow]'{title}' hasn't been watched yet.[/yellow] "
                f"Log it first with: [bold]watched {slug}[/bold]"
            )
            raise typer.Exit(code=1)

        console.print(f"[green]Rated:[/green] {title} — {score}/10")
        if review:
            console.print(f"[dim]Review:[/dim] {review}")

    except (RuntimeError, ValueError) as exc:
        _handle_error(exc)


@app.command()
def find(query_words: List[str] = typer.Argument(..., help="Search inside your saved movies.")) -> None:
    """Search your local saved movies without calling AI."""
    rows = db.find_saved_movies(_query(query_words))
    if not rows:
        console.print("No saved movies matched that search.")
        return
    _movie_table("Matching Saved Movies", rows)


@app.command()
def stats() -> None:
    """Show database stats."""
    data = db.get_stats_data()
    backlog = db.get_backlog_size()

    overview = Table(title="Movie Tracker Stats")
    overview.add_column("Metric")
    overview.add_column("Value", justify="right")

    labels = {
        "total_saved": "Total saved movies",
        "total_watches": "Total watch logs",
        "unique_watched": "Unique movies watched",
        "average_imdb_rating": "Average IMDb rating",
        "top_genre": "Most common genre",
    }
    for key, label in labels.items():
        value = data.get(key)
        overview.add_row(label, str(value if value is not None else "—"))
    overview.add_row("Backlog (unwatched)", str(backlog))
    console.print(overview)

    dist = db.get_rating_distribution()
    if dist:
        dist_table = Table(title="Your Rating Distribution")
        dist_table.add_column("Score", justify="center")
        dist_table.add_column("Movies", justify="right")
        dist_table.add_column("Bar")
        for row in dist:
            bar = " " * row["count"]
            dist_table.add_row(f"{row['score']}/10", str(row["count"]), f"[cyan]{bar}[/cyan]")
        console.print(dist_table)

    by_genre = db.get_avg_rating_by_genre()
    if by_genre:
        genre_table = Table(title="Avg Your Rating by Genre")
        genre_table.add_column("Genre")
        genre_table.add_column("Avg Rating", justify="right")
        genre_table.add_column("Rated Movies", justify="right")
        for row in by_genre:
            genre_table.add_row(str(row["genre"]), f"{row['avg_rating']}/10", str(row["count"]))
        console.print(genre_table)

    by_decade = db.get_avg_rating_by_decade()
    if by_decade:
        decade_table = Table(title="Avg Your Rating by Decade")
        decade_table.add_column("Decade")
        decade_table.add_column("Avg Rating", justify="right")
        decade_table.add_column("Rated Movies", justify="right")
        for row in by_decade:
            decade_table.add_row(f"{row['decade']}s", f"{row['avg_rating']}/10", str(row["count"]))
        console.print(decade_table)

    if not dist and not by_genre:
        console.print("[dim]Rate some movies to unlock breakdowns — try: rate inception --score 9[/dim]")


@app.command()
def top(limit: int = typer.Option(10, "--limit", "-n", min=1, max=50, help="Number of movies to show.")) -> None:
    """Show top-rated saved movies."""
    rows = db.get_top_rated_movies(limit=limit)
    if not rows:
        console.print("No movies saved yet.")
        return
    _movie_table(f"Top {limit} Saved Movies", rows)


@app.command()
def start() -> None:
    """Start an interactive session."""
    console.print(Panel(WELCOME_TEXT, title="[bold cyan]Movie Tracker CLI[/bold cyan]", expand=False))
    while True:
        try:
            line = input("\n>> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if line.lower() in ("quit", "exit", "q"):
            console.print("Bye!")
            break
        if not line:
            continue
        try:
            app(line.split(), standalone_mode=False)
        except Exception as e:
            console.print(f"[red]{e}[/red]")


@app.command()
def recommend(
    query_words: List[str] = typer.Argument(..., help="Describe what you want to watch.")
) -> None:
    """Get movie recommendations based on a description."""
    my_api_key = os.getenv("GENAI_KEY")
    client = OpenAI(api_key=my_api_key, base_url="https://api.groq.com/openai/v1")
    prompt = f"Recommend 5 movies for someone who wants: {_query(query_words)}. For each give: title, year, genre, and one sentence why. Be concise."
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    console.print(response.choices[0].message.content)


if __name__ == "__main__":
    app()