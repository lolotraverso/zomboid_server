#!/bin/bash

# Set the Project Zomboid server installation path
SERVER_PATH="/home/steam"
SERVER_EXEC="startzomboid.sh"
CONTROL_FIFO="/home/steam/Zomboid/zomboid.control"

echo "Project Zomboid Systemd Service & Socket Setup"
echo "=============================================="

# Create the control directory if it doesn't exist
echo "Step 1: Creating control directory..."
sudo mkdir -p /home/steam/Zomboid
sudo chown steam:steam /home/steam/Zomboid

# Create the systemd socket file
echo "Step 2: Creating systemd socket file..."
cat <<EOF | sudo tee /etc/systemd/system/zomboid.socket
[Unit]
Description=Project Zomboid Control Socket
BindsTo=zomboid.service

[Socket]
ListenFIFO=${CONTROL_FIFO}
FileDescriptorName=control
RemoveOnStop=true
SocketMode=0660
SocketUser=steam
SocketGroup=steam

[Install]
WantedBy=sockets.target
EOF

# Create the systemd service file
echo "Step 3: Creating systemd service file..."
cat <<EOF | sudo tee /etc/systemd/system/zomboid.service
[Unit]
Description=Project Zomboid Dedicated Server
After=network.target
Requires=zomboid.socket

[Service]
Type=simple
User=steam
Group=steam
WorkingDirectory=${SERVER_PATH}
ExecStart=/bin/bash ${SERVER_PATH}/${SERVER_EXEC} -servername "MyZomboidServer"
StandardInput=socket
StandardOutput=journal
StandardError=journal
Sockets=zomboid.socket
ExecStop=/bin/sh -c "echo save > ${CONTROL_FIFO}; sleep 15; echo quit > ${CONTROL_FIFO}"
Restart=on-failure
RestartSec=10
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
EOF

# Verify the script exists and is executable
echo "Step 4: Checking server script..."
if [ ! -f "${SERVER_PATH}/${SERVER_EXEC}" ]; then
    echo "WARNING: ${SERVER_PATH}/${SERVER_EXEC} not found!"
    echo "Please ensure Project Zomboid server is installed at ${SERVER_PATH}"
else
    echo "Server script found: ${SERVER_PATH}/${SERVER_EXEC}"
    # Make sure it's executable
    sudo chmod +x "${SERVER_PATH}/${SERVER_EXEC}"
fi

# Reload systemd to recognize the new services
echo "Step 5: Reloading systemd..."
sudo systemctl daemon-reload

# Validate the service files
echo "Step 6: Validating service files..."
if sudo systemd-analyze verify zomboid.socket zomboid.service; then
    echo "✓ Service files validated successfully"
else
    echo "✗ Service file validation failed!"
    exit 1
fi

# Enable the socket (this will auto-enable the service when needed)
echo "Step 7: Enabling Project Zomboid socket and service..."
sudo systemctl enable zomboid.socket
sudo systemctl enable zomboid.service

# Start the socket and service
echo "Step 8: Starting Project Zomboid socket and service..."
sudo systemctl start zomboid.socket
sudo systemctl start zomboid.service

# Check status of both
echo "Step 9: Checking service status..."
echo "Socket status:"
sudo systemctl status zomboid.socket --no-pager -l
echo ""
echo "Service status:"
sudo systemctl status zomboid.service --no-pager -l

echo ""
echo "Project Zomboid server is now running and will start automatically on boot!"
echo ""
echo "=============================================="
echo "USAGE INSTRUCTIONS:"
echo "=============================================="
echo ""
echo "Service Management:"
echo "  sudo systemctl start zomboid.service    # Start the server"
echo "  sudo systemctl stop zomboid.service     # Stop the server (stays stopped)"
echo "  sudo systemctl restart zomboid.service  # Restart the server"
echo "  sudo systemctl status zomboid.service   # Check server status"
echo "  sudo systemctl status zomboid.socket    # Check socket status"
echo ""
echo "Server Control (send commands to running server):"
echo "  echo 'help' > ${CONTROL_FIFO}          # Show available commands"
echo "  echo 'save' > ${CONTROL_FIFO}          # Save the world"
echo "  echo 'quit' > ${CONTROL_FIFO}          # Gracefully stop server"
echo "  echo 'players' > ${CONTROL_FIFO}       # List connected players"
echo ""
echo "View Server Logs:"
echo "  journalctl -u zomboid.service -f        # Follow server logs"
echo "  journalctl -u zomboid.service -n 50     # Last 50 log entries"
echo ""
echo "Boot & Restart Behavior:"
echo "  ✅ Starts automatically on boot"
echo "  ✅ Restarts automatically if it crashes (Restart=on-failure)"
echo "  ✅ Stays stopped when you manually stop it (perfect for troubleshooting)"
echo "  ✅ Manual stops are respected - no unwanted restarts"
echo ""
echo "Configuration files created:"
echo "  /etc/systemd/system/zomboid.service"
echo "  /etc/systemd/system/zomboid.socket"
echo "  Control FIFO: ${CONTROL_FIFO}"
EOF
