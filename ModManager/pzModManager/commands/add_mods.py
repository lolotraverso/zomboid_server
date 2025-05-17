"""
Command to add mods to the Project Zomboid server
"""
import os
from ModManager.pzModManager.commands.base_command import BaseCommand
from ModManager.pzModManager.config_handler import ConfigHandler
from ModManager.pzModManager.mod_manager import ModManager

class AddModsCommand(BaseCommand):
    """Command implementation for adding mods"""
    
    @classmethod
    def register_subparser(cls, subparsers):
        """Register the add command subparser"""
        parser = subparsers.add_parser(
            "add", 
            help="Add mods to the Project Zomboid server"
        )
        
        parser.add_argument(
            "--server-dir", 
            "-d", 
            default=os.environ.get("PZ_SERVER_DIR", "/path/to/server"),
            help="Project Zomboid server directory (default: env PZ_SERVER_DIR)"
        )
        
        parser.add_argument(
            "mods",
            nargs="+",
            help="Mod IDs or Workshop IDs to add (space separated)"
        )
        
        parser.add_argument(
            "--no-backup",
            action="store_true",
            help="Skip creating a backup of the config file"
        )
    
    def execute(self):
        """Execute the add command"""
        server_dir = self.args.server_dir
        mod_ids = self.args.mods
        create_backup = not self.args.no_backup
        
        # Validate server directory
        if not os.path.isdir(server_dir):
            print(f"Error: Server directory '{server_dir}' not found or not a directory")
            return False
        
        # Initialize handlers
        config_handler = ConfigHandler(server_dir)
        mod_manager = ModManager(server_dir)
        
        # Create backup if requested
        if create_backup:
            import shutil
            import time
            
            backup_file = f"{config_handler.server_ini}.{int(time.time())}.bak"
            try:
                shutil.copy2(config_handler.server_ini, backup_file)
                print(f"Created backup: {backup_file}")
            except Exception as e:
                print(f"Warning: Failed to create backup: {e}")
        
        # Process each mod ID
        mod_map = {}
        for mod_id_input in mod_ids:
            mod_id, workshop_id = mod_manager.resolve_mod_id(mod_id_input)
            
            if not mod_id or not workshop_id:
                print(f"Warning: Could not resolve mod ID for '{mod_id_input}', skipping")
                continue
                
            mod_map[mod_id] = workshop_id
            
        if not mod_map:
            print("No valid mods to add")
            return False
            
        # Add the mods to the config
        success = config_handler.add_mods(mod_map)
        
        if success:
            print(f"Successfully added {len(mod_map)} mods:")
            for mod_id, workshop_id in mod_map.items():
                print(f"  - {mod_id} (Workshop ID: {workshop_id})")
        else:
            print("Failed to add mods to the config")
            
        return success