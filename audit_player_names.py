"""
Script to audit player name normalization usage
Finds all places where player names are used and checks if extract_player_name is called
"""

import re
import ast
from pathlib import Path
from typing import List, Dict

def find_player_name_assignments(file_path: Path) -> List[Dict]:
    """Find all places where player names are assigned or used"""
    issues = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Pattern 1: Direct assignments to player_names dictionary
    pattern1 = r'player_names\[.*?\]\s*='
    for i, line in enumerate(lines, 1):
        if re.search(pattern1, line):
            # Check if extract_player_name is used nearby
            context_start = max(0, i - 5)
            context_end = min(len(lines), i + 5)
            context = '\n'.join(lines[context_start:context_end])
            
            if 'extract_player_name' not in context:
                issues.append({
                    'file': str(file_path),
                    'line': i,
                    'type': 'player_names assignment',
                    'code': line.strip(),
                    'issue': 'Player name assigned without normalization'
                })
    
    # Pattern 2: Gallery operations (add_player, update_player)
    pattern2 = r'(add_player|update_player)\s*\([^)]*name\s*='
    for i, line in enumerate(lines, 1):
        if re.search(pattern2, line):
            # Check if extract_player_name is used
            context_start = max(0, i - 10)
            context_end = min(len(lines), i + 10)
            context = '\n'.join(lines[context_start:context_end])
            
            if 'extract_player_name' not in context:
                issues.append({
                    'file': str(file_path),
                    'line': i,
                    'type': 'gallery operation',
                    'code': line.strip(),
                    'issue': 'Gallery operation may not normalize player name'
                })
    
    # Pattern 3: Dictionary keys or values with player names
    pattern3 = r'[\'"](.*?)[\'"].*?player.*?name|player.*?name.*?[\'"](.*?)[\'"]'
    # This is more complex, would need AST parsing
    
    return issues

def main():
    """Main function to audit codebase"""
    codebase_dir = Path(__file__).parent
    all_issues = []
    
    files_to_scan = [
        'combined_analysis_optimized.py',
        'player_gallery.py',
        'setup_wizard.py',
    ]
    
    for filename in files_to_scan:
        file_path = codebase_dir / filename
        if file_path.exists():
            print(f"Auditing {filename}...")
            issues = find_player_name_assignments(file_path)
            all_issues.extend(issues)
            print(f"  Found {len(issues)} potential issues")
    
    # Print results
    print(f"\n{'='*80}")
    print(f"Found {len(all_issues)} potential player name normalization issues")
    print(f"{'='*80}\n")
    
    for issue in all_issues:
        print(f"File: {issue['file']}")
        print(f"  Line {issue['line']}: {issue['type']}")
        print(f"  Code: {issue['code']}")
        print(f"  Issue: {issue['issue']}")
        print()
    
    # Save to file
    output_file = codebase_dir / 'player_name_audit_report.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"Player Name Normalization Audit Report\n")
        f.write(f"{'='*80}\n")
        f.write(f"Total issues found: {len(all_issues)}\n")
        f.write(f"{'='*80}\n\n")
        
        for issue in all_issues:
            f.write(f"File: {issue['file']}\n")
            f.write(f"  Line {issue['line']}: {issue['type']}\n")
            f.write(f"  Code: {issue['code']}\n")
            f.write(f"  Issue: {issue['issue']}\n")
            f.write("\n")
    
    print(f"Report saved to: {output_file}")

if __name__ == "__main__":
    main()

