#!/bin/bash

# Print starting message
echo "Starting Project Zomboid server installation..."

# Switch to the "steam" user (this assumes the script is running as a sudo user with the correct permissions)
echo "Step 1: Switching to 'steam' user..."
su - steam <<'EOF'

# Change to the home directory of the "steam" user
echo "Step 2: Changing to the Steam user's home directory..."
cd

# Run SteamCMD
echo "Step 3: Launching SteamCMD..."
steamcmd <<'END'

# Set the directory where the Project Zomboid server will be installed
echo "Step 4: Setting installation directory to /home/steam/pzsteam..."
force_install_dir /home/steam/pzsteam

# Log in anonymously to SteamCMD
echo "Step 5: Logging in anonymously..."
login anonymous

# Update and validate Project Zomboid server files
echo "Step 6: Updating and validating the Project Zomboid server..."
app_update 380870 validate

# Exit SteamCMD
echo "Step 7: Exiting SteamCMD..."
exit
END

# Back to the original user (exiting su - steam)
EOF

# Print completion message
echo "Project Zomboid server installation complete!"

