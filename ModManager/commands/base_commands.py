"""
Base command class for CLI commands
"""
from abc import ABC, abstractmethod
import argparse

class BaseCommand(ABC):
    """Abstract base class for all CLI commands"""
    
    def __init__(self, args):
        """Initialize the command with parsed arguments"""
        self.args = args
    
    @classmethod
    @abstractmethod
    def register_subparser(cls, subparsers):
        """Register this command's subparser"""
        pass
    
    @abstractmethod
    def execute(self):
        """Execute the command"""
        pass