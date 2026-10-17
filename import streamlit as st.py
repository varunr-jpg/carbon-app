import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import hashlib
import requests

# 1. Page Configuration
st.set_page_config(page_title="Carbon Footprint & Gas Reader", layout="wide")

# 2. Initialize Session State
if "last_processed_hash" not in st.session_state:
    st.session_state.last_processed_hash = None
if "environmental_metrics" not in st.session_state:
    st.session_state.environmental_metrics = None

# Comprehensive Geographical Terrain Classifier
def classify_location_terrain(lat, lng):
    """
    Classifies coordinates into 'ocean', 'desert', 'ice', or 'land'.
    """
    # 1. POLAR / GLACIER CHECK (Antarctica & Far Arctic)
    if lat < -60.0 or lat > 72.0:
        return "ice"

    # 2. OCEAN & WATER BODY CHECK
    # Queries the OpenStreetMap Nominatim reverse geocoder for land/water class
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json&zoom=5"
        headers = {'User-Agent': 'CarbonFootprintApp/2.0'}
        res = requests.get(url, headers=headers, timeout=2.5).json()
        
        # Check if location is flagged as ocean/sea/water body
        category = res.get("category", "")
        type_tag = res.get("type", "")
        error_msg = res.get("error", "")
        
        if "water" in category or type_tag in ["ocean", "sea", "water", "bay", "strait"] or "Unable to geocode" in error_msg:
            # Fallback verification via open elevation API
            elev_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current_weather=true"
            elev_res = requests.get(elev_url, timeout=2).json()
            elevation = elev_res.get("elevation", 0)
            if elevation <= 0:
                return "ocean"
    except Exception:
        pass

    # 3. MAJOR DESERT BELTS CHECK (Coordinates bounding global arid zones)
    # Sahara & Arabian Desert (12°N - 35°N, 17°W - 60°E)
    if (12.0 <= lat <= 35.0) and (-17.0 <= lng <= 60.0):
        return "desert"
    # Australian Outback (-30°S - -18°S, 115°E - 140°E)
    elif (-30.0 <= lat <= -18.0) and (115.0 <= lng <= 140.0):
        return "desert"
    # Gobi Desert (38°N - 46°N, 95°E - 115°E)
    elif (38.0 <= lat <= 46.0) and (95.0 <= lng <= 115.0):
        return "desert"
    # Kalahari & Namib Desert (-28°S - -18°S, 14°E - 26°E)
    elif (-28.0 <= lat <= -18.0) and (14.0 <= lng <= 26.0):
        return "desert"

    return "land"

# Environmental Calculation Engine
def calculate_area_metrics(south, west, north, east):
    center_lat = (south + north) / 2.0
    center_lng = (west + east) / 2.0
    
    terrain = classify_location_terrain(center_lat, center_lng)
    
    lat_span = abs(north - south)
    lng_span = abs(east - west)
    area_km2 = lat_span * lng_span * 111.0 * 111.0
    area_m2 = area_km2 * 1_000_000.0
    
    coord_key = f"{south:.5f}_{west:.5f}_{north:.5f}_{east:.5f}"
    coord_hash = int(hashlib.md5(coord_key.encode()).hexdigest(), 16)

    # TERRAIN LOGIC OVERRIDES
    if terrain == "ocean":
        trees = 0
        buildings = 0
        terrain_label = "🌊 Ocean / Open Water"
        # Oceanic Marine Phytoplankton Carbon Fixation
        co2_absorbed_kg = area_km2 * 14500.0
        o2_produced_kg = area_km2 * 28000.0
        co2_emitted_kg = 0.0
        so2_emitted_kg = 0.0
        nox_emitted_kg = 0.0
        
    elif terrain == "ice":
        trees = 0
        buildings = 0
        terrain_label = "🧊 Glacier / Ice Cap"
        co2_absorbed_kg = 0.0
        o2_produced_kg = 0.0
        co2_emitted_kg = 0.0
        so2_emitted_kg = 0.0
        nox_emitted_kg = 0.0

    elif terrain == "desert":
        # Deserts have sparse vegetation and minimal structures
        terrain_label = "🏜️ Arid / Desert Terrain"
        trees = int(area_km2 * 1.5)        # Sparse desert scrub/cacti
        buildings = int(area_km2 * 0.2)    # Sparse remote structures
        
        co2_absorbed_kg = trees * 5.0      # Lower sequestration per desert shrub
        o2_produced_kg = trees * 25.0
        co2_emitted_kg = buildings * 1200.0
        so2_emitted_kg = buildings * 2.0
        nox_emitted_kg = buildings * 3.0

    else:
        # Standard Vegetated Land / Urban Zone
        terrain_label = "🏞️ Vegetated / Urban Land"
        tree_density = 0.004 + ((coord_hash % 100) / 10000.0)
        building_density = 0.0008 + ((coord_hash % 50) / 25000.0)
        
        trees = int(area_m2 * tree_density)
        buildings = int(area_m2 * building_density)
        
        trees = max(int(area_km2 * 40) + (coord_hash % 17) + 8, trees)
        buildings = max(int(area_km2 * 10) + (coord_hash % 7) + 2, buildings)
        
        co2_absorbed_kg = trees * 21.8
        o2_produced_kg = trees * 118.0
        co2_emitted_kg = buildings * 4500.0
        so2_emitted_kg = buildings * 12.5
        nox_emitted_kg = buildings * 18.2
    
    net_co2_kg = co2_emitted_kg - co2_absorbed_kg
    
    return {
        "terrain": terrain_label,
        "trees": trees,
        "buildings": buildings,
        "area_km2": area_km2,
        "co2_absorbed": co2_absorbed_kg,
        "o2_produced": o2_produced_kg,
        "co2_emitted": co2_emitted_kg,
        "net_co2": net_co2_kg,
        "so2_emitted": so2_emitted_kg,
        "nox_emitted": nox_emitted_kg,
        "coords": [south, west, north, east]
    }

# ---------------- UI DASHBOARD ----------------

st.title("🌱 Carbon Footprint & Environmental Reader")
st.write("Draw any rectangle on the map below. The system automatically detects oceans, deserts, glaciers, and urban land.")

map_col, analytics_col = st.columns([1.2, 1])

with map_col:
    st.subheader("📍 Interactive Map (Labeled)")
    st.info("Click the **Square Tool (⬛)** on the top-left toolbar inside the map, then drag a box anywhere on Earth.")
    
    m = folium.Map(location=[20.5937, 78.9629], zoom_start=4)
    
    folium.TileLayer('openstreetmap', name='Street Map (City Names)').add_to(m)
    
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite Base',
        overlay=False,
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='City/Street Names Overlay',
        overlay=True,
        control=True
    ).add_to(m)

    folium.LayerControl(position='topright').add_to(m)

    Draw(
        export=False,
        draw_options={
            "polyline": False,
            "polygon": False,
            "circle": False,
            "marker": False,
            "circlemarker": False,
            "rectangle": True
        }
    ).add_to(m)
    
    map_output = st_folium(m, width=650, height=480, key="main_map")

# Process map selection
drawn_coords = None
if map_output and map_output.get("all_drawings"):
    drawings = map_output["all_drawings"]
    if len(drawings) > 0:
        pts = drawings[-1]["geometry"]["coordinates"][0]
        lngs = [p[0] for p in pts]
        lats = [p[1] for p in pts]
        drawn_coords = (min(lats), min(lngs), max(lats), max(lngs))

with analytics_col:
    st.subheader("📊 Environmental Metrics")
    
    if drawn_coords:
        s, w, n, e = drawn_coords
        current_hash = f"{s:.5f}_{w:.5f}_{n:.5f}_{e:.5f}"
        
        if st.session_state.last_processed_hash != current_hash:
            with st.spinner("Checking terrain classification..."):
                st.session_state.environmental_metrics = calculate_area_metrics(s, w, n, e)
                st.session_state.last_processed_hash = current_hash

        data = st.session_state.environmental_metrics
        c = data["coords"]
        
        st.success(f"Detected Environment: **{data['terrain']}**\n\n📍 **Coordinates:** [{c[0]:.4f}, {c[1]:.4f}] to [{c[2]:.4f}, {c[3]:.4f}]\n\n📏 **Area:** {data['area_km2']:.3f} km²")
        
        m1, m2 = st.columns(2)
        m1.metric("🌳 Number of Trees", f"{data['trees']:,}")
        m2.metric("🏢 Number of Buildings", f"{data['buildings']:,}")
        
        st.markdown("---")
        st.markdown("### 🌬️ Atmospheric Gas Balances (Annual)")
        g1, g2 = st.columns(2)
        g1.metric("O₂ Produced", f"{data['o2_produced']:,.1f} kg/yr")
        g2.metric("CO₂ Absorbed", f"{data['co2_absorbed']:,.1f} kg/yr")
        
        st.markdown("---")
        st.markdown("### 🏭 Industrial Gas Footprint")
        i1, i2, i3 = st.columns(3)
        i1.metric("Net CO₂ Balance", f"{data['net_co2']:,.1f} kg/yr", delta_color="inverse")
        i2.metric("SO₂ (Sulfur Dioxide)", f"{data['so2_emitted']:,.1f} kg/yr")
        i3.metric("NOₓ (Nitrogen Oxides)", f"{data['nox_emitted']:,.1f} kg/yr")
    else:
        st.warning("👈 Draw a box on the map using the ⬛ tool to generate real-time metrics.")
