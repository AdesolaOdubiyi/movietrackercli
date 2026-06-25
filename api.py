import os
from models import MovieSchema
import requests
import re
from typing import Optional

# create client w/ api key
my_api_key = os.getenv("TMDB_API_KEY")


# search movie w/ call to tdmb 

genre_map: dict[int, str] = {}

# get movie genre
def get_genre() -> dict[int, str]:
  if not genre_map:
    response = requests.get("https://api.themoviedb.org/3/genre/movie/list",params={"api_key": my_api_key, "language": "en"},
    timeout=10,)
    if response.status_code != 200:
      raise requests.HTTPError(f"TMDB returned {response.status_code}", response=response)
    else:
      for genre in response.json()["genres"]:
        genre_map.update({genre["id"]: genre["name"]})
  return genre_map

# split the year off the year so it can be passed in TMDB year filter
def split_year(query: str) -> tuple[str, Optional[int]]:
  match = re.search(r"\b(19\d{2}|20\d{2})\b\s*$", query.strip())
  if not match:
    return query, None
  year = int(match.group(1))
  title = query[: match.start()].strip()
  return title or query, year

def search_movie(query: str) -> MovieSchema:
  movie_title, year = split_year(query)
  params = {
    "api_key": my_api_key,
    "query": movie_title,
    "include_adult": False,
  }
  if year: 
    params["primary_release_year"] = year
  try:
    response = requests.get(f"https://api.themoviedb.org/3/search/movie", params=params, timeout=10)
    if response.status_code != 200:
      raise requests.HTTPError(f"TMDB returned {response.status_code}", response=response)
    else:
      results = response.json().get("results", [])
    if not results:
      raise RuntimeError(f"No movie found matched w/ {query}")
    
    movie = results[0]
    genre_map = get_genre()
    genres = []
    for genre_id in movie.get("genre_ids", []):
      if genre_id in genre_map:
        genres.append(genre_map[genre_id])
    if movie.get("release_date"):
      release_year = int(movie["release_date"][:4])
    else:
      release_year = 0
    
    if genres: 
      genre=", ".join(genres)
    else:
      genre = "Unknown"


    return MovieSchema(
      title=movie["title"],
      year=release_year,
      genre=genre,
      imdb_rating = round(movie.get("vote_average", 0.0), 1),
    )
  except requests.RequestException as exc:
    raise RuntimeError(f"TMDB failed to produce a reponse {exc}") from exc
