"""
Player ID Consolidation Tool
Merges duplicate player IDs that occur when tracking is lost
"""

import cv2
import pandas as pd
import numpy as np
import json
import os
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import scrolledtext

# Try to import matplotlib for heatmap generation
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not available. Heatmap generation will be skipped.")

try:
    from ultralytics import YOLO
    import supervision as sv
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


def load_team_color_config():
    """Load team color configuration"""
    if os.path.exists("team_color_config.json"):
        try:
            with open("team_color_config.json", 'r') as f:
                return json.load(f)
        except:
            return None
    return None


def analyze_id_sequences(df):
    """
    Analyze player ID sequences to find potential duplicates
    Returns: dict of {player_id: {'frames': list, 'positions': list, 'time_ranges': list}}
    """
    player_data = defaultdict(lambda: {
        'frames': [],
        'positions': [],
        'time_ranges': [],
        'total_frames': 0
    })
    
    # Group by player ID
    for _, row in df.iterrows():
        if pd.notna(row.get('player_id')):
            pid = int(row['player_id'])
            # FIX: Convert frame_num to int to prevent string subtraction error
            frame_num = int(row['frame']) if pd.notna(row.get('frame')) else 0
            timestamp = row.get('timestamp', 0)
            
            player_data[pid]['frames'].append(frame_num)
            player_data[pid]['total_frames'] += 1
            
            if pd.notna(row.get('player_x')) and pd.notna(row.get('player_y')):
                player_data[pid]['positions'].append((row['player_x'], row['player_y'], frame_num))
    
    # Find time ranges (continuous sequences)
    for pid in player_data:
        frames = sorted(player_data[pid]['frames'])
        if not frames:
            continue
        
        # Find gaps in frame sequence (gaps > 10 frames = new sequence)
        sequences = []
        current_seq = [frames[0]]
        
        for i in range(1, len(frames)):
            gap = frames[i] - frames[i-1]
            if gap <= 30:  # Small gap - same sequence
                current_seq.append(frames[i])
            else:  # Large gap - new sequence
                sequences.append((current_seq[0], current_seq[-1]))
                current_seq = [frames[i]]
        
        if current_seq:
            sequences.append((current_seq[0], current_seq[-1]))
        
        player_data[pid]['time_ranges'] = sequences
    
    return player_data


def find_potential_merges(df, player_data, max_gap_frames=300, max_distance=200, target_player_count=None, max_total_merges=None, player_name_assignments=None):
    """
    Find player IDs that are likely the same player
    Based on:
    - Player name assignments (if tracks have same assigned player name - highest priority)
    - Position continuity (player disappears then reappears nearby)
    - Time gaps (short gaps after one ID ends)
    - Total frames (merge small IDs into larger ones)
    - Target player count (merge until we reach target number of players)
    
    IMPROVED: More conservative merging with better scoring and filtering
    
    Args:
        player_name_assignments: dict of {track_id: player_name} from Review & Assignment or CSV
    
    If max_total_merges is None, it will be calculated adaptively based on:
    - Current player count vs target (if target specified)
    - Default: 300 merges for safety
    """
    # IMPROVED: Calculate adaptive merge cap if not specified
    if max_total_merges is None:
        if target_player_count is not None:
            current_count = len(player_data)
            needed_merges = current_count - target_player_count
            # Allow more merges if we're far from target, with 20% buffer
            # REMOVED hard cap of 2000 - allow all needed merges
            # Formula: needed_merges * 1.2 - allows 20% buffer for safety
            max_total_merges = int(needed_merges * 1.2)
            # But never go below 300 (minimum for quality control)
            max_total_merges = max(max_total_merges, 300)
            print(f"📊 Adaptive merge cap: {max_total_merges} merges (current: {current_count}, target: {target_player_count})")
        else:
            max_total_merges = 300  # Default safety cap
    
    merges = []
    
    # Phase 0: Find player name-based merges (HIGHEST PRIORITY - if tracks have same assigned player name)
    # This uses player assignments from Review & Assignment or CSV player_name column
    player_name_merges = []
    if player_name_assignments:
        # Group tracks by player name
        tracks_by_player = {}
        for track_id, player_name in player_name_assignments.items():
            if player_name and player_name not in ['Guest Player', 'None', None, '']:
                if player_name not in tracks_by_player:
                    tracks_by_player[player_name] = []
                tracks_by_player[player_name].append(track_id)
        
        # For each player with multiple tracks, merge them
        for player_name, track_ids in tracks_by_player.items():
            if len(track_ids) > 1:
                # Sort by total frames (merge smaller into larger)
                track_ids_with_frames = [(tid, player_data.get(tid, {}).get('total_frames', 0)) for tid in track_ids if tid in player_data]
                track_ids_with_frames.sort(key=lambda x: x[1], reverse=True)
                
                if len(track_ids_with_frames) > 1:
                    # Keep the largest track as target, merge others into it
                    target_track_id, target_frames = track_ids_with_frames[0]
                    
                    for source_track_id, source_frames in track_ids_with_frames[1:]:
                        # Check if tracks are temporally/spatially reasonable to merge
                        # Get time ranges for both tracks
                        target_data = player_data.get(target_track_id, {})
                        source_data = player_data.get(source_track_id, {})
                        
                        if target_data.get('time_ranges') and source_data.get('time_ranges'):
                            # Check if there's any temporal overlap or reasonable gap
                            target_ranges = target_data['time_ranges']
                            source_ranges = source_data['time_ranges']
                            
                            min_gap = float('inf')
                            has_overlap = False
                            for tr in target_ranges:
                                for sr in source_ranges:
                                    if not (tr[1] < sr[0] or sr[1] < tr[0]):
                                        has_overlap = True
                                        min_gap = 0
                                    else:
                                        gap = min(abs(tr[1] - sr[0]), abs(sr[1] - tr[0]))
                                        min_gap = min(min_gap, gap)
                            
                            # Only merge if overlap or reasonable gap (within 300 frames)
                            if has_overlap or min_gap <= 300:
                                player_name_merges.append({
                                    'from_id': source_track_id,
                                    'to_id': target_track_id,
                                    'gap_frames': min_gap if not has_overlap else 0,
                                    'distance': 0.0,  # Same player, distance doesn't matter
                                    'avg_distance': 0.0,
                                    'score': 0.95,  # Very high confidence (same player name)
                                    'from_frames': source_frames,
                                    'to_frames': target_frames,
                                    'merge_type': 'player_name'
                                })
    
    # Sort players by total frames (most active first)
    sorted_players = sorted(player_data.items(), key=lambda x: x[1]['total_frames'], reverse=True)
    
    # Phase 1: Find direct connections (ID ends, another starts nearby)
    # IMPROVED: More strict criteria for direct merges
    direct_merges = []
    for i, (pid1, data1) in enumerate(sorted_players):
        if data1['total_frames'] < 10:  # Increased threshold - need more frames for reliable merge
            continue
        
        if not data1['positions']:
            continue
        
        last_pos1 = data1['positions'][-1]  # (x, y, frame)
        last_frame1 = last_pos1[2]
        last_seq_end = max([seq[1] for seq in data1['time_ranges']]) if data1['time_ranges'] else last_frame1
        
        # Look for other IDs that start shortly after
        for j, (pid2, data2) in enumerate(sorted_players[i+1:], start=i+1):
            if data2['total_frames'] < 10:  # Increased threshold
                continue
            
            if not data2['positions']:
                continue
            
            first_pos2 = data2['positions'][0]  # (x, y, frame)
            first_frame2 = first_pos2[2]
            
            # Check if pid2 starts shortly after pid1 ends
            gap = first_frame2 - last_seq_end
            if gap < 0 or gap > max_gap_frames:
                continue
            
            # IMPROVED: Require smaller gap for better accuracy (was max_gap_frames, now 150)
            if gap > 150:  # More strict: only merge if gap is reasonable
                continue
            
            # Check if positions are close (player reappeared nearby)
            distance = np.sqrt((last_pos1[0] - first_pos2[0])**2 + (last_pos1[1] - first_pos2[1])**2)
            # IMPROVED: More strict distance requirement (was max_distance, now 150)
            if distance > 150:
                continue
            
            # Calculate average position overlap
            pos1_range_x = [p[0] for p in data1['positions']]
            pos1_range_y = [p[1] for p in data1['positions']]
            pos2_range_x = [p[0] for p in data2['positions']]
            pos2_range_y = [p[1] for p in data2['positions']]
            
            avg_x1, avg_y1 = np.mean(pos1_range_x), np.mean(pos1_range_y)
            avg_x2, avg_y2 = np.mean(pos2_range_x), np.mean(pos2_range_y)
            avg_distance = np.sqrt((avg_x1 - avg_x2)**2 + (avg_y1 - avg_y2)**2)
            
            # IMPROVED: Require similar average positions (within 100 pixels)
            if avg_distance > 100:
                continue
            
            # IMPROVED: Better scoring that penalizes large gaps and distances
            # Higher score = better match
            gap_score = 1.0 / (1.0 + gap / 10.0)  # Penalize gaps more
            distance_score = 1.0 / (1.0 + distance / 20.0)  # Penalize distance more
            avg_distance_score = 1.0 / (1.0 + avg_distance / 30.0)  # Penalize avg distance
            frame_ratio = min(data1['total_frames'], data2['total_frames']) / max(data1['total_frames'], data2['total_frames'])
            
            score = gap_score * distance_score * avg_distance_score * frame_ratio
            
            # IMPROVED: Minimum score threshold to filter low-quality merges
            if score < 0.01:  # Only keep high-quality merges
                continue
            
            direct_merges.append({
                'from_id': pid2,
                'to_id': pid1,  # Merge into the longer track
                'gap_frames': gap,
                'distance': distance,
                'avg_distance': avg_distance,
                'score': score,
                'from_frames': data2['total_frames'],
                'to_frames': data1['total_frames'],
                'merge_type': 'direct'
            })
    
    # Phase 1.5: Find consecutive/overlapping frame merges (CRITICAL for short tracks)
    # This handles tracks that appear in consecutive frames or overlap temporally
    consecutive_merges = []
    for i, (pid1, data1) in enumerate(sorted_players):
        if not data1['positions'] or not data1['time_ranges']:
            continue
        
        # Get frame range for this track
        frames1 = set()
        for start_frame, end_frame in data1['time_ranges']:
            frames1.update(range(int(start_frame), int(end_frame) + 1))
        
        # Look for other tracks that overlap or are consecutive
        for j, (pid2, data2) in enumerate(sorted_players[i+1:], start=i+1):
            if not data2['positions'] or not data2['time_ranges']:
                continue
            
            # Get frame range for this track
            frames2 = set()
            for start_frame, end_frame in data2['time_ranges']:
                frames2.update(range(int(start_frame), int(end_frame) + 1))
            
            # Check for overlap or consecutive frames
            overlap = frames1 & frames2
            gap = 0
            if not overlap:
                # Check if frames are consecutive (within 1-2 frames)
                min_frame1 = min(frames1) if frames1 else 0
                max_frame1 = max(frames1) if frames1 else 0
                min_frame2 = min(frames2) if frames2 else 0
                max_frame2 = max(frames2) if frames2 else 0
                
                if max_frame1 < min_frame2:
                    gap = min_frame2 - max_frame1 - 1
                elif max_frame2 < min_frame1:
                    gap = min_frame1 - max_frame2 - 1
                else:
                    gap = 0  # Overlapping
                
                # Only merge if gap is very small (0-2 frames) or overlapping
                if gap > 2:
                    continue
            
            # Check if positions are close (within reasonable distance)
            # Use last position of pid1 and first position of pid2, or average if overlapping
            avg_distance = None
            if overlap:
                # If overlapping, check if positions are similar during overlap
                overlap_frames_list = sorted(list(overlap))
                if len(overlap_frames_list) > 0:
                    # Get positions during overlap
                    pos1_overlap = [p for p in data1['positions'] if int(p[2]) in overlap]
                    pos2_overlap = [p for p in data2['positions'] if int(p[2]) in overlap]
                    
                    if pos1_overlap and pos2_overlap:
                        # Calculate average distance during overlap
                        distances = []
                        for p1 in pos1_overlap:
                            for p2 in pos2_overlap:
                                if abs(p1[2] - p2[2]) <= 1:  # Same or adjacent frame
                                    dist = np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
                                    distances.append(dist)
                        
                        if distances:
                            avg_distance = np.mean(distances)
                            if avg_distance > 100:  # Too far apart during overlap
                                continue
                        else:
                            # No matching frames, use average positions
                            avg_x1 = np.mean([p[0] for p in pos1_overlap])
                            avg_y1 = np.mean([p[1] for p in pos1_overlap])
                            avg_x2 = np.mean([p[0] for p in pos2_overlap])
                            avg_y2 = np.mean([p[1] for p in pos2_overlap])
                            avg_distance = np.sqrt((avg_x1 - avg_x2)**2 + (avg_y1 - avg_y2)**2)
                            if avg_distance > 100:
                                continue
                    else:
                        continue
                else:
                    continue
            else:
                # Consecutive frames - check if positions are close
                last_pos1 = data1['positions'][-1]  # Last position of pid1
                first_pos2 = data2['positions'][0]    # First position of pid2
                distance = np.sqrt((last_pos1[0] - first_pos2[0])**2 + (last_pos1[1] - first_pos2[1])**2)
                if distance > 150:  # Too far apart
                    continue
                avg_distance = distance
            
            if avg_distance is None:
                continue
            
            # High confidence score for overlapping/consecutive tracks
            overlap_bonus = 2.0 if overlap else 1.5
            gap_penalty = 1.0 / (1.0 + gap) if gap > 0 else 1.0
            frame_ratio = min(data1['total_frames'], data2['total_frames']) / max(data1['total_frames'], data2['total_frames']) if max(data1['total_frames'], data2['total_frames']) > 0 else 0.5
            
            score = overlap_bonus * gap_penalty * frame_ratio
            
            # Lower threshold for consecutive/overlapping merges (these are high confidence)
            if score < 0.3:
                continue
            
            consecutive_merges.append({
                'from_id': pid2 if data2['total_frames'] < data1['total_frames'] else pid1,
                'to_id': pid1 if data2['total_frames'] < data1['total_frames'] else pid2,
                'gap_frames': gap,
                'distance': avg_distance if overlap else distance,
                'avg_distance': avg_distance if overlap else distance,
                'score': score,
                'from_frames': min(data1['total_frames'], data2['total_frames']),
                'to_frames': max(data1['total_frames'], data2['total_frames']),
                'merge_type': 'consecutive' if gap <= 2 else 'overlapping'
            })
    
    # Phase 2: Find position-based merges (similar average positions)
    # IMPROVED: Much more conservative - only merge if very strong evidence
    position_merges = []
    for i, (pid1, data1) in enumerate(sorted_players):
        if data1['total_frames'] < 20:  # Increased threshold - need substantial data
            continue
        
        if not data1['positions']:
            continue
        
        pos1_x = [p[0] for p in data1['positions']]
        pos1_y = [p[1] for p in data1['positions']]
        avg_x1, avg_y1 = np.mean(pos1_x), np.mean(pos1_y)
        std_x1, std_y1 = np.std(pos1_x), np.std(pos1_y)
        
        # Look for other IDs with similar average positions
        for j, (pid2, data2) in enumerate(sorted_players[i+1:], start=i+1):
            if data2['total_frames'] < 20:  # Increased threshold
                continue
            
            if not data2['positions']:
                continue
            
            pos2_x = [p[0] for p in data2['positions']]
            pos2_y = [p[1] for p in data2['positions']]
            avg_x2, avg_y2 = np.mean(pos2_x), np.mean(pos2_y)
            
            # IMPROVED: Much stricter position similarity requirement
            avg_distance = np.sqrt((avg_x1 - avg_x2)**2 + (avg_y1 - avg_y2)**2)
            if avg_distance > 80:  # Much more strict (was max_distance * 0.5 = 100)
                continue
            
            # IMPROVED: Require temporal overlap or very close timing
            ranges1 = data1['time_ranges']
            ranges2 = data2['time_ranges']
            if not ranges1 or not ranges2:
                continue
            
            # Check if there's any time overlap or small gap
            min_gap = float('inf')
            has_overlap = False
            for r1 in ranges1:
                for r2 in ranges2:
                    # Check for overlap
                    if not (r1[1] < r2[0] or r2[1] < r1[0]):
                        has_overlap = True
                        min_gap = 0
                    else:
                        gap = min(abs(r1[1] - r2[0]), abs(r2[1] - r1[0]))
                        min_gap = min(min_gap, gap)
            
            # IMPROVED: Require overlap or very small gap (was max_gap_frames * 2)
            if not has_overlap and min_gap > 200:  # Much more strict
                continue
            
            # IMPROVED: Better scoring with multiple factors
            frame_ratio = min(data1['total_frames'], data2['total_frames']) / max(data1['total_frames'], data2['total_frames'])
            position_score = 1.0 / (1.0 + avg_distance / 20.0)  # Penalize distance
            gap_score = 1.0 / (1.0 + min_gap / 50.0) if min_gap > 0 else 1.0  # Penalize gaps
            overlap_bonus = 1.5 if has_overlap else 1.0  # Bonus for temporal overlap
            
            score = position_score * gap_score * frame_ratio * overlap_bonus
            
            # IMPROVED: Higher minimum score threshold
            if score < 0.05:  # Only keep high-quality merges
                continue
            
            position_merges.append({
                'from_id': pid2,
                'to_id': pid1,
                'gap_frames': min_gap,
                'distance': avg_distance,
                'avg_distance': avg_distance,
                'score': score,
                'from_frames': data2['total_frames'],
                'to_frames': data1['total_frames'],
                'merge_type': 'position'
            })
    
    # Combine all merges (prioritize player name merges, then consecutive/overlapping, then others)
    all_merges = player_name_merges + consecutive_merges + direct_merges + position_merges
    all_merges.sort(key=lambda x: x['score'], reverse=True)
    
    # NOTE: Hard cap will be applied at the end after all merges (including target-based) are collected
    # This prevents premature capping before target-based merges are added
    
    # IMPROVED: Remove conflicting merges (each ID can only merge into one other)
    # Also prioritize higher-scored merges when conflicts occur
    final_merges = []
    used_ids = set()
    used_to_ids = set()  # Track which IDs are being merged into (to avoid circular merges)
    
    for merge in all_merges:
        from_id = merge['from_id']
        to_id = merge['to_id']
        
        # Skip if from_id already used
        if from_id in used_ids:
            continue
        
        # IMPROVED: Skip if to_id is itself being merged (avoid chains during initial phase)
        if to_id in used_ids and to_id != from_id:
            # Check if this is a better merge (higher score) than the existing one
            existing_merge = next((m for m in final_merges if m['from_id'] == to_id), None)
            if existing_merge and merge['score'] > existing_merge['score']:
                # Replace the lower-scored merge
                final_merges.remove(existing_merge)
                used_ids.remove(to_id)
            else:
                continue
        
        final_merges.append(merge)
        used_ids.add(from_id)
        used_to_ids.add(to_id)
    
    # IMPROVED: If target player count specified, merge more conservatively
    # Only do aggressive target merging if we're significantly over target
    if target_player_count is not None:
        current_count = len(player_data)
        needed_merges = current_count - target_player_count
        
        # IMPROVED: Only do target-based merging if we're way over target (2x or more)
        # This prevents over-merging when we're close to target
        # ALSO: Check if we're already at the merge cap to avoid adding too many
        merges_so_far = len(final_merges)
        if needed_merges > 0 and current_count > target_player_count * 2 and merges_so_far < max_total_merges:
            # Get remaining IDs that haven't been merged
            merged_from_ids = set(m['from_id'] for m in final_merges)
            remaining_ids = [pid for pid, data in sorted_players if pid not in merged_from_ids]
            
            # Sort remaining by frame count (merge smallest into largest)
            remaining_with_frames = [(pid, player_data[pid]['total_frames']) for pid in remaining_ids]
            remaining_with_frames.sort(key=lambda x: x[1])
            
            # Group by position clusters (similar average positions = same player)
            # This helps merge IDs that are in the same area of the field
            # BUT: Only merge if we still need to reduce count, and be more conservative
            position_clusters = {}
            for pid, frames in remaining_with_frames:
                if pid not in player_data or not player_data[pid]['positions']:
                    continue
                
                pos_x = [p[0] for p in player_data[pid]['positions']]
                pos_y = [p[1] for p in player_data[pid]['positions']]
                avg_x, avg_y = np.mean(pos_x), np.mean(pos_y)
                
                # Find closest existing cluster
                cluster_key = None
                min_cluster_dist = max_distance * 0.08  # IMPROVED: Even more conservative - require very close positions (was 0.10)
                
                for key, cluster_data in position_clusters.items():
                    cluster_x, cluster_y, cluster_ids = cluster_data
                    dist = np.sqrt((avg_x - cluster_x)**2 + (avg_y - cluster_y)**2)
                    if dist < min_cluster_dist:
                        cluster_key = key
                        min_cluster_dist = dist
                        break
                
                if cluster_key is None:
                    # Create new cluster
                    cluster_key = len(position_clusters)
                    position_clusters[cluster_key] = [avg_x, avg_y, []]
                
                position_clusters[cluster_key][2].append(pid)
            
            # Merge IDs within each cluster (smallest to largest)
            # BUT: Only merge if we still need to reduce count toward target
            cluster_merge_count = 0
            for cluster_key, cluster_data in position_clusters.items():
                cluster_x, cluster_y, cluster_ids = cluster_data
                if len(cluster_ids) <= 1:
                    continue
                
                # Check if we still need merges
                current_remaining = current_count - len(merged_from_ids) - cluster_merge_count
                if current_remaining <= target_player_count:
                    break  # Stop merging if we've reached target
                
                # Sort by frame count
                cluster_with_frames = [(pid, player_data[pid]['total_frames']) for pid in cluster_ids]
                cluster_with_frames.sort(key=lambda x: x[1])
                
                # Only merge if cluster has more than 1 ID AND we need more merges
                if len(cluster_with_frames) > 1 and current_remaining > target_player_count:
                    largest_pid, largest_frames = cluster_with_frames[-1]
                    
                    # Only merge enough to get closer to target (don't merge all)
                    merges_in_cluster = 0
                    for small_pid, small_frames in cluster_with_frames[:-1]:
                        if small_pid in merged_from_ids:
                            continue
                        
                        # Check if we still need merges
                        if current_remaining - cluster_merge_count - merges_in_cluster <= target_player_count:
                            break
                        
                        # IMPROVED: Only merge if positions are actually very close
                        pos1_x = [p[0] for p in player_data[small_pid]['positions']]
                        pos1_y = [p[1] for p in player_data[small_pid]['positions']]
                        pos2_x = [p[0] for p in player_data[largest_pid]['positions']]
                        pos2_y = [p[1] for p in player_data[largest_pid]['positions']]
                        avg_x1, avg_y1 = np.mean(pos1_x), np.mean(pos1_y)
                        avg_x2, avg_y2 = np.mean(pos2_x), np.mean(pos2_y)
                        cluster_distance = np.sqrt((avg_x1 - avg_x2)**2 + (avg_y1 - avg_y2)**2)
                        
                        # IMPROVED: Only merge if positions are very close (within 50 pixels, was 60)
                        if cluster_distance > 50:
                            continue
                        
                        final_merges.append({
                            'from_id': small_pid,
                            'to_id': largest_pid,
                            'gap_frames': 0,
                            'distance': cluster_distance,
                            'avg_distance': cluster_distance,
                            'score': 0.4,  # IMPROVED: Lower score for cluster merges (was 0.6)
                            'from_frames': small_frames,
                            'to_frames': largest_frames,
                            'merge_type': 'position_cluster'
                        })
                        merged_from_ids.add(small_pid)
                        cluster_merge_count += 1
                        merges_in_cluster += 1
            
            # If still need more merges, merge smallest remaining into largest
            # But limit merges to preserve target count of final IDs
            remaining_ids = [pid for pid, data in sorted_players if pid not in merged_from_ids]
            
            if remaining_ids:
                remaining_with_frames = [(pid, player_data[pid]['total_frames']) for pid in remaining_ids]
                remaining_with_frames.sort(key=lambda x: x[1])
                
                # Calculate how many merges we've already created
                position_cluster_merges = len([m for m in final_merges if m['merge_type'] == 'position_cluster'])
                direct_merges_count = len([m for m in final_merges if m['merge_type'] == 'direct'])
                position_merges_count = len([m for m in final_merges if m['merge_type'] == 'position'])
                
                # Estimate remaining IDs after all merges
                # Each merge reduces count by 1 (merging one ID into another)
                total_merges_so_far = position_cluster_merges + direct_merges_count + position_merges_count
                estimated_remaining_after_merges = current_count - total_merges_so_far
                
                # IMPROVED: Only merge enough to get closer to target, not all the way
                # Be conservative - only merge if we're significantly over target
                estimated_over_target = estimated_remaining_after_merges - target_player_count
                
                # CRITICAL: Don't merge if we're already at or below target
                if estimated_remaining_after_merges <= target_player_count:
                    additional_merges_needed = 0
                else:
                    # IMPROVED: Only merge 50% of what's needed (be conservative)
                    # This prevents over-merging and allows manual review
                    additional_merges_needed = max(0, int(estimated_over_target * 0.5))
                    
                    # IMPROVED: Cap at reasonable maximum (don't merge everything at once)
                    # Also respect the global merge cap
                    remaining_merge_slots = max(0, max_total_merges - merges_so_far)
                    max_merges_per_phase = min(50, len(remaining_ids) // 2, remaining_merge_slots)  # Max 50 merges, half of remaining, or remaining slots
                    additional_merges_needed = min(additional_merges_needed, max_merges_per_phase)
                
                small_idx = 0
                large_idx = len(remaining_with_frames) - 1
                merge_count = 0
                
                # Group remaining IDs by position to merge within groups first
                # This prevents creating one giant chain
                position_groups = {}
                for pid, frames in remaining_with_frames:
                    if pid not in player_data or not player_data[pid]['positions']:
                        continue
                    pos_x = [p[0] for p in player_data[pid]['positions']]
                    pos_y = [p[1] for p in player_data[pid]['positions']]
                    avg_x, avg_y = np.mean(pos_x), np.mean(pos_y)
                    
                    # Find closest group (much more conservative threshold)
                    group_key = None
                    min_dist = max_distance * 0.12  # IMPROVED: Even more conservative (was 0.15)
                    for key, group_data in position_groups.items():
                        gx, gy, gids = group_data
                        dist = np.sqrt((avg_x - gx)**2 + (avg_y - gy)**2)
                        if dist < min_dist:
                            group_key = key
                            min_dist = dist
                    
                    if group_key is None:
                        group_key = len(position_groups)
                        position_groups[group_key] = [avg_x, avg_y, []]
                    
                    position_groups[group_key][2].append(pid)
                
                # Merge within groups first (smallest to largest in each group)
                # BUT: Only merge if we still need to reduce count
                for group_key, group_data in position_groups.items():
                    gx, gy, group_ids = group_data
                    if len(group_ids) <= 1:
                        continue
                    
                    # Check if we still need merges
                    current_remaining_after_group = current_count - len(merged_from_ids) - merge_count
                    if current_remaining_after_group <= target_player_count:
                        break  # Stop if we've reached target
                    
                    group_with_frames = [(pid, player_data[pid]['total_frames']) for pid in group_ids]
                    group_with_frames.sort(key=lambda x: x[1])
                    
                    # Only merge enough to get closer to target (don't merge all)
                    largest_pid = group_with_frames[-1][0]
                    for small_pid, small_frames in group_with_frames[:-1]:
                        if small_pid in merged_from_ids:
                            continue
                        
                        # Check if we still need merges
                        if merge_count >= additional_merges_needed:
                            break
                        
                        # Check if merging would go below target
                        if current_remaining_after_group - merge_count <= target_player_count:
                            break
                        
                        # IMPROVED: Only merge if positions are actually close
                        pos1_x = [p[0] for p in player_data[small_pid]['positions']]
                        pos1_y = [p[1] for p in player_data[small_pid]['positions']]
                        pos2_x = [p[0] for p in player_data[largest_pid]['positions']]
                        pos2_y = [p[1] for p in player_data[largest_pid]['positions']]
                        avg_x1, avg_y1 = np.mean(pos1_x), np.mean(pos1_y)
                        avg_x2, avg_y2 = np.mean(pos2_x), np.mean(pos2_y)
                        group_distance = np.sqrt((avg_x1 - avg_x2)**2 + (avg_y1 - avg_y2)**2)
                        
                        # IMPROVED: Only merge if positions are close (within 70 pixels, was 80)
                        if group_distance > 70:
                            continue
                        
                        final_merges.append({
                            'from_id': small_pid,
                            'to_id': largest_pid,
                            'gap_frames': 0,
                            'distance': group_distance,
                            'avg_distance': group_distance,
                            'score': 0.3,  # IMPROVED: Lower score for target_count merges (was 0.5)
                            'from_frames': small_frames,
                            'to_frames': group_with_frames[-1][1],
                            'merge_type': 'target_count'
                        })
                        merged_from_ids.add(small_pid)
                        merge_count += 1
                
                # If still need more merges, merge smallest remaining into largest
                # But only merge across groups if necessary
                remaining_ids = [pid for pid, data in sorted_players if pid not in merged_from_ids]
                remaining_with_frames = [(pid, player_data[pid]['total_frames']) for pid in remaining_ids]
                remaining_with_frames.sort(key=lambda x: x[1])
                
                small_idx = 0
                large_idx = len(remaining_with_frames) - 1
                
                # Calculate current remaining count before this loop
                current_remaining_before_loop = current_count - len(merged_from_ids)
                
                while (merge_count < additional_merges_needed and 
                       small_idx < large_idx and 
                       len(remaining_with_frames) > target_player_count and
                       current_remaining_before_loop - merge_count > target_player_count):  # Don't go below target
                    small_pid, small_frames = remaining_with_frames[small_idx]
                    large_pid, large_frames = remaining_with_frames[large_idx]
                    
                    if small_pid in merged_from_ids or large_pid in merged_from_ids:
                        if small_pid in merged_from_ids:
                            small_idx += 1
                        if large_pid in merged_from_ids:
                            large_idx -= 1
                        continue
                    
                    # Check if merging would go below target
                    if current_remaining_before_loop - merge_count <= target_player_count:
                        break
                    
                    # IMPROVED: Only merge if positions are reasonably close (even for forced merges)
                    pos1_x = [p[0] for p in player_data[small_pid]['positions']]
                    pos1_y = [p[1] for p in player_data[small_pid]['positions']]
                    pos2_x = [p[0] for p in player_data[large_pid]['positions']]
                    pos2_y = [p[1] for p in player_data[large_pid]['positions']]
                    avg_x1, avg_y1 = np.mean(pos1_x), np.mean(pos1_y)
                    avg_x2, avg_y2 = np.mean(pos2_x), np.mean(pos2_y)
                    forced_distance = np.sqrt((avg_x1 - avg_x2)**2 + (avg_y1 - avg_y2)**2)
                    
                    # IMPROVED: Require positions to be within 90 pixels even for forced merges (was 100)
                    if forced_distance > 90:
                        # Skip this merge - positions too far apart
                        small_idx += 1
                        continue
                    
                    # Create merge from small to large
                    final_merges.append({
                        'from_id': small_pid,
                        'to_id': large_pid,
                        'gap_frames': 0,
                        'distance': forced_distance,
                        'avg_distance': forced_distance,
                        'score': 0.2,  # IMPROVED: Much lower score for forced merges (was 0.4)
                        'from_frames': small_frames,
                        'to_frames': large_frames,
                        'merge_type': 'target_count'
                    })
                    
                    merged_from_ids.add(small_pid)
                    merge_count += 1
                    small_idx += 1
    
    # IMPROVED: Filter out low-quality merges before final validation
    # Remove merges with very low scores (likely false positives)
    MIN_SCORE_THRESHOLD = 0.001  # Minimum score to keep a merge
    final_merges = [m for m in final_merges if m['score'] >= MIN_SCORE_THRESHOLD]
    
    # IMPROVED: Sort by score again after filtering
    final_merges.sort(key=lambda x: x['score'], reverse=True)
    
    # CRITICAL: Apply cap to FINAL merges (after all target-based merges added)
    # This ensures we never suggest more than max_total_merges, regardless of merge type
    # NOTE: max_total_merges is now calculated based on needed merges, so this should rarely trigger
    if len(final_merges) > max_total_merges:
        original_count = len(final_merges)
        final_merges = final_merges[:max_total_merges]
        print(f"⚠ Applied merge cap: Limited to top {max_total_merges} merges (had {original_count} total)")
        print(f"   💡 Tip: If you need more merges, increase the target player count or set max_total_merges parameter")
    
    # Final validation: Ensure we don't over-consolidate
    # Simulate merge chains to get accurate final count
    if target_player_count is not None and len(final_merges) > 0:
        # Build merge map
        merge_map = {m['from_id']: m['to_id'] for m in final_merges}
        
        # Resolve chains (simplified version - just get final destinations)
        final_destinations = {}
        for from_id, to_id in merge_map.items():
            # Follow chain to final destination
            current = to_id
            while current in merge_map:
                current = merge_map[current]
            final_destinations[from_id] = current
        
        # Count unique final destinations
        unique_final_ids = set(final_destinations.values())
        
        # Count IDs that aren't being merged (remain as-is)
        all_ids = set(player_data.keys())
        merged_from_ids_set = set(m['from_id'] for m in final_merges)
        remaining_unmerged = all_ids - merged_from_ids_set
        
        # Also check if any "to_id" values are themselves merged (chains)
        to_ids_that_are_merged = set()
        for merge in final_merges:
            if merge['to_id'] in merged_from_ids_set:
                to_ids_that_are_merged.add(merge['to_id'])
        
        # Final count = unique final destinations + IDs that remain unmerged
        estimated_final_count = len(unique_final_ids) + len(remaining_unmerged)
        
        # If we're going below target, remove some merges (remove lowest scored ones)
        if estimated_final_count < target_player_count:
            # Sort merges by score (lowest first) and remove enough to reach target
            final_merges_sorted = sorted(final_merges, key=lambda x: x['score'])
            merges_to_remove = target_player_count - estimated_final_count
            if merges_to_remove > 0 and merges_to_remove < len(final_merges_sorted):
                # Remove lowest-scored merges until we're at target
                final_merges = final_merges_sorted[merges_to_remove:]
                # Re-sort by score (highest first) for consistency
                final_merges.sort(key=lambda x: x['score'], reverse=True)
    
    return final_merges


def resolve_merge_chains(merge_map):
    """
    Resolve transitive merges (if A→B and B→C, then A→C)
    This handles cases where IDs are merged into IDs that are themselves merged
    
    Example:
        merge_map = {1: 2, 2: 3, 4: 2}
        resolved = {1: 3, 2: 3, 4: 3}
        
    Note: Only resolves IDs that are in the merge_map (source IDs).
    Target IDs that are not sources are considered final IDs.
    """
    if not merge_map:
        return {}
    
    resolved_map = {}
    resolving = set()  # Track IDs currently being resolved (for cycle detection)
    
    def find_final_id(pid):
        """Recursively find the final ID that this ID should map to"""
        # If already resolved, return it
        if pid in resolved_map:
            return resolved_map[pid]
        
        # If not in merge map, this is a final ID (not being merged)
        if pid not in merge_map:
            resolved_map[pid] = pid
            return pid
        
        # Check for cycles (shouldn't happen, but safety check)
        if pid in resolving:
            # Cycle detected - break by making this a final ID
            resolved_map[pid] = pid
            return pid
        
        resolving.add(pid)
        
        # Follow the chain
        next_id = merge_map[pid]
        if next_id == pid:  # Self-reference
            resolved_map[pid] = pid
            resolving.remove(pid)
            return pid
        
        # Recursively resolve the next ID
        final_id = find_final_id(next_id)
        resolved_map[pid] = final_id
        resolving.remove(pid)
        return final_id
    
    # Resolve all source IDs in the merge map
    for pid in merge_map.keys():
        if pid not in resolved_map:
            find_final_id(pid)
    
    return resolved_map


def consolidate_ids(df, merge_map):
    """
    Apply ID consolidation to dataframe
    merge_map: dict of {old_id: new_id}
    CRITICAL FIX: Use memory-efficient operations to avoid crashes on large datasets
    """
    # Resolve merge chains (transitive merges)
    resolved_map = resolve_merge_chains(merge_map)
    
    # CRITICAL FIX: Use replace() instead of copy() + apply() for memory efficiency
    # This avoids creating multiple copies of large DataFrames
    df_consolidated = df.copy(deep=False)  # Shallow copy (faster, less memory)
    
    # Replace player IDs using map() which is more memory-efficient than apply()
    if 'player_id' in df_consolidated.columns:
        # Convert to numeric, handle NaN, then map
        player_id_series = pd.to_numeric(df_consolidated['player_id'], errors='coerce')
        # Use map() with fillna() - much faster and more memory-efficient than apply()
        df_consolidated['player_id'] = player_id_series.map(lambda x: resolved_map.get(int(x), x) if pd.notna(x) else x)
    
    # Replace possession player IDs
    if 'possession_player_id' in df_consolidated.columns:
        possession_id_series = pd.to_numeric(df_consolidated['possession_player_id'], errors='coerce')
        df_consolidated['possession_player_id'] = possession_id_series.map(lambda x: resolved_map.get(int(x), x) if pd.notna(x) else x)
    
    return df_consolidated


def consolidate_ids_chunked(df, merge_map, chunk_size=100000):
    """
    Apply ID consolidation to dataframe in chunks to avoid memory issues
    CRITICAL FIX: Process large DataFrames in chunks to prevent crashes
    Uses generator approach to avoid loading all chunks in memory at once
    """
    # Resolve merge chains once
    resolved_map = resolve_merge_chains(merge_map)
    
    # Process in chunks using generator to avoid memory buildup
    total_rows = len(df)
    processed_chunks = []
    
    # Process chunks one at a time and keep only a few in memory
    max_chunks_in_memory = 5  # Keep max 5 chunks in memory before concatenating
    
    for i in range(0, total_rows, chunk_size):
        chunk = df.iloc[i:i+chunk_size].copy(deep=False)
        
        # Replace player IDs
        if 'player_id' in chunk.columns:
            player_id_series = pd.to_numeric(chunk['player_id'], errors='coerce')
            chunk['player_id'] = player_id_series.map(lambda x: resolved_map.get(int(x), x) if pd.notna(x) else x)
        
        # Replace possession player IDs
        if 'possession_player_id' in chunk.columns:
            possession_id_series = pd.to_numeric(chunk['possession_player_id'], errors='coerce')
            chunk['possession_player_id'] = possession_id_series.map(lambda x: resolved_map.get(int(x), x) if pd.notna(x) else x)
        
        processed_chunks.append(chunk)
        
        # CRITICAL FIX: Periodically concatenate and clear to avoid memory buildup
        if len(processed_chunks) >= max_chunks_in_memory:
            # Concatenate accumulated chunks
            if len(processed_chunks) > 1:
                combined = pd.concat(processed_chunks, ignore_index=True)
                processed_chunks = [combined]  # Keep only the combined chunk
            else:
                # If only one chunk, keep it
                pass
    
    # Final concatenation of remaining chunks
    if len(processed_chunks) > 1:
        df_consolidated = pd.concat(processed_chunks, ignore_index=True)
    elif len(processed_chunks) == 1:
        df_consolidated = processed_chunks[0]
    else:
        # Empty result (shouldn't happen)
        df_consolidated = df.copy(deep=False)
    
    return df_consolidated


class IDConsolidationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Player ID Consolidation Tool")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        
        self.csv_file = None
        self.df = None
        self.player_data = None
        self.suggested_merges = []
        self.applied_merges = {}  # from_id: to_id
        self.rejected_merges = set()  # Set of (from_id, to_id) tuples that are rejected
        self.rejected_ids = set()  # Set of IDs that are completely rejected (and all their connections)
        self.target_player_count = tk.IntVar(value=12)  # Default: 11 players + coach
        self.video_path = None  # Store video path for playback viewer
        self.player_names = {}  # track_id: name (loaded from player_names.json)
        self.team_names = {}  # track_id: team_name (loaded from team config or player_names)
        self.seed_config = None  # Loaded from seed_config.json if available
        
        self.create_widgets()
        
        # Load player names and seed config (after widgets are created so log_text exists)
        self.load_player_names()
        self.load_seed_config()
        
        # Ensure window stays visible after widgets are created
        try:
            self.root.lift()
            self.root.focus_force()
            # Keep topmost briefly, then allow normal behavior
            self.root.attributes('-topmost', True)
            self.root.after(200, lambda: self.root.attributes('-topmost', False))
        except:
            pass
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # File selection
        file_frame = ttk.LabelFrame(main_frame, text="Load Files", padding="10")
        file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(file_frame, text="CSV File:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.csv_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.csv_path_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_csv).grid(row=0, column=2, padx=5)
        ttk.Button(file_frame, text="Load & Analyze", command=self.load_and_analyze).grid(row=0, column=3, padx=5)
        
        ttk.Label(file_frame, text="Video File:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=(5, 0))
        self.video_path_entry = ttk.Entry(file_frame, width=50)
        self.video_path_entry.grid(row=1, column=1, padx=5, pady=(5, 0))
        ttk.Button(file_frame, text="Browse", command=self.browse_video).grid(row=1, column=2, padx=5, pady=(5, 0))
        
        # Statistics and Target Count
        stats_frame = ttk.LabelFrame(main_frame, text="Statistics & Target", padding="10")
        stats_frame.pack(fill=tk.X, pady=5)
        
        stats_left = ttk.Frame(stats_frame)
        stats_left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.stats_label = ttk.Label(stats_left, text="Load CSV file to see statistics")
        self.stats_label.pack(anchor=tk.W)
        
        # Target player count
        target_frame = ttk.Frame(stats_frame)
        target_frame.pack(side=tk.RIGHT, padx=10)
        
        ttk.Label(target_frame, text="Target Player Count:").pack(side=tk.LEFT, padx=5)
        target_spinbox = ttk.Spinbox(target_frame, from_=1, to=50, 
                                     textvariable=self.target_player_count, width=10)
        target_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(target_frame, text="(11 players + coach = 12, or both teams = 23)").pack(side=tk.LEFT, padx=5)
        
        # Suggested merges
        merges_frame = ttk.LabelFrame(main_frame, text="Suggested ID Merges", padding="10")
        merges_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Treeview for merges
        columns = ('From ID', 'To ID', 'Gap (frames)', 'Distance', 'Avg Distance', 'Score', 'Type', 'Status')
        self.merges_tree = ttk.Treeview(merges_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.merges_tree.heading(col, text=col)
            self.merges_tree.column(col, width=100)
        
        self.merges_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Double-click to view in playback
        self.merges_tree.bind('<Double-1>', lambda e: self.open_playback_for_selected())
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(merges_frame, orient=tk.VERTICAL, command=self.merges_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.merges_tree.configure(yscrollcommand=scrollbar.set)
        
        # Add hint label
        hint_label = ttk.Label(merges_frame, text="💡 Tip: Double-click a merge to view it in the playback viewer", 
                              foreground="gray", font=("TkDefaultFont", 8))
        hint_label.pack(side=tk.BOTTOM, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(button_frame, text="Apply Selected Merges", command=self.apply_merges).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Apply All Suggested", command=self.apply_all_merges).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reject Selected", command=self.reject_merges).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear All Merges", command=self.clear_merges).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="View in Playback", command=self.open_playback_for_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Manage Player Names", command=self.open_player_names_editor).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Manage Team Names", command=self.open_team_names_editor).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Consolidated CSV", command=self.export_consolidated).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Generate Heatmap", command=self.generate_heatmap).pack(side=tk.LEFT, padx=5)
        
        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def log(self, message):
        """Add message to log"""
        if hasattr(self, 'log_text'):
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
        else:
            # Fallback if log_text doesn't exist yet
            print(message)
    
    def load_player_names(self):
        """Load player name mappings from player_names.json"""
        if os.path.exists("player_names.json"):
            try:
                with open("player_names.json", 'r') as f:
                    self.player_names = json.load(f)
                    # Convert keys to integers for consistency
                    self.player_names = {int(k): str(v) for k, v in self.player_names.items()}
                    self.log(f"✓ Loaded {len(self.player_names)} player name mappings")
            except Exception as e:
                self.log(f"Warning: Could not load player_names.json: {e}")
                self.player_names = {}
        else:
            self.player_names = {}
        
        # Also load team names from team color config or player_teams.json
        self.load_team_names()
    
    def load_team_names(self):
        """Load team name mappings"""
        self.team_names = {}
        
        # Try loading from team_color_config.json
        team_config = load_team_color_config()
        if team_config and 'team_colors' in team_config:
            # Extract team names from config
            for team_key in ['team1', 'team2']:
                if team_key in team_config['team_colors']:
                    team_data = team_config['team_colors'][team_key]
                    team_name = team_data.get('name', team_key)
                    # We'll map player IDs to teams later based on classification
        
        # Try loading from player_teams.json (if it exists)
        if os.path.exists("player_teams.json"):
            try:
                with open("player_teams.json", 'r') as f:
                    player_teams = json.load(f)
                    # Convert keys to integers
                    self.team_names = {int(k): str(v) for k, v in player_teams.items()}
                    self.log(f"✓ Loaded {len(self.team_names)} team assignments")
            except Exception as e:
                self.log(f"Warning: Could not load player_teams.json: {e}")
    
    def load_seed_config(self):
        """Load seed config from setup wizard if available"""
        if os.path.exists("seed_config.json"):
            try:
                with open("seed_config.json", 'r') as f:
                    self.seed_config = json.load(f)
                    self.log(f"✓ Loaded seed config from setup wizard")
            except Exception as e:
                self.log(f"Warning: Could not load seed_config.json: {e}")
                self.seed_config = None
        else:
            self.seed_config = None
    
    def browse_csv(self):
        """Browse for CSV file"""
        filename = filedialog.askopenfilename(
            title="Select Tracking CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.csv_path_var.set(filename)
    
    def browse_video(self):
        """Browse for video file"""
        filename = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.m4v *.mpg *.mpeg"), ("All files", "*.*")]
        )
        if filename:
            self.video_path = filename
            self.video_path_entry.delete(0, tk.END)
            self.video_path_entry.insert(0, filename)
    
    def load_and_analyze(self):
        """Load CSV and analyze for potential merges"""
        csv_file = self.csv_path_var.get()
        if not csv_file or not os.path.exists(csv_file):
            messagebox.showerror("Error", "Please select a valid CSV file")
            return
        
        try:
            self.log(f"Loading CSV: {csv_file}")
            self.df = pd.read_csv(csv_file)
            
            if 'player_id' not in self.df.columns:
                messagebox.showerror("Error", "CSV file must contain 'player_id' column")
                return
            
            # Analyze
            self.log("Analyzing player ID sequences...")
            self.player_data = analyze_id_sequences(self.df)
            
            # Find potential merges
            target_count = self.target_player_count.get()
            current_count = len(self.player_data)
            needed_merges = current_count - target_count
            
            # CRITICAL: Warn about extreme consolidation requests
            if needed_merges > 2000:
                warning_msg = (
                    f"⚠️ WARNING: Extreme consolidation requested!\n\n"
                    f"Current IDs: {current_count}\n"
                    f"Target: {target_count}\n"
                    f"Required merges: ~{needed_merges}\n\n"
                    f"This may cause performance issues or crashes.\n\n"
                    f"Recommended: Start with a higher target (e.g., {min(100, current_count // 10)}) "
                    f"and consolidate in multiple passes.\n\n"
                    f"Continue anyway?"
                )
                if not messagebox.askyesno("Extreme Consolidation Warning", warning_msg):
                    self.log("⚠️ Consolidation cancelled by user")
                    return
            
            # Extract player name assignments from CSV or player_names.json
            player_name_assignments = {}
            
            # First, try to get from CSV player_name column
            track_id_col = None
            for col in ['track_id', 'player_id', 'id']:
                if col in self.df.columns:
                    track_id_col = col
                    break
            
            if track_id_col and 'player_name' in self.df.columns:
                # Get unique track_id -> player_name mappings from CSV
                for track_id in self.df[track_id_col].dropna().unique():
                    track_data = self.df[self.df[track_id_col] == track_id]
                    player_names = track_data['player_name'].dropna().unique()
                    if len(player_names) > 0:
                        player_name = str(player_names[0]).strip()
                        if player_name and player_name not in ['Guest Player', 'None', '']:
                            try:
                                track_id_int = int(track_id)
                                player_name_assignments[track_id_int] = player_name
                            except (ValueError, TypeError):
                                pass
            
            # Also check player_names.json (may have more assignments)
            if self.player_names:
                for track_id, player_name in self.player_names.items():
                    if player_name and player_name not in ['Guest Player', 'None', '']:
                        try:
                            track_id_int = int(track_id)
                            # CSV takes precedence, but fill in gaps from player_names.json
                            if track_id_int not in player_name_assignments:
                                player_name_assignments[track_id_int] = str(player_name)
                        except (ValueError, TypeError):
                            pass
            
            if player_name_assignments:
                self.log(f"✓ Found {len(player_name_assignments)} player name assignments - will use for merging")
            
            self.log(f"Finding potential ID merges (target: {target_count} players, ~{needed_merges} merges needed)...")
            self.suggested_merges = find_potential_merges(self.df, self.player_data, 
                                                          target_player_count=target_count,
                                                          player_name_assignments=player_name_assignments)
            
            # Update statistics
            total_players = len(self.player_data)
            total_frames = len(self.df)
            after_merge_count = total_players - len(self.suggested_merges)
            self.stats_label.config(
                text=f"Total IDs: {total_players} | After Merges: {after_merge_count} | Target: {target_count} | Suggested Merges: {len(self.suggested_merges)}"
            )
            
            # Populate merge tree
            self.refresh_merges_tree()
            
            self.log(f"✓ Analysis complete! Found {len(self.suggested_merges)} potential merges")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not load CSV: {e}")
            self.log(f"Error: {e}")
    
    def refresh_merges_tree(self):
        """Refresh the merges treeview"""
        # Clear existing
        for item in self.merges_tree.get_children():
            self.merges_tree.delete(item)
        
        # Add suggested merges
        for merge in self.suggested_merges:
            from_id = merge['from_id']
            to_id = merge['to_id']
            merge_key = (from_id, to_id)
            
            # Check status
            if from_id in self.rejected_ids or to_id in self.rejected_ids:
                status = "Rejected (ID rejected)"
                tag = 'rejected'
            elif merge_key in self.rejected_merges:
                status = "Rejected"
                tag = 'rejected'
            elif from_id in self.applied_merges:
                status = "Applied"
                tag = 'applied'
            else:
                status = "Pending"
                tag = 'pending'
            
            merge_type = merge.get('merge_type', 'direct')
            item = self.merges_tree.insert('', tk.END, values=(
                from_id,
                to_id,
                f"{merge['gap_frames']:.0f}",
                f"{merge['distance']:.1f}",
                f"{merge['avg_distance']:.1f}",
                f"{merge['score']:.4f}",
                merge_type,
                status
            ), tags=(tag,))
        
        # Configure tags for visual feedback
        self.merges_tree.tag_configure('rejected', background='#f8d7da', foreground='#721c24')  # Light red
        self.merges_tree.tag_configure('applied', background='#d4edda', foreground='#155724')  # Light green
        self.merges_tree.tag_configure('pending', background='white')
    
    def apply_merges(self):
        """Apply selected merges"""
        selected = self.merges_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select merges to apply")
            return
        
        count = 0
        skipped = 0
        for item in selected:
            values = self.merges_tree.item(item, 'values')
            from_id = int(values[0])
            to_id = int(values[1])
            merge_key = (from_id, to_id)
            
            # Skip if rejected
            if from_id in self.rejected_ids or to_id in self.rejected_ids:
                skipped += 1
                continue
            if merge_key in self.rejected_merges:
                skipped += 1
                continue
            
            if from_id not in self.applied_merges:
                self.applied_merges[from_id] = to_id
                count += 1
                self.log(f"Applied merge: ID {from_id} → ID {to_id}")
        
        self.refresh_merges_tree()
        if count > 0:
            self.log(f"✓ Applied {count} merges")
        if skipped > 0:
            self.log(f"  Skipped {skipped} rejected merges")
    
    def reject_merges(self):
        """Reject selected merges and optionally all connected IDs"""
        selected = self.merges_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select merges to reject")
            return
        
        rejected_count = 0
        rejected_ids_set = set()
        
        for item in selected:
            values = self.merges_tree.item(item, 'values')
            from_id = int(values[0])
            to_id = int(values[1])
            merge_key = (from_id, to_id)
            
            # Reject this specific merge
            self.rejected_merges.add(merge_key)
            rejected_count += 1
            
            # Find all connected IDs (IDs that merge to/from these IDs)
            connected_ids = set()
            connected_ids.add(from_id)
            connected_ids.add(to_id)
            
            # Find all merges that involve these IDs
            for merge in self.suggested_merges:
                m_from = merge['from_id']
                m_to = merge['to_id']
                if m_from == from_id or m_from == to_id or m_to == from_id or m_to == to_id:
                    connected_ids.add(m_from)
                    connected_ids.add(m_to)
            
            # Ask user if they want to reject all connected IDs
            if len(connected_ids) > 2:
                response = messagebox.askyesno(
                    "Reject Connected IDs?",
                    f"Rejecting merge {from_id} → {to_id}.\n\n"
                    f"This will affect {len(connected_ids)} connected IDs:\n"
                    f"{', '.join(map(str, sorted(connected_ids)[:10]))}"
                    f"{'...' if len(connected_ids) > 10 else ''}\n\n"
                    f"Reject all connected IDs and their merges?"
                )
                if response:
                    rejected_ids_set.update(connected_ids)
                    # Reject all merges involving these IDs
                    for merge in self.suggested_merges:
                        if merge['from_id'] in connected_ids or merge['to_id'] in connected_ids:
                            self.rejected_merges.add((merge['from_id'], merge['to_id']))
                    self.log(f"Rejected {len(connected_ids)} IDs and all their merges")
            else:
                self.log(f"Rejected merge: ID {from_id} → ID {to_id}")
        
        # Add to rejected IDs set
        self.rejected_ids.update(rejected_ids_set)
        
        # Remove from applied merges if they were applied
        for from_id, to_id in list(self.applied_merges.items()):
            if from_id in self.rejected_ids or to_id in self.rejected_ids:
                del self.applied_merges[from_id]
                self.log(f"Removed applied merge {from_id} → {to_id} (ID rejected)")
        
        self.refresh_merges_tree()
        self.log(f"✓ Rejected {rejected_count} merge(s)")
        if rejected_ids_set:
            self.log(f"  Rejected {len(rejected_ids_set)} connected IDs")
    
    def apply_all_merges(self):
        """Apply all suggested merges"""
        if not self.suggested_merges:
            messagebox.showwarning("Warning", "No merges to apply")
            return
        
        # CRITICAL: Warn about applying too many merges at once
        total_merges = len(self.suggested_merges)
        if total_merges > 2000:
            warning_msg = (
                f"⚠️ WARNING: Applying {total_merges} merges at once!\n\n"
                f"This may take a long time and could cause the UI to freeze.\n\n"
                f"Recommended: Apply merges in smaller batches (e.g., 500-1000 at a time).\n\n"
                f"Continue anyway?"
            )
            if not messagebox.askyesno("Large Merge Warning", warning_msg):
                self.log("⚠️ Merge application cancelled by user")
                return
        
        count = 0
        skipped = 0
        for merge in self.suggested_merges:
            from_id = merge['from_id']
            to_id = merge['to_id']
            merge_key = (from_id, to_id)
            
            # Skip if rejected
            if from_id in self.rejected_ids or to_id in self.rejected_ids:
                skipped += 1
                continue
            if merge_key in self.rejected_merges:
                skipped += 1
                continue
            
            if from_id not in self.applied_merges:
                # Check if 'to_id' is itself merged (chain resolution)
                final_to_id = to_id
                max_chain_iterations = 1000  # Safety limit
                chain_iterations = 0
                while final_to_id in self.applied_merges and chain_iterations < max_chain_iterations:
                    final_to_id = self.applied_merges[final_to_id]
                    chain_iterations += 1
                
                if chain_iterations >= max_chain_iterations:
                    self.log(f"⚠️ Warning: Max chain iterations reached for merge {from_id} → {to_id}")
                
                self.applied_merges[from_id] = final_to_id
                count += 1
                if count % 100 == 0:  # Log every 100 merges to avoid spam
                    self.log(f"Applied {count}/{total_merges} merges...")
                    self.root.update()  # Update UI to prevent freezing
        
        if skipped > 0:
            self.log(f"Skipped {skipped} rejected merges")
        
        self.refresh_merges_tree()
        self.log(f"✓ Applied all {count} merges")
        
        # Show preview of consolidation
        if self.df is not None and self.player_data is not None:
            resolved_map = resolve_merge_chains(self.applied_merges)
            original_count = len(self.player_data)
            
            # Count unique final IDs after resolution
            all_source_ids = set(self.applied_merges.keys())
            all_target_ids = set(self.applied_merges.values())
            
            # Get all unique IDs that exist in the data
            all_ids = set(self.player_data.keys())
            
            # Build a map of what each ID resolves to
            final_id_map = {}
            for pid in all_ids:
                if pid in resolved_map:
                    # This ID is merged, find its final target
                    final_id_map[pid] = resolved_map[pid]
                else:
                    # This ID is not merged, it stays as itself
                    final_id_map[pid] = pid
            
            # Count unique final IDs
            unique_final_ids = set(final_id_map.values())
            consolidated_count = len(unique_final_ids)
            
            self.log(f"  Preview: {original_count} IDs → {consolidated_count} IDs")
        
        messagebox.showinfo("Success", f"Applied {count} merges")
    
    def clear_merges(self):
        """Clear all applied merges and rejections"""
        self.applied_merges = {}
        self.rejected_merges = set()
        self.rejected_ids = set()
        self.refresh_merges_tree()
        self.log("Cleared all merges and rejections")
    
    def open_playback_for_selected(self):
        """Open playback viewer for selected merge to see the IDs in action"""
        selected = self.merges_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a merge to view")
            return
        
        if not self.video_path or not os.path.exists(self.video_path):
            messagebox.showerror("Error", "Please load the video file first")
            return
        
        if self.df is None:
            messagebox.showerror("Error", "Please load and analyze the CSV file first")
            return
        
        # Get the first selected merge
        item = selected[0]
        values = self.merges_tree.item(item, 'values')
        from_id = int(values[0])
        to_id = int(values[1])
        
        # Find frames where these IDs appear
        from_frames = self.df[self.df['player_id'] == from_id]['frame'].unique().tolist()
        to_frames = self.df[self.df['player_id'] == to_id]['frame'].unique().tolist()
        
        if not from_frames and not to_frames:
            messagebox.showwarning("Warning", f"Could not find frames for IDs {from_id} and {to_id}")
            return
        
        # Find frames for each ID (for side-by-side comparison)
        from_frames_sorted = sorted([int(f) for f in from_frames]) if from_frames else []
        to_frames_sorted = sorted([int(f) for f in to_frames]) if to_frames else []
        
        # Get first frame for each ID
        frame1 = from_frames_sorted[0] if from_frames_sorted else None
        frame2 = to_frames_sorted[0] if to_frames_sorted else None
        
        if not frame1 and not frame2:
            messagebox.showwarning("Warning", f"Could not find frames for IDs {from_id} and {to_id}")
            return
        
        # Use defaults if one is missing
        if not frame1:
            frame1 = frame2 if frame2 else 0
            self.log(f"  Warning: ID {from_id} not found in frames. Using frame {frame1}")
        if not frame2:
            frame2 = frame1 if frame1 else 0
            self.log(f"  Warning: ID {to_id} not found in frames. Using frame {frame2}")
        
        self.log(f"  ID {from_id} appears in {len(from_frames_sorted)} frames (showing frame {frame1})")
        self.log(f"  ID {to_id} appears in {len(to_frames_sorted)} frames (showing frame {frame2})")
        
        # Find corresponding CSV file
        csv_path = self.csv_path_var.get()
        if not csv_path or not os.path.exists(csv_path):
            # Try to find CSV from video path
            base_name = os.path.splitext(self.video_path)[0]
            csv_path = f"{base_name}_tracking_data.csv"
            if not os.path.exists(csv_path):
                messagebox.showerror("Error", "Could not find corresponding CSV file")
                return
        
        try:
            from playback_viewer import PlaybackViewer
            
            viewer_window = tk.Toplevel(self.root)
            viewer_window.title(f"Playback Viewer - ID {from_id} → ID {to_id}")
            viewer_window.geometry("1200x800")
            viewer_window.transient(self.root)
            
            # Ensure window opens on top
            viewer_window.lift()
            viewer_window.attributes('-topmost', True)
            viewer_window.focus_force()
            viewer_window.after(200, lambda: viewer_window.attributes('-topmost', False))
            
            # Create playback viewer in comparison mode (side-by-side)
            app = PlaybackViewer(
                viewer_window,
                video_path=self.video_path,
                csv_path=csv_path,
                comparison_mode=True,
                frame1=frame1,
                frame2=frame2,
                id1=int(from_id),
                id2=int(to_id)
            )
            
            self.log(f"✓ Playback viewer opened in comparison mode")
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import playback_viewer.py: {str(e)}\n\n"
                               "Make sure playback_viewer.py is in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open playback viewer: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def export_consolidated(self):
        """Export consolidated CSV"""
        if self.df is None:
            messagebox.showerror("Error", "Please load and analyze CSV first")
            return
        
        if not self.applied_merges:
            messagebox.showwarning("Warning", "No merges applied. Nothing to export.")
            return
        
        # Ask for output filename
        output_file = filedialog.asksaveasfilename(
            title="Save Consolidated CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not output_file:
            return
        
        try:
            # CRITICAL FIX: Show progress for large datasets
            self.log("Applying merges to consolidate IDs...")
            self.root.update()  # Update GUI to show progress
            
            # Apply merges (with chain resolution)
            # CRITICAL FIX: Process in chunks if DataFrame is very large to avoid memory crash
            df_size_mb = self.df.memory_usage(deep=True).sum() / 1024 / 1024
            if df_size_mb > 500:  # If DataFrame is > 500MB, process in chunks
                self.log(f"  Large dataset detected ({df_size_mb:.1f}MB), processing in chunks...")
                df_consolidated = consolidate_ids_chunked(self.df, self.applied_merges, chunk_size=100000)
            else:
                df_consolidated = consolidate_ids(self.df, self.applied_merges)
            
            self.log("  Merges applied successfully")
            self.root.update()
            
            # Build mapping of old IDs to new consolidated IDs
            resolved_map = resolve_merge_chains(self.applied_merges)
            
            # Update player names for consolidated IDs
            consolidated_player_names = {}
            
            # CRITICAL FIX: Use dropna() to get unique IDs more efficiently
            # Get all unique consolidated IDs (exclude NaN)
            consolidated_ids_list = df_consolidated['player_id'].dropna().unique()
            
            for new_id in consolidated_ids_list:
                new_id_int = int(new_id)
                
                # Check if this new_id is a result of merging
                # Find the original IDs that merged into this one
                original_ids_for_new = []
                for old_id, merged_to in resolved_map.items():
                    if merged_to == new_id_int:
                        original_ids_for_new.append(old_id)
                
                # If this ID wasn't merged, it might be the target itself
                if not original_ids_for_new and new_id_int not in resolved_map:
                    # This ID was never merged, it's a final ID
                    original_ids_for_new = [new_id_int]
                elif new_id_int in resolved_map:
                    # CRITICAL FIX: This shouldn't happen after consolidation - if new_id_int is in resolved_map
                    # as a key, it means it was a SOURCE ID that got merged, so it shouldn't be in the
                    # final consolidated list. However, if it is, resolved_map[new_id_int] is already
                    # the final target (resolve_merge_chains already resolved all chains).
                    # So we should use resolved_map[new_id_int] directly without re-resolving.
                    final_target = resolved_map[new_id_int]
                    # Verify it's not in resolved_map (should be a final ID)
                    if final_target in resolved_map:
                        # This indicates a bug - log it but use the value anyway
                        self.log(f"⚠ Warning: ID {new_id_int} resolved to {final_target} which is still in merge map (possible bug)")
                    original_ids_for_new = [final_target]
                else:
                    # This ID is not in resolved_map (not a source), and no IDs merged into it
                    # It's a final ID that was never merged
                    original_ids_for_new = [new_id_int]
                
                # Try to find a name for this consolidated ID
                name_found = None
                
                # Priority 1: Check seed_config for mappings
                if self.seed_config and "player_mappings" in self.seed_config:
                    for orig_id in original_ids_for_new:
                        orig_id_str = str(orig_id)
                        if orig_id_str in self.seed_config["player_mappings"]:
                            name_found = self.seed_config["player_mappings"][orig_id_str]
                            break
                
                # Priority 2: Check player_names.json
                if not name_found:
                    for orig_id in original_ids_for_new:
                        if orig_id in self.player_names:
                            name_found = self.player_names[orig_id]
                            break
                
                # Priority 3: Use the "to_id" name if available (prefer keeping target ID's name)
                if not name_found and new_id_int in self.player_names:
                    name_found = self.player_names[new_id_int]
                
                # If we found a name, use it; otherwise use generic
                if name_found:
                    consolidated_player_names[new_id_int] = name_found
                else:
                    # Try to get name from any of the merged IDs
                    for orig_id in original_ids_for_new:
                        if orig_id in self.player_names:
                            consolidated_player_names[new_id_int] = self.player_names[orig_id]
                            break
            
            # Save updated player names
            if consolidated_player_names:
                # Convert to string keys for JSON
                names_to_save = {str(k): v for k, v in consolidated_player_names.items()}
                with open("player_names.json", 'w') as f:
                    json.dump(names_to_save, f, indent=4)
                self.log(f"✓ Updated player_names.json with {len(consolidated_player_names)} consolidated names")
            
            # CRITICAL FIX: Save CSV in chunks to avoid memory crash
            self.log("Writing consolidated CSV to disk...")
            self.root.update()
            
            # For very large DataFrames, write in chunks
            if len(df_consolidated) > 500000:  # If > 500k rows, write in chunks
                self.log(f"  Large dataset ({len(df_consolidated)} rows), writing in chunks...")
                # Write header first
                df_consolidated.head(0).to_csv(output_file, index=False, mode='w')
                # Write data in chunks
                chunk_size = 100000
                for i in range(0, len(df_consolidated), chunk_size):
                    chunk = df_consolidated.iloc[i:i+chunk_size]
                    chunk.to_csv(output_file, index=False, mode='a', header=False)
                    if i % (chunk_size * 5) == 0:
                        self.log(f"  Progress: {i}/{len(df_consolidated)} rows written...")
                        self.root.update()
            else:
                # Normal write for smaller datasets
                df_consolidated.to_csv(output_file, index=False)
            
            self.log("  CSV file written successfully")
            self.root.update()
            
            # Show statistics
            original_ids = len(self.player_data)
            consolidated_ids = df_consolidated['player_id'].nunique()
            reduction = original_ids - consolidated_ids
            target_count = self.target_player_count.get()
            
            self.log(f"✓ Exported consolidated CSV: {output_file}")
            self.log(f"  Original IDs: {original_ids}")
            self.log(f"  Consolidated IDs: {consolidated_ids}")
            self.log(f"  IDs Merged: {reduction}")
            self.log(f"  Target Count: {target_count}")
            
            # Check if we reached target
            if consolidated_ids <= target_count:
                status_msg = f"✓ Reached target! ({consolidated_ids} ≤ {target_count})"
            else:
                status_msg = f"⚠ Still above target ({consolidated_ids} > {target_count})"
            
            messagebox.showinfo("Success", 
                                  f"Consolidated CSV exported!\n\n"
                                  f"Original IDs: {original_ids}\n"
                                  f"Consolidated IDs: {consolidated_ids}\n"
                                  f"IDs Merged: {reduction}\n"
                                  f"Target: {target_count}\n\n"
                                  f"{status_msg}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Could not export CSV: {e}")
            self.log(f"Error: {e}")
    
    def open_player_names_editor(self):
        """Open player names editor window"""
        editor_window = tk.Toplevel(self.root)
        editor_window.title("Player Names Manager")
        editor_window.geometry("800x600")
        editor_window.transient(self.root)
        
        # Ensure window opens on top
        editor_window.lift()
        editor_window.attributes('-topmost', True)
        editor_window.focus_force()
        editor_window.after(200, lambda: editor_window.attributes('-topmost', False))
        
        # Main frame
        main_frame = ttk.Frame(editor_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Info label
        info_label = ttk.Label(main_frame, 
                              text=f"Loaded {len(self.player_names)} player name mappings.\n"
                                   f"After consolidation, names will be mapped to the final consolidated IDs.",
                              foreground="gray")
        info_label.pack(pady=5)
        
        # Check for duplicate names
        name_to_ids = {}
        for pid, name in self.player_names.items():
            if name not in name_to_ids:
                name_to_ids[name] = []
            name_to_ids[name].append(pid)
        
        duplicates = {name: ids for name, ids in name_to_ids.items() if len(ids) > 1}
        if duplicates:
            dup_text = f"⚠ Warning: {len(duplicates)} duplicate name(s) found: "
            dup_list = [f"{name} (IDs: {', '.join(map(str, ids))})" for name, ids in list(duplicates.items())[:3]]
            dup_text += ", ".join(dup_list)
            if len(duplicates) > 3:
                dup_text += f", ... ({len(duplicates) - 3} more)"
            dup_label = ttk.Label(main_frame, text=dup_text, foreground="orange", font=("Arial", 9, "bold"))
            dup_label.pack(pady=5)
        
        # Player names list
        list_frame = ttk.LabelFrame(main_frame, text="Player Name Mappings", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Treeview for player names
        columns = ('ID', 'Name', 'Status')
        names_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            names_tree.heading(col, text=col)
            if col == 'ID':
                names_tree.column(col, width=100)
            elif col == 'Name':
                names_tree.column(col, width=300)
            else:
                names_tree.column(col, width=200)
        
        names_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=names_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        names_tree.configure(yscrollcommand=scrollbar.set)
        
        # Populate tree
        # Check for duplicate names
        name_to_ids = {}
        for pid, name in self.player_names.items():
            if name not in name_to_ids:
                name_to_ids[name] = []
            name_to_ids[name].append(pid)
        
        for player_id, name in sorted(self.player_names.items()):
            # Check if this ID will be consolidated
            status = "Will be consolidated"
            if self.applied_merges:
                resolved_map = resolve_merge_chains(self.applied_merges)
                if player_id in resolved_map:
                    final_id = resolved_map[player_id]
                    status = f"→ ID {final_id}"
                elif player_id in resolved_map.values():
                    status = "Target ID"
                else:
                    status = "Unchanged"
            else:
                status = "Not consolidated yet"
            
            # Mark duplicates
            if len(name_to_ids.get(name, [])) > 1:
                status += " [DUPLICATE]"
            
            names_tree.insert('', tk.END, values=(player_id, name, status), 
                            tags=('duplicate' if len(name_to_ids.get(name, [])) > 1 else 'normal'))
        
        # Configure tag colors
        names_tree.tag_configure('duplicate', background='#fff3cd')  # Light yellow for duplicates
        names_tree.tag_configure('normal', background='white')
        
        # Edit section
        edit_frame = ttk.LabelFrame(main_frame, text="Edit Selected Player", padding="10")
        edit_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(edit_frame, text="ID:").grid(row=0, column=0, sticky=tk.W, padx=5)
        id_var = tk.StringVar()
        id_entry = ttk.Entry(edit_frame, textvariable=id_var, state='readonly', width=15)
        id_entry.grid(row=0, column=1, padx=5)
        
        ttk.Label(edit_frame, text="Name:").grid(row=0, column=2, sticky=tk.W, padx=5)
        name_var = tk.StringVar()
        name_entry = ttk.Entry(edit_frame, textvariable=name_var, width=30)
        name_entry.grid(row=0, column=3, padx=5)
        
        def on_select(event):
            selection = names_tree.selection()
            if selection:
                item = names_tree.item(selection[0])
                values = item['values']
                id_var.set(str(values[0]))
                name_var.set(str(values[1]))
        
        names_tree.bind('<<TreeviewSelect>>', on_select)
        
        def save_name():
            try:
                player_id = int(id_var.get())
                new_name = name_var.get().strip()
                if not new_name:
                    messagebox.showwarning("Warning", "Name cannot be empty")
                    return
                
                self.player_names[player_id] = new_name
                
                # Update tree
                selection = names_tree.selection()
                if selection:
                    # Recalculate status
                    status = names_tree.item(selection[0])['values'][2]
                    # Remove [DUPLICATE] tag if present
                    if "[DUPLICATE]" in status:
                        status = status.replace(" [DUPLICATE]", "")
                    
                    # Check if new name is duplicate
                    name_to_ids_check = {}
                    for pid, name in self.player_names.items():
                        if name not in name_to_ids_check:
                            name_to_ids_check[name] = []
                        name_to_ids_check[name].append(pid)
                    
                    if len(name_to_ids_check.get(new_name, [])) > 1:
                        status += " [DUPLICATE]"
                        names_tree.item(selection[0], values=(player_id, new_name, status), tags=('duplicate',))
                    else:
                        names_tree.item(selection[0], values=(player_id, new_name, status), tags=('normal',))
                
                # Save to file
                names_to_save = {str(k): v for k, v in self.player_names.items()}
                with open("player_names.json", 'w') as f:
                    json.dump(names_to_save, f, indent=4)
                
                # Refresh preview
                update_preview()
                
                # Update duplicate warning
                name_to_ids_updated = {}
                for pid, name in self.player_names.items():
                    if name not in name_to_ids_updated:
                        name_to_ids_updated[name] = []
                    name_to_ids_updated[name].append(pid)
                
                duplicates_updated = {name: ids for name, ids in name_to_ids_updated.items() if len(ids) > 1}
                if duplicates_updated:
                    dup_text = f"⚠ Warning: {len(duplicates_updated)} duplicate name(s) found: "
                    dup_list = [f"{name} (IDs: {', '.join(map(str, ids))})" for name, ids in list(duplicates_updated.items())[:3]]
                    dup_text += ", ".join(dup_list)
                    if len(duplicates_updated) > 3:
                        dup_text += f", ... ({len(duplicates_updated) - 3} more)"
                    info_label.config(text=f"Loaded {len(self.player_names)} player name mappings.\n"
                                          f"After consolidation, names will be mapped to the final consolidated IDs.\n\n"
                                          f"{dup_text}", foreground="gray")
                else:
                    info_label.config(text=f"Loaded {len(self.player_names)} player name mappings.\n"
                                          f"After consolidation, names will be mapped to the final consolidated IDs.",
                                      foreground="gray")
                
                messagebox.showinfo("Success", f"Updated name for ID {player_id}")
                self.log(f"Updated player name: ID {player_id} → {new_name}")
                
            except ValueError:
                messagebox.showerror("Error", "Please select a player first")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save name: {e}")
        
        ttk.Button(edit_frame, text="Save Name", command=save_name).grid(row=0, column=4, padx=5)
        
        def clear_name():
            """Clear the selected player's name (set to empty)"""
            try:
                player_id = int(id_var.get())
                if not player_id:
                    messagebox.showwarning("Warning", "Please select a player first")
                    return
                
                # Clear the name (set to empty string)
                self.player_names[player_id] = ""
                
                # Update tree
                selection = names_tree.selection()
                if selection:
                    status = names_tree.item(selection[0])['values'][2]
                    if "[DUPLICATE]" in status:
                        status = status.replace(" [DUPLICATE]", "")
                    names_tree.item(selection[0], values=(player_id, "", status), tags=('normal',))
                
                # Save to file
                names_to_save = {str(k): v for k, v in self.player_names.items()}
                with open("player_names.json", 'w') as f:
                    json.dump(names_to_save, f, indent=4)
                
                # Clear the name entry
                name_var.set("")
                
                # Refresh preview
                update_preview()
                
                messagebox.showinfo("Success", f"Cleared name for ID {player_id}")
                self.log(f"Cleared player name: ID {player_id}")
                
            except ValueError:
                messagebox.showwarning("Warning", "Please select a player first")
            except Exception as e:
                messagebox.showerror("Error", f"Could not clear name: {e}")
        
        def clear_all_names():
            """Clear all player names (reset to empty)"""
            if messagebox.askyesno("Confirm", "Are you sure you want to clear ALL player names? This cannot be undone."):
                try:
                    # Clear all names
                    for player_id in list(self.player_names.keys()):
                        self.player_names[player_id] = ""
                    
                    # Save to file
                    names_to_save = {str(k): v for k, v in self.player_names.items()}
                    with open("player_names.json", 'w') as f:
                        json.dump(names_to_save, f, indent=4)
                    
                    # Refresh the tree
                    names_tree.delete(*names_tree.get_children())
                    for player_id, name in sorted(self.player_names.items()):
                        status = "Not consolidated yet"
                        names_tree.insert('', tk.END, values=(player_id, name or "", status), tags=('normal',))
                    
                    # Clear edit fields
                    id_var.set("")
                    name_var.set("")
                    
                    # Refresh preview
                    update_preview()
                    
                    # Update info label
                    info_label.config(text=f"Cleared all {len(self.player_names)} player name mappings.",
                                    foreground="gray")
                    
                    messagebox.showinfo("Success", "All player names have been cleared")
                    self.log("Cleared all player names")
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Could not clear names: {e}")
        
        ttk.Button(edit_frame, text="Clear Name", command=clear_name).grid(row=0, column=5, padx=5)
        
        # Clear all button (separate section)
        clear_frame = ttk.Frame(main_frame)
        clear_frame.pack(fill=tk.X, pady=5)
        ttk.Button(clear_frame, text="Clear All Names", command=clear_all_names,
                  style="Danger.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Label(clear_frame, text="(Warning: This will clear ALL player names)", 
                 foreground="red", font=("Arial", 8)).pack(side=tk.LEFT, padx=5)
        
        # Configure danger button style
        style = ttk.Style()
        style.configure("Danger.TButton", foreground="red")
        
        # Preview consolidated names
        preview_frame = ttk.LabelFrame(main_frame, text="Preview Consolidated Names", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        preview_text = scrolledtext.ScrolledText(preview_frame, height=8, wrap=tk.WORD)
        preview_text.pack(fill=tk.BOTH, expand=True)
        
        def update_preview():
            preview_text.delete(1.0, tk.END)
            if not self.applied_merges or self.df is None:
                preview_text.insert(tk.END, "Load CSV and apply merges to see consolidated name preview.")
                return
            
            resolved_map = resolve_merge_chains(self.applied_merges)
            consolidated_ids = set()
            
            # Get all final consolidated IDs
            for old_id, new_id in resolved_map.items():
                consolidated_ids.add(new_id)
            
            # Add IDs that weren't merged
            if self.df is not None:
                all_ids = set(self.df['player_id'].dropna().unique().astype(int))
                for pid in all_ids:
                    if pid not in resolved_map:
                        consolidated_ids.add(pid)
            
            preview_text.insert(tk.END, f"After consolidation, you will have {len(consolidated_ids)} player IDs:\n\n")
            
            # Track which names are used
            name_usage = {}
            consolidated_name_map = {}
            
            for final_id in sorted(consolidated_ids):
                # Find name for this consolidated ID
                name = None
                # Check if this ID has a name
                if final_id in self.player_names:
                    name = self.player_names[final_id]
                else:
                    # Find original IDs that merged into this
                    for old_id, merged_to in resolved_map.items():
                        if merged_to == final_id and old_id in self.player_names:
                            name = self.player_names[old_id]
                            break
                
                consolidated_name_map[final_id] = name
                if name:
                    if name not in name_usage:
                        name_usage[name] = []
                    name_usage[name].append(final_id)
            
            # Show consolidated IDs with names
            for final_id in sorted(consolidated_ids):
                name = consolidated_name_map[final_id]
                if name:
                    # Check for duplicates
                    if len(name_usage.get(name, [])) > 1:
                        preview_text.insert(tk.END, f"ID {final_id}: {name} ⚠ DUPLICATE\n", "duplicate")
                    else:
                        preview_text.insert(tk.END, f"ID {final_id}: {name}\n")
                else:
                    preview_text.insert(tk.END, f"ID {final_id}: (no name assigned)\n")
            
            # Highlight duplicates
            preview_text.tag_configure("duplicate", foreground="red", font=("Arial", 9, "bold"))
            
            # Show summary of duplicates
            duplicates = {name: ids for name, ids in name_usage.items() if len(ids) > 1}
            if duplicates:
                preview_text.insert(tk.END, f"\n⚠ WARNING: {len(duplicates)} duplicate name(s) after consolidation:\n")
                for name, ids in duplicates.items():
                    preview_text.insert(tk.END, f"  '{name}' → IDs: {', '.join(map(str, sorted(ids)))}\n", "duplicate")
        
        update_preview()
        
        # Buttons for preview
        preview_buttons = ttk.Frame(preview_frame)
        preview_buttons.pack(pady=5)
        ttk.Button(preview_buttons, text="Refresh Preview", command=update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Button(preview_buttons, text="Edit Duplicates", command=self.edit_duplicates_in_preview).pack(side=tk.LEFT, padx=5)
    
    def edit_duplicates_in_preview(self):
        """Open editor to fix duplicate names in consolidated preview"""
        if not self.applied_merges or self.df is None:
            messagebox.showwarning("Warning", "Please load CSV and apply merges first")
            return
        
        resolved_map = resolve_merge_chains(self.applied_merges)
        consolidated_ids = set()
        
        # Get all final consolidated IDs
        for old_id, new_id in resolved_map.items():
            consolidated_ids.add(new_id)
        
        # Add IDs that weren't merged
        all_ids = set(self.df['player_id'].dropna().unique().astype(int))
        for pid in all_ids:
            if pid not in resolved_map:
                consolidated_ids.add(pid)
        
        # Find duplicates
        name_usage = {}
        consolidated_name_map = {}
        
        for final_id in sorted(consolidated_ids):
            name = None
            if final_id in self.player_names:
                name = self.player_names[final_id]
            else:
                for old_id, merged_to in resolved_map.items():
                    if merged_to == final_id and old_id in self.player_names:
                        name = self.player_names[old_id]
                        break
            
            consolidated_name_map[final_id] = name
            if name:
                if name not in name_usage:
                    name_usage[name] = []
                name_usage[name].append(final_id)
        
        duplicates = {name: ids for name, ids in name_usage.items() if len(ids) > 1}
        
        if not duplicates:
            messagebox.showinfo("No Duplicates", "No duplicate names found after consolidation!")
            return
        
        # Open editor window
        editor_window = tk.Toplevel(self.root)
        editor_window.title("Edit Duplicate Names")
        editor_window.geometry("600x500")
        editor_window.transient(self.root)
        editor_window.lift()
        editor_window.attributes('-topmost', True)
        editor_window.after(200, lambda: editor_window.attributes('-topmost', False))
        
        main_frame = ttk.Frame(editor_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=f"Found {len(duplicates)} duplicate name(s). Edit to resolve:", 
                 font=("Arial", 10, "bold")).pack(pady=5)
        
        # Treeview for duplicates
        columns = ('ID', 'Current Name', 'New Name')
        dup_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            dup_tree.heading(col, text=col)
            if col == 'ID':
                dup_tree.column(col, width=80)
            else:
                dup_tree.column(col, width=200)
        
        dup_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=dup_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        dup_tree.configure(yscrollcommand=scrollbar.set)
        
        # Populate with duplicates
        name_edits = {}  # final_id: new_name
        for name, ids in duplicates.items():
            for final_id in sorted(ids):
                dup_tree.insert('', tk.END, values=(final_id, name, name), 
                              tags=('duplicate',))
                name_edits[final_id] = name
        
        dup_tree.tag_configure('duplicate', background='#fff3cd')
        
        # Edit frame
        edit_frame = ttk.LabelFrame(main_frame, text="Edit Selected", padding="10")
        edit_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(edit_frame, text="ID:").grid(row=0, column=0, sticky=tk.W, padx=5)
        edit_id_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=edit_id_var, state='readonly', width=15).grid(row=0, column=1, padx=5)
        
        ttk.Label(edit_frame, text="New Name:").grid(row=0, column=2, sticky=tk.W, padx=5)
        edit_name_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=edit_name_var, width=30).grid(row=0, column=3, padx=5)
        
        def on_dup_select(event):
            selection = dup_tree.selection()
            if selection:
                item = dup_tree.item(selection[0])
                values = item['values']
                edit_id_var.set(str(values[0]))
                edit_name_var.set(str(values[1]))
        
        dup_tree.bind('<<TreeviewSelect>>', on_dup_select)
        
        def save_dup_edit():
            try:
                final_id = int(edit_id_var.get())
                new_name = edit_name_var.get().strip()
                if not new_name:
                    messagebox.showwarning("Warning", "Name cannot be empty")
                    return
                
                # Update the name for this consolidated ID
                name_edits[final_id] = new_name
                
                # Update tree
                selection = dup_tree.selection()
                if selection:
                    dup_tree.item(selection[0], values=(final_id, new_name, new_name))
                
                # Update player_names
                self.player_names[final_id] = new_name
                
                messagebox.showinfo("Success", f"Updated ID {final_id} to '{new_name}'")
            except ValueError:
                messagebox.showerror("Error", "Please select a duplicate to edit")
        
        ttk.Button(edit_frame, text="Save Edit", command=save_dup_edit).grid(row=0, column=4, padx=5)
        
        # Save all button
        def save_all_edits():
            # Save all edits to player_names.json
            names_to_save = {str(k): v for k, v in self.player_names.items()}
            with open("player_names.json", 'w') as f:
                json.dump(names_to_save, f, indent=4)
            
            messagebox.showinfo("Success", f"Saved all {len(name_edits)} name edits!")
            editor_window.destroy()
            # Refresh preview in main window
            if hasattr(self, 'open_player_names_editor'):
                # Trigger refresh if player names editor is open
                pass
        
        ttk.Button(main_frame, text="Save All Edits", command=save_all_edits).pack(pady=5)
    
    def open_team_names_editor(self):
        """Open team names editor window"""
        editor_window = tk.Toplevel(self.root)
        editor_window.title("Team Names Manager")
        editor_window.geometry("700x500")
        editor_window.transient(self.root)
        
        editor_window.lift()
        editor_window.attributes('-topmost', True)
        editor_window.focus_force()
        editor_window.after(200, lambda: editor_window.attributes('-topmost', False))
        
        main_frame = ttk.Frame(editor_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Info
        ttk.Label(main_frame, 
                 text=f"Manage team assignments for {len(self.player_names)} players.\n"
                      f"Teams are used for visualization and statistics.",
                 foreground="gray").pack(pady=5)
        
        # Team names list
        list_frame = ttk.LabelFrame(main_frame, text="Team Assignments", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ('Player ID', 'Player Name', 'Team')
        teams_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            teams_tree.heading(col, text=col)
            if col == 'Player ID':
                teams_tree.column(col, width=100)
            elif col == 'Player Name':
                teams_tree.column(col, width=250)
            else:
                teams_tree.column(col, width=150)
        
        teams_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=teams_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        teams_tree.configure(yscrollcommand=scrollbar.set)
        
        # Populate tree
        for player_id in sorted(self.player_names.keys()):
            name = self.player_names.get(player_id, f"Player {player_id}")
            team = self.team_names.get(player_id, "Unassigned")
            teams_tree.insert('', tk.END, values=(player_id, name, team))
        
        # Edit section
        edit_frame = ttk.LabelFrame(main_frame, text="Edit Selected Player Team", padding="10")
        edit_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(edit_frame, text="Player ID:").grid(row=0, column=0, sticky=tk.W, padx=5)
        team_id_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=team_id_var, state='readonly', width=15).grid(row=0, column=1, padx=5)
        
        ttk.Label(edit_frame, text="Player Name:").grid(row=0, column=2, sticky=tk.W, padx=5)
        team_name_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=team_name_var, state='readonly', width=25).grid(row=0, column=3, padx=5)
        
        ttk.Label(edit_frame, text="Team:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=(5, 0))
        team_var = tk.StringVar()
        team_combo = ttk.Combobox(edit_frame, textvariable=team_var, width=20, 
                                 values=["Team 1", "Team 2", "Unassigned", "Coach", "Referee"])
        team_combo.grid(row=1, column=1, padx=5, pady=(5, 0))
        
        def on_team_select(event):
            selection = teams_tree.selection()
            if selection:
                item = teams_tree.item(selection[0])
                values = item['values']
                team_id_var.set(str(values[0]))
                team_name_var.set(str(values[1]))
                team_var.set(str(values[2]))
        
        teams_tree.bind('<<TreeviewSelect>>', on_team_select)
        
        def save_team():
            try:
                player_id = int(team_id_var.get())
                new_team = team_var.get().strip()
                if not new_team:
                    messagebox.showwarning("Warning", "Please select a team")
                    return
                
                self.team_names[player_id] = new_team
                
                # Update tree
                selection = teams_tree.selection()
                if selection:
                    values = list(teams_tree.item(selection[0])['values'])
                    values[2] = new_team
                    teams_tree.item(selection[0], values=values)
                
                # Save to file
                with open("player_teams.json", 'w') as f:
                    json.dump({str(k): v for k, v in self.team_names.items()}, f, indent=4)
                
                messagebox.showinfo("Success", f"Updated team for player {player_id}")
                self.log(f"Updated team assignment: Player {player_id} → {new_team}")
            except ValueError:
                messagebox.showerror("Error", "Please select a player first")
        
        ttk.Button(edit_frame, text="Save Team", command=save_team).grid(row=1, column=2, padx=5, pady=(5, 0))
    
    def generate_heatmap(self):
        """Generate heatmap from consolidated CSV"""
        if self.df is None:
            messagebox.showerror("Error", "Please load and analyze CSV first")
            return
        
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showerror("Error", "matplotlib is not available. Please install it: pip install matplotlib")
            return
        
        try:
            # Check if we have a consolidated CSV, otherwise use current df
            csv_file = self.csv_path_var.get()
            if not csv_file or not os.path.exists(csv_file):
                messagebox.showerror("Error", "Please load a CSV file first")
                return
            
            # Ask for output filename
            output_file = filedialog.asksaveasfilename(
                title="Save Heatmap",
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
            )
            
            if not output_file:
                return
            
            self.log("Generating heatmap from consolidated data...")
            
            # Use consolidated data if available, otherwise use original
            if self.applied_merges:
                df_consolidated = consolidate_ids(self.df, self.applied_merges)
                self.log(f"  Using consolidated data ({len(self.applied_merges)} merges applied)")
            else:
                df_consolidated = self.df
                self.log("  Using original data (no merges applied)")
            
            # Extract player positions
            if 'player_x' not in df_consolidated.columns or 'player_y' not in df_consolidated.columns:
                messagebox.showerror("Error", "CSV file must contain 'player_x' and 'player_y' columns")
                return
            
            # Filter out NaN values
            valid_positions = df_consolidated.dropna(subset=['player_x', 'player_y'])
            
            if len(valid_positions) == 0:
                messagebox.showerror("Error", "No valid position data found in CSV")
                return
            
            # Get positions
            x_positions = valid_positions['player_x'].values
            y_positions = valid_positions['player_y'].values
            
            # Get video dimensions if available (from original CSV metadata or estimate)
            # Try to get max dimensions as frame size
            max_x = max(x_positions) if len(x_positions) > 0 else 1920
            max_y = max(y_positions) if len(y_positions) > 0 else 1080
            
            # Round up to reasonable dimensions
            width = int(np.ceil(max_x / 100) * 100) if max_x > 0 else 1920
            height = int(np.ceil(max_y / 100) * 100) if max_y > 0 else 1080
            
            # Create heatmap
            self.log(f"  Processing {len(valid_positions)} position points...")
            self.log(f"  Frame dimensions: {width}x{height}")
            
            plt.figure(figsize=(width/100, height/100), dpi=100)
            plt.hist2d(x_positions, y_positions, bins=50, cmap='hot')
            plt.colorbar(label='Player Density')
            plt.xlabel('X Position (pixels)')
            plt.ylabel('Y Position (pixels)')
            
            # Determine title
            if self.applied_merges:
                unique_ids = df_consolidated['player_id'].nunique()
                original_ids = len(self.player_data) if self.player_data else 0
                plt.title(f'Player Position Heatmap (Consolidated: {original_ids} → {unique_ids} IDs)')
            else:
                unique_ids = df_consolidated['player_id'].nunique()
                plt.title(f'Player Position Heatmap ({unique_ids} unique IDs)')
            
            plt.gca().invert_yaxis()  # Invert Y axis to match video coordinates
            plt.savefig(output_file, dpi=100, bbox_inches='tight')
            plt.close()
            
            self.log(f"✓ Heatmap saved: {output_file}")
            messagebox.showinfo("Success", f"Heatmap generated and saved to:\n{output_file}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not generate heatmap: {e}")
            self.log(f"Error: {e}")


def main():
    root = tk.Tk()
    app = IDConsolidationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

