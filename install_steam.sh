#!/bin/bash

# Print starting message
echo "Starting SteamCMD installation and setup script..."

# Add the user 'steam'
echo "Step 1: Adding user 'steam'..."
sudo adduser steam

# Add the 'steam' user to the sudo group
echo "Step 2: Adding 'steam' user to the 'sudo' group..."
sudo usermod -aG sudo steam

# Give 'steam' user ownership of its home directory
echo "Step 3: Giving ownership of /home/steam/ to the 'steam' user..."
sudo chown steam:steam /home/steam/ -R

# Set proper permissions for the home directory
echo "Step 4: Setting permissions (755) for /home/steam/..."
sudo chmod -R 755 /home/steam/

# Change to the 'steam' user's home directory
echo "Step 5: Changing directory to /home/steam..."
cd /home/steam

# Enable the 'multiverse' repository
echo "Step 6: Enabling the 'multiverse' repository..."
sudo add-apt-repository multiverse

# Enable the i386 architecture
echo "Step 7: Enabling the i386 architecture..."
sudo dpkg --add-architecture i386

# Update the package list
echo "Step 8: Updating package list..."
sudo apt update

# Install SteamCMD
echo "Step 9: Installing SteamCMD..."
sudo apt install steamcmd -y

# Print completion message
echo "SteamCMD installation and setup complete!"

