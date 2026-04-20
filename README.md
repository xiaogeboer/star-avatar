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

- Windows: double-click `start.bat` (or run `sports-avatar-tool.exe`)
- macOS: double-click `start.command` (or run `./sports-avatar-tool`)

Default output folder in packaged mode:

- `./avatars` beside executable

## Cross-Platform CI Build

Workflow file:

- `.github/workflows/build-portable.yml`

It builds and uploads portable zip artifacts for:

- Windows
- macOS

## macOS Signing + Notarization (CI)

The macOS job is configured to sign and notarize automatically.  
You need to add the following GitHub repository secrets:

- `APPLE_DEVELOPER_ID_APPLICATION_CERT_BASE64`
- `APPLE_DEVELOPER_ID_APPLICATION_CERT_PASSWORD`
- `APPLE_DEVELOPER_ID_APPLICATION_IDENTITY`
- `APPLE_ID`
- `APPLE_APP_SPECIFIC_PASSWORD`
- `APPLE_TEAM_ID`

If these secrets are missing, the macOS workflow will fail intentionally.

Note:

- A single executable cannot run on all OSes. The workflow generates one package per target OS.
