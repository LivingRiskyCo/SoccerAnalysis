"""
Quick utility to apply player assignments from JSON or player_names.json to a CSV file.

This is useful if you made assignments in Review & Assignment before the "Save to CSV" 
button was available, and need to apply those assignments to your CSV.
"""

import pandas as pd
import json
import os
import sys
from tkinter import filedialog, messagebox
import tkinter as tk

def apply_assignments_to_csv(csv_file, assignments_source, output_file=None):
    """
    Apply player assignments to a CSV file.
    
    Args:
        csv_file: Path to CSV file
        assignments_source: Either:
            - Path to JSON file with assignments (from Export Assignments)
            - Path to player_names.json
            - Dictionary of {track_id: player_name}
        output_file: Output CSV path (default: adds _tagged suffix)
    
    Returns:
        Path to output file
    """
    # Load CSV
    df = pd.read_csv(csv_file)
    
    # Get track ID column
    track_id_col = None
    for col in ['track_id', 'player_id', 'id']:
        if col in df.columns:
            track_id_col = col
            break
    
    if track_id_col is None:
        raise ValueError("CSV file must contain 'track_id', 'player_id', or 'id' column")
    
    # Load assignments
    if isinstance(assignments_source, dict):
        assignments = assignments_source
    elif isinstance(assignments_source, str):
        if os.path.exists(assignments_source):
            with open(assignments_source, 'r') as f:
                data = json.load(f)
                # Handle different JSON formats
                if isinstance(data, dict):
                    # Could be direct assignments or player_names.json format
                    if all(isinstance(k, (int, str)) and isinstance(v, str) for k, v in data.items()):
                        # Direct assignments format
                        assignments = {int(k): str(v) for k, v in data.items()}
                    else:
                        # Might be anchor frames or other format
                        assignments = {}
                else:
                    assignments = {}
        else:
            raise FileNotFoundError(f"Assignments file not found: {assignments_source}")
    else:
        raise ValueError("assignments_source must be a dict or file path")
    
    if not assignments:
        raise ValueError("No assignments found in source")
    
    # Create or update player_name column
    if 'player_name' not in df.columns:
        df['player_name'] = None
    
    # Apply assignments
    updated_count = 0
    for track_id, player_name in assignments.items():
        try:
            track_id_int = int(track_id)
            mask = df[track_id_col] == track_id_int
            rows_updated = mask.sum()
            if rows_updated > 0:
                df.loc[mask, 'player_name'] = str(player_name)
                updated_count += rows_updated
        except (ValueError, TypeError) as e:
            print(f"Warning: Could not process track_id {track_id}: {e}")
            continue
    
    # Determine output file
    if output_file is None:
        base_name = os.path.splitext(csv_file)[0]
        output_file = f"{base_name}_tagged.csv"
    
    # Save
    df.to_csv(output_file, index=False)
    
    return output_file, len(assignments), updated_count


def main():
    """Interactive GUI version"""
    root = tk.Tk()
    root.withdraw()  # Hide main window
    
    print("=" * 60)
    print("Apply Player Assignments to CSV")
    print("=" * 60)
    print()
    
    # Select CSV file
    print("Step 1: Select the CSV file to update...")
    csv_file = filedialog.askopenfilename(
        title="Select CSV File to Update",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    
    if not csv_file:
        print("Cancelled.")
        return
    
    print(f"✓ Selected CSV: {os.path.basename(csv_file)}")
    print()
    
    # Select assignments source
    print("Step 2: Select the assignments file...")
    print("  (This can be a JSON file from 'Export Assignments' or player_names.json)")
    assignments_file = filedialog.askopenfilename(
        title="Select Assignments File (JSON)",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )
    
    if not assignments_file:
        print("Cancelled.")
        return
    
    print(f"✓ Selected assignments: {os.path.basename(assignments_file)}")
    print()
    
    # Try to load from player_names.json if the selected file doesn't work
    assignments_source = assignments_file
    
    # Also check for player_names.json in current directory
    if not os.path.exists(assignments_file):
        if os.path.exists("player_names.json"):
            print("⚠ Selected file not found, trying player_names.json...")
            assignments_source = "player_names.json"
    
    try:
        # Apply assignments
        print("Step 3: Applying assignments...")
        output_file, tracks_updated, rows_updated = apply_assignments_to_csv(
            csv_file, assignments_source
        )
        
        print()
        print("=" * 60)
        print("✓ SUCCESS!")
        print("=" * 60)
        print(f"Output file: {output_file}")
        print(f"Tracks updated: {tracks_updated}")
        print(f"Total rows updated: {rows_updated}")
        print()
        print("You can now load this CSV in Consolidate IDs to merge")
        print("tracks with the same player name.")
        print("=" * 60)
        
        messagebox.showinfo("Success",
            f"Applied {tracks_updated} assignments to CSV!\n\n"
            f"Output: {os.path.basename(output_file)}\n"
            f"Rows updated: {rows_updated}\n\n"
            f"You can now load this CSV in Consolidate IDs.")
        
    except Exception as e:
        error_msg = f"Error: {e}"
        print()
        print("=" * 60)
        print("✗ ERROR")
        print("=" * 60)
        print(error_msg)
        print("=" * 60)
        messagebox.showerror("Error", error_msg)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

