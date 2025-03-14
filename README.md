# FordPass Battery Monitor

A cross-platform utility to monitor your Ford EV battery status and display notifications when charging status changes.

![Notification Example](https://via.placeholder.com/400x100?text=Battery+Status+Notification)

## Overview

This script checks your Ford EV's battery status at regular intervals and displays desktop notifications when the battery range or charge percentage changes. It works on Windows, macOS, and Linux (Ubuntu).

### Features

- Monitor battery charge percentage and range
- Display native desktop notifications when values change
- Round values to prevent notifications from small fluctuations
- Remember previous state between runs
- Cross-platform support (Windows, Linux, macOS)
- Multiple notification methods for different platforms

## Requirements

- Python 3.6 or higher
- FordPass account with an EV vehicle
- Your vehicle's VIN number

## Installation

### Step 1: Download the scripts

- Save `fordpass_api.py` (renamed from `fordpass-api.py` if needed)
- Save `battery_monitor.py`

### Step 2: Install dependencies

#### Core dependency (for all platforms)
```bash
pip install requests
```

#### Windows-specific dependency
```bash
pip install win10toast
```

#### Linux (Ubuntu) dependencies (install at least one)
```bash
# Option 1
sudo apt install python3-notify2

# Option 2
sudo apt install python3-gi gir1.2-notify-0.7

# Option 3
sudo apt install libnotify-bin
```

#### macOS
No additional dependencies required.

### Step 3: Make the script executable (Linux/macOS only)
```bash
chmod +x battery_monitor.py
```

## Usage

### Basic Usage

```bash
python battery_monitor.py
```

You'll be prompted to enter your FordPass username, password, and VIN.

### Using Command-line Arguments

```bash
python battery_monitor.py --username your_email@example.com --password your_password --vin YOUR_VEHICLE_VIN
```

### Using Environment Variables

```bash
# Set environment variables
export FORDPASS_USERNAME=your_email@example.com
export FORDPASS_PASSWORD=your_password
export FORDPASS_VIN=YOUR_VEHICLE_VIN

# Run the script
python battery_monitor.py
```

### Command-line Options

```
--username, -u      FordPass username/email
--password, -p      FordPass password
--vin, -v           Vehicle identification number
--interval, -i      Check interval in seconds (default: 60)
--config, -c        Config file path (default: battery_monitor_config.json)
--daemon, -d        Run as a daemon in the background (Linux/macOS only)
```

## Running at Startup

### Windows

1. Create a batch file (e.g., `run_monitor.bat`) with:
   ```batch
   @echo off
   cd /d %~dp0
   python battery_monitor.py
   ```

2. Press `Win + R`, type `shell:startup` and press Enter
3. Copy or create a shortcut to your batch file in this folder

### Ubuntu/Linux

Create a systemd service:

1. Create a file at `/etc/systemd/system/fordpass-battery-monitor.service`:
   ```ini
   [Unit]
   Description=FordPass Battery Monitor
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   User=YOUR_USERNAME
   WorkingDirectory=/path/to/script/directory
   ExecStart=/usr/bin/python3 /path/to/script/directory/battery_monitor.py
   Restart=always
   RestartSec=30
   Environment="FORDPASS_USERNAME=your_email@example.com"
   Environment="FORDPASS_PASSWORD=your_password"
   Environment="FORDPASS_VIN=YOUR_VEHICLE_VIN"

   [Install]
   WantedBy=multi-user.target
   ```

2. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable fordpass-battery-monitor
   sudo systemctl start fordpass-battery-monitor
   ```

### macOS

1. Create a file at `~/Library/LaunchAgents/com.fordpass.batterymonitor.plist`:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.fordpass.batterymonitor</string>
       <key>ProgramArguments</key>
       <array>
           <string>/usr/bin/python3</string>
           <string>/path/to/battery_monitor.py</string>
       </array>
       <key>EnvironmentVariables</key>
       <dict>
           <key>FORDPASS_USERNAME</key>
           <string>your_email@example.com</string>
           <key>FORDPASS_PASSWORD</key>
           <string>your_password</string>
           <key>FORDPASS_VIN</key>
           <string>YOUR_VEHICLE_VIN</string>
       </dict>
       <key>RunAtLoad</key>
       <true/>
       <key>KeepAlive</key>
       <true/>
   </dict>
   </plist>
   ```

2. Load the agent:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.fordpass.batterymonitor.plist
   ```

## Troubleshooting

### Script can't find the FordPassAPI module

Make sure:
- Both script files are in the same directory
- The FordPass API file is named either `fordpass_api.py` or `fordpass-api.py`

### No notifications appear

#### Windows
- Install win10toast: `pip install win10toast`
- Check Windows notification settings

#### Linux/Ubuntu
- Install notification package: `sudo apt install python3-notify2`
- Test if notifications work: `notify-send "Test" "This is a test"`

#### macOS
- Check if notifications are enabled in System Preferences

### Authentication Failures

- Verify your FordPass credentials work in the mobile app
- Try running the original FordPass API script directly to test

## Security Notes

- Consider using environment variables instead of hardcoded credentials
- Set appropriate file permissions on the config file
- For better security, use a credentials manager or password vault

## Disclaimer

This project is not affiliated with, endorsed by, or connected to Ford Motor Company. Use at your own risk.

## License

This project is available under the MIT License.

## Credits

Based on the FordPass API Python Implementation.
