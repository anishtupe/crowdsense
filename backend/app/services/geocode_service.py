"""
Geocode service: resolve place-name mentions in text to coordinates.

Stub implementation. For real use, either:
  - run a NER model to extract place names, then call a geocoding API
    (Nominatim/OpenStreetMap, Google Geocoding, etc.), or
  - rely solely on the GPS coordinates the client already sends with
    each report (simplest, and what the rest of this scaffold assumes).
"""
from __future__ import annotations

from typing import Optional, Tuple


def extract_location_mention(text: Optional[str]) -> Optional[str]:
    """Very naive placeholder — real version should use spaCy NER or similar."""
    return None


def geocode_place_name(place: str) -> Optional[Tuple[float, float]]:
    """Returns (lat, lon) or None. Wire up a real geocoding API here."""
    return None
