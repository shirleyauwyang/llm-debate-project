"""Run the supplied final sample, offline unless --live is passed."""
from pathlib import Path
import sys
from debate import main

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    run = "final" if "--live" in sys.argv else "mock_final"
    sys.argv[1:1] = ["run", "--manifest", str(root / "final_manifest.json"),
                     "--out", str(root / "runs_v2" / run)]
    main()
