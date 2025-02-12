import streamlit as st
import osmnx as ox
import networkx as nx
import folium
from streamlit_folium import folium_static
import google.generativeai as genai
from datetime import datetime

POLICE_NUMBER = "+919380460725"  # Replace with your actual police number

# Configure Gemini AI
GEMINI_API_KEY = "AIzaSyCc-f4VEvlTR8zuQKqa-tNiXbva9AF3RAU"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

def send_police_alert(start, end, route_length):
    current_time = datetime.now().strftime("%H:%M")
    message = f"""
    🚨 Emergency Vehicle Alert 🚨
    From: {start}
    To: {end}
    Time: {current_time}
    Route Length: {route_length} nodes
    Please ensure clear traffic conditions.
    """
    try:
        # Simulated send - replace with actual SMS API code
        st.success(f"Alert sent to traffic police at {POLICE_NUMBER}")
        st.markdown(f"**Message Content:**\n{message}")
        return True
    except Exception as e:
        st.error(f"Alert failed: {str(e)}")
        return False

# Predefined Bengaluru locations
BENGALURU_LOCATIONS = [
    "Koramangala, Bengaluru",
    "Indiranagar, Bengaluru",
    "Whitefield, Bengaluru",
    # ... (rest of locations remain the same)
    "Shivaji Nagar, Bengaluru"
]

# Cache the graph loading with simplified=False
@st.cache_data(ttl=3600)
def load_city_graph(city_name):
    return ox.graph_from_place(city_name, network_type="drive", simplify=False)

@st.cache_data(ttl=3600)
def cached_geocode(location):
    return ox.geocode(location)

def get_traffic_weight(road_type, current_hour):
    base_weights = {
        'motorway': 1.0,
        'trunk': 1.2,
        'primary': 1.3,
        'secondary': 1.4,
        'tertiary': 1.5,
        'residential': 1.6,
        'unclassified': 1.8
    }
    
    rush_hours = [8, 9, 17, 18, 19]
    time_multiplier = 1.5 if current_hour in rush_hours else 1.0
    road_type = str(road_type).lower() if road_type else 'unclassified'
    return next((w * time_multiplier for k, w in base_weights.items() if k in road_type), 1.8)

def plot_route_on_map(G, route):
    route_edges = list(zip(route[:-1], route[1:]))
    
    center_lat = G.nodes[route[0]]['y']
    center_lon = G.nodes[route[0]]['x']
    m = folium.Map(location=[center_lat, center_lon], 
                  zoom_start=13,
                  tiles='cartodbpositron')
    
    coordinates = []
    for u, v in route_edges:
        edge_coords = []
        try:
            data = G.get_edge_data(u, v)[0]
            if 'geometry' in data:
                coords = list(data['geometry'].coords)
                edge_coords.extend(coords)
            else:
                start_coords = (G.nodes[u]['x'], G.nodes[u]['y'])
                end_coords = (G.nodes[v]['x'], G.nodes[v]['y'])
                edge_coords.extend([start_coords, end_coords])
        except (KeyError, IndexError):
            continue
            
        coordinates.extend(edge_coords)
    
    folium.PolyLine(
        locations=[[lat, lon] for lon, lat in coordinates],
        weight=5,
        color='red',
        opacity=0.8
    ).add_to(m)
    
    folium.Marker(
        [G.nodes[route[0]]['y'], G.nodes[route[0]]['x']],
        popup='Start',
        icon=folium.Icon(color='green')
    ).add_to(m)
    
    folium.Marker(
        [G.nodes[route[-1]]['y'], G.nodes[route[-1]]['x']],
        popup='End',
        icon=folium.Icon(color='red')
    ).add_to(m)
    
    return m

def optimize_route(G, start_node, end_node):
    current_hour = datetime.now().hour
    
    for u, v, k, data in G.edges(data=True, keys=True):
        road_type = data.get('highway', 'unclassified')
        data['weight'] = get_traffic_weight(road_type, current_hour)
    
    try:
        return nx.shortest_path(G, start_node, end_node, weight='weight')
    except nx.NetworkXNoPath:
        return None

def get_route_analysis(start, end, route_exists=True):
    if not route_exists:
        return "Unable to analyze route as no valid path was found."
    
    prompt = f"""
    Analyze the optimal driving route from {start} to {end} in Bengaluru.
    Consider:
    - Typical traffic patterns
    - Road types and capacity
    - Time of day impacts
    Provide a brief 2-3 sentence analysis.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Route analysis unavailable: {str(e)}"

def main():
    st.title("🚗 Smart Traffic Router - Bengaluru")
    st.caption("Optimized routes considering traffic patterns and road types")
    
    city = "Bengaluru, India"
    
    with st.spinner("Loading city map data..."):
        try:
            G = load_city_graph(city)
        except Exception as e:
            st.error(f"Error loading map data: {str(e)}")
            return

    # Location input section
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Start Location")
        start_method = st.radio("Input method:", ["Select", "Custom"], key="start")
        if start_method == "Select":
            start = st.selectbox("From predefined list", BENGALURU_LOCATIONS, index=1)
        else:
            start = st.text_input("Enter custom address", "Indiranagar, Bengaluru")
    
    with col2:
        st.subheader("End Location")
        end_method = st.radio("Input method:", ["Select", "Custom"], key="end")
        if end_method == "Select":
            end = st.selectbox("From predefined list", BENGALURU_LOCATIONS, index=0)
        else:
            end = st.text_input("Enter custom address", "Koramangala, Bengaluru")

    if st.button("Find Optimal Route", type="primary"):
        with st.spinner("Calculating your route..."):
            try:
                start_coords = cached_geocode(start)
                end_coords = cached_geocode(end)
                start_node = ox.distance.nearest_nodes(G, start_coords[1], start_coords[0])
                end_node = ox.distance.nearest_nodes(G, end_coords[1], end_coords[0])
                route = optimize_route(G, start_node, end_node)
                
                if route:
                    m = plot_route_on_map(G, route)
                    folium_static(m)
                    
                    with st.spinner("Analyzing route..."):
                        analysis = get_route_analysis(start, end)
                        st.info("🤖 Route Analysis: " + analysis)
                    
                    st.success("✅ Route found successfully!")

                    # Add police alert section
                    st.divider()
                    st.subheader("🚨 Emergency Traffic Alert")
                    
                    if st.button("Notify Traffic Police"):
                        with st.spinner("Sending emergency alert..."):
                            route_length = len(route)
                            alert_sent = send_police_alert(start, end, route_length)
                            
                            if alert_sent:
                                st.markdown(f"""
                                **Alert Details:**
                                - Recipient: `{POLICE_NUMBER}`
                                - Route: {start} → {end}
                                - Sent at: {datetime.now().strftime("%H:%M:%S")}
                                """)
                else:
                    st.error("❌ No valid route found between these locations")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.info("💡 Tip: Please ensure valid locations within Bengaluru")

if __name__ == "__main__":
    main()
