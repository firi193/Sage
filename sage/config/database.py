"""
Database configuration for Sage API Key Manager
Supports both SQLite (development) and PostgreSQL (production)
"""

import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Generator, Union
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Database configuration manager"""
    
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self.database_url = os.getenv('DATABASE_URL')
        self.use_postgres = self.environment == 'production' and self.database_url
        
    def get_connection_params(self) -> dict:
        """Get database connection parameters"""
        if self.use_postgres:
            return self._parse_postgres_url()
        else:
            return {
                'type': 'sqlite',
                'keys_db': 'sage_keys.db',
                'grants_db': 'sage_grants.db', 
                'policy_db': 'sage_policy.db',
                'audit_db': 'sage_audit_logs.db'
            }
    
    def _parse_postgres_url(self) -> dict:
        """Parse PostgreSQL connection URL"""
        if not self.database_url:
            raise ValueError("DATABASE_URL not set for production")
            
        # Parse DATABASE_URL (format: postgresql://user:password@host:port/database)
        import urllib.parse as urlparse
        url = urlparse.urlparse(self.database_url)
        
        return {
            'type': 'postgres',
            'host': url.hostname,
            'port': url.port or 5432,
            'database': url.path[1:],  # Remove leading slash
            'user': url.username,
            'password': url.password
        }
    
    @contextmanager
    def get_connection(self, db_name: str = None) -> Generator[Union[sqlite3.Connection, psycopg2.extensions.connection], None, None]:
        """Get database connection based on environment"""
        params = self.get_connection_params()
        
        if params['type'] == 'sqlite':
            # SQLite connection
            db_file = params.get(f'{db_name}_db' if db_name else 'keys_db')
            conn = sqlite3.connect(db_file)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()
                
        else:
            # PostgreSQL connection
            conn = psycopg2.connect(
                host=params['host'],
                port=params['port'],
                database=params['database'],
                user=params['user'],
                password=params['password']
            )
            conn.autocommit = False
            try:
                yield conn
            finally:
                conn.close()


# Global database config instance
db_config = DatabaseConfig()


def get_db_connection(db_name: str = None):
    """Get database connection - use this in your services"""
    return db_config.get_connection(db_name)


def is_postgres():
    """Check if using PostgreSQL"""
    return db_config.use_postgres


def get_table_prefix():
    """Get table prefix for PostgreSQL (to separate different databases)"""
    if is_postgres():
        return {
            'keys': 'sage_keys',
            'grants': 'sage_grants', 
            'policy': 'sage_policy',
            'audit': 'sage_audit'
        }
    return None