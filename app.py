
import streamlit as st
import osmnx as ox
import networkx as nx
import folium
from streamlit_folium import folium_static
import google.generativeai as genai
from datetime import datetime
import requests
from scipy.spatial import KDTree
import numpy as np

# Configure APIs
TOMTOM_API_KEY = "GFtqAElXhWwsq6W7oqbF3ffnYdVNk9fp" 
GEMINI_API_KEY = "AIzaSyAyTR7dqVmST6QjRdoXokJ044tcOjYs6BI" 
POLICE_NUMBER = "+1234567890"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Predefined Bengaluru locations
BENGALURU_LOCATIONS = [
    "Koramangala, Bengaluru", "Indiranagar, Bengaluru", "Whitefield, Bengaluru",
    "Jayanagar, Bengaluru", "Malleshwaram, Bengaluru", "Rajajinagar, Bengaluru",
    "Basavanagudi, Bengaluru", "Electronic City, Bengaluru", "HSR Layout, Bengaluru",
    "BTM Layout, Bengaluru", "Marathahalli, Bengaluru", "Yelahanka, Bengaluru",
    "Hebbal, Bengaluru", "KR Puram, Bengaluru", "Banashankari, Bengaluru",
    "Ulsoor, Bengaluru", "Sadashivanagar, Bengaluru", "MG Road, Bengaluru",
    "Vijayanagar, Bengaluru", "JP Nagar, Bengaluru", "Sarjapur, Bengaluru",
    "Bellandur, Bengaluru", "Kengeri, Bengaluru", "Nagarbhavi, Bengaluru",
    "Hennur, Bengaluru", "RT Nagar, Bengaluru", "Frazer Town, Bengaluru",
    "Bommanahalli, Bengaluru", "Domlur, Bengaluru", "Shivaji Nagar, Bengaluru"
]

@st.cache_data(ttl=3600)
def load_city_graph(city_name):
    return ox.graph_from_place(city_name, network_type="drive", simplify=False)

@st.cache_data(ttl=3600)
def cached_geocode(location):
    return ox.geocode(location)

def fetch_traffic_data(bbox):
    url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
    params = {'key': TOMTOM_API_KEY, 'bbox': bbox, 'zoom': 12}
    try:
        response = requests.get(url, params=params)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"Traffic API Error: {str(e)}")
        return None

def process_traffic_data(traffic_json):
    segments = []
    for segment in traffic_json.get('flowSegmentData', []):
        coords = segment['coordinates']['coordinate']
        if len(coords) < 2:
            continue
            
        midpoint = (
            sum(c['latitude'] for c in coords) / len(coords),
            sum(c['longitude'] for c in coords) / len(coords)
        )
        
        segments.append({
            'midpoint': midpoint,
            'speed': segment['currentSpeed'],
            'free_flow': segment['freeFlowSpeed']
        })
    
    points = np.array([(s['midpoint'][0], s['midpoint'][1]) for s in segments])
    return KDTree(points), segments

def update_edge_weights(G, traffic_tree, traffic_segments):
    for u, v, data in G.edges(data=True):
        if 'geometry' in data:
            midpoint = data['geometry'].interpolate(0.5, normalized=True)
            lat, lon = midpoint.y, midpoint.x
        else:
            u_data = G.nodes[u]
            v_data = G.nodes[v]
            lat = (u_data['y'] + v_data['y']) / 2
            lon = (u_data['x'] + v_data['x']) / 2
        
        _, idx = traffic_tree.query([lat, lon])
        segment = traffic_segments[idx]
        
        length = data['length']
        current_speed = max(segment['speed'], 5)
        data['traffic_weight'] = (length / 1000) / (current_speed / 3.6)

def get_traffic_aware_graph(G):
    if G is None:
        st.error("Graph G is not initialized correctly.")
        return None
    
    try:
        bbox = ox.graph_to_gdfs(G, nodes=False, edges=False).total_bounds
        bbox_str = f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}"
        
        traffic_data = fetch_traffic_data(bbox_str)
        if traffic_data:
            traffic_tree, traffic_segments = process_traffic_data(traffic_data)
            update_edge_weights(G, traffic_tree, traffic_segments)
        return G

    except AttributeError as e:
        st.error(f"AttributeError: {e}")
        return None

def optimize_route(G, start_node, end_node):
    for u, v, data in G.edges(data=True):
        data['weight'] = data.get('traffic_weight', (data['length']/1000)/(30/3.6))
    try:
        return nx.shortest_path(G, start_node, end_node, weight='weight')
    except nx.NetworkXNoPath:
        return None

def plot_route_on_map(G, route):
    route_edges = list(zip(route[:-1], route[1:]))
    center_lat = G.nodes[route[0]]['y']
    center_lon = G.nodes[route[0]]['x']
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles='cartodbpositron')
    
    poly_coords = []
    for u, v in route_edges:
        if 'geometry' in G[u][v][0]:
            poly_coords.extend(list(G[u][v][0]['geometry'].coords))
        else:
            poly_coords.extend([(G.nodes[u]['x'], G.nodes[u]['y']), 
                              (G.nodes[v]['x'], G.nodes[v]['y'])])
    
    folium.PolyLine([[y, x] for x, y in poly_coords], weight=5, color='red', opacity=0.8).add_to(m)
    folium.Marker([G.nodes[route[0]]['y'], G.nodes[route[0]]['x']], icon=folium.Icon(color='green')).add_to(m)
    folium.Marker([G.nodes[route[-1]]['y'], G.nodes[route[-1]]['x']], icon=folium.Icon(color='red')).add_to(m)
    return m

def main():
    st.title("🚦 Bengaluru Smart Traffic Router")
    
    G = load_city_graph("Bengaluru, India")
    G = get_traffic_aware_graph(G)
    
    start = st.selectbox("From", BENGALURU_LOCATIONS, index=1)
    end = st.selectbox("To", BENGALURU_LOCATIONS, index=0)
    
    if st.button("Calculate Optimal Route"):
        start_coords = cached_geocode(start)
        end_coords = cached_geocode(end)
        start_node = ox.distance.nearest_nodes(G, start_coords[1], start_coords[0])
        end_node = ox.distance.nearest_nodes(G, end_coords[1], end_coords[0])
        route = optimize_route(G, start_node, end_node)
        
        if route:
            folium_static(plot_route_on_map(G, route))
        else:
            st.error("No viable route found")

if __name__ == "__main__":
    main()

