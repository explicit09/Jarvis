"""Web-related tools for J.A.R.V.I.S.

Provides tools for:
- Web search
- URL fetching
- Information retrieval
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from livekit.agents import llm

logger = logging.getLogger(__name__)

# HTTP client for web requests
_http_client: Optional[httpx.AsyncClient] = None


def _get_http_client() -> httpx.AsyncClient:
    """Get or create HTTP client."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "J.A.R.V.I.S/1.0 (Voice Assistant)"
            },
        )
    return _http_client


@llm.function_tool
async def web_search(query: str, num_results: int = 3) -> str:
    """Search the web for information.

    Args:
        query: Search query
        num_results: Number of results to return (1-5)
    """
    import asyncio

    # Handle string input from API calls
    if isinstance(num_results, str):
        try:
            num_results = int(num_results)
        except ValueError:
            num_results = 3

    num_results = max(1, min(5, num_results))

    try:
        from ddgs import DDGS

        # Run sync search in executor to not block
        def do_search():
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=num_results))

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, do_search)

        if not results:
            return f"No results found for '{query}'."

        # Format results
        output = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            output.append(f"{i}. {title}\n   {body}\n   {href}")

        return "\n\n".join(output)

    except ImportError:
        logger.error("duckduckgo-search not installed")
        return "Web search unavailable. Install duckduckgo-search package."
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return f"Search failed: {str(e)}"


@llm.function_tool
async def fetch_url(url: str) -> str:
    """Fetch content from a URL.

    Args:
        url: The URL to fetch
    """
    try:
        client = _get_http_client()
        response = await client.get(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        if "text/html" in content_type:
            # For HTML, extract text content (simplified)
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                    self._skip = False

                def handle_starttag(self, tag, attrs):
                    if tag in ("script", "style", "head"):
                        self._skip = True

                def handle_endtag(self, tag):
                    if tag in ("script", "style", "head"):
                        self._skip = False

                def handle_data(self, data):
                    if not self._skip:
                        text = data.strip()
                        if text:
                            self.text_parts.append(text)

            extractor = TextExtractor()
            extractor.feed(response.text)
            text = " ".join(extractor.text_parts)

            # Truncate if too long
            if len(text) > 2000:
                text = text[:2000] + "... [truncated]"

            return text

        elif "application/json" in content_type:
            import json

            data = response.json()
            return json.dumps(data, indent=2)[:2000]

        else:
            # Return raw text for other content types
            return response.text[:2000]

    except httpx.HTTPError as e:
        logger.error(f"URL fetch failed: {e}")
        return f"Failed to fetch URL: {str(e)}"
    except Exception as e:
        logger.error(f"URL fetch error: {e}")
        return f"Error fetching URL: {str(e)}"


@llm.function_tool
async def get_weather(city: str) -> str:
    """Get current weather for a city.

    Args:
        city: City name (e.g., 'New York', 'London')
    """
    try:
        # Use wttr.in for weather (no API key required)
        client = _get_http_client()
        response = await client.get(
            f"https://wttr.in/{city}",
            params={"format": "j1"},
        )
        response.raise_for_status()
        data = response.json()

        current = data["current_condition"][0]
        location = data["nearest_area"][0]

        city_name = location["areaName"][0]["value"]
        country = location["country"][0]["value"]
        temp_c = current["temp_C"]
        temp_f = current["temp_F"]
        desc = current["weatherDesc"][0]["value"]
        humidity = current["humidity"]
        wind_mph = current["windspeedMiles"]

        return (
            f"Weather in {city_name}, {country}: {desc}. "
            f"Temperature: {temp_f}F ({temp_c}C). "
            f"Humidity: {humidity}%. "
            f"Wind: {wind_mph} mph."
        )

    except httpx.HTTPError as e:
        logger.error(f"Weather fetch failed: {e}")
        return f"Could not get weather: {str(e)}"
    except Exception as e:
        logger.error(f"Weather error: {e}")
        return f"Error getting weather: {str(e)}"


@llm.function_tool
async def get_definition(word: str) -> str:
    """Get the definition of a word.

    Args:
        word: The word to define
    """
    try:
        client = _get_http_client()
        response = await client.get(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        )

        if response.status_code == 404:
            return f"No definition found for '{word}'"

        response.raise_for_status()
        data = response.json()

        if not data:
            return f"No definition found for '{word}'"

        entry = data[0]
        word = entry.get("word", word)
        phonetic = entry.get("phonetic", "")

        definitions = []
        for meaning in entry.get("meanings", [])[:2]:
            part_of_speech = meaning.get("partOfSpeech", "")
            for defn in meaning.get("definitions", [])[:2]:
                definition = defn.get("definition", "")
                if definition:
                    definitions.append(f"({part_of_speech}) {definition}")

        if definitions:
            result = f"{word}"
            if phonetic:
                result += f" {phonetic}"
            result += ": " + " | ".join(definitions)
            return result
        else:
            return f"No definition found for '{word}'"

    except Exception as e:
        logger.error(f"Definition lookup error: {e}")
        return f"Error looking up definition: {str(e)}"


def get_web_tools() -> list:
    """Get all web tools."""
    return [
        web_search,
        fetch_url,
        get_weather,
        get_definition,
    ]
