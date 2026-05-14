# FinalsTracker

> [!NOTE]
> This project was made with assistance an AI via [Opencode](https://opencode.ai/)

A real-time second-monitor side tracker for **THE FINALS** by Embark Studios. Captures on-screen game data via OCR and displays live stats, session summaries, and match history on a dashboard accessible from any browser on your second monitor.

> [!WARNING]
> This project is extreme WIP, features listed on this page may not even exist yet or were broken last commit.\
> Currently, I consider the project to be: **NONFUNCTIONAL**

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Python Backend                        │
│                                                          │
│  ┌────────────┐  ┌──────────┐  ┌────────────────────┐    │
│  │ GameWindow │  │  Screen  │  │   OCR Pipeline     │    │
│  │ (win32gui) │─▶│ Capture  │─▶│ (OpenCV+Tesseract) │    │
│  └────────────┘  │  (mss)   │  └─────────┬──────────┘    │
│                  └──────────┘            │               │
│                                          ▼               │
│  ┌────────────┐  ┌──────────┐  ┌────────────────────┐    │
│  │  Database  │  │ Session  │◀─│  State Machine +   │    │
│  │  (SQLite)  │  │ Tracker  │  │     Parser         │    │
│  └────────────┘  └────┬─────┘  └────────────────────┘    │
│                       │                                  │
│                       ▼                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │            LiveServer (aiohttp + WebSocket)      │    │
│  │                http://127.0.0.1:8080             │    │
│  └───────────────────────┬──────────────────────────┘    │
└──────────────────────────┼───────────────────────────────┘
                           │ WebSocket (JSON)
                           ▼
┌──────────────────────────────────────────────────────────┐
│                Second Monitor Dashboard                  │
│              (HTML/CSS/JS - any browser)                 │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Live Match  │  │    Session   │  │    Match     │    │
│  │  (HUD data)  │  │    Summary   │  │   History    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└──────────────────────────────────────────────────────────┘
```

### Flow

1. **GameWindow** detects the THE FINALS process window via `win32gui`
2. **ScreenCapture** uses `mss` to capture specific screen regions at configurable FPS
3. **OCR Pipeline** preprocesses images (grayscale, threshold, denoise) and runs `pytesseract` to extract text
4. **Parser** converts raw OCR output into structured match data (kills, score, etc.)
5. **StateMachine** tracks game lifecycle: MENU → LOADING → INGAME → SCOREBOARD → SUMMARY
6. **SessionTracker** accumulates per-match and per-session stats
7. **MatchDatabase** persists matches to SQLite for historical analysis
8. **LiveServer** serves the dashboard and pushes real-time JSON updates via WebSocket
9. **Dashboard** (any browser on second monitor) receives updates and re-renders live

## Project Structure

```
FinalsTracker/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── config.json                  # User configuration
├── debug_replay.py              # Debug replay tool
├── region_calibrator.py         # Region calibration tool
├── data/                        # Created at runtime - SQLite DB lives here
├── debug_sessions/              # Debug recording sessions
└── src/
    ├── main.py                  # Entry point, wires everything together
    ├── capture/
    │   ├── window.py            # Game window detection via win32gui
    │   └── screen.py            # Screen region capture via mss
    ├── ocr/
    │   ├── pipeline.py          # OpenCV preprocessing + pytesseract OCR
    │   └── regions.py           # Screen region definitions (fractional coords)
    ├── game/
    │   ├── state_machine.py     # Game lifecycle state machine
    │   └── parser.py            # OCR data structs and parsing helpers
    ├── tracker/
    │   ├── session.py           # Per-session stat accumulation
    │   └── database.py          # SQLite match persistence
    ├── server/
    │   └── server.py            # aiohttp WebSocket + static file server
    ├── dashboard/
    │   ├── index.html           # Dashboard main page
    │   ├── style.css            # CSS for the dashboard
    │   └── app.js               # WebSocket client + live UI updates
    └── debug/
        ├── recorder.py          # Debug recorder to record full sessions
        ├── replay.py            # Debug replay viewer to replay full sessions
        └── region_calibrator.py # Debug region calibration tool
```

## Setup

### Prerequisites

- **Python 3.14+** (untested on versions below, might work)
- **Tesseract OCR** (separate installation required):
  - Download from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
  - Install to default location (or add to PATH manually)
  - Verify: `tesseract --version`

### Installation

```bash
# Clone or cd into the project
cd FinalsTracker

# Create virtual environment (recommended)
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

| Package         | Purpose                                                          |
|-----------------|------------------------------------------------------------------|
| `opencv-python` | Image preprocessing (grayscale, threshold, denoising)            |
| `numpy`         | Array operations for image data                                  |
| `pywin32`       | Windows API bindings (game window detection, process management) |
| `mss`           | Fast multi-monitor screen capture                                |
| `pytesseract`   | Python wrapper for Tesseract OCR engine                          |
| `aiohttp`       | Async HTTP + WebSocket server                                    |
| `Pillow`        | Image format handling                                            |
| `PyQt6`         | Debug tools GUI                                                  |

## Configuration

Edit `config.json` to adjust settings:

```json5
{
    "capture": {
        "fps": 10,               // How often to capture regions (fps)
        "monitor_index": 0       // Monitor to capture (0 = primary)
    },
    "game": {
        "window_title": "THE FINALS",  // Window title substring to match
        "scoreboard_debounce_sec": 0.3 // Debounce for Tab key detection
    },
    "server": {
        "host": "127.0.0.1",     // Dashboard IP (127.0.0.1 is localhost, set as "" to bind to your device IP)
        "port": 8080             // Dashboard Web UI port
    },
    "database": {
        "path": "data/matches.db" // SQLite database path (relative to config)
    },
    "logging": {
        "console_level": "INFO",  // LOD to show in console
        "file_level": "DEBUG",    // LOD to show in file
        "log_dir": "logs",        // log directory
        "log_file": "tracker.log" // log name, does not support making multiple files (yet)
    },
    "debug": {
        "save_captures": false,          // Save debug screenshots
        "save_dir": "debug_captures",    // Debug capture directory
        "record_sessions": false,        // Record debug sessions
        "sessions_dir": "debug_sessions" // Session recording directory
    },
    "calibration": {                     // calibration of regions
        "regions_preset": "2560x1440",   // tuned screen size
        "custom_regions": {}             // unused artifact of older features, might be removed in the future
    }
}
```

### Screen Region Calibration

Screen regions are defined as fractional coordinates `(left, top, right, bottom)` in the range `[0, 1]` relative to the game window size. Defaults target 2560x1440 but auto-scale to any resolution.

To calibrate for your setup:
1. Use the **Region Calibrator** tool (see Debug Tools below)
2. Or edit `src/ocr/regions.py` directly
3. Each region is `(left_frac, top_frac, right_frac, bottom_frac)`

## Usage

```bash
# Ensure game is running (windowed / borderless)
cd FinalsTracker
.\venv\Scripts\activate

# Run the tracker
python -m src.main config.json
```

1. The tracker will auto-detect THE FINALS window
2. Open a browser on your second monitor to `http://127.0.0.1:8080`
3. The dashboard updates in real-time as you play
4. Press Ctrl+C in terminal to stop

### What Gets Tracked

| Data                                       | Source         | When               |
|--------------------------------------------|----------------|--------------------|
| Kills, Deaths, Assists, Combat Score, etc. | Scoreboard     | When Tab is held   |
| Team cash/score                            | HUD region     | During match       |
| Match result (win/loss)                    | Summary screen | Match end          |
| Full scoreboard                            | Tab overlay    | When Tab is held   |
| Session aggregates                         | Computed       | Across all matches |
| Career history                             | SQLite DB      | Across sessions    |

## Debug Tools

> [!NOTE]
> These debug tools are all quite experimental (they aren't the priority here!) so often users may into unique issues regarding them

### Debug Replay Tool

Based on the First Robotics Competition (FRC) tool "AdvantageScope", the replay tool allows to rewatch saved sessions and analyze what might be
causing issues.

> [!CAUTION]
> This tool can cause stuttering, lag, or more during gameplay - use at your own risk!\
> (it also uses a lot of storage!!!)

**Location:** `debug_replay.py`

**Features:**
- Timeline with play/pause, speed control (0.25x-4x), frame scrubbing
- Image viewer with region overlay boxes drawn on top
- Data panel showing extracted values per frame
- Game state shown in status bar

**Usage:**

To use this feature you must enable it in your config.json
```json5
{
  // ...

  "debug": {
    "save_captures": false,
    "save_dir": "debug_captures",
    "record_sessions": false,        // set to true to begin recording
    "sessions_dir": "debug_sessions" // location of the session info 
  },
  
  // ...
}
```

```bash
# Launch empty viewer
python debug_replay.py

# Load specific session
python debug_replay.py debug_sessions/session_20240512_123456

# Load most recent session
python debug_replay.py --latest
```

**Session Structure:**
```
session_{time}/
├── metadata.json         # capture config, fps, window title, etc.
└── frames/
    └── frame_{id}/       # id is an increasing integer value
        ├── metadata.json # regions, extracted values, game state, etc.
        └── raw.png       # raw unedited screenshot
```

### Region Calibrator

A visual tool to help define OCR regions based on screenshots.

**Location:** `region_calibrator.py`

**Features:**
- Load any screenshot (PNG/JPG/BMP)
- **Shift + drag** to select a region (zoom/pan with Ctrl+scroll and drag)
- Real-time display of fractional coordinates
- Save multiple named regions
- Export all regions as Python dict for direct use in `src/ocr/regions.py`

**Usage:**
```bash
python region_calibrator.py
```

**Workflow:**
1. Load a screenshot from game capture
2. Hold Shift + drag to select a region
3. See values update in "Current Selection" panel
4. Click "Save Region" to name and store it
5. Repeat for all needed regions
6. Click "Export All as Python Dict" and update `src/ocr/regions.py` as necessary

## How the OCR Works

1. **Capture**: `mss` grabs a specific pixel region of the game window
2. **Preprocess**: OpenCV converts to grayscale, applies OTSU thresholding, denoises, and optionally upscales
3. **OCR**: `pytesseract` reads the processed image with character whitelisting (digits only for scores)
4. **Parse**: Raw text is cleaned and converted to integers or structured fields
5. **Validate**: Results with implausible values are discarded and retried on next frame

### Tips for Better OCR Accuracy

- Play in **borderless windowed** mode (required for screen capture)
- Use 2560x1440 resolution for best results with default region definitions
- Ensure the game UI is at default scale (100% UI scaling in Windows)
- Good lighting (no extreme HDR over-brightness)

## Safety

This tool uses **screen capture only** - it reads pixels from the screen, the same way a screenshot tool or streaming software does. It does NOT:
- Read or modify game memory
- Inject code into any process
- Intercept network traffic
- Hook any game functions

This is the same approach used by `finals-stats.com` and `thefinals.gg`, and complies with Embark's guidelines for third-party tools.

