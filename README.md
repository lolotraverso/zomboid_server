# Zomboid Server Guide
#### This file will have the general info on how to create and maintain a Zomboid server on a Linux LXC

## Resources

- Good github project to the basic installation of the server:
    https://github.com/Bobagi/Project-Zomboid-Ubuntu-Server





## Custom scripts
    
- install_steam.sh: This script will only install steam.
    This will do the followwing:
        - Update & Upgrade.
        - Create the steam user, add to sudo and give it a home.
        - add the multiverse repository and the i386 architecture.
        - Install steamcmd.

- install_zomboid.sh:
    - Creates /home/steam/pzsteam
    - installs zomboid app.

- zomboid_as_service.sh
    - Creates the necessary to run zomboid continuously as a service.
