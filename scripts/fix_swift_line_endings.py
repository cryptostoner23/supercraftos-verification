#!/usr/bin/env python3
"""Fix Swift source files with CRLF line endings to LF for Xcode compatibility."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'ios_app_dist' / 'YourApp.swiftpm'

def fix_line_endings(file_path: Path):
    """Convert CRLF to LF in Swift source files."""
    content = file_path.read_text(encoding='utf-8')
    if '\r\n' in content:
        content = content.replace('\r\n', '\n')
        file_path.write_text(content, encoding='utf-8')
        print(f"✅ Fixed line endings in {file_path}")

def main():
    # Check for CRLF issues
    problematic_files = []
    for swift_file in BUNDLE.glob('*.swift'):
        content = swift_file.read_text(encoding='utf-8')
        if '\r\n' in content:
            problematic_files.append(swift_file)
    
    if problematic_files:
        print(f"⚠️  Found {len(problematic_files)} Swift files with CRLF line endings:")
        for f in problematic_files:
            print(f"  - {f.name}")
        print("⚠️  Fixing line endings...")
        for f in problematic_files:
            fix_line_endings(f)
        print("✅ Line endings fixed")
    else:
        print("✅ All Swift files have correct LF line endings")

if __name__ == '__main__':
    main()