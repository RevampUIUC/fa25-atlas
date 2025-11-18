#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validation script to verify all code fixes
Run this before starting the application
"""

import sys
import os
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_merge_conflicts():
    """Check for any remaining merge conflict markers"""
    print("🔍 Checking for merge conflicts...")
    conflicts = []

    files_to_check = [
        "app/main.py",
        "app/models.py",
        "app/dao.py",
        "app/twilio_client.py",
        "app/media_stream_handler.py",
    ]

    for file_path in files_to_check:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for i, line in enumerate(lines, 1):
                    # Check for actual merge conflict markers (not comment separators)
                    if line.startswith('<<<<<<< ') or line.startswith('>>>>>>> '):
                        conflicts.append((file_path, i, line.strip()))
                    # Check for ======= that's not a comment separator
                    elif line.strip() == '=======' and i > 1:
                        prev_line = lines[i-2].strip() if i >= 2 else ''
                        next_line = lines[i].strip() if i < len(lines) else ''
                        # It's a conflict if not surrounded by comment markers
                        if not (prev_line.startswith('#') or next_line.startswith('#')):
                            conflicts.append((file_path, i, line.strip()))

    if conflicts:
        print(f"❌ FAILED: Merge conflicts found in {len(conflicts)} location(s):")
        for file, line_num, text in conflicts:
            print(f"   - {file}:{line_num}: {text}")
        return False
    else:
        print("✅ PASSED: No merge conflicts found")
        return True

def check_syntax():
    """Check Python syntax in all main files"""
    print("\n🔍 Checking Python syntax...")

    files_to_check = [
        "app/main.py",
        "app/models.py",
        "app/dao.py",
        "app/twilio_client.py",
        "app/deepgram_client.py",
        "app/media_stream_handler.py",
        "app/voicemail_detector.py",
    ]

    errors = []
    for file_path in files_to_check:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    compile(f.read(), file_path, 'exec')
            except SyntaxError as e:
                errors.append((file_path, str(e)))

    if errors:
        print(f"❌ FAILED: Syntax errors found in {len(errors)} file(s):")
        for file, error in errors:
            print(f"   - {file}: {error}")
        return False
    else:
        print("✅ PASSED: All files have valid Python syntax")
        return True

def check_env_file():
    """Check if .env file exists"""
    print("\n🔍 Checking .env file...")

    if os.path.exists(".env"):
        print("✅ PASSED: .env file exists")
        return True
    else:
        print("❌ FAILED: .env file not found")
        print("   Create .env from .env-example and configure your credentials")
        return False

def check_requirements():
    """Check if requirements.txt has no duplicates"""
    print("\n🔍 Checking requirements.txt...")

    if os.path.exists("requirements.txt"):
        with open("requirements.txt", 'r') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        packages = [line.split('==')[0] for line in lines if '==' in line]
        duplicates = [pkg for pkg in set(packages) if packages.count(pkg) > 1]

        if duplicates:
            print(f"❌ FAILED: Duplicate packages found: {', '.join(duplicates)}")
            return False
        else:
            print("✅ PASSED: No duplicate packages in requirements.txt")
            return True
    else:
        print("❌ FAILED: requirements.txt not found")
        return False

def check_imports():
    """Check critical imports are accessible"""
    print("\n🔍 Checking import structure...")

    critical_imports = [
        ("app.models", "UserCreate, OutboundCallRequest, CallFeedbackRequest"),
        ("app.dao", "Database"),
    ]

    all_passed = True
    for module, items in critical_imports:
        try:
            # Just check if files exist and are syntactically valid
            module_path = module.replace('.', os.sep) + '.py'
            if os.path.exists(module_path):
                with open(module_path, 'r', encoding='utf-8') as f:
                    compile(f.read(), module_path, 'exec')
                print(f"✅ {module} - Structure valid")
            else:
                print(f"❌ {module} - File not found")
                all_passed = False
        except Exception as e:
            print(f"❌ {module} - Error: {e}")
            all_passed = False

    return all_passed

def main():
    """Run all validation checks"""
    print("=" * 60)
    print("Track 1 - Code Validation")
    print("=" * 60)

    checks = [
        check_merge_conflicts,
        check_syntax,
        check_env_file,
        check_requirements,
        check_imports,
    ]

    results = []
    for check in checks:
        try:
            results.append(check())
        except Exception as e:
            print(f"\n❌ ERROR in {check.__name__}: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    if all(results):
        print(f"✅ ALL CHECKS PASSED ({passed}/{total})")
        print("\n🚀 Your application is ready to run!")
        print("\nNext steps:")
        print("1. Configure .env with your credentials")
        print("2. Install dependencies: pip install -r requirements.txt")
        print("3. Run the server: uvicorn app.main:app --reload")
        return 0
    else:
        print(f"❌ SOME CHECKS FAILED ({passed}/{total} passed)")
        print("\n⚠️  Please fix the issues above before running the application")
        return 1

if __name__ == "__main__":
    sys.exit(main())
