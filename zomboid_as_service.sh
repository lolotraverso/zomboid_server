#!/bin/bash

# Set the Project Zomboid server installation path
SERVER_PATH="/home/steam/pzsteam"
SERVER_EXEC="start-server.sh"

# Create a new systemd service file for Project Zomboid
echo "Step 1: Creating systemd service file..."

cat <<EOF | sudo tee /etc/systemd/system/zomboid.service
[Unit]
Description=Project Zomboid Dedicated Server
After=network.target

[Service]
Type=simple
User=steam
ExecStart=${SERVER_PATH}/${SERVER_EXEC} -servername "MyZomboidServer"
WorkingDirectory=${SERVER_PATH}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd to recognize the new service
echo "Step 2: Reloading systemd to recognize the new service..."
sudo systemctl daemon-reload

# Enable the service to start on boot
echo "Step 3: Enabling Project Zomboid service to start on boot..."
sudo systemctl enable zomboid.service

# Start the Project Zomboid server service
echo "Step 4: Starting Project Zomboid server service..."
sudo systemctl start zomboid.service

# Print completion message
echo "Project Zomboid server is now running as a service!"
echo "You can manage the server with the following commands:"
echo "  sudo systemctl start zomboid.service    # Start the server"
echo "  sudo systemctl stop zomboid.service     # Stop the server"
echo "  sudo systemctl restart zomboid.service  # Restart the server"
echo "  sudo systemctl status zomboid.service   # Check server status"

