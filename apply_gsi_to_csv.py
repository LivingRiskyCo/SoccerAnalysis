"""
Apply GSI (Gaussian Smoothed Interpolation) to an existing tracking CSV file.

This script fills small gaps in tracking data by interpolating between known positions.
Use this AFTER analysis to smooth tracks and fill gaps without rerunning the entire analysis.

Usage:
    python apply_gsi_to_csv.py "path/to/tracking_data.csv" --interval 20 --tau 10.0
    python apply_gsi_to_csv.py "path/to/tracking_data.csv" --output "path/to/smoothed_data.csv"
"""

import argparse
import sys
from pathlib import Path

try:
    from gsi_smoothing import apply_gsi_to_csv, SKLEARN_AVAILABLE
except ImportError:
    print("❌ Error: Could not import gsi_smoothing module")
    print("   Make sure gsi_smoothing.py is in the same directory")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Apply GSI smoothing to tracking CSV file to fill gaps and smooth tracks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Apply GSI with default settings (interval=20, tau=10.0)
  python apply_gsi_to_csv.py tracking_data.csv

  # Apply GSI with custom settings
  python apply_gsi_to_csv.py tracking_data.csv --interval 30 --tau 15.0

  # Save to new file instead of overwriting
  python apply_gsi_to_csv.py tracking_data.csv --output smoothed_tracking_data.csv

Parameters:
  --interval: Maximum frame gap to interpolate (default: 20)
              Higher values fill larger gaps, but may be less accurate
              
  --tau: Time constant for Gaussian smoothing (default: 10.0)
         Higher values = more smoothing (smoother but may lag)
         Lower values = less smoothing (more responsive but may be jittery)
        """
    )
    
    parser.add_argument('csv_path', type=str, help='Path to input CSV file')
    parser.add_argument('--output', type=str, default=None, 
                       help='Output CSV path (if not specified, overwrites input file)')
    parser.add_argument('--interval', type=int, default=20,
                       help='Maximum frame gap to interpolate (default: 20)')
    parser.add_argument('--tau', type=float, default=10.0,
                       help='Time constant for Gaussian smoothing (default: 10.0)')
    
    args = parser.parse_args()
    
    # Check if sklearn is available
    if not SKLEARN_AVAILABLE:
        print("❌ Error: sklearn is not available")
        print("   Install with: pip install scikit-learn")
        sys.exit(1)
    
    # Check if input file exists
    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"❌ Error: CSV file not found: {csv_path}")
        sys.exit(1)
    
    print(f"📊 Applying GSI smoothing to: {csv_path}")
    print(f"   → Interval: {args.interval} frames (max gap to fill)")
    print(f"   → Tau: {args.tau} (smoothing strength)")
    
    if args.output:
        output_path = Path(args.output)
        print(f"   → Output: {output_path}")
    else:
        print(f"   → Output: {csv_path} (overwriting original)")
        output_path = None
    
    try:
        # Apply GSI smoothing
        smoothed_df = apply_gsi_to_csv(
            str(csv_path),
            output_path=str(output_path) if output_path else None,
            interval=args.interval,
            tau=args.tau
        )
        
        print(f"\n✅ GSI smoothing complete!")
        print(f"   → Processed {len(smoothed_df)} rows")
        print(f"   → Filled gaps up to {args.interval} frames")
        
        if output_path:
            print(f"   → Saved to: {output_path}")
        else:
            print(f"   → Updated: {csv_path}")
        
        print(f"\n💡 Tip: Reload the CSV in Playback Viewer to see smoothed tracks")
        
    except Exception as e:
        print(f"❌ Error applying GSI smoothing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

