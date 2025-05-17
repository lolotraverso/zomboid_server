"""
Configuration file handler for Project Zomboid server
"""
import os
import re
from pzModManager.utils.file_utils import read_file, write_file

class ConfigHandler:
    """Handles reading and modifying Project Zomboid server configuration files"""
    
    def __init__(self, server_dir):
        """
        Initialize with the server directory path
        
        Args:
            server_dir (str): Path to the Project Zomboid server directory
        """
        self.server_dir = server_dir
        self.mods_file = os.path.join(server_dir, "mods", "mods.info")
        self.server_ini = os.path.join(server_dir, "server.ini")
        
    def get_active_mods(self):
        """
        Get a list of active mods from the server configuration
        
        Returns:
            dict: Dictionary with mod IDs as keys and Workshop IDs as values
        """
        active_mods = {}
        
        # Read server.ini to get Mods= and WorkshopItems= lines
        server_config = read_file(self.server_ini)
        
        # Extract mod IDs from Mods= line
        mods_match = re.search(r'Mods=(.*?)(\r?\n|$)', server_config)
        workshop_match = re.search(r'WorkshopItems=(.*?)(\r?\n|$)', server_config)
        
        if mods_match:
            # Handle escaped characters in mod names properly
            mod_line = mods_match.group(1)
            mod_ids = []
            current_mod = ""
            escape_next = False
            
            for char in mod_line:
                if escape_next:
                    current_mod += char
                    escape_next = False
                elif char == '\\':
                    escape_next = True
                elif char == ';':
                    mod_ids.append(current_mod)
                    current_mod = ""
                else:
                    current_mod += char
                    
            # Don't forget the last mod
            if current_mod:
                mod_ids.append(current_mod)
        else:
            mod_ids = []
            
        if workshop_match:
            workshop_ids = workshop_match.group(1).split(';')
        else:
            workshop_ids = []
        
        # Create a dictionary mapping mod IDs to workshop IDs
        for i in range(min(len(mod_ids), len(workshop_ids))):
            if mod_ids[i] and workshop_ids[i]:
                active_mods[mod_ids[i]] = workshop_ids[i]
                
        return active_mods
    
    def add_mods(self, mod_map):
        """
        Add mods to the server configuration
        
        Args:
            mod_map (dict): Dictionary mapping mod IDs to workshop IDs
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not mod_map:
            return False
            
        # Read server.ini
        server_config = read_file(self.server_ini)
        
        # Extract current mod IDs and workshop IDs
        mods_match = re.search(r'Mods=(.*?)(\r?\n|$)', server_config)
        workshop_match = re.search(r'WorkshopItems=(.*?)(\r?\n|$)', server_config)
        
        if mods_match and workshop_match:
            # Parse the mod line properly handling escaped characters
            mod_line = mods_match.group(1)
            current_mods = []
            current_mod = ""
            escape_next = False
            
            for char in mod_line:
                if escape_next:
                    current_mod += char
                    escape_next = False
                elif char == '\\':
                    current_mod += '\\'  # Keep the escape character
                    escape_next = True
                elif char == ';':
                    current_mods.append(current_mod)
                    current_mod = ""
                else:
                    current_mod += char
                    
            # Don't forget the last mod
            if current_mod:
                current_mods.append(current_mod)
                
            current_workshop = workshop_match.group(1).split(';') if workshop_match.group(1) else []
            
            # Check if we need to pad the workshop IDs list to match mods list length
            if len(current_mods) > len(current_workshop):
                current_workshop.extend([''] * (len(current_mods) - len(current_workshop)))
            
            # Add new mods while maintaining order correlation
            for mod_id, workshop_id in mod_map.items():
                if mod_id not in current_mods:
                    current_mods.append(mod_id)
                    current_workshop.append(workshop_id)
                else:
                    # If mod already exists, update its workshop ID at the correct position
                    idx = current_mods.index(mod_id)
                    current_workshop[idx] = workshop_id
            
            # Ensure the lists are the same length
            if len(current_mods) > len(current_workshop):
                current_workshop.extend([''] * (len(current_mods) - len(current_workshop)))
            elif len(current_workshop) > len(current_mods):
                current_mods.extend([''] * (len(current_workshop) - len(current_mods)))
            
            # Update the config file
            new_mods_line = f"Mods={';'.join(current_mods)}"
            new_workshop_line = f"WorkshopItems={';'.join(current_workshop)}"
            
            # Replace the lines in the config
            server_config = re.sub(r'Mods=.*?(\r?\n|$)', f"{new_mods_line}\n", server_config)
            server_config = re.sub(r'WorkshopItems=.*?(\r?\n|$)', f"{new_workshop_line}\n", server_config)
            
            # Write the updated config back to the file
            return write_file(self.server_ini, server_config)
        else:
            # If the lines don't exist, add them
            lines = server_config.splitlines()
            mods_str = ';'.join(mod_map.keys())
            workshop_str = ';'.join(mod_map.values())
            
            lines.append(f"Mods={mods_str}")
            lines.append(f"WorkshopItems={workshop_str}")
            
            return write_file(self.server_ini, '\n'.join(lines))
