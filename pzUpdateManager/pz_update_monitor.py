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
from datetime import datetime, timedelta
from pathlib import Path
import configparser

class PZUpdateMonitor:
    def __init__(self, config_file="pz_monitor.conf"):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        
        # Configuration
        self.steam_api_key = self.config.get('steam', 'api_key')
        self.app_id = self.config.get('steam', 'app_id', fallback='108600')  # PZ App ID
        self.workshop_items = self.config.get('steam', 'workshop_items', fallback='').split(',')
        
        self.server_host = self.config.get('server', 'host', fallback='localhost')
        self.server_port = self.config.getint('server', 'port', fallback=16261)
        self.rcon_port = self.config.getint('server', 'rcon_port', fallback=27015)
        self.rcon_password = self.config.get('server', 'rcon_password')
        self.service_name = self.config.get('server', 'service_name', fallback='zomboid')
        
        self.check_interval = self.config.getint('monitor', 'check_interval', fallback=300)  # 5 minutes
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Setup database for tracking versions
        self.init_database()
        
        # Restart timer
        self.restart_timer = None
        self.restart_scheduled = False
        
    def init_database(self):
        """Initialize SQLite database to track version history"""
        self.db = sqlite3.connect('pz_versions.db')
        cursor = self.db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS versions (
                id INTEGER PRIMARY KEY,
                type TEXT,  -- 'game' or 'mod'
                item_id TEXT,
                version TEXT,
                last_updated TIMESTAMP,
                UNIQUE(type, item_id)
            )
        ''')
        self.db.commit()
    
    def check_steam_app_update(self):
        """Check if Project Zomboid has been updated"""
        try:
            url = f"http://api.steampowered.com/ISteamApps/GetAppList/v0002/"
            response = requests.get(url, timeout=10)
            
            # Get current build info
            url2 = f"https://api.steamcmd.net/v1/info/{self.app_id}"
            build_response = requests.get(url2, timeout=10)
            
            if build_response.status_code == 200:
                data = build_response.json()
                current_build = data['data'][self.app_id]['depots']['branches']['public']['buildid']
                
                cursor = self.db.cursor()
                cursor.execute("SELECT version FROM versions WHERE type='game' AND item_id=?", (self.app_id,))
                result = cursor.fetchone()
                
                if result is None or result[0] != current_build:
                    self.logger.info(f"Game update detected! New build: {current_build}")
                    cursor.execute("""
                        INSERT OR REPLACE INTO versions (type, item_id, version, last_updated)
                        VALUES ('game', ?, ?, ?)
                    """, (self.app_id, current_build, datetime.now()))
                    self.db.commit()
                    return True
                    
        except Exception as e:
            self.logger.error(f"Error checking game updates: {e}")
        
        return False
    
    def check_workshop_mod_updates(self):
        """Check if any subscribed workshop mods have been updated"""
        if not self.workshop_items or self.workshop_items == ['']:
            return False
            
        try:
            for item_id in self.workshop_items:
                item_id = item_id.strip()
                if not item_id:
                    continue
                    
                url = f"https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
                data = {
                    'itemcount': 1,
                    'publishedfileids[0]': item_id
                }
                
                response = requests.post(url, data=data, timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result['response']['publishedfiledetails']:
                        mod_data = result['response']['publishedfiledetails'][0]
                        last_updated = mod_data.get('time_updated', 0)
                        
                        cursor = self.db.cursor()
                        cursor.execute("SELECT version FROM versions WHERE type='mod' AND item_id=?", (item_id,))
                        db_result = cursor.fetchone()
                        
                        if db_result is None or int(db_result[0]) < last_updated:
                            self.logger.info(f"Mod update detected! Item ID: {item_id}")
                            cursor.execute("""
                                INSERT OR REPLACE INTO versions (type, item_id, version, last_updated)
                                VALUES ('mod', ?, ?, ?)
                            """, (item_id, str(last_updated), datetime.now()))
                            self.db.commit()
                            return True
                            
        except Exception as e:
            self.logger.error(f"Error checking mod updates: {e}")
        
        return False
    
    def get_player_count(self):
        """Get current number of connected players via RCON"""
        try:
            # Using RCON to get player list
            cmd = f'mcrcon -H {self.server_host} -P {self.rcon_port} -p "{self.rcon_password}" "players"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                output = result.stdout.strip()
                # Parse the player count from output
                # Output format typically: "Players connected (X): player1, player2..."
                if "Players connected (" in output:
                    count_str = output.split("Players connected (")[1].split(")")[0]
                    return int(count_str)
                return 0
        except Exception as e:
            self.logger.error(f"Error getting player count: {e}")
        
        return -1  # Error state
    
    def send_server_message(self, message):
        """Send message to all connected players via RCON"""
        try:
            escaped_message = message.replace('"', '\\"')
            cmd = f'mcrcon -H {self.server_host} -P {self.rcon_port} -p "{self.rcon_password}" "servermsg \\"{escaped_message}\\""'
            subprocess.run(cmd, shell=True, timeout=10)
            self.logger.info(f"Sent message: {message}")
        except Exception as e:
            self.logger.error(f"Error sending server message: {e}")
    
    def restart_server(self):
        """Restart the Project Zomboid server service"""
        try:
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
    
    def run_monitor_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting Project Zomboid update monitor...")
        
        while True:
            try:
                game_updated = self.check_steam_app_update()
                mod_updated = self.check_workshop_mod_updates()
                
                if game_updated or mod_updated:
                    self.logger.info("Update detected!")
                    self.handle_update_detected()
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Monitor stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                time.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    monitor = PZUpdateMonitor()
    monitor.run_monitor_loop()