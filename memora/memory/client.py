"""
Neo4j client module for connecting to Neo4j Aura instance.
Handles connection management and provides a singleton pattern for database access.
"""
import os
import logging
from typing import Optional
from dotenv import load_dotenv
from neo4j import GraphDatabase, AsyncGraphDatabase

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class Neo4jClient:
    """
    Neo4j client wrapper for managing database connections.
    Supports both synchronous and asynchronous operations.
    """
    
    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        """
        Initialize Neo4j client with connection parameters.
        
        Args:
            uri: Neo4j connection URI (defaults to NEO4J_URI env var)
            username: Neo4j username (defaults to NEO4J_USERNAME env var)
            password: Neo4j password (defaults to NEO4J_PASSWORD env var)
            database: Neo4j database name (defaults to NEO4J_DATABASE env var)
        """
        self.uri = uri or os.getenv("NEO4J_URI")
        self.username = username or os.getenv("NEO4J_USERNAME")
        self.password = password or os.getenv("NEO4J_PASSWORD")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        
        if not all([self.uri, self.username, self.password]):
            raise ValueError(
                "Missing Neo4j connection parameters. "
                "Provide uri, username, password or set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD env vars."
            )
        
        self._driver: Optional[GraphDatabase] = None
        self._async_driver: Optional[AsyncGraphDatabase] = None
    
    def connect(self) -> None:
        """Establish synchronous connection to Neo4j."""
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            # Verify connectivity
            self._driver.verify_connectivity()
            logger.info(f"Successfully connected to Neo4j at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    async def connect_async(self) -> None:
        """Establish asynchronous connection to Neo4j."""
        try:
            self._async_driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            # Verify connectivity
            await self._async_driver.verify_connectivity()
            logger.info(f"Successfully connected to Neo4j (async) at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j (async): {e}")
            raise
    
    def get_session(self):
        """Get a synchronous session."""
        if not self._driver:
            self.connect()
        return self._driver.session(database=self.database)
    
    async def get_async_session(self):
        """Get an asynchronous session."""
        if not self._async_driver:
            await self.connect_async()
        return self._async_driver.session(database=self.database)
    
    def close(self) -> None:
        """Close synchronous driver connection."""
        if self._driver:
            self._driver.close()
            logger.info("Neo4j synchronous driver closed")
    
    async def close_async(self) -> None:
        """Close asynchronous driver connection."""
        if self._async_driver:
            await self._async_driver.close()
            logger.info("Neo4j asynchronous driver closed")


# Singleton instance
_neo4j_client: Optional[Neo4jClient] = None


def get_neo4j_client() -> Neo4jClient:
    """
    Get or create the singleton Neo4j client instance.
    
    Returns:
        Neo4jClient: The singleton client instance
    """
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient()
    return _neo4j_client

