"""
Gallery Cleanup Utility
Removes corrupted reference frames from player_gallery.json

Usage:
    python cleanup_gallery.py --video "20251001_183951" --players "Cameron Melnik,Ellie Hill,Rocco Piazza"
    python cleanup_gallery.py --video "20251001_183951" --remove-all  # Remove ALL frames from this video
    python cleanup_gallery.py --list-videos  # List all videos in gallery
    python cleanup_gallery.py --list-players --video "20251001_183951"  # List players with frames from this video
"""

import json
import os
import argparse
from typing import Dict, List, Set
from pathlib import Path


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
        backup_path = gallery_path.replace('.json', '_backup.json')
        print(f"📦 Creating backup: {backup_path}")
        with open(gallery_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
    
    with open(gallery_path, 'w', encoding='utf-8') as f:
        json.dump(gallery, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved gallery to {gallery_path}")


def find_video_in_path(video_path: str, search_term: str) -> bool:
    """Check if video_path contains the search term"""
    if not video_path:
        return False
    return search_term.lower() in video_path.lower()


def remove_frames_from_video(gallery: Dict, video_search: str, player_names: List[str] = None, remove_all: bool = False) -> Dict:
    """
    Remove reference frames from a specific video
    
    Args:
        gallery: Gallery dictionary
        video_search: Video identifier to search for (e.g., "20251001_183951")
        player_names: List of player names to clean (if None, clean all players)
        remove_all: If True, remove ALL frames from this video regardless of player
    
    Returns:
        Updated gallery dictionary
    """
    removed_count = 0
    affected_players = set()
    
    # Gallery structure: {player_id: profile_dict, ...}
    # Check if it's the old nested format or new flat format
    if 'players' in gallery:
        players_dict = gallery['players']
    else:
        # Flat format - gallery itself is the players dict
        players_dict = gallery
    
    for player_id, profile in players_dict.items():
        player_name = profile.get('name', 'Unknown')
        
        # Skip if we're targeting specific players and this isn't one of them
        if player_names and not remove_all:
            if player_name not in player_names:
                continue
        
        # Check main reference_frames
        if 'reference_frames' in profile and profile['reference_frames']:
            original_count = len(profile['reference_frames'])
            profile['reference_frames'] = [
                rf for rf in profile['reference_frames']
                if not find_video_in_path(rf.get('video_path', ''), video_search)
            ]
            removed = original_count - len(profile['reference_frames'])
            if removed > 0:
                removed_count += removed
                affected_players.add(player_name)
                print(f"  ✓ Removed {removed} frame(s) from '{player_name}' (main reference_frames)")
        
        # Check uniform_variants
        if 'uniform_variants' in profile and profile['uniform_variants']:
            for uniform_key, frames in profile['uniform_variants'].items():
                if frames:
                    original_count = len(frames)
                    profile['uniform_variants'][uniform_key] = [
                        rf for rf in frames
                        if not find_video_in_path(rf.get('video_path', ''), video_search)
                    ]
                    removed = original_count - len(profile['uniform_variants'][uniform_key])
                    if removed > 0:
                        removed_count += removed
                        affected_players.add(player_name)
                        print(f"  ✓ Removed {removed} frame(s) from '{player_name}' (uniform_variant: {uniform_key})")
        
        # Check foot_reference_frames
        if 'foot_reference_frames' in profile and profile['foot_reference_frames']:
            original_count = len(profile['foot_reference_frames'])
            profile['foot_reference_frames'] = [
                rf for rf in profile['foot_reference_frames']
                if not find_video_in_path(rf.get('video_path', ''), video_search)
            ]
            removed = original_count - len(profile['foot_reference_frames'])
            if removed > 0:
                removed_count += removed
                affected_players.add(player_name)
                print(f"  ✓ Removed {removed} frame(s) from '{player_name}' (foot_reference_frames)")
        
        # Check best images (body, jersey, foot)
        for image_key in ['best_body_image', 'best_jersey_image', 'best_foot_image']:
            if image_key in profile and profile[image_key]:
                img = profile[image_key]
                if find_video_in_path(img.get('video_path', ''), video_search):
                    profile[image_key] = None
                    removed_count += 1
                    affected_players.add(player_name)
                    print(f"  ✓ Removed {image_key} from '{player_name}'")
    
    print(f"\nSummary:")
    print(f"   Removed {removed_count} reference frame(s) from {len(affected_players)} player(s)")
    if affected_players:
        print(f"   Affected players: {', '.join(sorted(affected_players))}")
    
    return gallery


def list_videos_in_gallery(gallery: Dict):
    """List all unique videos in the gallery"""
    videos = set()
    
    # Gallery structure: {player_id: profile_dict, ...}
    if 'players' in gallery:
        players_dict = gallery['players']
    else:
        players_dict = gallery
    
    for player_id, profile in players_dict.items():
        # Check main reference_frames
        if 'reference_frames' in profile and profile['reference_frames']:
            for rf in profile['reference_frames']:
                video_path = rf.get('video_path', '')
                if video_path:
                    videos.add(video_path)
        
        # Check uniform_variants
        if 'uniform_variants' in profile and profile['uniform_variants']:
            for frames in profile['uniform_variants'].values():
                for rf in frames:
                    video_path = rf.get('video_path', '')
                    if video_path:
                        videos.add(video_path)
        
        # Check foot_reference_frames
        if 'foot_reference_frames' in profile and profile['foot_reference_frames']:
            for rf in profile['foot_reference_frames']:
                video_path = rf.get('video_path', '')
                if video_path:
                    videos.add(video_path)
    
    print(f"Found {len(videos)} unique video(s) in gallery:")
    for video in sorted(videos):
        print(f"   - {video}")


def list_players_for_video(gallery: Dict, video_search: str):
    """List all players that have reference frames from a specific video"""
    players_with_frames = {}
    
    # Gallery structure: {player_id: profile_dict, ...}
    if 'players' in gallery:
        players_dict = gallery['players']
    else:
        players_dict = gallery
    
    for player_id, profile in players_dict.items():
        player_name = profile.get('name', 'Unknown')
        frame_count = 0
        
        # Count frames in main reference_frames
        if 'reference_frames' in profile and profile['reference_frames']:
            for rf in profile['reference_frames']:
                if find_video_in_path(rf.get('video_path', ''), video_search):
                    frame_count += 1
        
        # Count frames in uniform_variants
        if 'uniform_variants' in profile and profile['uniform_variants']:
            for frames in profile['uniform_variants'].values():
                for rf in frames:
                    if find_video_in_path(rf.get('video_path', ''), video_search):
                        frame_count += 1
        
        # Count frames in foot_reference_frames
        if 'foot_reference_frames' in profile and profile['foot_reference_frames']:
            for rf in profile['foot_reference_frames']:
                if find_video_in_path(rf.get('video_path', ''), video_search):
                    frame_count += 1
        
        if frame_count > 0:
            players_with_frames[player_name] = frame_count
    
    if players_with_frames:
        print(f"Players with frames from video '{video_search}':")
        for player_name, count in sorted(players_with_frames.items()):
            print(f"   - {player_name}: {count} frame(s)")
    else:
        print(f"No players have frames from video '{video_search}'")


def main():
    parser = argparse.ArgumentParser(description='Clean up corrupted reference frames from player gallery')
    parser.add_argument('--gallery', default='player_gallery.json', help='Path to player_gallery.json')
    parser.add_argument('--video', help='Video identifier to search for (e.g., "20251001_183951")')
    parser.add_argument('--players', help='Comma-separated list of player names to clean (e.g., "Cameron Melnik,Ellie Hill")')
    parser.add_argument('--remove-all', action='store_true', help='Remove ALL frames from the specified video (all players)')
    parser.add_argument('--list-videos', action='store_true', help='List all videos in the gallery')
    parser.add_argument('--list-players', action='store_true', help='List players with frames from the specified video')
    parser.add_argument('--no-backup', action='store_true', help='Skip creating a backup before saving')
    
    args = parser.parse_args()
    
    # Load gallery
    gallery = load_gallery(args.gallery)
    if not gallery:
        return
    
    # List videos
    if args.list_videos:
        list_videos_in_gallery(gallery)
        return
    
    # List players for video
    if args.list_players:
        if not args.video:
            print("❌ --list-players requires --video")
            return
        list_players_for_video(gallery, args.video)
        return
    
    # Clean up frames
    if args.video:
        player_names = None
        if args.players:
            player_names = [p.strip() for p in args.players.split(',')]
            print(f"🧹 Cleaning frames from video '{args.video}' for players: {', '.join(player_names)}")
        elif args.remove_all:
            print(f"🧹 Removing ALL frames from video '{args.video}' (all players)")
        else:
            print("⚠ No --players specified and --remove-all not set. Use --players or --remove-all")
            return
        
        gallery = remove_frames_from_video(gallery, args.video, player_names, args.remove_all)
        save_gallery(gallery, args.gallery, backup=not args.no_backup)
        print(f"\n✅ Cleanup complete!")
    else:
        print("❌ No action specified. Use --list-videos, --list-players, or --video with --players/--remove-all")


if __name__ == '__main__':
    main()

