"""
SQLite database provider implementation.
"""
import os
import sqlite3
from pathlib import Path
from typing import Optional
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.base import BaseCheckpointSaver

from core.database_provider import DatabaseProvider, DatabaseFactory


class SQLiteProvider(DatabaseProvider):
    """SQLite database provider for LangGraph checkpointing"""
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize SQLite provider.
        
        Args:
            db_path: Path to SQLite database file. Use ':memory:' for in-memory DB.
            **kwargs: Additional configuration
        """
        self.db_path = db_path or os.getenv("DB_PATH", "./data/adag.db")
        self.extra_config = kwargs
        self._checkpointer: Optional[SqliteSaver] = None
        self._connection: Optional[sqlite3.Connection] = None
        
        # Validate configuration
        self.validate_config()
        
        # Initialize database
        self.initialize()
    
    def get_checkpointer(self) -> BaseCheckpointSaver:
        """
        Get SqliteSaver instance.
        
        Returns:
            SqliteSaver: Configured SQLite checkpoint saver
        """
        if self._checkpointer is None:
            # Create a persistent connection
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
            # Create the SqliteSaver with the connection
            self._checkpointer = SqliteSaver(self._connection)
        
        return self._checkpointer
    
    def get_provider_name(self) -> str:
        """Get the provider name"""
        return "sqlite"
    
    def validate_config(self) -> bool:
        """
        Validate SQLite configuration.
        
        Returns:
            bool: True if valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        if not self.db_path:
            raise ValueError("db_path is required for SQLite provider")
        
        # If not in-memory, check if directory exists or can be created
        if self.db_path != ":memory:":
            db_file = Path(self.db_path)
            db_dir = db_file.parent
            
            if not db_dir.exists():
                try:
                    db_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    raise ValueError(
                        f"Cannot create database directory '{db_dir}': {str(e)}"
                    )
        
        return True
    
    def initialize(self):
        """Initialize the SQLite database"""
        # The SqliteSaver will automatically create tables when first used
        # We just ensure the checkpointer is created
        _ = self.get_checkpointer()


# Register the SQLite provider with the factory
DatabaseFactory.register_provider("sqlite", SQLiteProvider)
