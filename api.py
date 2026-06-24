import os
from google import genai
from models import MovieSchema

# create client w/ api key
my_api_key = os.getenv("GENAI_KEY")
client = genai.Client(api_key=my_api_key)


# search movie w/ call to gemini api

def search_movie(query: str) -> MovieSchema:
    prompt = f"""
    Use live Google Search to find the best matching movie for this user query:
    "{query}"

    Return exactly one movie. Prefer a theatrically released feature film when the
    query is ambiguous. Use current, accurate public data. The IMDb rating must be a
    number from 0 to 10. Do not include explanations, markdown, or extra fields.
    """
    try:
      interaction = client.interactions.create(
          model="gemini-3.5-flash",
          input=prompt,
          tools=[{"type": "google_search"}],
          response_format={
              "type": "text",
              "mime_type": "application/json",
              "schema": MovieSchema.model_json_schema(),
          },
      )
      return MovieSchema.model_validate_json(interaction.output_text)
    except Exception as exc:
      raise RuntimeError(f"Gemini failed to produce a response: {exc}") from exc