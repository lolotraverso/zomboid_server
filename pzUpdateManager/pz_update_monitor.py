#!/usr/bin/env python3
"""
Project Zomboid Server Update Monitor
Works with systemd service using RCON + proper log file reading
"""

import json
import time
import subprocess
import threading
import requests
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
import socket
import struct
import os
import glob
from datetime import datetime, timedelta
from pathlib import Path
import configparser

class RCONClient:
    """Project Zomboid RCON client implementation"""
    
    def __init__(self, host, port, password):
        self.host = host
        self.port = port
        self.password = password
        self.socket = None
        self.request_id = 0
    
    def connect(self):
        """Connect to RCON server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            
            # Authenticate
            self._send_packet(3, self.password)  # SERVERDATA_AUTH
            response = self._receive_packet()
            
            if response[0] == -1:  # Authentication failed
                raise Exception("RCON authentication failed")
                
            return True
        except Exception as e:
            if self.socket:
                self.socket.close()
                self.socket = None
            raise e
    
    def send_command(self, command):
        """Send command and return response (handles multi-packet responses)"""
        if not self.socket:
            self.connect()
        
        try:
            self._send_packet(2, command)  # SERVERDATA_EXECCOMMAND
            
            # Handle multi-packet response
            full_response = ""
            packet_count = 0
            max_packets = 10
            
            while packet_count < max_packets:
                try:
                    # Set timeout - longer for first packet, shorter for additional packets
                    if packet_count == 0:
                        self.socket.settimeout(10)  # First packet
                    else:
                        self.socket.settimeout(0.5)  # Additional packets
                    
                    request_id, packet_type, body = self._receive_packet()
                    packet_count += 1
                    
                    if body:
                        full_response += body
                    
                    # If we get an empty packet, that usually signals the end
                    if len(body) == 0:
                        break
                        
                except socket.timeout:
                    # Timeout means no more packets coming
                    break
                except Exception:
                    # Any other error means we're done
                    break
            
            # Reset timeout
            self.socket.settimeout(10)
            return full_response
            
        except Exception as e:
            self.close()
            raise e
    
    def _send_packet(self, packet_type, body):
        """Send RCON packet"""
        self.request_id += 1
        body_bytes = body.encode('utf-8')
        
        packet = struct.pack('<ii', self.request_id, packet_type) + body_bytes + b'\x00\x00'
        length = len(packet)
        
        self.socket.send(struct.pack('<i', length) + packet)
    
    def _receive_packet(self):
        """Receive RCON packet"""
        # Read packet length
        length_data = self.socket.recv(4)
        if len(length_data) < 4:
            raise Exception("Failed to receive packet length")
        
        length = struct.unpack('<i', length_data)[0]
        
        # Read packet data
        data = b''
        while len(data) < length:
            chunk = self.socket.recv(length - len(data))
            if not chunk:
                raise Exception("Connection closed while receiving packet")
            data += chunk
        
        # Parse packet
        request_id, packet_type = struct.unpack('<ii', data[:8])
        body = data[8:-2].decode('utf-8')  # Remove null terminators
        
        return request_id, packet_type, body
    
    def close(self):
        """Close RCON connection"""
        if self.socket:
            self.socket.close()
            self.socket = None

class PZUpdateMonitor:
    def __init__(self, config_file="pz_monitor.conf"):
        self.config = configparser.ConfigParser()
        
        # Debug info
        print(f"Script location: {os.path.abspath(__file__)}")
        print(f"Current working directory: {os.getcwd()}")
        
        # Try to find config file in multiple locations
        config_paths = [
            config_file,  # Current working directory
            os.path.join(os.path.dirname(__file__), config_file),  # Same directory as script
            os.path.join(os.path.expanduser("~"), config_file),  # Home directory
            f"/etc/{config_file}",  # System config directory
        ]
        
        config_found = False
        for config_path in config_paths:
            if os.path.exists(config_path):
                self.config.read(config_path)
                config_found = True
                print(f"Using config file: {os.path.abspath(config_path)}")
                break
        
        if not config_found:
            print(f"Warning: Config file '{config_file}' not found in any of these locations:")
            for path in config_paths:
                exists = "✓" if os.path.exists(path) else "✗"
                print(f"  {exists} {os.path.abspath(path)}")
            print("\nCreating default config file...")
            self.create_default_config(config_paths[1])  # Create in script directory
            self.config.read(config_paths[1])
        
        # Configuration with proper error handling
        try:
            self.steam_api_key = self.config.get('steam', 'api_key')
            if self.steam_api_key == 'YOUR_STEAM_API_KEY_HERE':
                print("Error: Please edit the config file and replace 'YOUR_STEAM_API_KEY_HERE' with your actual Steam API key.")
                print("Get your API key from: https://steamcommunity.com/dev/apikey")
                exit(1)
        except (configparser.NoSectionError, configparser.NoOptionError):
            print("Error: Steam API key not found in config. Please edit the config file and add your Steam API key.")
            print("Get your API key from: https://steamcommunity.com/dev/apikey")
            exit(1)
            
        self.app_id = self.config.get('steam', 'app_id', fallback='108600')  # PZ App ID
        
        self.server_host = self.config.get('server', 'host', fallback='localhost')
        self.server_port = self.config.getint('server', 'port', fallback=16261)
        self.rcon_port = self.config.getint('server', 'rcon_port', fallback=27015)
        
        try:
            self.rcon_password = self.config.get('server', 'rcon_password')
            if self.rcon_password == 'your_rcon_password_here':
                print("Error: Please edit the config file and set your RCON password.")
                print("This should match the RCONPassword in your Project Zomboid server configuration.")
                exit(1)
        except (configparser.NoSectionError, configparser.NoOptionError):
            print("Error: RCON password not found in config. Please edit the config file and add your RCON password.")
            exit(1)
            
        self.service_name = self.config.get('server', 'service_name', fallback='zomboid')
        
        # Log file paths for finding checkModsNeedUpdate results
        self.log_paths = self.config.get('server', 'log_paths', fallback='').split(',') if self.config.get('server', 'log_paths', fallback='') else []
        
        self.check_interval = self.config.getint('monitor', 'check_interval', fallback=300)  # 5 minutes
        self.check_mods = self.config.getboolean('monitor', 'check_mods', fallback=True)  # Enabled by default
        
        # Setup logging (both console and file)
        self.setup_logging()
        
        # Setup database for tracking Steam versions
        self.init_database()
        
        # Setup RCON client
        self.rcon = RCONClient(self.server_host, self.rcon_port, self.rcon_password)
        
        # Restart timer
        self.restart_timer = None
        self.restart_scheduled = False
    
    def setup_logging(self):
        """Setup both console and file logging"""
        log_level = logging.DEBUG if os.getenv('PZ_DEBUG') else logging.INFO
        
        # Create logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler with rotation (10MB max, keep 5 files)
        log_file = self.config.get('monitor', 'log_file', fallback='pz_monitor.log')
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Also setup root logger to prevent duplicate messages
        logging.getLogger().handlers.clear()
        
        self.logger.info(f"Logging to console and file: {log_file}")
        
    def create_default_config(self, config_path):
        """Create a default configuration file"""
        default_config = """[steam]
# Get your Steam Web API key from: https://steamcommunity.com/dev/apikey
api_key = YOUR_STEAM_API_KEY_HERE

# Project Zomboid App ID (default: 108600)
app_id = 108600

[server]
# Server connection details
host = localhost
port = 16261
rcon_port = 27015
rcon_password = your_rcon_password_here

# Systemd service name for your PZ server
service_name = zomboid

# Optional: Specific log file paths (comma-separated)
# Leave empty to auto-detect common locations
log_paths = 

[monitor]
# How often to check for updates (in seconds)
check_interval = 300

# Whether to check for mod updates
check_mods = true

# Log file for this monitor (default: pz_monitor.log)
log_file = pz_monitor.log
"""
        
        try:
            with open(config_path, 'w') as f:
                f.write(default_config)
            print(f"Created default config file at: {config_path}")
            print("Please edit this file and add your Steam API key and RCON password.")
        except Exception as e:
            print(f"Failed to create config file: {e}")
            exit(1)
        
    def init_database(self):
        """Initialize SQLite database to track Steam version history"""
        self.db = sqlite3.connect('pz_steam_versions.db')
        cursor = self.db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS steam_versions (
                id INTEGER PRIMARY KEY,
                type TEXT,  -- 'game'
                app_id TEXT,
                build_id TEXT,
                last_checked TIMESTAMP,
                UNIQUE(type, app_id)
            )
        ''')
        self.db.commit()
    
    def find_server_log_files(self):
        """Find Project Zomboid server log files"""
        log_files = []
        
        # Use configured paths if provided
        if self.log_paths and self.log_paths[0].strip():
            configured_paths = [p.strip() for p in self.log_paths if p.strip()]
            for path in configured_paths:
                if os.path.exists(path) and os.path.isfile(path):
                    log_files.append(path)
            if log_files:
                self.logger.debug(f"Using configured log files: {log_files}")
                return log_files
        
        # Common PZ installation locations
        common_locations = [
            "/home/steam/Zomboid/Logs",
            f"/home/{os.getenv('USER', 'steam')}/Zomboid/Logs", 
            os.path.expanduser("~/.local/share/Project Zomboid/Logs"),
            "/opt/zomboid/Logs",
            "/srv/zomboid/Logs",
            "./Zomboid/Logs",
            "./Logs"
        ]
        
        for log_dir in common_locations:
            if os.path.exists(log_dir) and os.path.isdir(log_dir):
                # Look for DebugLog-server.txt files (naming pattern: DD-MM-YY_HH-MM-SS_DebugLog-server.txt)
                pattern = os.path.join(log_dir, "*DebugLog-server.txt")
                matching_files = glob.glob(pattern)
                
                if matching_files:
                    # Sort by modification time, newest first
                    matching_files.sort(key=os.path.getmtime, reverse=True)
                    log_files.extend(matching_files[:2])  # Take 2 most recent files
                    self.logger.debug(f"Found {len(matching_files)} log files in {log_dir}, using newest: {matching_files[:2]}")
                    break  # Stop at first directory with logs
        
        return log_files
    
    def get_recent_log_content(self, hours=1):
        """Get recent log content from server logs"""
        recent_content = []
        
        # Method 1: Read from log files
        log_files = self.find_server_log_files()
        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    # For efficiency, read only the last part of the file
                    f.seek(0, 2)  # Go to end
                    file_size = f.tell()
                    
                    # Read last 50KB or whole file if smaller
                    read_size = min(50000, file_size)
                    f.seek(max(0, file_size - read_size))
                    
                    content = f.read()
                    lines = content.split('\n')
                    recent_content.extend(lines)
                    
                    self.logger.debug(f"Read {len(lines)} lines from {os.path.basename(log_file)}")
                    
            except Exception as e:
                self.logger.debug(f"Could not read {log_file}: {e}")
        
        # Method 2: Get from systemd journal as backup
        if not recent_content:
            try:
                cutoff_time = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
                cmd = ['journalctl', '-u', self.service_name, '--since', cutoff_time, '--no-pager', '-q']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0 and result.stdout.strip():
                    journal_lines = result.stdout.split('\n')
                    recent_content.extend(journal_lines)
                    self.logger.debug(f"Got {len(journal_lines)} lines from systemd journal")
            except Exception as e:
                self.logger.debug(f"Could not read systemd journal: {e}")
        
        return recent_content
    
    def check_steam_game_update(self):
        """Check if there's a newer build available on Steam compared to what we last knew"""
        try:
            # Get current Steam build info
            url = f"https://api.steamcmd.net/v1/info/{self.app_id}"
            response = requests.get(url, timeout=10)
            self.logger.info("Checking for game updates.")
            
            if response.status_code == 200:
                data = response.json()
                steam_build = data['data'][self.app_id]['depots']['branches']['public']['buildid']
                
                cursor = self.db.cursor()
                cursor.execute("SELECT build_id FROM steam_versions WHERE type='game' AND app_id=?", (self.app_id,))
                result = cursor.fetchone()
                
                if result is None:
                    # First run - initialize database with current build, don't trigger update
                    self.logger.info(f"First run: initializing database with current Steam build {steam_build}")
                    cursor.execute("""
                        INSERT OR REPLACE INTO steam_versions (type, app_id, build_id, last_checked)
                        VALUES ('game', ?, ?, ?)
                    """, (self.app_id, steam_build, datetime.now()))
                    self.db.commit()
                    return False  # Don't trigger update on first run
                elif result[0] != steam_build:
                    # We have a previous build and it's different - this is a real update
                    self.logger.info(f"Steam build changed from {result[0]} to {steam_build}")
                    cursor.execute("""
                        INSERT OR REPLACE INTO steam_versions (type, app_id, build_id, last_checked)
                        VALUES ('game', ?, ?, ?)
                    """, (self.app_id, steam_build, datetime.now()))
                    self.db.commit()
                    return True
                else:
                    # Same build as before, no update
                    self.logger.info(f"Steam build unchanged: {steam_build}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error checking Steam game updates: {e}")
        
        return False
    
    def check_server_mods_need_update(self):
        """Check if server mods need updates using RCON + log file reading.
            As per this: https://www.reddit.com/r/projectzomboid/comments/15277k7/checking_for_mod_updates_on_dedicated_server/
            checkModsNeedUpdates has two outputs:
            Mods need update:   There are mods that need to be updated
            Mods updated:	The mods are up to date
        """
        try:
            self.logger.info("Checking for mod updates via RCON...")
            
            # Send the checkModsNeedUpdate command via RCON
            response = self.rcon.send_command("checkModsNeedUpdate")
            self.logger.debug(f"RCON command sent, response: {response}")
            
            # The actual result is written to server logs, so wait and check logs
            time.sleep(8)  # Give server more time to process and write to log
            
            # Get recent log content
            recent_logs = self.get_recent_log_content(hours=1)
            
            if not recent_logs:
                self.logger.warning("No server logs found to check mod update status")
                return False
            
            # Look for CheckModsNeedUpdate responses in the logs
            self.logger.debug(f"Checking {len(recent_logs)} log lines for mod update status")
            
            # Find lines with CheckModsNeedUpdate responses
            check_lines = []
            for line in recent_logs:
                if "CheckModsNeedUpdate:" in line:
                    check_lines.append(line.strip())
                    self.logger.debug(f"Found CheckModsNeedUpdate line: {line.strip()}")
            
            if not check_lines:
                self.logger.warning("No CheckModsNeedUpdate responses found in logs")
                return False
            
            # Parse the most recent CheckModsNeedUpdate response
            latest_response = check_lines[-1]  # Get the most recent one
            self.logger.info(f"Latest mod check response: {latest_response}")
            
            # Check specific patterns in the actual PZ log format
            if "CheckModsNeedUpdate: Mods updated." in latest_response:
                self.logger.info("Mods are up to date")
                return False
            elif "CheckModsNeedUpdate: Mods need update." in latest_response:
                self.logger.info("Mods need updating.")
                return True
            elif "CheckModsNeedUpdate: Checking...." in latest_response:
                # This means it's still checking, wait a bit more
                self.logger.info("Server still checking mods, waiting longer...")
                time.sleep(5)
                
                # Check again for completion
                recent_logs = self.get_recent_log_content(hours=1)
                check_lines = [line for line in recent_logs if "CheckModsNeedUpdate:" in line]
                
                if check_lines:
                    latest_response = check_lines[-1]
                    self.logger.info(f"Final mod check response: {latest_response}")
                    
                    if "CheckModsNeedUpdate: Mods updated." in latest_response:
                        self.logger.info("Mods are up to date")
                        return False
                    elif "CheckModsNeedUpdate: Mods need update." in latest_response:
                        self.logger.info("Mods need updating.")
                        return True
            
            # Also check for specific "Mod xxx needs updating" messages
            mod_update_lines = []
            for line in recent_logs:
                if "Needs updating" in line and "Mod " in line:
                    mod_update_lines.append(line.strip())
                    self.logger.debug(f"Found mod update needed line: {line.strip()}")
            
            if mod_update_lines:
                self.logger.info(f"Found {len(mod_update_lines)} mods that need updating:")
                for line in mod_update_lines:
                    self.logger.info(f"  {line}")
                return True
            
            # If we get here, assume no updates needed
            self.logger.info("No mod updates detected")
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking mod updates: {e}")
            return False
    
    def get_player_count(self):
        """Get current number of connected players via RCON"""
        try:
            response = self.rcon.send_command("players")
            
            if response and "Players connected (" in response:
                count_str = response.split("Players connected (")[1].split(")")[0]
                return int(count_str)
            return 0
        except Exception as e:
            self.logger.error(f"Error getting player count: {e}")
        
        return -1  # Error state
    
    def send_server_message(self, message):
        """Send message to all connected players via RCON"""
        try:
            self.rcon.send_command(f'servermsg "{message}"')
            self.logger.info(f"Sent message: {message}")
        except Exception as e:
            self.logger.error(f"Error sending server message: {e}")
    
    def restart_server(self):
        """Restart the Project Zomboid server service"""
        try:
            # Send save command before restart
            self.logger.info("Saving server before restart...")
            self.rcon.send_command("save")
            time.sleep(5)  # Give time for save to complete
            
            self.logger.info("Restarting Project Zomboid server...")
            subprocess.run(['sudo', 'systemctl', 'restart', self.service_name], check=True)
            self.logger.info("Server restarted successfully")
            self.restart_scheduled = False
        except Exception as e:
            self.logger.error(f"Error restarting server: {e}")
    
    def schedule_restart_with_warnings(self):
        """Schedule restart with 30-minute warning and 1-minute reminder"""
        if self.restart_scheduled:
            self.logger.info("Restart already scheduled, skipping...")
            return
            
        self.restart_scheduled = True
        
        # Send initial warning
        self.send_server_message("🔄 SERVER UPDATE AVAILABLE! Server will restart in 30 minutes. Please finish your current activities.")
        
        # Schedule 1-minute warning
        def send_final_warning():
            self.send_server_message("⚠️ SERVER RESTART IN 1 MINUTE! Please save your progress and find a safe location!")
            
        # Schedule restart
        def do_restart():
            self.send_server_message("🔧 Server restarting now for updates...")
            time.sleep(5)  # Give players time to see the message
            self.restart_server()
        
        # Set timers
        warning_timer = threading.Timer(29 * 60, send_final_warning)  # 29 minutes
        restart_timer = threading.Timer(30 * 60, do_restart)  # 30 minutes
        
        warning_timer.start()
        restart_timer.start()
        
        self.restart_timer = restart_timer
        self.logger.info("Scheduled restart in 30 minutes with warnings")
    
    def handle_update_detected(self):
        """Handle when an update is detected"""
        player_count = self.get_player_count()
        
        if player_count == -1:
            self.logger.error("Could not determine player count, skipping restart")
            return
        elif player_count == 0:
            self.logger.info("No players connected, restarting server immediately")
            self.restart_server()
        else:
            self.logger.info(f"{player_count} players connected, scheduling restart with warnings")
            self.schedule_restart_with_warnings()
    
    def test_server_connection(self):
        """Test RCON connection to server and log file access"""
        try:
            self.logger.info("Testing RCON connection...")
            self.logger.info(f"Connecting to {self.server_host}:{self.rcon_port}")
            
            # Test with a simple command first
            response = self.rcon.send_command("players")
            self.logger.debug(f"Players command response length: {len(response) if response else 0}")
            
            if response is not None:
                self.logger.info("✓ RCON connection successful")
                self.logger.debug(f"Players response: {response}")
                rcon_working = True
            else:
                self.logger.error("RCON returned None response")
                rcon_working = False
            
            # Test log file access
            self.logger.info("Testing log file access...")
            log_files = self.find_server_log_files()
            if log_files:
                self.logger.info(f"✓ Found {len(log_files)} log files: {log_files}")
            else:
                self.logger.warning("⚠ No log files found - mod checking may not work")
                self.logger.info("Consider adding log_paths to your config file")
            
            return rcon_working
            
        except Exception as e:
            self.logger.error(f"Server connection test failed: {e}")
            self.logger.error(f"Error details: {type(e).__name__}: {str(e)}")
            return False
    
    def run_monitor_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting Project Zomboid update monitor...")
        
        # Test connection first
        if not self.test_server_connection():
            self.logger.error("Cannot connect to server. Please check RCON configuration.")
            return
        
        while True:
            try:
                # Check if Steam has a newer game version
                game_updated = self.check_steam_game_update()
                
                # Check if server mods need updates (if enabled)
                mods_need_update = False
                if self.check_mods:
                    mods_need_update = self.check_server_mods_need_update()
                
                if game_updated:
                    self.logger.info("Game update detected on Steam!")
                    self.handle_update_detected()
                elif mods_need_update:
                    self.logger.info("Mod updates needed!")
                    self.handle_update_detected()
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Monitor stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                time.sleep(60)  # Wait before retrying
        
        # Cleanup
        self.rcon.close()

if __name__ == "__main__":
    import sys
    
    # Check for test mode
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "test":
            print("=== Testing RCON Connection Only ===")
            monitor = PZUpdateMonitor()
            if monitor.test_server_connection():
                print("✅ RCON test passed!")
            else:
                print("❌ RCON test failed!")
            sys.exit(0)
            
        elif command == "test-steam-update":
            print("=== Simulating Steam Game Update ===")
            monitor = PZUpdateMonitor()
            
            # Force a fake steam update by setting an old build ID in database
            cursor = monitor.db.cursor()
            cursor.execute("SELECT build_id FROM steam_versions WHERE type='game' AND app_id=?", (monitor.app_id,))
            result = cursor.fetchone()
            
            if result:
                old_build = result[0]
                # Set database to a fake old build ID
                fake_old_build = "12345678"
                cursor.execute("""
                    UPDATE steam_versions SET build_id=? WHERE type='game' AND app_id=?
                """, (fake_old_build, monitor.app_id))
                monitor.db.commit()
                print(f"Set database to fake old build: {fake_old_build}")
                
                # Now run the check - it should detect the "update"
                if monitor.check_steam_game_update():
                    print("✅ Steam update detected! Testing restart workflow...")
                    monitor.handle_update_detected()
                else:
                    print("❌ Failed to detect simulated steam update")
                    
                # Restore original build ID
                cursor.execute("""
                    UPDATE steam_versions SET build_id=? WHERE type='game' AND app_id=?
                """, (old_build, monitor.app_id))
                monitor.db.commit()
                print(f"Restored original build ID: {old_build}")
            else:
                print("No existing build ID found. Run the monitor once first to initialize.")
            
            sys.exit(0)
            
        elif command == "test-mod-update":
            print("=== Simulating Mod Update ===")
            monitor = PZUpdateMonitor()
            
            # Create fake log content without touching real files
            from datetime import datetime
            timestamp = datetime.now().strftime("%y-%m-%d %H:%M:%S.%f")[:-3]
            fake_log_lines = [
                f"[{timestamp}] LOG  : General     , {int(datetime.now().timestamp() * 1000)}> CheckModsNeedUpdate: Checking....",
                f"[{timestamp}] LOG  : General     , {int(datetime.now().timestamp() * 1000) + 1000}> CheckModsNeedUpdate: Mods need update.",
                f"[{timestamp}] LOG  : General     , {int(datetime.now().timestamp() * 1000) + 2000}> Mod BetterSorting Needs updating from version 1.2 to 1.3"
            ]
            
            print("Mocking log content with fake mod update messages:")
            for line in fake_log_lines:
                print(f"  {line}")
            
            # Mock the get_recent_log_content method to return our fake logs
            original_get_recent_log_content = monitor.get_recent_log_content
            monitor.get_recent_log_content = lambda hours=1: fake_log_lines
            
            try:
                # Now test the mod checking with mocked log content
                print("\nTesting mod update detection with mocked logs...")
                if monitor.check_server_mods_need_update():
                    print("✅ Mod update detected! Testing restart workflow...")
                    monitor.handle_update_detected()
                else:
                    print("❌ Failed to detect simulated mod update")
            finally:
                # Always restore the original method
                monitor.get_recent_log_content = original_get_recent_log_content
                print("✓ Log reading method restored")
            
            sys.exit(0)
            
        elif command == "test-restart-immediate":
            print("=== Testing Immediate Restart (No Players) ===")
            monitor = PZUpdateMonitor()
            
            # Mock no players connected
            original_get_player_count = monitor.get_player_count
            monitor.get_player_count = lambda: 0
            
            print("Simulating update with 0 players connected...")
            monitor.handle_update_detected()
            
            # Restore original method
            monitor.get_player_count = original_get_player_count
            sys.exit(0)
            
        elif command == "test-restart-scheduled":
            print("=== Testing Scheduled Restart (With Players) ===")
            monitor = PZUpdateMonitor()
            
            # Mock players connected
            original_get_player_count = monitor.get_player_count
            monitor.get_player_count = lambda: 3  # Simulate 3 players
            
            print("Simulating update with 3 players connected...")
            monitor.handle_update_detected()
            
            print("Restart scheduled! Check server messages.")
            print("The server will restart in 30 minutes with warnings.")
            
            # Restore original method
            monitor.get_player_count = original_get_player_count
            sys.exit(0)
            
        elif command == "test-mod-uptodate":
            print("=== Simulating Mods Up-to-Date ===")
            monitor = PZUpdateMonitor()
            
            # Create fake log content showing mods are up to date
            from datetime import datetime
            timestamp = datetime.now().strftime("%y-%m-%d %H:%M:%S.%f")[:-3]
            fake_log_lines = [
                f"[{timestamp}] LOG  : General     , {int(datetime.now().timestamp() * 1000)}> CheckModsNeedUpdate: Checking....",
                f"[{timestamp}] LOG  : General     , {int(datetime.now().timestamp() * 1000) + 2000}> CheckModsNeedUpdate: Mods updated."
            ]
            
            print("Mocking log content with up-to-date mod messages:")
            for line in fake_log_lines:
                print(f"  {line}")
            
            # Mock the get_recent_log_content method
            original_get_recent_log_content = monitor.get_recent_log_content
            monitor.get_recent_log_content = lambda hours=1: fake_log_lines
            
            try:
                print("\nTesting mod update detection with mocked logs...")
                if monitor.check_server_mods_need_update():
                    print("❌ Incorrectly detected mod update (should be up-to-date)")
                else:
                    print("✅ Correctly detected mods are up-to-date")
            finally:
                monitor.get_recent_log_content = original_get_recent_log_content
                print("✓ Log reading method restored")
            
            sys.exit(0)
            print("Project Zomboid Update Monitor - Test Commands:")
            print("")
            print("  test                    - Test RCON connection only")
            print("  test-steam-update       - Simulate Steam game update detection")
            print("  test-mod-update         - Simulate mod update detection")
            print("  test-restart-immediate  - Test immediate restart (0 players)")
            print("  test-restart-scheduled  - Test scheduled restart (with players)")
            print("  help                    - Show this help message")
            print("")
            print("Examples:")
            print("  python3 pz_update_monitor.py test-steam-update")
            print("  python3 pz_update_monitor.py test-mod-update")
            sys.exit(0)
        else:
            print(f"Unknown command: {command}")
            print("Run 'python3 pz_update_monitor.py help' for available commands")
            sys.exit(1)
    
    # Normal operation
    monitor = PZUpdateMonitor()
    monitor.run_monitor_loop()