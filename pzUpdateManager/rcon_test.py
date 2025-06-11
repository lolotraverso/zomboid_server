#!/usr/bin/env python3
"""
Minimal RCON test using the exact same code from working v17
"""

import socket
import struct

def test_rcon_v17_style(host, port, password):
    """Test RCON exactly like the working v17 version"""
    print(f"Testing RCON connection to {host}:{port}")
    
    try:
        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        
        print("Connecting to socket...")
        sock.connect((host, port))
        print("✓ Socket connected")
        
        # Send auth packet (EXACTLY like v17)
        print("Sending authentication...")
        request_id = 1
        packet_type = 3  # SERVERDATA_AUTH
        body = password.encode('utf-8')
        packet = struct.pack('<ii', request_id, packet_type) + body + b'\x00\x00'
        length = len(packet)
        sock.send(struct.pack('<i', length) + packet)
        print("✓ Auth packet sent")
        
        # Receive auth response
        print("Waiting for auth response...")
        length_data = sock.recv(4)
        length = struct.unpack('<i', length_data)[0]
        data = sock.recv(length)
        response_id, response_type = struct.unpack('<ii', data[:8])
        print(f"Auth response: ID={response_id}, Type={response_type}")
        
        if response_id == -1:
            print("❌ Authentication failed")
            sock.close()
            return False
        
        print("✓ Authentication successful")
        
        # Test with a simpler command first
        print("\n--- Testing simple 'players' command ---")
        if test_command(sock, "players", 3):
            print("✓ Players command working!")
        
        # Test with help command 
        print("\n--- Testing 'help' command ---")
        if test_command(sock, "help", 4):
            print("✓ Help command working!")
            sock.close()
            return True
        
        print("❌ Both commands failed")
        sock.close()
        return False
    except Exception as e:
        print(f"❌ Error trying to send commands.")
        return False
        
        sock.close()
        return False

def test_command(sock, command, request_id):
    """Test a single command and handle multi-packet responses"""
    try:
        # Send command
        print(f"Sending '{command}' command...")
        packet_type = 2  # SERVERDATA_EXECCOMMAND  
        body = command.encode('utf-8')
        packet = struct.pack('<ii', request_id, packet_type) + body + b'\x00\x00'
        length = len(packet)
        sock.send(struct.pack('<i', length) + packet)
        print(f"✓ {command} command sent")
        
        # Receive response(s)
        print(f"Waiting for {command} response...")
        full_response = ""
        packet_count = 0
        
        while packet_count < 10:  # Limit to prevent infinite loop
            try:
                # Set short timeout to check for additional packets
                if packet_count > 0:
                    sock.settimeout(0.5)
                else:
                    sock.settimeout(10)  # First packet gets longer timeout
                
                length_data = sock.recv(4)
                if len(length_data) < 4:
                    print(f"Incomplete length data on packet {packet_count + 1}")
                    break
                    
                length = struct.unpack('<i', length_data)[0]
                data = sock.recv(length)
                response_id, response_type = struct.unpack('<ii', data[:8])
                body = data[8:-2].decode('utf-8')
                
                packet_count += 1
                print(f"Packet {packet_count}: ID={response_id}, Type={response_type}, Length={len(body)}")
                
                if body:
                    full_response += body
                    print(f"  Body preview: {body[:100]}...")
                else:
                    print(f"  Empty body")
                
                # If we get an empty packet, that often signals the end
                if len(body) == 0:
                    print("  (Empty packet - likely end of response)")
                    break
                    
            except socket.timeout:
                print(f"Timeout after packet {packet_count} - no more data")
                break
            except Exception as e:
                print(f"Error reading packet {packet_count + 1}: {e}")
                break
        
        print(f"\nTotal packets received: {packet_count}")
        print(f"Full response length: {len(full_response)}")
        if full_response:
            print(f"Full response preview: {full_response[:200]}...")
        
        # Reset timeout
        sock.settimeout(10)
        
        # Check for expected content
        if command == "help" and "List of server commands" in full_response:
            return True
        elif command == "players" and ("Players connected" in full_response or "No players" in full_response):
            return True
        elif len(full_response) > 0:
            print(f"⚠ Got response but unexpected format for {command}")
            return True  # At least we got something
        else:
            print(f"❌ No response data received for {command}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing {command}: {e}")
        return False
        
        sock.close()
        return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        if 'sock' in locals():
            sock.close()
        return False

if __name__ == "__main__":
    import configparser
    import os
    
    # Try to load config
    config = configparser.ConfigParser()
    config_found = False
    
    for config_file in ["pz_monitor.conf", os.path.expanduser("~/pz_monitor.conf")]:
        if os.path.exists(config_file):
            config.read(config_file)
            config_found = True
            print(f"Using config: {config_file}")
            break
    
    if config_found:
        try:
            host = config.get('server', 'host', fallback='localhost')
            port = config.getint('server', 'rcon_port', fallback=27015)
            password = config.get('server', 'rcon_password')
            
            print(f"Config values:")
            print(f"  Host: {host}")
            print(f"  Port: {port}")
            print(f"  Password: {'*' * len(password)}")
            
        except Exception as e:
            print(f"Config error: {e}")
            exit(1)
    else:
        print("No config found, using manual input:")
        host = input("RCON host [localhost]: ").strip() or "localhost"
        port = int(input("RCON port [27015]: ").strip() or "27015")
        password = input("RCON password: ").strip()
    
    print("\n" + "="*50)
    success = test_rcon_v17_style(host, port, password)
    print("="*50)
    
    if success:
        print("🎉 RCON test PASSED - connection working!")
    else:
        print("❌ RCON test FAILED")
        print("\nTroubleshooting:")
        print("1. Check server is running: sudo systemctl status zomboid")
        print("2. Check RCON config in servertest.ini:")
        print("   RCONPort=27015")
        print("   RCONPassword=your_password")
        print("3. Check if port is open: netstat -tlnp | grep 27015")