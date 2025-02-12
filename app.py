import streamlit as st
import osmnx as ox
import networkx as nx
import folium
from streamlit_folium import folium_static
import google.generativeai as genai
from datetime import datetime

# Configure Gemini AI
GEMINI_API_KEY = "AIzaSyCc-f4VEvlTR8zuQKqa-tNiXbva9AF3RAU"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# List of predefined Bengaluru locations
BENGALURU_LOCATIONS = [
    "Koramangala, Bengaluru",
    "Indiranagar, Bengaluru",
    "Whitefield, Bengaluru",
    "Jayanagar, Bengaluru",
    "Malleshwaram, Bengaluru",
    "Rajajinagar, Bengaluru",
    "Basavanagudi, Bengaluru",
    "Electronic City, Bengaluru",
    "HSR Layout, Bengaluru",
    "BTM Layout, Bengaluru",
    "Marathahalli, Bengaluru",
    "Yelahanka, Bengaluru",
    "Hebbal, Bengaluru",
    "KR Puram, Bengaluru",
    "Banashankari, Bengaluru",
    "Ulsoor, Bengaluru",
    "Sadashivanagar, Bengaluru",
    "MG Road, Bengaluru",
    "Vijayanagar, Bengaluru",
    "JP Nagar, Bengaluru",
    "Sarjapur, Bengaluru",
    "Bellandur, Bengaluru",
    "Kengeri, Bengaluru",
    "Nagarbhavi, Bengaluru",
    "Hennur, Bengaluru",
    "RT Nagar, Bengaluru",
    "Frazer Town, Bengaluru",
    "Bommanahalli, Bengaluru",
    "Domlur, Bengaluru",
    "Shivaji Nagar, Bengaluru"
]

# Cache the graph loading
@st.cache_data(ttl=3600)
def load_city_graph(city_name):
    return ox.graph_from_place(city_name, network_type="drive", simplify=True)

# Cache geocoding results
@st.cache_data(ttl=3600)
def cached_geocode(location):
    return ox.geocode(location)

def get_traffic_weight(road_type, current_hour):
    """
    Determine traffic weight based on road type and time of day
    """
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
    base_weight = next((w for k, w in base_weights.items() if k in road_type), 1.8)
    
    return base_weight * time_multiplier

def plot_route_on_map(G, route):
    """
    Create a folium map with the route plotted
    """
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
                start_coords = [G.nodes[u]['y'], G.nodes[u]['x']]
                end_coords = [G.nodes[v]['y'], G.nodes[v]['x']]
                edge_coords.extend([start_coords, end_coords])
        except:
            continue
            
        coordinates.extend(edge_coords)
    
    # Add the route line
    folium.PolyLine(
        locations=[[lat, lon] for lon, lat in coordinates],
        weight=5,
        color='red',
        opacity=0.8
    ).add_to(m)
    
    # Add markers for start and end points
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
    """
    Optimize route considering road types and time of day
    """
    current_hour = datetime.now().hour
    
    for u, v, k, data in G.edges(data=True, keys=True):
        road_type = data.get('highway', 'unclassified')
        data['weight'] = get_traffic_weight(road_type, current_hour)
    
    try:
        return nx.shortest_path(G, start_node, end_node, weight='weight')
    except nx.NetworkXNoPath:
        return None

def get_route_analysis(start, end, route_exists=True):
    """
    Get AI analysis of the route
    """
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
    
    # Load graph with progress indicator
    with st.spinner("Loading city map data..."):
        try:
            G = load_city_graph(city)
        except Exception as e:
            st.error(f"Error loading map data: {str(e)}")
            return

    # User inputs with dropdowns
    col1, col2 = st.columns(2)
    with col1:
        start = st.selectbox(
            "Start location",
            options=BENGALURU_LOCATIONS,
            index=1  # Default to Indiranagar
        )
    with col2:
        end = st.selectbox(
            "End location",
            options=BENGALURU_LOCATIONS,
            index=0  # Default to Koramangala
        )

    if st.button("Find Optimal Route", type="primary"):
        with st.spinner("Calculating your route..."):
            try:
                # Get coordinates
                start_coords = cached_geocode(start)
                end_coords = cached_geocode(end)
                
                # Find nearest nodes
                start_node = ox.distance.nearest_nodes(G, start_coords[1], start_coords[0])
                end_node = ox.distance.nearest_nodes(G, end_coords[1], end_coords[0])
                
                # Calculate route
                route = optimize_route(G, start_node, end_node)
                
                if route:
                    # Create and display map
                    m = plot_route_on_map(G, route)
                    folium_static(m)
                    
                    # Get AI analysis
                    with st.spinner("Analyzing route..."):
                        analysis = get_route_analysis(start, end)
                        st.info("🤖 Route Analysis: " + analysis)
                        
                    # Display additional route information
                    st.success("✅ Route found successfully!")
                    
                else:
                    st.error("❌ No valid route found between these locations")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.info("💡 Tip: Please ensure you've entered valid locations within Bengaluru")

if __name__ == "__main__":
    main()
