import sqlite3
from datetime import datetime
from typing import List, Tuple, Optional
from models import MovieSchema

DB_NAME = "movies.db"

# ALL OUR DB OPERATIONS

# function to establish the connection
def get_db_connection():
  conn = sqlite3.connect(DB_NAME)
  conn.row_factory = sqlite3
  return conn

# function to initalize the DB (something with conn i think)
def init_db():
  """Creates our movie and watched tables"""
  conn.execute("""
    CREATE TABLE IF NOT EXISTS movies (
    slug TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    year INTEGER,
    genre TEXT,
    imdb_rating REAL
    )
  """)
  conn.execute("""
      CREATE TABLE IF NOT EXISTS watched (
          movie_slug TEXT PRIMARY KEY,
          watched_date TEXT,
          FOREIGN KEY(movie_slug) REFERENCES movies(slug) ON DELETE CASCADE
          )
      """)
      conn.commit()

# function to save movie to DB
def save_movie_to_db(movie: MovieSchema) -> str:
  
# function to get saved movies
def get_saved_movies() -> List[Tuple[str, int]]:

# function to mark a movie as watched
def mark_as_watched(slug: str):

# function to get the statistics on watched movies and saved movies
def get_stats_data() -> Tuple[int, int]:

# function to get top rated movies
def get_top_rated_movies() -> List[Tuple[str, float]]:
