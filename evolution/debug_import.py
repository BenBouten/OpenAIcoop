
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

try:
    from evolution.entities.lifeform import Lifeform
    with open("traceback.txt", "w") as f:
        f.write("SUCCESS")
    print("Import successful")
except ImportError as e:
    with open("traceback.txt", "w") as f:
        f.write(f"Import failed: {e}\n")
        import traceback
        traceback.print_exc(file=f)
except Exception as e:
    with open("traceback.txt", "w") as f:
        f.write(f"Other error: {e}\n")
        import traceback
        traceback.print_exc(file=f)
