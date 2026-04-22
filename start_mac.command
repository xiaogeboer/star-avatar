#!/bin/bash
cd "$(dirname "$0")"
echo "========================================"
echo "  Sports Avatar Downloader - Web UI"
echo "========================================"
echo ""
echo "  Starting server..."
echo "  Browser will open automatically."
echo "  Press Ctrl+C to stop."
echo ""
python3 web_server.py
