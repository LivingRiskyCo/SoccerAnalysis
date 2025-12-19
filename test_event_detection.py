"""
Test event detection on existing CSV files.
Run this on your current video to see what it detects!

Usage:
    python test_event_detection.py <tracking_csv_path> [options]

Example:
    python test_event_detection.py game_analyzed_tracking_data.csv
    python test_event_detection.py game_analyzed_tracking_data.csv --min-confidence 0.4
"""

import sys
import argparse
from event_detector import EventDetector

def main():
    parser = argparse.ArgumentParser(
        description="Test event detection on existing CSV tracking data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python test_event_detection.py game_analyzed_tracking_data.csv
  
  # Lower confidence threshold for more detections
  python test_event_detection.py game_analyzed_tracking_data.csv --min-confidence 0.3
  
  # Custom pass detection parameters
  python test_event_detection.py game_analyzed_tracking_data.csv --min-ball-speed 2.0 --min-pass-distance 3.0
        """
    )
    
    parser.add_argument('csv_path', help='Path to tracking CSV file')
    parser.add_argument('--min-confidence', type=float, default=0.5,
                       help='Minimum confidence threshold (default: 0.5, lower = more detections)')
    parser.add_argument('--min-ball-speed', type=float, default=3.0,
                       help='Minimum ball speed for pass detection in m/s (default: 3.0)')
    parser.add_argument('--min-pass-distance', type=float, default=5.0,
                       help='Minimum pass distance in meters (default: 5.0)')
    parser.add_argument('--possession-threshold', type=float, default=1.5,
                       help='Ball possession distance threshold in meters (default: 1.5)')
    parser.add_argument('--no-shots', action='store_true',
                       help='Skip shot detection')
    parser.add_argument('--no-zones', action='store_true',
                       help='Skip zone occupancy analysis')
    parser.add_argument('--export', action='store_true',
                       help='Export events to CSV file')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Event Detection Test")
    print("=" * 60)
    print(f"CSV file: {args.csv_path}")
    print(f"Confidence threshold: {args.min_confidence}")
    print()
    
    # Initialize detector
    detector = EventDetector(args.csv_path)
    
    if not detector.load_tracking_data():
        print("Failed to load tracking data")
        return 1
    
    # Detect passes
    print("\n" + "=" * 60)
    passes = detector.detect_passes(
        min_ball_speed=args.min_ball_speed,
        min_pass_distance=args.min_pass_distance,
        possession_threshold=args.possession_threshold,
        confidence_threshold=args.min_confidence
    )
    
    detector.events.extend(passes)
    
    if passes:
        print(f"\n📊 Pass Detection Results:")
        print(f"   Total passes detected: {len(passes)}")
        print(f"\n   Top 10 passes (by confidence):")
        sorted_passes = sorted(passes, key=lambda x: x.confidence, reverse=True)
        for i, pass_event in enumerate(sorted_passes[:10], 1):
            receiver = pass_event.metadata.get('receiver_name') if pass_event.metadata else None
            distance = pass_event.metadata.get('pass_distance_m', 0) if pass_event.metadata else 0
            print(f"   {i:2d}. Frame {pass_event.frame_num:5d} ({pass_event.timestamp:6.1f}s) - "
                  f"Conf: {pass_event.confidence:.2f} - "
                  f"{pass_event.player_name or f'Player {pass_event.player_id}'} → "
                  f"{receiver or 'Unknown'} ({distance:.1f}m)")
    else:
        print("\n   ⚠ No passes detected")
        print("   → Try lowering --min-confidence or --min-ball-speed")
        print("   → Check that ball tracking data exists in CSV")
    
    # Detect shots
    if not args.no_shots:
        print("\n" + "=" * 60)
        shots = detector.detect_shots(confidence_threshold=args.min_confidence)
        detector.events.extend(shots)
        
        if shots:
            print(f"\n📊 Shot Detection Results:")
            print(f"   Total shots detected: {len(shots)}")
            print(f"\n   Top 10 shots (by confidence):")
            sorted_shots = sorted(shots, key=lambda x: x.confidence, reverse=True)
            for i, shot_event in enumerate(sorted_shots[:10], 1):
                speed = shot_event.metadata.get('ball_speed_mps', 0) if shot_event.metadata else 0
                print(f"   {i:2d}. Frame {shot_event.frame_num:5d} ({shot_event.timestamp:6.1f}s) - "
                      f"Conf: {shot_event.confidence:.2f} - "
                      f"{shot_event.player_name or f'Player {shot_event.player_id}'} - "
                      f"Speed: {speed:.1f} m/s")
        else:
            print("\n   ⚠ No shots detected")
            print("   → Try lowering --min-confidence")
    
    # Zone occupancy analysis
    if not args.no_zones:
        print("\n" + "=" * 60)
        zones = {
            'defensive_third': (0.0, 0.0, 1.0, 0.33),
            'midfield': (0.0, 0.33, 1.0, 0.67),
            'attacking_third': (0.0, 0.67, 1.0, 1.0)
        }
        zone_stats = detector.detect_zone_occupancy(zones)
        
        if zone_stats:
            print(f"\n📊 Zone Occupancy Results:")
            print(f"   Total player-zone combinations: {len(zone_stats)}")
            print(f"\n   Top 15 zone occupancies (by time):")
            sorted_zones = sorted(zone_stats.items(), key=lambda x: x[1]['time'], reverse=True)
            for key, stats in sorted_zones[:15]:
                player_name = stats['player_name'] or f"Player {stats['player_id']}"
                print(f"   {player_name:20s} - {stats['zone']:20s}: "
                      f"{stats['time']:6.1f}s ({stats['frames']:4d} frames)")
        else:
            print("\n   ⚠ No zone data found")
            print("   → Check that player tracking data exists in CSV")
    
    # Export events
    if args.export and detector.events:
        output_path = args.csv_path.replace('.csv', '_detected_events.csv')
        detector.export_events(output_path)
        print(f"\n✓ Events exported to: {output_path}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total events detected: {len(detector.events)}")
    if detector.events:
        event_types = {}
        for event in detector.events:
            event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
        print("\nEvents by type:")
        for event_type, count in sorted(event_types.items()):
            print(f"  {event_type}: {count}")
        
        avg_confidence = sum(e.confidence for e in detector.events) / len(detector.events)
        print(f"\nAverage confidence: {avg_confidence:.2f}")
        print(f"\n💡 Tips:")
        print(f"  • Lower confidence threshold for more detections: --min-confidence 0.3")
        print(f"  • Adjust pass detection: --min-ball-speed 2.0 --min-pass-distance 3.0")
        print(f"  • Export to CSV: --export")
    else:
        print("\n⚠ No events detected")
        print("  This could mean:")
        print("  • Video quality/tracking is insufficient")
        print("  • Thresholds are too strict (try --min-confidence 0.3)")
        print("  • No actual events occurred in the video")
        print("  • Ball/player tracking data is missing or incomplete")
    
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())

