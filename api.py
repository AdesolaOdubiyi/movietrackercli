import os
from openai import OpenAI
from models import MovieSchema

# create client w/ api key
my_api_key = os.getenv("GENAI_KEY")
client = OpenAI(api_key=my_api_key, base_url="https://api.groq.com/openai/v1")


# search movie w/ call to gemini api

def search_movie(query: str) -> MovieSchema:
    prompt = f"""
    Find the best matching movie for this user query:
    "{query}"

    Return exactly one movie. Prefer a theatrically released feature film when the
    query is ambiguous. Use accurate public data. The IMDb rating must be a
    number from 0 to 10. Do not include explanations, markdown, or extra fields.
    """
    try:
      completion = client.chat.completions.parse(
          model="openai/gpt-oss-20b",
          messages=[{"role": "user", "content": prompt}],
          response_format=MovieSchema,
      )
      return completion.choices[0].message.parsed
    except Exception as exc:
      raise RuntimeError(f"Groq failed to produce a response: {exc}") from exc

