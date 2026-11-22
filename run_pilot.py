"""Run the supplied pilot sample, offline unless --live is passed."""
from pathlib import Path
import sys
from debate import main

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    run = "pilot" if "--live" in sys.argv else "mock_pilot"
    sys.argv[1:1] = ["run", "--manifest", str(root / "pilot_manifest.json"),
                     "--out", str(root / "runs" / run)]
    main()
