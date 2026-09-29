from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from shapely.wkt import loads as wkt_loads
from shapely.wkb import loads as wkb_loads
from shapely.geometry.base import BaseGeometry

def safe_from_shape(lon, lat, engine=None):
    p = Point(lon, lat)
    return from_shape(p, srid=4326)

def safe_to_shape(geom):
    """Safely converts a database geometry column value (GeoAlchemy2 WKB, WKT, or Shapely Geometry)
    to a Shapely geometry object."""
    if geom is None:
        return None
    if isinstance(geom, BaseGeometry):
        return geom
    try:
        return to_shape(geom)
    except Exception:
        if isinstance(geom, str):
            return wkt_loads(geom)
        elif isinstance(geom, (bytes, bytearray)):
            return wkb_loads(geom)
        raise
