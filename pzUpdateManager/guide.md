# Project Zomboid Update Monitor - Setup Guide

A Python script that automatically monitors for Project Zomboid game and mod updates, and handles server restarts with player warnings.

## Features

- **Automatic Game Update Detection** - Monitors Steam for new PZ builds
- **Mod Update Checking** - Uses RCON to check if workshop mods need updates  
- **Smart Restart Handling** - Immediate restart if no players, 30-minute countdown if players are connected
- **Player Notifications** - Sends in-game messages with restart warnings
- **Systemd Service Integration** - Works with existing PZ server setups
- **Comprehensive Logging** - Logs to both console and rotating log files

## Requirements

- Python 3.6+
- Project Zomboid dedicated server running as systemd service
- RCON enabled on your PZ server
- Steam Web API key

## Installation

1. **Download the script** to your server:
   ```bash
   wget https://raw.githubusercontent.com/[your-repo]/pz_update_monitor.py
   chmod +x pz_update_monitor.py
   ```

2. **Install required Python packages**:
   ```bash
   pip3 install requests
   ```

3. **Get a Steam Web API key**:
   - Visit: https://steamcommunity.com/dev/apikey
   - Sign in and create a key
   - Note down your API key

## Configuration

### Server Configuration (Project Zomboid)

1. **Enable RCON** in your PZ server config (`servertest.ini`):
   ```ini
   RCONPort=27015
   RCONPassword=your_secure_password_here
   ```

2. **Restart your PZ server** to apply RCON settings:
   ```bash
   sudo systemctl restart zomboid
   ```

### Monitor Configuration

1. **Run the script once** to create the default config:
   ```bash
   python3 pz_update_monitor.py
   ```

2. **Edit the generated config file** (`pz_monitor.conf`):
   ```ini
   [steam]
   api_key = YOUR_STEAM_API_KEY_HERE  # Replace with actual key
   app_id = 108600

   [server]
   host = localhost
   port = 16261
   rcon_port = 27015
   rcon_password = your_secure_password_here  # Match your servertest.ini
   service_name = zomboid  # Your systemd service name

   [monitor]
   check_interval = 300  # Check every 5 minutes
   check_mods = true     # Enable mod checking
   log_file = pz_monitor.log  # Log file location
   ```

## Testing

### Test RCON Connection
```bash
python3 pz_update_monitor.py test
```
Should show:
```
✓ RCON connection successful
✓ Found 2 log files: ['/home/steam/Zomboid/Logs/...']
✅ RCON test passed!
```

### Simulate Game Update
```bash
python3 pz_update_monitor.py test-steam-update
```
This will:
1. Temporarily set database to fake old build ID
2. Run Steam update check (will detect "update")
3. Trigger restart workflow
4. Restore original build ID

Expected output:
```
=== Simulating Steam Game Update ===
Set database to fake old build: 12345678
Steam build changed from 12345678 to [current_build]
✅ Steam update detected! Testing restart workflow...
[player count check and restart logic]
Restored original build ID: [current_build]
```

### Simulate Mod Updates
```bash
python3 pz_update_monitor.py test-mod-update
```
This will:
1. Create fake log content in memory (no file contamination)
2. Mock the log reading function temporarily
3. Test mod update detection with realistic log entries
4. Restore normal log reading afterward

Expected output:
```
=== Simulating Mod Update ===
Mocking log content with fake mod update messages:
  [11-06-25 13:19:47.123] LOG : General , 1749641987123> CheckModsNeedUpdate: Checking....
  [11-06-25 13:19:48.123] LOG : General , 1749641988123> CheckModsNeedUpdate: Mods need update.
  [11-06-25 13:19:49.123] LOG : General , 1749641989123> Mod BetterSorting Needs updating from version 1.2 to 1.3

Testing mod update detection with mocked logs...
Latest mod check response: CheckModsNeedUpdate: Mods need update.
Mods need updating.
✅ Mod update detected! Testing restart workflow...
✓ Log reading method restored
```

### Simulate Mods Up-to-Date
```bash
python3 pz_update_monitor.py test-mod-uptodate
```
Tests the opposite scenario - when mods are already up-to-date:
```
=== Simulating Mods Up-to-Date ===
Mocking log content with up-to-date mod messages:
  [timestamp] CheckModsNeedUpdate: Checking....
  [timestamp] CheckModsNeedUpdate: Mods updated.

Testing mod update detection with mocked logs...
✅ Correctly detected mods are up-to-date
✓ Log reading method restored
```

### Test Restart Scenarios

**Immediate Restart (No Players):**
```bash
python3 pz_update_monitor.py test-restart-immediate
```
Simulates 0 players → should restart immediately

**Scheduled Restart (With Players):**
```bash
python3 pz_update_monitor.py test-restart-scheduled
```
Simulates 3 players → should schedule 30-minute countdown

### Get Help
```bash
python3 pz_update_monitor.py help
```

### Complete Test Sequence
Test everything step by step:
```bash
# 1. Test RCON connection
python3 pz_update_monitor.py test

# 2. Test Steam update detection
python3 pz_update_monitor.py test-steam-update

# 3. Test mod update detection (updates needed)
python3 pz_update_monitor.py test-mod-update

# 4. Test mod detection (up-to-date)
python3 pz_update_monitor.py test-mod-uptodate

# 5. Test scheduled restart (safe - only sends messages)
python3 pz_update_monitor.py test-restart-scheduled
```

### Test Log Files
The script automatically detects PZ log files in common locations:
- `/home/steam/Zomboid/Logs/`
- `/home/[user]/Zomboid/Logs/`
- `~/.local/share/Project Zomboid/Logs/`

Log files follow the pattern: `DD-MM-YY_HH-MM-SS_DebugLog-server.txt`

## Running

### Manual Testing
```bash
python3 pz_update_monitor.py
```

### Run as Service (Recommended)

1. **Create a systemd service** (`/etc/systemd/system/pz-monitor.service`):
   ```ini
   [Unit]
   Description=Project Zomboid Update Monitor
   After=network.target
   Wants=zomboid.service

   [Service]
   Type=simple
   User=steam
   Group=steam
   WorkingDirectory=/home/steam/pz-monitor
   ExecStart=/usr/bin/python3 /home/steam/pz-monitor/pz_update_monitor.py
   Restart=always
   RestartSec=60

   [Install]
   WantedBy=multi-user.target
   ```

2. **Enable and start the service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable pz-monitor.service
   sudo systemctl start pz-monitor.service
   ```

3. **Check service status**:
   ```bash
   sudo systemctl status pz-monitor.service
   sudo journalctl -u pz-monitor.service -f
   ```

## How It Works

### Game Update Detection
1. **Queries Steam API** every 5 minutes for current build ID
2. **Compares with stored build ID** in local SQLite database
3. **Triggers restart** if build ID changes

### Mod Update Detection  
1. **Sends `checkModsNeedUpdate`** via RCON to PZ server
2. **Monitors PZ log files** for response:
   - `CheckModsNeedUpdate: Mods updated.` → No updates needed
   - `CheckModsNeedUpdate: Mods need update.` → Updates needed
3. **Triggers restart** if mods need updates

### Restart Behavior
- **No players connected** → Immediate restart
- **Players connected** → 30-minute countdown with warnings:
  - Initial message: "SERVER UPDATE AVAILABLE! Server will restart in 30 minutes"
  - 1-minute warning: "SERVER RESTART IN 1 MINUTE!"
  - Automatic save and restart

## Logging

### Log Files
- **Console output** - Real-time monitoring
- **Rotating log file** - `pz_monitor.log` (10MB max, 5 files kept)
- **Debug mode** - Set `PZ_DEBUG=1` environment variable

### Log Locations
Logs are automatically written to the current directory. You can configure the log file location in the config:
```ini
[monitor]
log_file = /path/to/custom/pz_monitor.log
```

## Troubleshooting

### RCON Connection Issues
```bash
# Check if RCON port is open
sudo netstat -tlnp | grep 27015

# Test with manual RCON client
sudo apt install mcrcon
mcrcon -H localhost -P 27015 -p your_password "help"
```

### Log File Detection Issues
Add specific paths to your config:
```ini
[server]
log_paths = /home/steam/Zomboid/Logs/11-06-25_11-07-15_DebugLog-server.txt
```

### Permission Issues
Ensure the monitor has permission to:
- Read PZ log files
- Restart the systemd service (sudo access)
- Write to the database and log files

### Common Error Messages

**"RCON authentication failed"**
- Check RCON password matches `servertest.ini`
- Verify RCON is enabled (RCONPassword not empty)

**"No server logs found"**
- Check PZ server is running and writing logs
- Verify log file paths in config
- Check file permissions

**"Could not determine player count"**
- RCON connection issue
- Server may be restarting or overloaded

## Advanced Configuration

### Custom Log Paths
```ini
[server]
log_paths = /custom/path/to/logs/server.txt,/another/path/log.txt
```

### Different Check Intervals
```ini
[monitor]
check_interval = 600  # Check every 10 minutes instead of 5
```

### Disable Mod Checking
```ini
[monitor]
check_mods = false  # Only check for game updates
```

## Files Created

The monitor creates these files in its working directory:
- `pz_monitor.conf` - Configuration file
- `pz_steam_versions.db` - SQLite database tracking Steam builds  
- `pz_monitor.log` - Main log file
- `pz_monitor.log.1`, `.2`, etc. - Rotated log files

## Support

If you encounter issues:
1. Check the log files for detailed error messages
2. Test RCON connection manually
3. Verify PZ server log file permissions
4. Ensure Steam API key is valid
5. Check systemd service status if running as service

For debugging, run with debug mode:
```bash
PZ_DEBUG=1 python3 pz_update_monitor.py test
```