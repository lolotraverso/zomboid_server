#!/usr/bin/env python3
"""
Project Zomboid Server Mod Manager CLI
"""
import argparse
import sys
from commands.list_mods import ListModsCommand
from commands.add_mods import AddModsCommand

def main():
    """Main entry point for the CLI application"""
    parser = argparse.ArgumentParser(description="Project Zomboid Server Mod Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Register commands
    ListModsCommand.register_subparser(subparsers)
    AddModsCommand.register_subparser(subparsers)

    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute the command
    if args.command == "list":
        cmd = ListModsCommand(args)
        cmd.execute()
    elif args.command == "add":
        cmd = AddModsCommand(args)
        cmd.execute()

if __name__ == "__main__":
    main()