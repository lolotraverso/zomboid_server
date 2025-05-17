# Project Zomboid Mod Manager

A Python CLI tool for managing mods on a Project Zomboid Linux server.

## Features

- List active mods on your Project Zomboid server
- Add mods by their Workshop ID
- More features coming soon!

## Installation

### From source

```bash
# Clone the repository
git clone https://github.com/yourusername/pzmod-manager.git
cd pzmod-manager

# Install the package
pip install -e .
```

## Usage

### Setting up

It's recommended to set the `PZ_SERVER_DIR` environment variable to point to your Project Zomboid server directory:

```bash
export PZ_SERVER_DIR=/path/to/your/project_zomboid_server
```

### List active mods

```bash
# Basic usage
pzmod list

# Specify server directory manually
pzmod list --server-dir /path/to/server

# Output in different formats
pzmod list --format json
pzmod list --format csv
```

### Add mods

```bash
# Add mods by Workshop ID
pzmod add 2392709985 2553809727

# Add mods by mod ID
pzmod add workshop-2392709985 workshop-2553809727

# Skip creating a backup
pzmod add 2392709985 --no-backup
```

## Extending the Tool

The tool is designed to be modular and easily extensible. To add a new command:

1. Create a new file in the `commands` directory
2. Extend the `BaseCommand` class
3. Implement the required methods
4. Register your command in `main.py`

Example of a new command:

```python
from commands.base_command import BaseCommand

class MyNewCommand(BaseCommand):
    @classmethod
    def register_subparser(cls, subparsers):
        parser = subparsers.add_parser(
            "mycommand", 
            help="Description of my command"
        )
        # Add arguments...
    
    def execute(self):
        # Implementation...
        pass
```

Then register it in `main.py`:

```python
from commands.my_new_command import MyNewCommand

# In main()
MyNewCommand.register_subparser(subparsers)

# In the command execution section
elif args.command == "mycommand":
    cmd = MyNewCommand(args)
    cmd.execute()
```

## License

MIT License
