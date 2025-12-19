"""
Gaussian Smoothed Interpolation (GSI) for track smoothing
Based on BoxMOT's GSI implementation, adapted for real-time and post-processing use
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from pathlib import Path
import pandas as pd

try:
    from sklearn.gaussian_process import GaussianProcessRegressor as GPR
    from sklearn.gaussian_process.kernels import RBF
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠ sklearn not available. Install with: pip install scikit-learn")
    print("  GSI smoothing will be disabled.")


def linear_interpolation(input_: np.ndarray, interval: int) -> np.ndarray:
    """
    Perform linear interpolation on the input data to fill in missing frames.
    
    Args:
        input_: Input array with shape (n, m) where columns are [frame, track_id, x, y, w, h, ...]
        interval: The maximum frame gap to interpolate.
    
    Returns:
        Interpolated array with additional rows for the interpolated frames.
    """
    if len(input_) == 0:
        return input_
    
    # Sort by track_id, then frame
    input_ = input_[np.lexsort((input_[:, 0], input_[:, 1]))]
    output_ = input_.copy()
    
    id_pre, f_pre, row_pre = -1, -1, np.zeros((input_.shape[1],))
    for row in input_:
        f_curr, id_curr = int(row[0]), int(row[1])
        if id_curr == id_pre and f_pre + 1 < f_curr < f_pre + interval:
            # Interpolate missing frames
            for i, f in enumerate(range(f_pre + 1, f_curr), start=1):
                step = (row - row_pre) / (f_curr - f_pre) * i
                row_new = row_pre + step
                row_new[0] = f  # Ensure frame number is integer
                row_new[1] = id_curr  # Ensure track_id is correct
                output_ = np.vstack((output_, row_new))
        id_pre, row_pre, f_pre = id_curr, row, f_curr
    
    # Sort again after interpolation
    return output_[np.lexsort((output_[:, 0], output_[:, 1]))]


def gaussian_smooth(input_: np.ndarray, tau: float) -> np.ndarray:
    """
    Apply Gaussian smoothing to the input data.
    
    Args:
        input_: Input array with shape (n, m) where columns are [frame, track_id, x, y, w, h, ...]
        tau: Time constant for Gaussian smoothing (higher = more smoothing).
    
    Returns:
        Smoothed array with the same shape as the input.
    """
    if not SKLEARN_AVAILABLE or len(input_) == 0:
        return input_
    
    output_ = []
    ids = set(int(id_) for id_ in input_[:, 1])
    
    for id_ in ids:
        tracks = input_[input_[:, 1] == id_]
        if len(tracks) < 2:
            # Not enough data to smooth
            output_.extend(tracks.tolist())
            continue
        
        # Adaptive length scale based on track length
        len_scale = np.clip(tau * np.log(tau ** 3 / len(tracks)), tau ** -1, tau ** 2)
        t = tracks[:, 0].reshape(-1, 1)  # Frame numbers
        
        # Smooth x, y, w, h (columns 2-5)
        smoothed_data = []
        for i in range(2, min(6, tracks.shape[1])):
            data = tracks[:, i].reshape(-1, 1)
            try:
                gpr = GPR(RBF(len_scale, 'fixed'))
                gpr.fit(t, data)
                smoothed = gpr.predict(t)
                # gpr.predict may return (y_mean, y_std) tuple or an array;
                # handle both cases:
                if isinstance(smoothed, tuple):
                    smoothed = smoothed[0]
                smoothed = np.asarray(smoothed).reshape(-1, 1)
                smoothed_data.append(smoothed)
            except Exception as e:
                # If smoothing fails, use original data
                smoothed_data.append(data)
        
        # Reconstruct rows with smoothed coordinates
        # Only keep core columns: [frame, track_id, x, y, w, h]
        for j in range(len(t)):
            row = [float(t[j, 0]), int(id_)]
            # Add smoothed x, y, w, h
            for data in smoothed_data:
                row.append(float(data[j, 0]))
            # Ensure we have exactly 6 columns (frame, track_id, x, y, w, h)
            while len(row) < 6:
                # Fill missing w, h with defaults if needed
                if len(row) == 4:
                    row.append(40.0)  # w
                if len(row) == 5:
                    row.append(80.0)  # h
            output_.append(row[:6])  # Only keep first 6 columns
    
    return np.array(output_, dtype=float)


def apply_gsi_to_tracks(track_history: Dict[int, List[Tuple[int, float, float, float, float]]], 
                       interval: int = 20, tau: float = 10.0) -> Dict[int, List[Tuple[int, float, float, float, float]]]:
    """
    Apply GSI to track history dictionary.
    
    Args:
        track_history: Dict mapping track_id to list of (frame, x, y, w, h) tuples
        interval: Maximum frame gap to interpolate
        tau: Time constant for Gaussian smoothing
    
    Returns:
        Smoothed track history dictionary
    """
    if not SKLEARN_AVAILABLE or len(track_history) == 0:
        return track_history
    
    # Convert to numpy array format: [frame, track_id, x, y, w, h]
    data_list = []
    for track_id, positions in track_history.items():
        for frame, x, y, w, h in positions:
            data_list.append([frame, track_id, x, y, w, h])
    
    if len(data_list) == 0:
        return track_history
    
    input_array = np.array(data_list)
    
    # Apply linear interpolation
    interpolated = linear_interpolation(input_array, interval)
    
    # Apply Gaussian smoothing
    smoothed = gaussian_smooth(interpolated, tau)
    
    # Convert back to dictionary format
    smoothed_history = defaultdict(list)
    for row in smoothed:
        frame, track_id = int(row[0]), int(row[1])
        x, y, w, h = row[2], row[3], row[4], row[5]
        smoothed_history[track_id].append((frame, x, y, w, h))
    
    # Sort by frame for each track
    for track_id in smoothed_history:
        smoothed_history[track_id].sort(key=lambda x: x[0])
    
    return dict(smoothed_history)


def apply_gsi_to_csv(csv_path: str, output_path: Optional[str] = None, 
                     interval: int = 20, tau: float = 10.0) -> pd.DataFrame:
    """
    Apply GSI to tracking CSV file.
    
    Args:
        csv_path: Path to input CSV file with columns: frame_num, track_id, player_x, player_y, ...
        output_path: Optional path to save smoothed CSV (if None, overwrites input)
        interval: Maximum frame gap to interpolate
        tau: Time constant for Gaussian smoothing
    
    Returns:
        DataFrame with smoothed tracks
    """
    if not SKLEARN_AVAILABLE:
        print("⚠ sklearn not available. Cannot apply GSI.")
        return pd.read_csv(csv_path)
    
    # Load CSV (skip comment lines starting with '#')
    df = pd.read_csv(csv_path, comment='#')
    
    if len(df) == 0:
        return df
    
    # Find column names (check for common variations)
    # Try frame column
    if 'frame_num' in df.columns:
        frame_col = 'frame_num'
    elif 'frame' in df.columns:
        frame_col = 'frame'
    else:
        raise ValueError(f"Could not find frame column. Available: {list(df.columns)}")
    
    # Try track_id column (check player_id first since that's what the CSV uses)
    if 'player_id' in df.columns:
        track_col = 'player_id'
    elif 'track_id' in df.columns:
        track_col = 'track_id'
    elif 'tracker_id' in df.columns:
        track_col = 'tracker_id'
    elif 'id' in df.columns:
        track_col = 'id'
    else:
        raise ValueError(f"Could not find track_id column. Available: {list(df.columns)}")
    
    # Try x column
    if 'player_x' in df.columns:
        x_col = 'player_x'
    elif 'player_x_ft' in df.columns:
        x_col = 'player_x_ft'
    elif 'x' in df.columns:
        x_col = 'x'
    elif 'center_x' in df.columns:
        x_col = 'center_x'
    else:
        raise ValueError(f"Could not find x coordinate column. Available: {list(df.columns)}")
    
    # Try y column
    if 'player_y' in df.columns:
        y_col = 'player_y'
    elif 'player_y_ft' in df.columns:
        y_col = 'player_y_ft'
    elif 'y' in df.columns:
        y_col = 'y'
    elif 'center_y' in df.columns:
        y_col = 'center_y'
    else:
        raise ValueError(f"Could not find y coordinate column. Available: {list(df.columns)}")
    
    # Convert to numpy array format: [frame, track_id, x, y, w, h]
    # For CSV, we don't have w, h, so we'll use a default size or estimate
    data_list = []
    for _, row in df.iterrows():
        frame = int(row[frame_col])
        track_id = int(row[track_col])
        x = float(row[x_col])
        y_val = row[y_col]
        y = float(y_val) if y_val is not None else 0.0
        # Estimate w, h from bounding box if available, otherwise use defaults
        if 'width' in df.columns:
            width_val = row['width']
            w = float(width_val) if width_val is not None else 40.0
        else:
            w = 40.0
        if 'height' in df.columns:
            height_val = row['height']
            h = float(height_val) if height_val is not None else 80.0
        else:
            h = 80.0
        data_list.append([frame, track_id, x, y, w, h])

    if len(data_list) == 0:
        return df

    input_array = np.array(data_list)

    interpolated = linear_interpolation(input_array, interval)
    
    # Apply Gaussian smoothing
    smoothed = gaussian_smooth(interpolated, tau)
    
    # Convert back to DataFrame - preserve all original columns
    # Map smoothed coordinates back to DataFrame by (frame, track_id) key
    smoothed_dict = {}
    for row in smoothed:
        frame, track_id = int(row[0]), int(row[1])
        x, y = row[2], row[3]
        smoothed_dict[(frame, track_id)] = (x, y)
    
    # Create new DataFrame with smoothed coordinates
    smoothed_rows = []
    for idx, row in df.iterrows():
        frame = int(row[frame_col])
        track_id = int(row[track_col])
        
        # Create a copy of the row
        new_row = row.copy()
        
        # Update with smoothed coordinates if available
        if (frame, track_id) in smoothed_dict:
            x, y = smoothed_dict[(frame, track_id)]
            new_row[x_col] = x
            new_row[y_col] = y
        
        smoothed_rows.append(new_row)
    
    smoothed_df = pd.DataFrame(smoothed_rows)
    
    # Save if output path specified
    if output_path:
        smoothed_df.to_csv(output_path, index=False)
        print(f"✓ GSI smoothed CSV saved to: {output_path}")
    elif output_path is None:
        # Overwrite original
        smoothed_df.to_csv(csv_path, index=False)
        print(f"✓ GSI smoothed CSV saved to: {csv_path}")
    
    return smoothed_df


def apply_gsi_realtime(track_positions: Dict[int, Tuple[float, float]], 
                      track_history: Dict[int, List[Tuple[int, float, float]]],
                      current_frame: int, tau: float = 10.0) -> Dict[int, Tuple[float, float]]:
    """
    Apply real-time GSI smoothing to current track positions using history.
    
    Args:
        track_positions: Current frame positions {track_id: (x, y)}
        track_history: History of positions {track_id: [(frame, x, y), ...]}
        current_frame: Current frame number
        tau: Time constant for Gaussian smoothing
    
    Returns:
        Smoothed positions {track_id: (x, y)}
    """
    if not SKLEARN_AVAILABLE or len(track_positions) == 0:
        return track_positions
    
    smoothed_positions = {}
    
    for track_id, (x, y) in track_positions.items():
        if track_id not in track_history or len(track_history[track_id]) < 2:
            # Not enough history, use current position
            smoothed_positions[track_id] = (x, y)
            continue
        
        # Get recent history (last 30 frames)
        recent_history = track_history[track_id][-30:]
        if len(recent_history) < 2:
            smoothed_positions[track_id] = (x, y)
            continue
        
        # Prepare data for smoothing
        frames = np.array([f for f, _, _ in recent_history] + [current_frame]).reshape(-1, 1)
        x_vals = np.array([px for _, px, _ in recent_history] + [x]).reshape(-1, 1)
        y_vals = np.array([py for _, _, py in recent_history] + [y]).reshape(-1, 1)
        
        try:
            # Adaptive length scale
            len_scale = np.clip(tau * np.log(tau ** 3 / len(frames)), tau ** -1, tau ** 2)
            
            # Smooth x coordinate
            gpr_x = GPR(RBF(len_scale, 'fixed'))
            gpr_x.fit(frames[:-1], x_vals[:-1])
            pred_x = gpr_x.predict(frames[-1:])
            # Handle tuple return or array
            if isinstance(pred_x, tuple):
                pred_x = pred_x[0]
            pred_x = np.asarray(pred_x)
            smoothed_x = float(pred_x.flat[0])

            # Smooth y coordinate
            gpr_y = GPR(RBF(len_scale, 'fixed'))
            gpr_y.fit(frames[:-1], y_vals[:-1])
            pred_y = gpr_y.predict(frames[-1:])
            # Handle tuple return or array
            if isinstance(pred_y, tuple):
                pred_y = pred_y[0]
            pred_y = np.asarray(pred_y)
            smoothed_y = float(pred_y.flat[0])
            
            smoothed_positions[track_id] = (smoothed_x, smoothed_y)
        except Exception as e:
            # If smoothing fails, use current position
            smoothed_positions[track_id] = (x, y)
    
    return smoothed_positions

