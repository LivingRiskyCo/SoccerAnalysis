"""
Test script to verify professional format exports.
Demonstrates conversion from CSV to all supported formats.
"""

import os
import sys

def test_export():
    """Test the professional format export."""
    
    # Find a tracking CSV file
    csv_files = [f for f in os.listdir('.') if f.endswith('_tracking_data.csv')]
    
    if not csv_files:
        print("❌ No tracking CSV files found in current directory.")
        print("   Run your analysis first to generate tracking data:")
        print("   python combined_analysis_optimized.py --input video.mp4 ...")
        return False
    
    # Use the first CSV file found
    csv_file = csv_files[0]
    print(f"✓ Found tracking data: {csv_file}")
    
    # Import the export module
    try:
        from export_to_professional_formats import export_all_formats
    except ImportError as e:
        print(f"❌ Error importing export module: {e}")
        return False
    
    # Run export
    print(f"\n📊 Exporting {csv_file} to professional formats...")
    try:
        export_all_formats(csv_file, output_dir='.', fps=24.0)
        print("\n✅ SUCCESS! All formats exported.")
        
        # List generated files
        base_name = csv_file.replace('_tracking_data.csv', '')
        formats = {
            f"{base_name}_sportscode.xml": "Hudl SportsCode",
            f"{base_name}_tracab.json": "Second Spectrum / TRACAB",
            f"{base_name}_dartfish.xml": "Dartfish / Nacsport",
            f"{base_name}_statsperform.json": "Stats Perform / Opta"
        }
        
        print("\n📁 Generated files:")
        for filename, platform in formats.items():
            if os.path.exists(filename):
                size = os.path.getsize(filename)
                size_kb = size / 1024
                print(f"  ✓ {filename:40s} ({size_kb:>7.1f} KB) - {platform}")
            else:
                print(f"  ✗ {filename:40s} (NOT FOUND)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_usage_examples():
    """Show common usage examples."""
    print("\n" + "="*70)
    print("USAGE EXAMPLES")
    print("="*70)
    
    print("\n1. Export all formats:")
    print("   python export_to_professional_formats.py \\")
    print("       --csv 20-sec_analyzed_tracking_data.csv \\")
    print("       --fps 24")
    
    print("\n2. Export specific format:")
    print("   python export_to_professional_formats.py \\")
    print("       --csv 20-sec_analyzed_tracking_data.csv \\")
    print("       --format tracab")
    
    print("\n3. Custom output directory:")
    print("   python export_to_professional_formats.py \\")
    print("       --csv 20-sec_analyzed_tracking_data.csv \\")
    print("       --output-dir ./exports \\")
    print("       --fps 30")
    
    print("\n4. High-speed video (120 FPS):")
    print("   python export_to_professional_formats.py \\")
    print("       --csv highspeed_tracking_data.csv \\")
    print("       --fps 120")
    
    print("\n" + "="*70)
    print("IMPORTING INTO PLATFORMS")
    print("="*70)
    
    print("\n• Hudl SportsCode:")
    print("    File → Import → XML Data → Select *_sportscode.xml")
    
    print("\n• Second Spectrum:")
    print("    POST to API endpoint with *_tracab.json")
    
    print("\n• Dartfish:")
    print("    File → Import → Tracking Data → Select *_dartfish.xml")
    
    print("\n• Stats Perform:")
    print("    Upload *_statsperform.json to Opta platform")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    print("="*70)
    print("PROFESSIONAL SPORTS ANALYSIS EXPORT - TEST")
    print("="*70)
    
    success = test_export()
    
    if success:
        show_usage_examples()
        
        print("\n✅ Test complete! Your tracking data is ready for:")
        print("   • Coaching analysis (SportsCode/Hudl)")
        print("   • Broadcast overlays (TRACAB/Second Spectrum)")
        print("   • Video tagging (Dartfish/Nacsport)")
        print("   • Statistical analysis (Stats Perform/Opta)")
        
        print("\n📚 Read PROFESSIONAL_EXPORT_GUIDE.md for detailed instructions.")
    else:
        print("\n❌ Test failed. Check error messages above.")
        sys.exit(1)

