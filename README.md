# Sports Avatar Tool

Download player avatars from [TheSportsDB Free API](https://www.thesportsdb.com/free_sports_api).

## Local Run (Python)

Run web UI:

```powershell
python .\web_server.py
```

Open:

`http://127.0.0.1:8765`

Optional custom output folder:

```powershell
python .\web_server.py --output-dir "D:\sports_avatars"
```

## Features

- Input one or more player names from browser
- Download all same-name matches automatically (avoids overwrite/mis-match on duplicate names)
- Select output folder by typing path or using folder picker
- Preview downloaded images in result table

## Build Portable Package

Build package for current OS:

```powershell
python -m pip install pyinstaller
python .\packaging\build_portable.py
```

Output:

- `release/sports-avatar-tool-<os>-<arch>.zip`

Users can unzip and run directly:

- Windows: `web_server.exe`
- macOS/Linux: `web_server`

Default output folder in packaged mode:

- `./avatars` beside executable

## Cross-Platform CI Build

Workflow file:

- `.github/workflows/build-portable.yml`

It builds and uploads portable zip artifacts for:

- Windows
- macOS

Note:

- A single executable cannot run on all OSes. The workflow generates one package per target OS.
