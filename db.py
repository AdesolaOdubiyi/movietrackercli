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
  