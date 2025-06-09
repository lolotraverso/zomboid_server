#!/usr/bin/env python3
"""
Project Zomboid Server Update Monitor
Monitors for game and workshop mod updates, manages server restarts with player notifications
"""

import json
import time
import subprocess
import threading
import requests
import sqlite3
import logging
import socket
import struct
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
        """Send command and return response"""
        if not self.socket:
            self.connect()
        
        try:
            self._send_packet(2, command)  # SERVERDATA_EXECCOMMAND
            response = self._receive_packet()
            return response[2]  # Return the response body
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
        self.config.read(config_file)
        
        # Configuration
        self.steam_api_key = self.config.get('steam', 'api_key')
        self.app_id = self.config.get('steam', 'app_id', fallback='108600')  # PZ App ID
        
        self.server_host = self.config.get('server', 'host', fallback='localhost')
        self.server_port = self.config.getint('server', 'port', fallback=16261)
        self.rcon_port = self.config.getint('server', 'rcon_port', fallback=27015)
        self.rcon_password = self.config.get('server', 'rcon_password')
        self.service_name = self.config.get('server', 'service_name', fallback='zomboid')
        
        self.check_interval = self.config.getint('monitor', 'check_interval', fallback=300)  # 5 minutes
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Setup database for tracking Steam versions
        self.init_database()
        
        # Setup RCON client
        self.rcon = RCONClient(self.server_host, self.rcon_port, self.rcon_password)
        
        # Restart timer
        self.restart_timer = None
        self.restart_scheduled = False
        
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
    
    def check_steam_game_update(self):
        """Check if there's a newer build available on Steam compared to what we last knew"""
        try:
            # Get current Steam build info
            url = f"https://api.steamcmd.net/v1/info/{self.app_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                steam_build = data['data'][self.app_id]['depots']['branches']['public']['buildid']
                
                cursor = self.db.cursor()
                cursor.execute("SELECT build_id FROM steam_versions WHERE type='game' AND app_id=?", (self.app_id,))
                result = cursor.fetchone()
                
                if result is None or result[0] != steam_build:
                    self.logger.info(f"New Steam build detected: {steam_build}")
                    cursor.execute("""
                        INSERT OR REPLACE INTO steam_versions (type, app_id, build_id, last_checked)
                        VALUES ('game', ?, ?, ?)
                    """, (self.app_id, steam_build, datetime.now()))
                    self.db.commit()
                    return True
                    
        except Exception as e:
            self.logger.error(f"Error checking Steam game updates: {e}")
        
        return False
    
    def check_server_mods_need_update(self):
        """Use the server's built-in checkModsNeedUpdate command"""
        try:
            response = self.rcon.send_command("checkModsNeedUpdate")
            self.logger.info(f"Mod update check response: {response}")
            
            # The command returns information about mods that need updates
            # If any mods need updating, the response will contain details
            if response and ("need" in response.lower() or "update" in response.lower()):
                # Parse the response to see if updates are actually needed
                if "no updates" not in response.lower() and "up to date" not in response.lower():
                    self.logger.info("Mods need updates according to server")
                    return True
            
            return False
        except Exception as e:
            self.logger.error(f"Error checking mod updates via RCON: {e}")
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
        """Test RCON connection to server"""
        try:
            self.logger.info("Testing RCON connection...")
            response = self.rcon.send_command("help")
            self.logger.info("RCON connection successful")
            return True
        except Exception as e:
            self.logger.error(f"RCON connection failed: {e}")
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
                
                # Check if server mods need updates using server's own command
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
    monitor = PZUpdateMonitor()
    monitor.run_monitor_loop()