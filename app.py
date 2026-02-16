import math
from collections.abc import Callable

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
box_style = {"backgroundColor": "#00000000", "color": "white"}
textbox_style = {"border": "1px solid #555"} | box_style

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
                dl.TileLayer(
                    url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                    attribution="Tiles © Esri"
                ),
                dl.TileLayer(
                    url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
                    attribution="Tiles © Esri",
                ),
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
                "right": "12px",
                "zIndex": 9999,
                "background": "rgba(30,30,30,0.9)",
                "padding": "12px",
                "borderRadius": "12px",
                "boxShadow": "0 6px 18px rgba(0,0,0,0.15)",
                "fontFamily": "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
                "minWidth": "260px",
            },
            children=[
                html.Div("Start", style={"fontWeight": 700, "marginBottom": "6px"} | box_style),
                html.Div(
                    style={"display": "grid", "gridTemplateColumns": "48px 1fr", "gap": "8px", "alignItems": "center"},
                    children=[
                        html.Label("Lat:", style={"textAlign": "right"} | box_style),
                        dcc.Input(id="start-lat", type="text", placeholder="e.g. 1.3521", debounce=False,
                                  style=textbox_style),
                        html.Label("Lon:", style={"textAlign": "right"} | box_style),
                        dcc.Input(id="start-lon", type="text", placeholder="e.g. 103.8198", debounce=False,
                                  style=textbox_style),
                    ],
                ),
                html.Hr(style={"margin": "12px 0"}),

                html.Div("Destination", style={"fontWeight": 700, "marginBottom": "6px"} | box_style),
                html.Div(
                    style={"display": "grid", "gridTemplateColumns": "48px 1fr", "gap": "8px",
                           "alignItems": "center"},
                    children=[
                        html.Label("Lat:", style={"textAlign": "right"} | box_style),
                        dcc.Input(id="dest-lat", type="text", placeholder="e.g. 35.6895", debounce=False,
                                  style=textbox_style),
                        html.Label("Lon:", style={"textAlign": "right"} | box_style),
                        dcc.Input(id="dest-lon", type="text", placeholder="e.g. 139.6917", debounce=False,
                                  style=textbox_style),
                    ],
                ),
                html.Div(
                    "Tip: if either Lat/Lon is not a number, that point disappears.",
                    style={"marginTop": "10px", "fontSize": "12px", "color": "white"},
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
                "background": "rgba(30,30,30,0.9)",
                "padding": "12px",
                "borderRadius": "12px",
                "boxShadow": "0 6px 18px rgba(0,0,0,0.15)",
                "fontFamily": "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
            },
            children=[
                html.Div("Distance & Azimuth (Start → Destination)",
                         style={"fontWeight": 700, "marginBottom": "6px"} | box_style),
                dcc.Textarea(
                    id="result-box",
                    value="Enter both Start and Destination coordinates to compute distance and azimuth.",
                    readOnly=True,
                    style={
                        "width": "100%",
                        "height": "80px",
                        "resize": "none",
                          } | textbox_style,
                ),
            ],
        ),
    ],
)
make_deg_positive: Callable[[float], float] = lambda deg: (deg + 360) % 360

plane_icon = {
    "iconUrl": "https://cdn-icons-png.flaticon.com/512/870/870194.png",
    "iconSize": [32, 32],
    "iconAnchor": [16, 16]
}

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
            icon=plane_icon
        )

    if dest_ok:
        dest_marker = dl.Marker(
            position=[d_lat, d_lon],
            children=[dl.Tooltip("Destination"), dl.Popup(f"Dest: {d_lat:.3f}, {d_lon:.3f}")],
        )

    if start_ok and dest_ok:
        # Geodesic distance + azimuth
        fwd_az_deg, back_az_deg, dist_m = geod.inv(s_lon, s_lat, d_lon, d_lat)
        az = make_deg_positive(fwd_az_deg)
        dist_km = dist_m / 1000
        # --- Generate great-circle points ---
        N = 1024  # number of segments (increase for smoother curve)
        gc_lonlat = geod.npts(s_lon, s_lat, d_lon, d_lat, N, False, 0, 0)
        gc_points = [[lat, lon] for lon, lat in gc_lonlat]
        # Route crosses antimeridian
        if not (-180 <= d_lon - s_lon <= 180):
            start_marker.position[1] = make_deg_positive(s_lon)
            dest_marker.position[1] = make_deg_positive(d_lon)
            for lat_lon in gc_points:
                lat_lon[1] = make_deg_positive(lat_lon[1])
        # --- Curved polyline ---
        line = dl.Polyline(
            positions=gc_points,
            color="black",
            weight=2,
        )
        result = f"Distance: {dist_km:.3f} km\nAzimuth: {az:.1f}° (clockwise from true north)"
        # Fit map to both points
        bounds = [[min(s_lat, d_lat), min(s_lon, d_lon)], [max(s_lat, d_lat), max(s_lon, d_lon)]]
    else:
        result = "Enter both Start and Destination coordinates to compute distance and azimuth."

    return start_marker, dest_marker, line, result, bounds


if __name__ == "__main__":
    app.run(debug=True)
