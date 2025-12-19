"""
Per-Video Player Gallery and CSV Editor
Allows editing player references for a specific video:
- Rename players in gallery references (e.g., Cameron Melnik → Anay Rao)
- Remove players from gallery references for a video
- Remove players from CSV file for a video

Usage:
    # Rename player in gallery
    python edit_video_players.py --video "20251001_183951" --rename "Cameron Melnik" "Anay Rao"
    
    # Remove players from gallery
    python edit_video_players.py --video "20251001_183951" --remove-players "James Carlson,Ellie Hill,Rocco Piazza"
    
    # Remove players from CSV
    python edit_video_players.py --csv "path/to/file.csv" --remove-players "James Carlson,Ellie Hill,Rocco Piazza"
    
    # Combined: rename and remove in one command
    python edit_video_players.py --video "20251001_183951" --rename "Cameron Melnik" "Anay Rao" --remove-players "James Carlson,Ellie Hill,Rocco Piazza"
    
    # List players in video
    python edit_video_players.py --video "20251001_183951" --list-players
"""

import json
import os
import sys
import argparse
import pandas as pd
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path
from datetime import datetime


def load_gallery(gallery_path: str = "player_gallery.json") -> Dict:
    """Load the player gallery JSON file"""
    if not os.path.exists(gallery_path):
        print(f"❌ Gallery file not found: {gallery_path}")
        return {}
    
    with open(gallery_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_gallery(gallery: Dict, gallery_path: str = "player_gallery.json", backup: bool = True):
    """Save the gallery, optionally creating a backup first"""
    if backup and os.path.exists(gallery_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = gallery_path.replace('.json', f'_backup_{timestamp}.json')
        print(f"📦 Creating backup: {backup_path}")
        with open(gallery_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
    
    with open(gallery_path, 'w', encoding='utf-8') as f:
        json.dump(gallery, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved gallery to {gallery_path}")


def find_video_in_path(video_path: str, search_term: str) -> bool:
    """Check if video_path contains the search term (case-insensitive)"""
    if not video_path:
        return False
    # Normalize paths for comparison
    video_path_norm = os.path.normpath(os.path.abspath(video_path)).lower()
    search_term_norm = search_term.lower()
    return search_term_norm in video_path_norm or os.path.basename(video_path_norm).startswith(search_term_norm)


def get_video_path_from_search(gallery: Dict, search_term: str) -> Optional[str]:
    """Find the full video path that matches the search term"""
    if not gallery:
        return None
    
    # Try to find a matching video path in any player's reference frames
    for player_id, player_data in gallery.items():
        if not isinstance(player_data, dict):
            continue
        
        # Check reference_frames
        ref_frames = player_data.get('reference_frames', [])
        if isinstance(ref_frames, list):
            for ref in ref_frames:
                if isinstance(ref, dict):
                    video_path = ref.get('video_path', '')
                    if find_video_in_path(video_path, search_term):
                        return video_path
        
        # Check uniform_variants
        uniform_variants = player_data.get('uniform_variants', {})
        if isinstance(uniform_variants, dict):
            for variant_frames in uniform_variants.values():
                if isinstance(variant_frames, list):
                    for ref in variant_frames:
                        if isinstance(ref, dict):
                            video_path = ref.get('video_path', '')
                            if find_video_in_path(video_path, search_term):
                                return video_path
        
        # Check foot_reference_frames
        foot_frames = player_data.get('foot_reference_frames', [])
        if isinstance(foot_frames, list):
            for ref in foot_frames:
                if isinstance(ref, dict):
                    video_path = ref.get('video_path', '')
                    if find_video_in_path(video_path, search_term):
                        return video_path
    
    return None


def list_players_in_video(gallery: Dict, video_search: str) -> Dict[str, int]:
    """List all players that have reference frames from the specified video"""
    players = {}
    video_path = get_video_path_from_search(gallery, video_search)
    
    if not video_path:
        print(f"⚠ Could not find video matching '{video_search}' in gallery")
        return players
    
    print(f"📹 Found video: {os.path.basename(video_path)}")
    
    for player_id, player_data in gallery.items():
        if not isinstance(player_data, dict):
            continue
        
        player_name = player_data.get('name', 'Unknown')
        frame_count = 0
        
        # Check reference_frames
        ref_frames = player_data.get('reference_frames', [])
        if isinstance(ref_frames, list):
            for ref in ref_frames:
                if isinstance(ref, dict) and find_video_in_path(ref.get('video_path', ''), video_search):
                    frame_count += 1
        
        # Check uniform_variants
        uniform_variants = player_data.get('uniform_variants', {})
        if isinstance(uniform_variants, dict):
            for variant_frames in uniform_variants.values():
                if isinstance(variant_frames, list):
                    for ref in variant_frames:
                        if isinstance(ref, dict) and find_video_in_path(ref.get('video_path', ''), video_search):
                            frame_count += 1
        
        # Check foot_reference_frames
        foot_frames = player_data.get('foot_reference_frames', [])
        if isinstance(foot_frames, list):
            for ref in foot_frames:
                if isinstance(ref, dict) and find_video_in_path(ref.get('video_path', ''), video_search):
                    frame_count += 1
        
        if frame_count > 0:
            players[player_name] = frame_count
    
    return players


def rename_player_in_gallery(gallery: Dict, video_search: str, old_name: str, new_name: str) -> Tuple[int, int]:
    """Rename a player in gallery references for a specific video, transferring frames if needed"""
    video_path = get_video_path_from_search(gallery, video_search)
    if not video_path:
        print(f"⚠ Could not find video matching '{video_search}' in gallery")
        return 0, 0
    
    # Find source player (old_name)
    source_player_id = None
    source_player_data = None
    for player_id, player_data in gallery.items():
        if isinstance(player_data, dict) and player_data.get('name', '') == old_name:
            source_player_id = player_id
            source_player_data = player_data
            break
    
    if not source_player_id:
        print(f"⚠ Player '{old_name}' not found in gallery")
        return 0, 0
    
    # Find target player (new_name) - may not exist yet
    target_player_id = None
    target_player_data = None
    for player_id, player_data in gallery.items():
        if isinstance(player_data, dict) and player_data.get('name', '') == new_name:
            target_player_id = player_id
            target_player_data = player_data
            break
    
    frames_transferred = 0
    
    # Collect frames to transfer from source player
    frames_to_transfer = {
        'reference_frames': [],
        'uniform_variants': {},
        'foot_reference_frames': []
    }
    
    # Extract frames from reference_frames
    ref_frames = source_player_data.get('reference_frames', [])
    if isinstance(ref_frames, list):
        for ref in ref_frames:
            if isinstance(ref, dict) and find_video_in_path(ref.get('video_path', ''), video_search):
                frames_to_transfer['reference_frames'].append(ref)
                frames_transferred += 1
    
    # Extract frames from uniform_variants
    uniform_variants = source_player_data.get('uniform_variants', {})
    if isinstance(uniform_variants, dict):
        for variant_key, variant_frames in uniform_variants.items():
            if isinstance(variant_frames, list):
                matching_frames = [
                    ref for ref in variant_frames
                    if isinstance(ref, dict) and find_video_in_path(ref.get('video_path', ''), video_search)
                ]
                if matching_frames:
                    if variant_key not in frames_to_transfer['uniform_variants']:
                        frames_to_transfer['uniform_variants'][variant_key] = []
                    frames_to_transfer['uniform_variants'][variant_key].extend(matching_frames)
                    frames_transferred += len(matching_frames)
    
    # Extract frames from foot_reference_frames
    foot_frames = source_player_data.get('foot_reference_frames', [])
    if isinstance(foot_frames, list):
        for ref in foot_frames:
            if isinstance(ref, dict) and find_video_in_path(ref.get('video_path', ''), video_search):
                frames_to_transfer['foot_reference_frames'].append(ref)
                frames_transferred += 1
    
    if frames_transferred == 0:
        print(f"⚠ No frames found for '{old_name}' in video '{video_search}'")
        return 0, 0
    
    # Remove frames from source player
    if isinstance(source_player_data.get('reference_frames'), list):
        source_player_data['reference_frames'] = [
            ref for ref in source_player_data['reference_frames']
            if not (isinstance(ref, dict) and find_video_in_path(ref.get('video_path', ''), video_search))
        ]
    
    if isinstance(source_player_data.get('uniform_variants'), dict):
        for variant_key, variant_frames in source_player_data['uniform_variants'].items():
            if isinstance(variant_frames, list):
                source_player_data['uniform_variants'][variant_key] = [
                    ref for ref in variant_frames
                    if not (isinstance(ref, dict) and find_video_in_path(ref.get('video_path', ''), video_search))
                ]
    
    if isinstance(source_player_data.get('foot_reference_frames'), list):
        source_player_data['foot_reference_frames'] = [
            ref for ref in source_player_data['foot_reference_frames']
            if not (isinstance(ref, dict) and find_video_in_path(ref.get('video_path', ''), video_search))
        ]
    
    # Add frames to target player (or create new player)
    if target_player_id:
        # Target player exists - add frames to it
        if not isinstance(target_player_data.get('reference_frames'), list):
            target_player_data['reference_frames'] = []
        target_player_data['reference_frames'].extend(frames_to_transfer['reference_frames'])
        
        if not isinstance(target_player_data.get('uniform_variants'), dict):
            target_player_data['uniform_variants'] = {}
        for variant_key, frames in frames_to_transfer['uniform_variants'].items():
            if variant_key not in target_player_data['uniform_variants']:
                target_player_data['uniform_variants'][variant_key] = []
            target_player_data['uniform_variants'][variant_key].extend(frames)
        
        if not isinstance(target_player_data.get('foot_reference_frames'), list):
            target_player_data['foot_reference_frames'] = []
        target_player_data['foot_reference_frames'].extend(frames_to_transfer['foot_reference_frames'])
        
        print(f"  ✓ Transferred {frames_transferred} frames from '{old_name}' to existing '{new_name}'")
    else:
        # Target player doesn't exist - rename source player
        source_player_data['name'] = new_name
        # Add frames back (they were already in the player, just need to restore)
        if not isinstance(source_player_data.get('reference_frames'), list):
            source_player_data['reference_frames'] = []
        source_player_data['reference_frames'].extend(frames_to_transfer['reference_frames'])
        
        if not isinstance(source_player_data.get('uniform_variants'), dict):
            source_player_data['uniform_variants'] = {}
        for variant_key, frames in frames_to_transfer['uniform_variants'].items():
            if variant_key not in source_player_data['uniform_variants']:
                source_player_data['uniform_variants'][variant_key] = []
            source_player_data['uniform_variants'][variant_key].extend(frames)
        
        if not isinstance(source_player_data.get('foot_reference_frames'), list):
            source_player_data['foot_reference_frames'] = []
        source_player_data['foot_reference_frames'].extend(frames_to_transfer['foot_reference_frames'])
        
        print(f"  ✓ Renamed '{old_name}' → '{new_name}' ({frames_transferred} frames)")
    
    return frames_transferred, 1


def remove_players_from_gallery(gallery: Dict, video_search: str, player_names: List[str]) -> int:
    """Remove reference frames for specified players from a specific video"""
    video_path = get_video_path_from_search(gallery, video_search)
    if not video_path:
        print(f"⚠ Could not find video matching '{video_search}' in gallery")
        return 0
    
    player_names_set = {name.strip() for name in player_names}
    frames_removed = 0
    
    for player_id, player_data in gallery.items():
        if not isinstance(player_data, dict):
            continue
        
        player_name = player_data.get('name', '')
        if player_name not in player_names_set:
            continue
        
        # Remove from reference_frames
        ref_frames = player_data.get('reference_frames', [])
        if isinstance(ref_frames, list):
            original_count = len(ref_frames)
            player_data['reference_frames'] = [
                ref for ref in ref_frames
                if not (isinstance(ref, dict) and find_video_in_path(ref.get('video_path', ''), video_search))
            ]
            removed = original_count - len(player_data['reference_frames'])
            frames_removed += removed
        
        # Remove from uniform_variants
        uniform_variants = player_data.get('uniform_variants', {})
        if isinstance(uniform_variants, dict):
            for variant_key, variant_frames in uniform_variants.items():
                if isinstance(variant_frames, list):
                    original_count = len(variant_frames)
                    uniform_variants[variant_key] = [
                        ref for ref in variant_frames
                        if not (isinstance(ref, dict) and find_video_in_path(ref.get('video_path', ''), video_search))
                    ]
                    removed = original_count - len(uniform_variants[variant_key])
                    frames_removed += removed
        
        # Remove from foot_reference_frames
        foot_frames = player_data.get('foot_reference_frames', [])
        if isinstance(foot_frames, list):
            original_count = len(foot_frames)
            player_data['foot_reference_frames'] = [
                ref for ref in foot_frames
                if not (isinstance(ref, dict) and find_video_in_path(ref.get('video_path', ''), video_search))
            ]
            removed = original_count - len(player_data['foot_reference_frames'])
            frames_removed += removed
        
        if frames_removed > 0:
            print(f"  ✓ Removed {frames_removed} frames for '{player_name}' from video")
    
    return frames_removed


def rename_player_in_csv(csv_path: str, old_name: str, new_name: str, output_path: Optional[str] = None) -> int:
    """Rename a player in CSV file"""
    if not os.path.exists(csv_path):
        print(f"❌ CSV file not found: {csv_path}")
        return 0
    
    # Read CSV, skipping comment lines
    try:
        df = pd.read_csv(csv_path, comment='#')
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return 0
    
    # Find player name column
    player_col = None
    for col in ['player_name', 'player', 'name']:
        if col in df.columns:
            player_col = col
            break
    
    if not player_col:
        print(f"⚠ Could not find player name column in CSV. Available columns: {list(df.columns)}")
        return 0
    
    # Extract player names (handle list format)
    def extract_player_name(value):
        if pd.isna(value):
            return None
        if isinstance(value, str):
            # Try to parse as list
            if value.startswith('[') and value.endswith(']'):
                try:
                    import ast
                    parsed = ast.literal_eval(value)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        return str(parsed[0]).strip()
                except:
                    pass
            return value.strip()
        return str(value).strip()
    
    df[player_col + '_extracted'] = df[player_col].apply(extract_player_name)
    
    # Count rows before
    original_count = len(df[df[player_col + '_extracted'] == old_name])
    
    # Rename player
    mask = df[player_col + '_extracted'] == old_name
    
    # Update the player name column
    # If it's a list format, update the first element
    def update_player_name(value):
        if pd.isna(value):
            return value
        if isinstance(value, str):
            if value.startswith('[') and value.endswith(']'):
                try:
                    import ast
                    parsed = ast.literal_eval(value)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        parsed[0] = new_name
                        return str(parsed)
                except:
                    pass
            return new_name
        return new_name
    
    df.loc[mask, player_col] = df.loc[mask, player_col].apply(update_player_name)
    df = df.drop(columns=[player_col + '_extracted'])
    
    rows_renamed = original_count
    
    # Save to output path or overwrite
    output = output_path or csv_path
    if output == csv_path:
        # Create backup
        backup_path = csv_path.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        print(f"📦 Creating backup: {backup_path}")
        df_original = pd.read_csv(csv_path, comment='#')
        df_original.to_csv(backup_path, index=False)
    
    # Preserve comment lines at the top
    comment_lines = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip().startswith('#'):
                comment_lines.append(line)
            else:
                break
    
    # Write CSV with comments
    with open(output, 'w', encoding='utf-8') as f:
        for comment in comment_lines:
            f.write(comment)
        df.to_csv(f, index=False)
    
    print(f"✓ Renamed {rows_renamed} rows from '{old_name}' to '{new_name}' in CSV")
    return rows_renamed


def remove_players_from_csv(csv_path: str, player_names: List[str], output_path: Optional[str] = None) -> int:
    """Remove rows for specified players from CSV file"""
    if not os.path.exists(csv_path):
        print(f"❌ CSV file not found: {csv_path}")
        return 0
    
    player_names_set = {name.strip() for name in player_names}
    
    # Read CSV, skipping comment lines
    try:
        df = pd.read_csv(csv_path, comment='#')
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return 0
    
    # Find player name column
    player_col = None
    for col in ['player_name', 'player', 'name']:
        if col in df.columns:
            player_col = col
            break
    
    if not player_col:
        print(f"⚠ Could not find player name column in CSV. Available columns: {list(df.columns)}")
        return 0
    
    # Count rows before
    original_count = len(df)
    
    # Filter out rows for specified players
    # Handle list format like ['Cameron Melnik', 'Blue', '']
    def extract_player_name(value):
        if pd.isna(value):
            return None
        if isinstance(value, str):
            # Try to parse as list
            if value.startswith('[') and value.endswith(']'):
                try:
                    import ast
                    parsed = ast.literal_eval(value)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        return str(parsed[0]).strip()
                except:
                    pass
            return value.strip()
        return str(value).strip()
    
    df[player_col + '_extracted'] = df[player_col].apply(extract_player_name)
    df_filtered = df[~df[player_col + '_extracted'].isin(player_names_set)]
    df_filtered = df_filtered.drop(columns=[player_col + '_extracted'])
    
    rows_removed = original_count - len(df_filtered)
    
    # Save to output path or overwrite
    output = output_path or csv_path
    if output == csv_path:
        # Create backup
        backup_path = csv_path.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        print(f"📦 Creating backup: {backup_path}")
        df.to_csv(backup_path, index=False)
    
    # Preserve comment lines at the top
    comment_lines = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip().startswith('#'):
                comment_lines.append(line)
            else:
                break
    
    # Write CSV with comments
    with open(output, 'w', encoding='utf-8') as f:
        for comment in comment_lines:
            f.write(comment)
        df_filtered.to_csv(f, index=False)
    
    print(f"✓ Removed {rows_removed} rows from CSV ({original_count} → {len(df_filtered)})")
    return rows_removed


def main():
    parser = argparse.ArgumentParser(description='Edit player gallery and CSV for specific videos')
    parser.add_argument('--gallery', default='player_gallery.json', help='Path to player gallery JSON')
    parser.add_argument('--video', help='Video search term (e.g., "20251001_183951" or video filename)')
    parser.add_argument('--csv', help='Path to CSV file to edit')
    parser.add_argument('--rename', nargs=2, metavar=('OLD_NAME', 'NEW_NAME'), help='Rename player in gallery or CSV')
    parser.add_argument('--rename-csv', nargs=2, metavar=('OLD_NAME', 'NEW_NAME'), help='Rename player in CSV file only')
    parser.add_argument('--remove-players', help='Comma-separated list of player names to remove')
    parser.add_argument('--list-players', action='store_true', help='List all players in video')
    parser.add_argument('--no-backup', action='store_true', help='Skip creating backups')
    
    args = parser.parse_args()
    
    if not args.video and not args.csv:
        parser.print_help()
        print("\n❌ Must specify either --video or --csv")
        return
    
    # Handle gallery operations
    if args.video:
        gallery = load_gallery(args.gallery)
        if not gallery:
            print("❌ Could not load gallery")
            return
        
        if args.list_players:
            print(f"\n📋 Players in video '{args.video}':")
            players = list_players_in_video(gallery, args.video)
            if players:
                for name, count in sorted(players.items()):
                    print(f"  • {name}: {count} frames")
            else:
                print("  (No players found)")
            return
        
        frames_changed = 0
        
        # Rename player
        if args.rename:
            old_name, new_name = args.rename
            print(f"\n🔄 Renaming '{old_name}' → '{new_name}' in video '{args.video}'...")
            frames_renamed, players_updated = rename_player_in_gallery(gallery, args.video, old_name, new_name)
            frames_changed += frames_renamed
            if frames_renamed > 0:
                save_gallery(gallery, args.gallery, backup=not args.no_backup)
        
        # Remove players
        if args.remove_players:
            player_list = [p.strip() for p in args.remove_players.split(',')]
            print(f"\n🗑️ Removing players from video '{args.video}': {', '.join(player_list)}")
            frames_removed = remove_players_from_gallery(gallery, args.video, player_list)
            frames_changed += frames_removed
            if frames_removed > 0:
                save_gallery(gallery, args.gallery, backup=not args.no_backup)
        
        if frames_changed == 0 and (args.rename or args.remove_players):
            print("⚠ No changes made - check video search term and player names")
    
    # Handle CSV operations
    if args.csv:
        rows_changed = 0
        
        # Rename player in CSV
        if args.rename_csv:
            old_name, new_name = args.rename_csv
            print(f"\n🔄 Renaming '{old_name}' → '{new_name}' in CSV...")
            rows_renamed = rename_player_in_csv(args.csv, old_name, new_name)
            rows_changed += rows_renamed
        
        # Remove players from CSV
        if args.remove_players:
            player_list = [p.strip() for p in args.remove_players.split(',')]
            print(f"\n🗑️ Removing players from CSV: {', '.join(player_list)}")
            rows_removed = remove_players_from_csv(args.csv, player_list)
            rows_changed += rows_removed
        
        if rows_changed == 0 and (args.rename_csv or args.remove_players):
            print("⚠ No changes made - check player names")
        elif not args.rename_csv and not args.remove_players:
            print("⚠ CSV specified but no --rename-csv or --remove-players given")


if __name__ == '__main__':
    # Fix encoding for Windows
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    main()

