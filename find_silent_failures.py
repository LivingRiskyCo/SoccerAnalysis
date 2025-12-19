"""
Script to find silent failures in the codebase
Helps identify places where exceptions are caught but not properly logged
"""

import re
import os
from pathlib import Path

def find_silent_failures(file_path: Path):
    """Find silent failures in a Python file"""
    issues = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    in_try = False
    try_line = 0
    
    for i, line in enumerate(lines, 1):
        # Check for try block
        if re.search(r'\btry\s*:', line):
            in_try = True
            try_line = i
        
        # Check for except block
        if in_try and re.search(r'\bexcept\s+.*:', line):
            # Check if except block is empty or only has pass
            except_line = i
            # Look ahead to see what's in the except block
            j = i
            content_found = False
            while j < len(lines) and j < i + 10:  # Check next 10 lines
                next_line = lines[j].strip()
                # Skip comments and empty lines
                if next_line and not next_line.startswith('#'):
                    if next_line == 'pass':
                        # Found pass - check if there's anything else
                        if j == i:  # pass on same line as except
                            content_found = False
                        else:
                            # Check if there's anything before pass
                            for k in range(i + 1, j):
                                if lines[k].strip() and not lines[k].strip().startswith('#'):
                                    content_found = True
                                    break
                    elif not next_line.startswith('except') and not next_line.startswith('finally'):
                        content_found = True
                        break
                j += 1
            
            if not content_found:
                issues.append({
                    'file': str(file_path),
                    'try_line': try_line,
                    'except_line': except_line,
                    'issue': 'Silent failure - except block may be empty or only contains pass'
                })
            
            in_try = False
        
        # Check for bare except
        if re.search(r'\bexcept\s*:', line):
            issues.append({
                'file': str(file_path),
                'line': i,
                'issue': 'Bare except clause - catches all exceptions including SystemExit'
            })
    
    return issues

def main():
    """Main function to scan codebase"""
    codebase_dir = Path(__file__).parent
    issues = []
    
    # Files to scan
    files_to_scan = [
        'combined_analysis_optimized.py',
        'player_gallery.py',
        'soccer_analysis_gui.py',
        'setup_wizard.py',
        'playback_viewer.py',
    ]
    
    for filename in files_to_scan:
        file_path = codebase_dir / filename
        if file_path.exists():
            print(f"Scanning {filename}...")
            file_issues = find_silent_failures(file_path)
            issues.extend(file_issues)
    
    # Print results
    print(f"\n{'='*80}")
    print(f"Found {len(issues)} potential silent failures")
    print(f"{'='*80}\n")
    
    for issue in issues:
        print(f"File: {issue['file']}")
        if 'line' in issue:
            print(f"  Line {issue['line']}: {issue['issue']}")
        else:
            print(f"  Try block starts at line {issue['try_line']}")
            print(f"  Except at line {issue['except_line']}: {issue['issue']}")
        print()
    
    # Save to file
    output_file = codebase_dir / 'silent_failures_report.txt'
    with open(output_file, 'w') as f:
        f.write(f"Silent Failures Report\n")
        f.write(f"{'='*80}\n")
        f.write(f"Total issues found: {len(issues)}\n")
        f.write(f"{'='*80}\n\n")
        
        for issue in issues:
            f.write(f"File: {issue['file']}\n")
            if 'line' in issue:
                f.write(f"  Line {issue['line']}: {issue['issue']}\n")
            else:
                f.write(f"  Try block starts at line {issue['try_line']}\n")
                f.write(f"  Except at line {issue['except_line']}: {issue['issue']}\n")
            f.write("\n")
    
    print(f"Report saved to: {output_file}")

if __name__ == "__main__":
    main()

