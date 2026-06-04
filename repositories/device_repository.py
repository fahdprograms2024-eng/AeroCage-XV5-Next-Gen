"""
File Name: device_repository.py
Version: 8.2.0 | Status: Active
Purpose: Handles secure SQLite database operations for Devices and Groups.
         Implements AES-256 encryption for passwords and UUID for IDs.
"""
import sqlite3
import uuid
from typing import Optional, List, Tuple, Any
from contextlib import contextmanager

# Import core modules for security and DB management
from core.database import DatabaseManager
from core.security import encrypt_data, decrypt_data, generate_uuid
from utils.logger import get_logger

logger = get_logger(__name__)

class DeviceRepository:
    """
    Repository layer for Devices and Groups.
    Ensures data integrity, security (encryption), and proper resource management.
    """

    def __init__(self):
        self.db_manager = DatabaseManager()
        self._init_tables()

    def _init_tables(self):
        """Initialize database tables with security constraints."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Groups Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Devices Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    ip TEXT NOT NULL,
                    user TEXT DEFAULT 'root',
                    password_encrypted TEXT, -- Encrypted password
                    group_id TEXT,
                    status TEXT DEFAULT 'Offline',
                    bands TEXT DEFAULT '',
                    last_seen TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
                )
                """)
                
                # Indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_ip ON devices(ip)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_group ON devices(group_id)")
                
                conn.commit()
                logger.info("Database tables initialized successfully (v8.2.0).")
        except Exception as e:
            logger.error(f"Failed to initialize tables: {e}")
            raise

    # --- Group Operations ---

    def create_group(self, name: str) -> Optional[str]:
        """Create a new group. Returns group ID or None on failure."""
        group_id = generate_uuid()
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO groups (id, name) VALUES (?, ?)",
                    (group_id, name)
                )
                conn.commit()
                logger.info(f"Group created: {name} (ID: {group_id})")
                return group_id
        except sqlite3.IntegrityError:
            logger.warning(f"Group name '{name}' already exists.")
            return None
        except Exception as e:
            logger.error(f"Error creating group: {e}")
            return None

    def get_all_groups(self) -> List[Tuple[str, str]]:
        """Retrieve all groups (id, name)."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name FROM groups ORDER BY created_at DESC")
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error retrieving groups: {e}")
            return []

    def get_group_by_id(self, group_id: str) -> Optional[Tuple[str, str]]:
        """Retrieve a group by ID."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name FROM groups WHERE id = ?", (group_id,))
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"Error retrieving group: {e}")
            return None

    def delete_group(self, group_id: str) -> bool:
        """Delete a group."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM groups WHERE id = ?", (group_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting group: {e}")
            return False

    # --- Device Operations ---

    def create_device(self, name: str, ip: str, user: str = 'root', plain_password: str = None, group_id: str = None) -> Optional[str]:
        """
        Create a new device. Encrypts password before storing.
        Returns device ID or None on failure.
        """
        device_id = generate_uuid()
        password_encrypted = None
        if plain_password:
            password_encrypted = encrypt_data(plain_password)
        
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO devices (id, name, ip, user, password_encrypted, group_id) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (device_id, name, ip, user, password_encrypted, group_id))
                conn.commit()
                logger.info(f"Device created: {name} (IP: {ip}, ID: {device_id})")
                return device_id
        except sqlite3.IntegrityError:
            logger.warning(f"Device with IP '{ip}' already exists.")
            return None
        except Exception as e:
            logger.error(f"Error creating device: {e}")
            return None

    def get_all_devices(self) -> List[Tuple]:
        """
        Retrieve all devices with joined group name.
        Returns: List of tuples (id, name, ip, user, password_encrypted, group_id, group_name, status, bands)
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.id, d.name, d.ip, d.user, d.password_encrypted, d.group_id, g.name, d.status, d.bands 
                    FROM devices d 
                    LEFT JOIN groups g ON d.group_id = g.id
                """)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error retrieving devices: {e}")
            return []

    def get_device_by_id(self, dev_id: str) -> Optional[Tuple]:
        """Retrieve a device by ID with group info."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.id, d.name, d.ip, d.user, d.password_encrypted, d.group_id, g.name, d.status, d.bands 
                    FROM devices d 
                    LEFT JOIN groups g ON d.group_id = g.id
                    WHERE d.id = ?
                """, (dev_id,))
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"Error retrieving device by ID: {e}")
            return None

    def get_device_by_ip(self, ip: str) -> Optional[Tuple]:
        """Retrieve a device by IP address."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.id, d.name, d.ip, d.user, d.password_encrypted, d.group_id, g.name, d.status, d.bands 
                    FROM devices d 
                    LEFT JOIN groups g ON d.group_id = g.id
                    WHERE d.ip = ?
                """, (ip,))
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"Error retrieving device by IP: {e}")
            return None

    def update_device_status(self, dev_id: str, status: str, bands: str = None) -> bool:
        """Update device status and optionally bands."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                if bands:
                    cursor.execute("""
                        UPDATE devices 
                        SET status = ?, bands = ?, updated_at = CURRENT_TIMESTAMP 
                        WHERE id = ?
                    """, (status, bands, dev_id))
                else:
                    cursor.execute("""
                        UPDATE devices 
                        SET status = ?, updated_at = CURRENT_TIMESTAMP 
                        WHERE id = ?
                    """, (status, dev_id))
                
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating device status: {e}")
            return False

    def update_device_password(self, dev_id: str, plain_password: str) -> bool:
        """Update device password (encrypts before storing)."""
        try:
            password_encrypted = encrypt_data(plain_password)
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE devices 
                    SET password_encrypted = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (password_encrypted, dev_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating device password: {e}")
            return False

    def delete_device(self, dev_id: str) -> bool:
        """Delete a device."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM devices WHERE id = ?", (dev_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting device: {e}")
            return False

    def get_decrypted_password(self, dev_id: str) -> Optional[str]:
        """
        Retrieve and decrypt password for a specific device.
        WARNING: Use this only when absolutely necessary (e.g., for SSH connection).
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT password_encrypted FROM devices WHERE id = ?", (dev_id,))
                row = cursor.fetchone()
                if row and row:
                    return decrypt_data(row)
                return None
        except Exception as e:
            logger.error(f"Error decrypting password for device {dev_id}: {e}")
            return None
