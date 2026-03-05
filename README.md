# moises-local-mac (Phase 2)

Local, macOS-only "Moises-like" stem splitter.

## What’s included
- `engine/`: local FastAPI engine that runs `demucs-mlx`, then Phase-2 post-processing (residual correction, peak limiting)
- `macos-app/MoisesLocalMac/`: SwiftUI client that auto-starts the engine, runs jobs, shows progress, and keeps a local Library (SQLite)

## Dev prerequisites
- macOS
- Xcode (for the SwiftUI app)
- Python 3 (for the local engine)
- `demucs-mlx` installed in the engine venv

## Engine setup
```bash
cd engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install demucs-mlx
```

## Run in dev
In this Phase 2 setup the app auto-starts the engine by running:
`python3 -m uvicorn server:app --host 127.0.0.1 --port 8732`
from the `engine/` directory.

> Note: In Phase 3 you would bundle the engine + venv inside the .app.

## Open in VS Code
Just open the folder `moises-local-mac` in VS Code.
