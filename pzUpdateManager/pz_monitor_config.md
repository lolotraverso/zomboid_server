# Project Zomboid Update Monitor - Setup Guide

## Configuration File (pz_monitor.conf)

Create this configuration file in the same directory as the Python script:

```ini
[steam]
# Get your Steam Web API key from: https://steamcommunity.com/dev/apikey
api_key = YOUR_STEAM_API_KEY_HERE

# Project Zomboid App ID (default: 108600)
app_id = 108600

# Comma-separated list of Workshop mod IDs you want to monitor
# Find these in the mod URLs: steamcommunity.com/sharedfiles/filedetails/?id=WORKSHOP_ID
workshop_items = 2169435993,2313387159,2366717227

[server]
# Server connection details
host = localhost
port = 16261
rcon_port = 27015
rcon_password = your_rcon_password_here

# Systemd service name for your PZ server
service_name = zomboid

[monitor]
# How often to check for updates (in seconds)
check_interval = 300
```

## Installation Steps

### 1. Install Dependencies

```bash
# Update system
sudo apt update

# Install Python and pip
sudo apt install python3 python3-pip

# Install required Python packages
pip3 install requests

# Install mcrcon for RCON communication
sudo apt install mcrcon
```

### 2. Setup RCON in Project Zomboid

Edit your Project Zomboid server configuration file (usually in `~/.local/share/Project Zomboid/Server/`):

```ini
# In your server.ini file, enable RCON:
RCONPort=27015
RCONPassword=your_secure_password_here
```

### 3. Configure Systemd Service (Optional but Recommended)

Create a systemd service for the monitor:

```bash
sudo nano /etc/systemd/system/pz-monitor.service
```

Add this content:

```ini
[Unit]
Description=Project Zomboid Update Monitor
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/your/script
ExecStart=/usr/bin/python3 /path/to/your/script/pz_update_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pz-monitor
sudo systemctl start pz-monitor
```

### 4. Sudo Permissions for Service Restart

The script needs to restart your PZ server service. Add sudo permissions:

```bash
sudo visudo
```

Add this line (replace `username` with your actual username):

```
username ALL=(ALL) NOPASSWD: /bin/systemctl restart zomboid
```

## Usage

### Manual Run
```bash
python3 pz_update_monitor.py
```

### Check Service Status
```bash
sudo systemctl status pz-monitor
```

### View Logs
```bash
sudo journalctl -u pz-monitor -f
```

## How It Works

1. **Update Detection**: 
   - Monitors Steam API for Project Zomboid build changes
   - Checks Workshop API for subscribed mod updates
   - Stores version info in local SQLite database

2. **Player Check**: 
   - Uses RCON to query current player count
   - If no players: immediate restart
   - If players online: scheduled restart with warnings

3. **Notification System**: 
   - 30-minute warning when update detected
   - 1-minute final warning
   - Uses RCON to send in-game messages

4. **Restart Process**: 
   - Gracefully restarts systemd service
   - Maintains update history in database

## Troubleshooting

### Common Issues:

1. **RCON Connection Failed**: 
   - Check RCON port and password in server config
   - Ensure server is running and RCON is enabled

2. **Permission Denied on Restart**: 
   - Verify sudo configuration for systemctl
   - Check service name matches your actual service

3. **Steam API Errors**: 
   - Verify Steam API key is valid
   - Check internet connection and API rate limits

4. **Workshop Mod Detection**: 
   - Ensure mod IDs are correct (numbers only)
   - Some private/removed mods may cause errors

### Debug Mode:

To run with verbose logging:

```python
# In the script, change logging level:
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
```

## Customization Options

- **Check Interval**: Adjust `check_interval` in config (default: 5 minutes)
- **Warning Times**: Modify timer durations in `schedule_restart_with_warnings()`
- **Messages**: Customize server messages in the notification functions
- **Additional Checks**: Add custom update detection logic for other sources

## Security Notes

- Store configuration file with restricted permissions: `chmod 600 pz_monitor.conf`
- Use a strong RCON password
- Consider running the service as a dedicated user
- Monitor logs for any suspicious activity