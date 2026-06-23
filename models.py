# db schema models or object models
# database entity structure and the strict Pydantic model Gemini must adhere to when compiling data from Google Search

import re
from pydantic import BaseModel, Field

# Pydantic Schema for Structured GenAI and Search Outputs
class MovieSchema(BaseModel):
  #we'll need title, year, genre, and imdb rating
  title: str = Field(description="Official movie title (i.e. 'Interstellar)")
  year: int = Field(description="Four digit release year (i.e. '2014)")
  genre: str = Field(description="Genre separated by commas (i.e. 'Action, Sci-Fie)")
  imdb_rating: float = Field(description="Current IMDB score out of ten")

  @property
  def slug(self) -> str:
    # strip everything except alphanumeric characters and spaces
    clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', self.title).lower()
    # replace spaces with a dash
    clean_title = re.sub(r'\s+', '-', clean_title.strip())
    return f"{clean_title}-{self.year}"