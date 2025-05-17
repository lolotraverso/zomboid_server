"""
Command to list active mods on the Project Zomboid server
"""
import os
from tabulate import tabulate
from pzModManager.commands.base_commands import BaseCommand
from pzModManager.config_handler import ConfigHandler
from pzModManager.mod_manager import ModManager

class ListModsCommand(BaseCommand):
    """Command implementation for listing active mods"""
    
    @classmethod
    def register_subparser(cls, subparsers):
        """Register the list command subparser"""
        parser = subparsers.add_parser(
            "list", 
            help="List active mods on the Project Zomboid server"
        )
        
        parser.add_argument(
            "--server-dir", 
            "-d", 
            default=os.environ.get("PZ_SERVER_DIR", "/path/to/server"),
            help="Project Zomboid server directory (default: env PZ_SERVER_DIR)"
        )
        
        parser.add_argument(
            "--format", 
            "-f", 
            choices=["table", "csv", "json"],
            default="table",
            help="Output format (default: table)"
        )
    
    def execute(self):
        """Execute the list command"""
        server_dir = self.args.server_dir
        output_format = self.args.format
        
        # Validate server directory
        if not os.path.isdir(server_dir):
            print(f"Error: Server directory '{server_dir}' not found or not a directory")
            return False
        
        # Initialize handlers
        config_handler = ConfigHandler(server_dir)
        mod_manager = ModManager(server_dir)
        
        # Get active mods
        mods = config_handler.get_active_mods()
        
        if not mods:
            print("No active mods found.")
            return True
        
        # Build the output data
        output_data = []
        for mod_id, workshop_id in mods.items():
            mod_info = mod_manager.get_mod_info(workshop_id) or {}
            
            # Handle mod ID that's not in workshop-XXXXX format
            mod_type = "Workshop" if mod_id.startswith("workshop-") else "Custom"
            
            output_data.append({
                "Mod ID": mod_id,
                "Workshop ID": workshop_id,
                "Type": mod_type,
                "Name": mod_info.get("name", mod_id),  # Use mod_id as name if not found
                "Description": mod_info.get("description", "")
            })
        
        # Output according to format
        if output_format == "table":
            headers = ["Mod ID", "Workshop ID", "Type", "Name"]
            table_data = [[item[h] for h in headers] for item in output_data]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        elif output_format == "csv":
            print("Mod ID,Workshop ID,Type,Name,Description")
            for item in output_data:
                print(f"{item['Mod ID']},{item['Workshop ID']},{item['Type']},\"{item['Name']}\",\"{item['Description']}\"")
        elif output_format == "json":
            import json
            print(json.dumps(output_data, indent=2))
        
        print(f"\nTotal mods: {len(output_data)}")
        
        # Check for mismatches in the configuration
        mods_match = re.search(r'Mods=(.*?)(\r?\n|$)', read_file(config_handler.server_ini))
        workshop_match = re.search(r'WorkshopItems=(.*?)(\r?\n|$)', read_file(config_handler.server_ini))
        
        if mods_match and workshop_match:
            # Get mod_ids with proper escaping handling
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
                
            workshop_ids = workshop_match.group(1).split(';') if workshop_match.group(1) else []
            
            if len(mod_ids) != len(workshop_ids):
                print(f"\nWARNING: Mismatch in configuration - {len(mod_ids)} mod IDs but {len(workshop_ids)} workshop IDs")
                print("This may cause issues with mod loading in Project Zomboid.")
                
                # Show the problematic entries
                diff = abs(len(mod_ids) - len(workshop_ids))
                if len(mod_ids) > len(workshop_ids):
                    print(f"The following {diff} mod(s) do not have corresponding workshop IDs:")
                    for i in range(len(workshop_ids), len(mod_ids)):
                        print(f"  - {mod_ids[i]}")
                else:
                    print(f"The following {diff} workshop ID(s) do not have corresponding mods:")
                    for i in range(len(mod_ids), len(workshop_ids)):
                        print(f"  - {workshop_ids[i]}")
                        
        return True
