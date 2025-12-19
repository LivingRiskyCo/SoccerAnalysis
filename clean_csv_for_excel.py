"""
Clean CSV for Excel Editing
Removes comment lines and empty rows to make CSV Excel-compatible

Usage:
    python clean_csv_for_excel.py "path/to/file.csv"
    python clean_csv_for_excel.py "path/to/file.csv" --output "path/to/cleaned_file.csv"
"""

import pandas as pd
import sys
import argparse
import os
from datetime import datetime


def clean_csv_for_excel(csv_path: str, output_path: str = None, keep_backup: bool = True):
    """Clean CSV file to make it Excel-compatible"""
    if not os.path.exists(csv_path):
        print(f"❌ CSV file not found: {csv_path}")
        return False
    
    # Read CSV, skipping comment lines
    try:
        df = pd.read_csv(csv_path, comment='#')
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return False
    
    # Remove completely empty rows (all NaN)
    df = df.dropna(how='all')
    
    # Remove rows where frame is NaN (invalid rows)
    if 'frame' in df.columns:
        df = df.dropna(subset=['frame'])
    
    # Determine output path
    if output_path is None:
        output_path = csv_path
    
    # Create backup if overwriting original
    if output_path == csv_path and keep_backup:
        backup_path = csv_path.replace('.csv', f'_excel_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        print(f"📦 Creating backup: {backup_path}")
        try:
            # Read original file to preserve comments in backup
            with open(csv_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
        except Exception as e:
            print(f"⚠ Could not create backup: {e}")
    
    # Save cleaned CSV (no comments, no empty rows)
    try:
        df.to_csv(output_path, index=False, encoding='utf-8-sig')  # utf-8-sig for Excel compatibility
        print(f"✓ Cleaned CSV saved to: {output_path}")
        print(f"   → Removed comment lines and empty rows")
        print(f"   → Rows: {len(df)} (cleaned)")
        return True
    except Exception as e:
        print(f"❌ Error saving CSV: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Clean CSV file for Excel editing')
    parser.add_argument('csv_path', help='Path to CSV file to clean')
    parser.add_argument('--output', '-o', help='Output path (default: overwrite original)')
    parser.add_argument('--no-backup', action='store_true', help='Skip creating backup')
    
    args = parser.parse_args()
    
    success = clean_csv_for_excel(
        args.csv_path,
        output_path=args.output,
        keep_backup=not args.no_backup
    )
    
    if success:
        print("\n✅ CSV is now Excel-compatible!")
        print("   → You can open and edit it in Excel")
        print("   → Comment lines have been removed (metadata preserved in backup)")
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()

