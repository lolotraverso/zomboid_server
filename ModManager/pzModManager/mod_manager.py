"""
Mod management functionality
"""
import os
import re
import json
import requests
from pzModManager.utils.file_utils import read_file

class ModManager:
    """Handles operations related to Project Zomboid mods"""
    
    def __init__(self, server_dir):
        """
        Initialize with the server directory path
        
        Args:
            server_dir (str): Path to the Project Zomboid server directory
        """
        self.server_dir = server_dir
        self.workshop_cache = {}
        
    def get_mod_info(self, workshop_id):
        """
        Get information about a mod from the Steam Workshop or local cache
        
        Args:
            workshop_id (str): Steam Workshop ID for the mod
            
        Returns:
            dict: Mod information or None if not found
        """
        # Check cache first
        if workshop_id in self.workshop_cache:
            return self.workshop_cache[workshop_id]
            
        # TODO: Add Steam Workshop API integration if needed
        # For now, we'll try to get info from local files
        
        # Check if mod is installed locally
        local_mod_dir = os.path.join(self.server_dir, "steamapps", "workshop", "content", "108600", workshop_id)
        if os.path.exists(local_mod_dir):
            # Try to find mod.info or similar files
            mod_info_path = os.path.join(local_mod_dir, "mod.info")
            if os.path.exists(mod_info_path):
                content = read_file(mod_info_path)
                #name_match = re.search(r'name=(.*?)(\r?\n|$)', content)
                name_match = re.search(r'name=([^\r\n]*)', content)
                desc_match = re.search(r'description=(.*?)(\r?\n|$)', content)
                
                mod_info = {
                    "id": workshop_id,
                    "name": name_match.group(1) if name_match else "Unknown",
                    "description": desc_match.group(1) if desc_match else "",
                    "local": True
                }
                
                # Cache the result
                self.workshop_cache[workshop_id] = mod_info
                return mod_info
                
        return None
    
    def resolve_mod_id(self, mod_id_or_name):
        """
        Resolve a mod ID or name to a proper mod ID and workshop ID
        
        Args:
            mod_id_or_name (str): Mod ID, Workshop ID, or mod name
            
        Returns:
            tuple: (mod_id, workshop_id) or (None, None) if not found
        """
        # Check if it's a direct Steam Workshop ID (numeric)
        if mod_id_or_name.isdigit():
            # We have a Workshop ID, but need to find the corresponding mod ID
            # For now, return a placeholder - this would require more complex logic
            # or external API calls in a real implementation
            return (f"workshop-{mod_id_or_name}", mod_id_or_name)
            
        # Check if it's already a mod ID in workshop-XXXXX format
        if mod_id_or_name.startswith("workshop-"):
            # Extract the workshop ID from the mod ID
            workshop_id = mod_id_or_name.split("-")[1]
            return (mod_id_or_name, workshop_id)
            
        # If it's a custom mod ID (like in the sample file), we need to generate 
        # a Workshop ID for it or ask the user for one
        print(f"WARNING: Mod '{mod_id_or_name}' doesn't follow workshop-XXXXX format.")
        print("Please provide the workshop ID for this mod:")
        try:
            workshop_id = input("> ")
            if workshop_id.isdigit():
                return (mod_id_or_name, workshop_id)
        except:
            pass
            
        # If we can't resolve it, return None
        return (None, None)
