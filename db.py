import sqlite3
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from models import MovieSchema

DB_NAME = "movies.db"

# ALL OUR DB OPERATIONS

# current_timestamp
def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# function to establish the connection
def get_db_connection(db_path: str = DB_NAME) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# function to add user rating and user review columns if they dont alredy exists
# doing this since its a change to our existing db
def _migrate(db_path: str = DB_NAME) -> None:
    with get_db_connection(db_path) as conn:
        for sql in [
            "ALTER TABLE movies ADD COLUMN user_rating INTEGER",
            "ALTER TABLE movies ADD COLUMN user_rating TEXT",
        ]:
            try:
                conn.execute(sql)
            except Exception:
                pass # because this means column already exists



# function to initalize the DB (something with conn i think)
def init_db(db_path: str = DB_NAME) -> None:
    with get_db_connection(db_path) as db_connection:
        db_connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS movies (
                slug TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                year INTEGER NOT NULL,
                genre TEXT NOT NULL,
                imdb_rating REAL NOT NULL CHECK (imdb_rating >= 0 AND imdb_rating <= 10),
                saved_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                user_rating INTEGER,
                user_review TEXT
            );

            CREATE TABLE IF NOT EXISTS watched_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movie_slug TEXT NOT NULL,
                watched_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_watched_log_movie_slug
                ON watched_log(movie_slug);
            CREATE INDEX IF NOT EXISTS idx_watched_log_watched_at
                ON watched_log(watched_at);
            """
        )
# perform no operation if the columns already exists
_migrate()

# function to save movie to DB
def save_movie_to_db(movie: MovieSchema, db_path: str = DB_NAME) -> str:
    current_timestamp = utc_now()
    with get_db_connection(db_path) as db_connection:
        db_connection.execute(
            """
            INSERT INTO movies (slug, title, year, genre, imdb_rating, saved_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title,
                year = excluded.year,
                genre = excluded.genre,
                imdb_rating = excluded.imdb_rating,
                updated_at = excluded.updated_at;
            """,
            (
                movie.slug,
                movie.title,
                movie.year,
                movie.genre,
                movie.imdb_rating,
                current_timestamp,
                current_timestamp,
            ),
        )
    return movie.slug


# function to get a single saved movie by slug
def get_movie(slug: str, db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as db_connection:
        movie_row = db_connection.execute(
            """
            SELECT
                movie.*,
                COUNT(watch_log.id) AS times_watched,
                MAX(watch_log.watched_at) AS last_watched_at
            FROM movies AS movie
            LEFT JOIN watched_log AS watch_log ON watch_log.movie_slug = movie.slug
            WHERE movie.slug = ?
            GROUP BY movie.slug;
            """,
            (slug,),
        ).fetchone()
    if movie_row:
        return dict(movie_row)
    else:
        return None


# function to search saved movies by slug, title, year, or genre
def find_saved_movies(
    search_text: str,
    limit: int = 10,
    db_path: str = DB_NAME,
) -> List[Dict[str, Any]]:
    search_pattern = f"%{search_text.strip()}%"
    with get_db_connection(db_path) as db_connection:
        movie_rows = db_connection.execute(
            """
            SELECT
                movie.*,
                COUNT(watch_log.id) AS times_watched,
                MAX(watch_log.watched_at) AS last_watched_at
            FROM movies AS movie
            LEFT JOIN watched_log AS watch_log ON watch_log.movie_slug = movie.slug
            WHERE movie.slug LIKE ? OR movie.title LIKE ? OR CAST(movie.year AS TEXT) LIKE ? OR movie.genre LIKE ?
            GROUP BY movie.slug
            ORDER BY movie.saved_at DESC
            LIMIT ?;
            """,
            (search_pattern, search_pattern, search_pattern, search_pattern, limit),
        ).fetchall()
    matching_movies = []
    for movie_row in movie_rows:
        matching_movies.append(dict(movie_row))
    return matching_movies


# function to get saved movies
def get_saved_movies(watched_only: bool = False, db_path: str = DB_NAME) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as db_connection:
        movie_rows = db_connection.execute(
            """
            SELECT
                movie.*,
                COUNT(watch_log.id) AS times_watched,
                MAX(watch_log.watched_at) AS last_watched_at
            FROM movies AS movie
            LEFT JOIN watched_log AS watch_log ON watch_log.movie_slug = movie.slug
            GROUP BY movie.slug
            HAVING (? = 0 OR COUNT(watch_log.id) > 0)
            ORDER BY movie.saved_at DESC;
            """,
            [watched_only],
        ).fetchall()
    saved_movies = []
    for movie_row in movie_rows:
        saved_movies.append(dict(movie_row))
    return saved_movies


# function to mark a movie as watched
def mark_as_watched(slug: str, db_path: str = DB_NAME) -> None:
    watched_at = utc_now()
    if not get_movie(slug, db_path):
        raise ValueError(f"No saved movie exists with slug '{slug}'")
    with get_db_connection(db_path) as db_connection:
        db_connection.execute(
            "INSERT INTO watched_log (movie_slug, watched_at) VALUES (?, ?);",
            (slug, watched_at),
        )


# function to get top rated movies
def get_top_rated_movies(limit: int = 10, db_path: str = DB_NAME) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as db_connection:
        movie_rows = db_connection.execute(
            """
            SELECT
                movie.*,
                COUNT(watch_log.id) AS times_watched,
                MAX(watch_log.watched_at) AS last_watched_at
            FROM movies AS movie
            LEFT JOIN watched_log AS watch_log ON watch_log.movie_slug = movie.slug
            GROUP BY movie.slug
            ORDER BY movie.imdb_rating DESC, movie.year DESC, movie.title ASC
            LIMIT ?;
            """,
            (limit,),
        ).fetchall()
    top_movies = []
    for movie_row in movie_rows:
        top_movies.append(dict(movie_row))
    return top_movies

# function for users to rate a movie, safeguard to return False if movie not watched yet
def rate_movie(slug: str, rating: int, review: Optional[str] = None,
    db_path: str = DB_NAME) -> bool:
    movie = get_movie(slug, db_path)

    if not movie:
        raise ValueError(f"Movie '{slug}' not found.")

    # movie was saved but never watched
    if not movie["times_watched"]:
        return False

    with get_db_connection(db_path) as conn:
        conn.execute(
            "UPDATE movies SET user_rating = ?, user_review = ?, updated_at = ? WHERE slug = ?",
            (rating, review, utc_now(), slug),
        )

    return True

# function to get rating distribution across all rated movies
def get_rating_distribution(db_path: str = DB_NAME) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT user_rating AS score, COUNT(*) AS count
            FROM movies
            WHERE user_rating IS NOT NULL
            GROUP BY user_rating
            ORDER BY user_rating
            """
        ).fetchall()
    rating_distribution = []
    for row in rows:
        rating_distribution.append(dict(row))
    return rating_distribution

# function to get average user rating grouped by genre
def get_avg_rating_by_genre(db_path: str = DB_NAME) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT genre, ROUND(AVG(user_rating), 2) AS avg_rating, COUNT(*) AS count
            FROM movies
            WHERE user_rating IS NOT NULL AND genre IS NOT NULL
            GROUP BY genre
            ORDER BY avg_rating DESC
            """
        ).fetchall()
    avg_by_genre = []
    for row in rows:
        avg_by_genre.append(dict(row))
    return avg_by_genre

# function to get avereage user rating grouped by decade
def get_avg_rating_by_decade(db_path: str = DB_NAME) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT (year / 10) * 10 AS decade,
                   ROUND(AVG(user_rating), 2) AS avg_rating,
                   COUNT(*) AS count
            FROM movies
            WHERE user_rating IS NOT NULL AND year IS NOT NULL
            GROUP BY decade
            ORDER BY decade
            """
        ).fetchall()
        avg_by_decade = []
        for row in rows:
            avg_by_decade.append(dict(row))
    return avg_by_decade

# function to get count of saved movies never watched
def get_backlog_size(db_path: str = DB_NAME) -> int:
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM movies
            WHERE slug NOT IN (SELECT DISTINCT movie_slug FROM
                watched_log)
            """
        ).fetchone()
    return row["n"] if row else 0

# function to get the statistics on watched movies and saved movies
def get_stats_data(db_path: str = DB_NAME) -> Dict[str, Any]:
    saved_movies = get_saved_movies(db_path=db_path)
    total_saved = len(saved_movies)

    total_watches = 0
    unique_watched = 0
    rating_total = 0.0
    genre_counter: Counter[str] = Counter()

    for movie in saved_movies:
        times_watched = int(movie["times_watched"] or 0)
        total_watches += times_watched
        if times_watched > 0:
            unique_watched += 1

        rating_total += float(movie["imdb_rating"])

        for genre in str(movie["genre"]).split(","):
            genre = genre.strip()
            if genre:
                genre_counter[genre] += 1

    average_imdb_rating = None
    if total_saved:
        average_imdb_rating = round(rating_total / total_saved, 2)

    if genre_counter:
        most_common_genre = genre_counter.most_common(1)[0][0]
    else:
        most_common_genre = None
    return {
        "total_saved": total_saved,
        "total_watches": total_watches,
        "unique_watched": unique_watched,
        "average_imdb_rating": average_imdb_rating,
        "top_genre": most_common_genre,
    }
