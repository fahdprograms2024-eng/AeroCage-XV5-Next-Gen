#!/usr/bin/env python3
"""
File Name: device_repository.py
Purpose: Handles SQLite database operations for Devices and Groups.
"""
import sqlite3
import os
from utils.logger import AeroLogger

class DeviceRepository:
    def __init__(self):
        self.db_path = "aerocage.db"
        self.logger = AeroLogger.get_logger()
        self._init_db()

    def _init_db(self):
        if not os.path.exists(self.db_path):
            self.logger.info("Initializing new database...")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    ip TEXT NOT NULL,
                    user TEXT DEFAULT 'root',
                    password TEXT,
                    group_id INTEGER,
                    status TEXT DEFAULT 'Offline',
                    bands TEXT DEFAULT '',
                    FOREIGN KEY (group_id) REFERENCES groups (id)
                )
            """)
            
            conn.commit()
            conn.close()

    def insert_group(self, name):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO groups (name) VALUES (?)", (name,))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            self.logger.warning(f"Group '{name}' already exists.")
            return False

    def get_all_groups(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM groups")
        groups = cursor.fetchall()
        conn.close()
        return groups

    def get_all_devices(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.id, d.name, d.ip, d.user, d.password, d.group_id, g.name, d.status, d.bands 
            FROM devices d 
            LEFT JOIN groups g ON d.group_id = g.id
        """)
        devices = cursor.fetchall()
        conn.close()
        return devices

    def get_device_by_id(self, dev_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.id, d.name, d.ip, d.user, d.password, d.group_id, g.name, d.status, d.bands 
            FROM devices d 
            LEFT JOIN groups g ON d.group_id = g.id
            WHERE d.id = ?
        """, (dev_id,))
        device = cursor.fetchone()
        conn.close()
        return device

    def delete_device(self, dev_id):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM devices WHERE id = ?", (dev_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error deleting device: {e}")
            return False
