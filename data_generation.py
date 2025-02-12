import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def generate_synthetic_data(num_entries=10000):
    # Set random seed for reproducibility
    np.random.seed(42)
    
    # Generate timestamps over a 30-day period
    base_timestamp = datetime(2024, 1, 1)
    timestamps = [base_timestamp + timedelta(minutes=random.randint(0, 43200)) 
                 for _ in range(num_entries)]
    timestamps.sort()
    
    # Define major cities in India with their lat/long
    cities = {
        'Delhi': (28.6139, 77.2090),
        'Mumbai': (19.0760, 72.8777),
        'Bangalore': (12.9716, 77.5946),
        'Chennai': (13.0827, 80.2707),
        'Kolkata': (22.5726, 88.3639)
    }
    
    # Generate location data
    locations = []
    for _ in range(num_entries):
        city = random.choice(list(cities.keys()))
        base_lat, base_long = cities[city]
        # Add small random variations to create different locations within each city
        lat = base_lat + np.random.normal(0, 0.02)
        long = base_long + np.random.normal(0, 0.02)
        locations.append((lat, long))
    
    # Generate road segment IDs (format: CITY_XXXX)
    road_segments = [f"{random.choice(list(cities.keys()))}_{random.randint(1000, 9999)}" 
                    for _ in range(num_entries)]
    
    # Generate traffic volume (higher during peak hours)
    def get_traffic_volume(hour):
        if 8 <= hour <= 10 or 17 <= hour <= 19:  # Peak hours
            return int(np.random.normal(800, 200))
        elif 23 <= hour <= 4:  # Night hours
            return int(np.random.normal(100, 50))
        else:  # Normal hours
            return int(np.random.normal(400, 150))
    
    traffic_volumes = [max(50, get_traffic_volume(t.hour)) for t in timestamps]
    
    # Generate average vehicle speed (inversely related to traffic volume)
    speeds = [max(5, min(80, np.random.normal(60 - (vol/800)*30, 10))) 
              for vol in traffic_volumes]
    
    # Incident types and their probabilities
    incident_types = [
        np.random.choice(['none', 'accident', 'construction', 'road_closure', 'heavy_traffic'],
                        p=[0.80, 0.05, 0.08, 0.02, 0.05])
        for _ in range(num_entries)
    ]
    
    # Weather conditions based on time of year
    weather_conditions = [
        np.random.choice(['clear', 'cloudy', 'rain', 'fog', 'haze'],
                        p=[0.4, 0.3, 0.1, 0.1, 0.1])
        for _ in range(num_entries)
    ]
    
    # Generate AQI (worse during peak traffic and certain weather conditions)
    def get_aqi(traffic_vol, weather, hour):
        base_aqi = np.random.normal(150, 30)  # Base AQI
        traffic_factor = traffic_vol / 400  # Traffic impact
        weather_factor = 1.2 if weather in ['fog', 'haze'] else 1.0
        time_factor = 1.2 if (8 <= hour <= 10 or 17 <= hour <= 19) else 1.0
        return int(max(50, min(500, base_aqi * traffic_factor * weather_factor * time_factor)))
    
    aqi_values = [get_aqi(vol, weather, t.hour) 
                  for vol, weather, t in zip(traffic_volumes, weather_conditions, timestamps)]
    
    # Create DataFrame
    df = pd.DataFrame({
        'timestamp': timestamps,
        'latitude': [loc[0] for loc in locations],
        'longitude': [loc[1] for loc in locations],
        'road_segment_id': road_segments,
        'traffic_volume': traffic_volumes,
        'average_vehicle_speed': speeds,
        'incident_type': incident_types,
        'weather_conditions': weather_conditions,
        'air_quality_index': aqi_values,
        'day_of_week': [t.strftime('%A') for t in timestamps],
        'time_of_day': [t.strftime('%H:%M:%S') for t in timestamps]
    })
    
    return df

# Generate the data
df = generate_synthetic_data(10000)

# Add some data quality checks
assert len(df) == 10000, "Data length mismatch"
assert not df.isnull().any().any(), "Missing values found"
assert all(50 <= aqi <= 500 for aqi in df['air_quality_index']), "AQI out of range"
assert all(5 <= speed <= 80 for speed in df['average_vehicle_speed']), "Speed out of range"

# Save to CSV
df.to_csv('synthetic_traffic_data.csv', index=False)

# Display first few rows and basic statistics
print("\nFirst few rows of the generated data:")
print(df.head())
print("\nBasic statistics:")
print(df.describe())