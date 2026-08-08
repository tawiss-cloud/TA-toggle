# TA toggle (Titan Army Monitor Switcher)

Python utility for automatic switching of monitor settings for Titan Army monitors.

The program allows you to switch between Standard and Gaming monitor modes manually or automatically depending on whether a game or supported media player is running.

## Features

- Automatic game detection
- Automatic media player detection (MPC-HC, MPC-BE, VLC, PotPlayer)
- HDR detection
- Manual mode switching (Ctrl + Alt + Z)
- System tray application
- Custom brightness
- Custom Local Dimming
- Automatic return to Standard mode
- HDR color preset support

## Requirements

- Windows 10 / Windows 11
- Python 3.10+
- Monitor with DDC/CI enabled
- Titan Army monitor (or compatible VCP commands)

## Installation

Clone the repository or download it as ZIP.

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python toggle_modes.py
```

## Controls

### Ctrl + Alt + Z

- Switch monitor mode
- If HDR is enabled, applies HDR color preset

## Automatic switching

When enabled the application monitors running windows.

It switches to Gaming mode when:

- a fullscreen game is detected
- supported media players are running fullscreen

Returns to Standard mode when the application closes.

## Configuration

Settings are stored in

```
monitor_settings.json
```

## Screenshots

[(Add screenshots here)](https://github.com/tawiss-cloud/TA-toggle/blob/main/screenshots/scr.png?raw=true)

## License

MIT
