#!/usr/bin/env python3
import sys
import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
STUBS_DIR = PROJECT_ROOT / "packages" / "cascade-sdk" / "src" / "cascade"

def test_stubs():
    print(f"🔍 Verifying stubs in {STUBS_DIR}...")
    
    if not STUBS_DIR.exists():
        print(f"❌ Stubs directory not found: {STUBS_DIR}")
        sys.exit(1)

    has_errors = False
    
    # Recursively find all .pyi files
    for pyi_file in STUBS_DIR.glob("**/*.pyi"):
        try:
            with open(pyi_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Attempt to parse the file into an Abstract Syntax Tree
            # This catches SyntaxErrors like "<class 'str'>" or invalid indents
            ast.parse(content, filename=str(pyi_file))
            print(f"✅ [PASS] {pyi_file.relative_to(PROJECT_ROOT)}")
            
        except SyntaxError as e:
            has_errors = True
            print(f"❌ [FAIL] {pyi_file.relative_to(PROJECT_ROOT)}")
            print(f"   Line {e.lineno}: {e.text.strip() if e.text else ''}")
            print(f"   Error: {e.msg}")
        except Exception as e:
            has_errors = True
            print(f"❌ [FAIL] {pyi_file.relative_to(PROJECT_ROOT)}: {e}")

    if has_errors:
        print("\n🚫 Verification failed. Please fix the stub generator.")
        sys.exit(1)
    else:
        print("\n🎉 All stubs are valid Python syntax!")

if __name__ == "__main__":
    test_stubs()