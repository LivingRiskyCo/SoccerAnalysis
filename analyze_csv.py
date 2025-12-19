"""
CSV Analysis Script
Analyze tracking data from soccer analysis CSV files
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import argparse
import os

def calculate_distance(x1, y1, x2, y2):
    """Calculate Euclidean distance between two points"""
    # Convert to numeric types to handle string inputs
    x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
    return np.sqrt((x2 - x1)**2 + (y2 - y1)**2)

def analyze_tracking_data(csv_file):
    """
    Analyze tracking data from CSV file.
    Generates statistics and visualizations.
    """
    print(f"Loading data from: {csv_file}")
    df = pd.read_csv(csv_file)
    
    # Convert coordinate columns to numeric, handling any string values
    numeric_columns = ['player_x', 'player_y', 'ball_x', 'ball_y', 'frame', 'player_id']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    print(f"\nTotal frames: {len(df)}")
    print(f"Unique players detected: {df['player_id'].nunique()}")
    print(f"Ball detected in: {df['ball_detected'].sum()} frames")
    
    # Calculate distance traveled per player
    print("\n" + "="*60)
    print("Distance Traveled Analysis")
    print("="*60)
    
    player_distances = {}
    for player_id in df['player_id'].dropna().unique():
        player_data = df[df['player_id'] == player_id].sort_values('frame')
        if len(player_data) < 2:
            continue
        
        # Calculate distance between consecutive frames
        distances = []
        for i in range(1, len(player_data)):
            x1, y1 = player_data.iloc[i-1]['player_x'], player_data.iloc[i-1]['player_y']
            x2, y2 = player_data.iloc[i]['player_x'], player_data.iloc[i]['player_y']
            if not (pd.isna(x1) or pd.isna(y1) or pd.isna(x2) or pd.isna(y2)):
                dist = calculate_distance(x1, y1, x2, y2)
                distances.append(dist)
        
        total_distance = sum(distances)
        player_distances[player_id] = total_distance
        print(f"Player #{int(player_id)}: {total_distance:.2f} pixels traveled")
    
    # Possession analysis
    print("\n" + "="*60)
    print("Possession Analysis")
    print("="*60)
    
    possession_data = df[df['possession_player_id'].notna()]
    if len(possession_data) > 0:
        possession_counts = possession_data['possession_player_id'].value_counts()
        print("\nPossession time (frames):")
        for player_id, count in possession_counts.items():
            percentage = (count / len(possession_data)) * 100
            print(f"Player #{int(player_id)}: {count} frames ({percentage:.1f}%)")
    
    # Ball tracking analysis
    print("\n" + "="*60)
    print("Ball Tracking Analysis")
    print("="*60)
    
    ball_data = df[df['ball_detected'] == True]
    if len(ball_data) > 0:
        print(f"Ball detected in {len(ball_data)} frames ({len(ball_data)/len(df)*100:.1f}%)")
        
        # Calculate ball movement distance
        ball_distances = []
        for i in range(1, len(ball_data)):
            x1, y1 = ball_data.iloc[i-1]['ball_x'], ball_data.iloc[i-1]['ball_y']
            x2, y2 = ball_data.iloc[i]['ball_x'], ball_data.iloc[i]['ball_y']
            if not (pd.isna(x1) or pd.isna(y1) or pd.isna(x2) or pd.isna(y2)):
                dist = calculate_distance(x1, y1, x2, y2)
                ball_distances.append(dist)
        
        if ball_distances:
            total_ball_distance = sum(ball_distances)
            print(f"Total ball movement: {total_ball_distance:.2f} pixels")
    
    # Generate visualizations
    base_name = os.path.splitext(csv_file)[0]
    
    # Distance traveled chart
    if player_distances:
        plt.figure(figsize=(10, 6))
        players = [f"Player #{int(p)}" for p in player_distances.keys()]
        distances = list(player_distances.values())
        plt.bar(players, distances)
        plt.xlabel('Player')
        plt.ylabel('Distance Traveled (pixels)')
        plt.title('Distance Traveled by Player')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f'{base_name}_distance_chart.png', dpi=150)
        print(f"\nDistance chart saved: {base_name}_distance_chart.png")
        plt.close()
    
    # Possession chart
    if len(possession_data) > 0:
        plt.figure(figsize=(10, 6))
        possession_counts = possession_data['possession_player_id'].value_counts()
        players = [f"Player #{int(p)}" for p in possession_counts.index]
        counts = possession_counts.values
        plt.bar(players, counts)
        plt.xlabel('Player')
        plt.ylabel('Possession Time (frames)')
        plt.title('Possession Time by Player')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f'{base_name}_possession_chart.png', dpi=150)
        print(f"Possession chart saved: {base_name}_possession_chart.png")
        plt.close()
    
    print("\n" + "="*60)
    print("Analysis complete!")
    print("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze tracking data from CSV file")
    parser.add_argument("csv_file", help="Path to CSV tracking data file")
    args = parser.parse_args()
    
    if not os.path.exists(args.csv_file):
        print(f"Error: File not found: {args.csv_file}")
        sys.exit(1)
    
    analyze_tracking_data(args.csv_file)


