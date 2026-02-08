import math

import dash_leaflet as dl
from dash import Dash, html, dcc, Input, Output
from pyproj import Geod

geod = Geod(ellps="WGS84")


def parse_float(s) -> float:
    """Return float(s) if possible, else None."""
    try:
        return float(str(s).strip())
    except Exception:
        return math.nan


def valid_lat_lon(lat, lon):
    """Optional range checks (still requires numeric)."""
    if lat is None or lon is None:
        return False
    return (-90.0 <= lat <= 90.0) and (-180.0 <= lon <= 180.0)


app = Dash(__name__)
app.title = "Distance & Azimuth Tool"

# --- Layout ---
app.layout = html.Div(
    style={"height": "100vh", "width": "100vw", "margin": 0, "padding": 0, "position": "relative"},
    children=[
        # Map (full screen)
        dl.Map(
            id="map",
            center=[0, 0],
            zoom=2,
            style={"height": "100%", "width": "100%"},
            children=[
                dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"),
                # Dynamic layers:
                html.Div(id="start-layer"),
                html.Div(id="dest-layer"),
                html.Div(id="line-layer"),
            ],
        ),

        # Top-left control panel overlay
        html.Div(
            style={
                "position": "absolute",
                "top": "12px",
                "left": "12px",
                "zIndex": 9999,
                "background": "rgba(255,255,255,0.92)",
                "padding": "12px",
                "borderRadius": "12px",
                "boxShadow": "0 6px 18px rgba(0,0,0,0.15)",
                "fontFamily": "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
                "minWidth": "260px",
            },
            children=[
                html.Div("Start", style={"fontWeight": 700, "marginBottom": "6px"}),
                html.Div(
                    style={"display": "grid", "gridTemplateColumns": "48px 1fr", "gap": "8px", "alignItems": "center"},
                    children=[
                        html.Label("Lat:", style={"textAlign": "right"}),
                        dcc.Input(id="start-lat", type="text", placeholder="e.g. 1.3521", debounce=False),
                        html.Label("Lon:", style={"textAlign": "right"}),
                        dcc.Input(id="start-lon", type="text", placeholder="e.g. 103.8198", debounce=False),
                    ],
                ),
                html.Hr(style={"margin": "12px 0"}),

                html.Div("Destination", style={"fontWeight": 700, "marginBottom": "6px"}),
                html.Div(
                    style={"display": "grid", "gridTemplateColumns": "48px 1fr", "gap": "8px", "alignItems": "center"},
                    children=[
                        html.Label("Lat:", style={"textAlign": "right"}),
                        dcc.Input(id="dest-lat", type="text", placeholder="e.g. 35.6895", debounce=False),
                        html.Label("Lon:", style={"textAlign": "right"}),
                        dcc.Input(id="dest-lon", type="text", placeholder="e.g. 139.6917", debounce=False),
                    ],
                ),
                html.Div(
                    "Tip: if either Lat/Lon is not a number, that point disappears.",
                    style={"marginTop": "10px", "fontSize": "12px", "color": "#444"},
                ),
            ],
        ),

        # Bottom results box
        html.Div(
            style={
                "position": "absolute",
                "left": "12px",
                "right": "12px",
                "bottom": "12px",
                "zIndex": 9999,
                "background": "rgba(255,255,255,0.92)",
                "padding": "12px",
                "borderRadius": "12px",
                "boxShadow": "0 6px 18px rgba(0,0,0,0.15)",
                "fontFamily": "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
            },
            children=[
                html.Div("Distance & Azimuth (Start → Destination)", style={"fontWeight": 700, "marginBottom": "6px"}),
                dcc.Textarea(
                    id="result-box",
                    value="Enter both Start and Destination coordinates to compute distance and azimuth.",
                    readOnly=True,
                    style={"width": "100%", "height": "80px", "resize": "none"},
                ),
            ],
        ),
    ],
)


# --- Callback: update markers, polyline, bounds, result text ---
@app.callback(
    Output("start-layer", "children"),
    Output("dest-layer", "children"),
    Output("line-layer", "children"),
    Output("result-box", "value"),
    Output("map", "bounds"),
    Input("start-lat", "value"),
    Input("start-lon", "value"),
    Input("dest-lat", "value"),
    Input("dest-lon", "value"),
)
def update_map(start_lat_s: str, start_lon_s: str, dest_lat_s: str, dest_lon_s: str):
    s_lat: float = parse_float(start_lat_s)
    s_lon: float = parse_float(start_lon_s)
    d_lat: float = parse_float(dest_lat_s)
    d_lon: float = parse_float(dest_lon_s)

    start_ok = valid_lat_lon(s_lat, s_lon)
    dest_ok = valid_lat_lon(d_lat, d_lon)

    start_marker = None
    dest_marker = None
    line = None
    bounds = None

    if start_ok:
        start_marker = dl.Marker(
            position=[s_lat, s_lon],
            children=[dl.Tooltip("Start"), dl.Popup(f"Start: {s_lat:.3f}, {s_lon:.3f}")],
        )

    if dest_ok:
        # Entering Western Hemisphere from the west
        if s_lon - d_lon > 180:
            d_lon += 360
        dest_marker = dl.Marker(
            position=[d_lat, d_lon],
            children=[dl.Tooltip("Destination"), dl.Popup(f"Dest: {d_lat:.3f}, {d_lon:.3f}")],
        )

    if start_ok and dest_ok:
        # Geodesic distance + azimuth
        fwd_az_deg, back_az_deg, dist_m = geod.inv(s_lon, s_lat, d_lon, d_lat)
        az = (fwd_az_deg + 360) % 360
        dist_km = dist_m / 1000
        # --- Generate great-circle points ---
        N = 1024  # number of segments (increase for smoother curve)
        gc_lonlat = geod.npts(s_lon, s_lat, d_lon, d_lat, N, False, 0, 0)
        shift_right: bool = d_lon > 180
        gc_points = [(lat, (lon + 360) % 360 if shift_right else lon) for lon, lat in gc_lonlat]
        # --- Curved polyline ---
        line = dl.Polyline(
            positions=gc_points,
            color="blue",
            weight=3,
        )
        result = f"Distance: {dist_km:.3f} km\nAzimuth (Start → Dest): {az:.1f}° (clockwise from true North)"
        # Fit map to both points
        bounds = [[min(s_lat, d_lat), min(s_lon, d_lon)], [max(s_lat, d_lat), max(s_lon, d_lon)]]
    else:
        result = "Enter both Start and Destination coordinates to compute distance and azimuth."

    return start_marker, dest_marker, line, result, bounds


if __name__ == "__main__":
    app.run(debug=True)
