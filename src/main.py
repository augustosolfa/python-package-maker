import sys
import os

def main():
    print("=========================================")
    print("      Portable Windows Application       ")
    print("=========================================")
    print(f"Python Version: {sys.version}")
    print(f"Executable:     {sys.executable}")
    print(f"Working Dir:    {os.getcwd()}")
    print("-----------------------------------------")
    print("sys.path:")
    for path in sys.path:
        print(f"  - {path}")
    print("-----------------------------------------")
    print("Attempting to import standard & external libs:")
    try:
        import urllib.request
        print("  [SUCCESS] imported urllib.request")
    except ImportError as e:
        print(f"  [FAILED] importing urllib.request: {e}")

    try:
        # Test loading a site-package dependency if present
        import requests
        print("  [SUCCESS] imported requests")
        print(f"            Version: {requests.__version__}")
    except ImportError as e:
        print(f"  [INFO] requests package not available (expected if not installed): {e}")

    print("=========================================")
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
