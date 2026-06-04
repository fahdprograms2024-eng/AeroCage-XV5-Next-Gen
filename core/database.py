"""
File Name: core/database.py
Version: 8.0.0 [AeroCage Next Gen]
Description: Centralized Database Engine for AeroCage-XV5.
             Handles all CRUD operations, encryption integration, and data validation.
             Ensures atomic transactions and strict schema enforcement.
"""

import os
import sqlite3
import re
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

# استيراد محرك التشفير (تأكد من وجوده في نفس المسار أو أعلى)
from core.security import SecurityEngine

logger = logging.getLogger("AeroCage.Database")

class DatabaseManager:
    """
    مدير قاعدة البيانات الموحد.
    يتعامل مع SQLite ويضمن تشفير البيانات الحساسة وصحة المدخلات.
    """
    
    _instance = None
    _db_path = None
    _conn = None
    _security_engine = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = None):
        """تهيئة الاتصال وقاعدة البيانات إذا لم تكن مهيأة."""
        if self._conn is not None:
            return # Already initialized

        # تحديد مسار قاعدة البيانات
        if db_path:
            self._db_path = db_path
        else:
            # المسار الافتراضي
            project_root = Path(__file__).resolve().parent.parent
            self._db_path = project_root / "data" / "aerocage.db"

        # إنشاء المجلد إذا لم يوجد
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)

        # تهيئة محرك التشفير
        self._security_engine = SecurityEngine()

        # الاتصال بقاعدة البيانات
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row # لاستخدام الأسماء كـ keys
        
        # تفعيل Foreign Keys
        self._conn.execute("PRAGMA foreign_keys = ON;")
        
        # إنشاء الجداول
        self._create_tables()
        logger.info(f"Database initialized successfully at: {self._db_path}")

    def _create_tables(self):
        """إنشاء الجداول الأساسية إذا لم توجد."""
        cursor = self._conn.cursor()
        
        # جدول المجموعات
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # جدول الأكسسات المهاجمة
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS attackers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ip TEXT UNIQUE NOT NULL,
            user TEXT DEFAULT 'root',
            password_encrypted BLOB NOT NULL, -- مخزن كـ bytes مشفرة
            group_id INTEGER,
            status TEXT DEFAULT 'offline', -- offline, online, error
            current_channel TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
        );
        """)

        # جدول أرشيف الفحص (للتتبع التاريخي)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS archives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attacker_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ssid TEXT,
            channel TEXT,
            mac_address TEXT,
            signal_strength INTEGER,
            clients_data TEXT, -- JSON string لتخزين بيانات الزبائن المعقدة
            scan_type TEXT, -- 'full_scan', 'client_check', etc.
            FOREIGN KEY (attacker_id) REFERENCES attackers(id) ON DELETE CASCADE
        );
        """)

        # جدول العمليات (الهجمات)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attacker_id INTEGER NOT NULL,
            operation_type TEXT NOT NULL, -- 'deauth', 'scan', 'setup'
            target_network TEXT,
            target_mac TEXT,
            pid INTEGER,
            status TEXT DEFAULT 'running', -- running, completed, failed, stopped
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP,
            comment TEXT,
            FOREIGN KEY (attacker_id) REFERENCES attackers(id) ON DELETE CASCADE
        );
        """)

        self._conn.commit()
        logger.info("Database schema verified and tables created.")

    # --- دوال التحقق من الصحة (Validation) ---
    def _validate_ip(self, ip: str) -> bool:
        """التحقق من صحة عنوان IP."""
        pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
        if not re.match(pattern, ip):
            return False
        # التحقق من أن كل جزء بين 0 و 255
        parts = ip.split('.')
        return all(0 <= int(part) <= 255 for part in parts)

    def _validate_mac(self, mac: str) -> bool:
        """التحقق من صحة عنوان MAC."""
        pattern = r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$"
        return bool(re.match(pattern, mac))

    def _validate_essid(self, essid: str) -> bool:
        """التحقق من صحة اسم الشبكة (لا يمكن أن يكون فارغًا)."""
        return bool(essid and len(essid.strip()) > 0)

    # --- دوال إدارة المجموعات ---
    def add_group(self, name: str, comment: str = "") -> int:
        """إضافة مجموعة جديدة."""
        if not self._validate_essid(name):
            raise ValueError("Group name cannot be empty.")
        
        cursor = self._conn.cursor()
        try:
            cursor.execute("INSERT INTO groups (name, comment) VALUES (?, ?)", (name, comment))
            self._conn.commit()
            logger.info(f"Group '{name}' added successfully.")
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.error(f"Group '{name}' already exists.")
            raise ValueError(f"Group '{name}' already exists.")

    def update_group(self, group_id: int, name: str = None, comment: str = None) -> bool:
        """تعديل مجموعة."""
        if name and not self._validate_essid(name):
            raise ValueError("Group name cannot be empty.")
        
        cursor = self._conn.cursor()
        updates = []
        params = []
        if name:
```python
            updates.append("name = ?")
            params.append(name)
        if comment is not None:
            updates.append("comment = ?")
            params.append(comment)
        
        if not updates:
            return True  # لا تغيير
        
        params.append(group_id)
        cursor.execute(f"UPDATE groups SET {', '.join(updates)} WHERE id = ?", params)
        self._conn.commit()
        logger.info(f"Group ID {group_id} updated.")
        return cursor.rowcount > 0

    def delete_group(self, group_id: int) -> bool:
        """حذف مجموعة."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        self._conn.commit()
        logger.info(f"Group ID {group_id} deleted.")
        return cursor.rowcount > 0

    def get_all_groups(self) -> List[Dict[str, Any]]:
        """جلب كل المجموعات."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM groups ORDER BY name ASC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    # --- دوال إدارة الأكسسات ---
    def add_attacker(self, name: str, ip: str, user: str = "root", password: str, group_id: Optional[int] = None) -> int:
        """إضافة أكسس جديد."""
        if not self._validate_essid(name):
            raise ValueError("Attacker name cannot be empty.")
        if not self._validate_ip(ip):
            raise ValueError("Invalid IP address.")
        
        # تشفير كلمة السر
        encrypted_password = self._security_engine.encrypt_password(password)
        
        cursor = self._conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO attackers (name, ip, user, password_encrypted, group_id)
                VALUES (?, ?, ?, ?, ?)
            """, (name, ip, user, encrypted_password, group_id))
            self._conn.commit()
            logger.info(f"Attacker '{name}' (IP: {ip}) added successfully.")
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                logger.error(f"Attacker with IP '{ip}' or name '{name}' already exists.")
                raise ValueError(f"Attacker with IP '{ip}' or name '{name}' already exists.")
            raise

    def update_attacker(self, attacker_id: int, name: str = None, ip: str = None, user: str = None, password: str = None, group_id: Optional[int] = None) -> bool:
        """تعديل أكسس."""
        updates = []
        params = []
        
        if name and not self._validate_essid(name):
            raise ValueError("Attacker name cannot be empty.")
        if ip and not self._validate_ip(ip):
            raise ValueError("Invalid IP address.")
        
        if name:
            updates.append("name = ?")
            params.append(name)
        if ip:
            updates.append("ip = ?")
            params.append(ip)
        if user:
            updates.append("user = ?")
            params.append(user)
        if password:
            encrypted_password = self._security_engine.encrypt_password(password)
            updates.append("password_encrypted = ?")
            params.append(encrypted_password)
        if group_id is not None:
            updates.append("group_id = ?")
            params.append(group_id)
        
        if not updates:
            return True  # لا تغيير
        
        params.append(attacker_id)
        cursor = self._conn.cursor()
        cursor.execute(f"UPDATE attackers SET {', '.join(updates)} WHERE id = ?", params)
        self._conn.commit()
        logger.info(f"Attacker ID {attacker_id} updated.")
        return cursor.rowcount > 0

    def delete_attacker(self, attacker_id: int) -> bool:
        """حذف أكسس."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM attackers WHERE id = ?", (attacker_id,))
        self._conn.commit()
        logger.info(f"Attacker ID {attacker_id} deleted.")
        return cursor.rowcount > 0

    def get_all_attackers(self) -> List[Dict[str, Any]]:
        """جلب كل الأكسسات مع اسم المجموعة."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT a.*, g.name as group_name
            FROM attackers a
            LEFT JOIN groups g ON a.group_id = g.id
            ORDER BY a.name ASC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_attacker_by_id(self, attacker_id: int) -> Optional[Dict[str, Any]]:
        """جلب أكسس حسب ID."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT a.*, g.name as group_name
            FROM attackers a
            LEFT JOIN groups g ON a.group_id = g.id
            WHERE a.id = ?
        """, (attacker_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_attacker_by_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        """جلب أكسس حسب IP."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT a.*, g.name as group_name
            FROM attackers a
            LEFT JOIN groups g ON a.group_id = g.id
            WHERE a.ip = ?
        """, (ip,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def decrypt_password(self, attacker_id: int) -> str:
        """فك تشفير كلمة سر أكسس."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT password_encrypted FROM attackers WHERE id = ?", (attacker_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Attacker ID {attacker_id} not found.")
        encrypted = row
        return self._security_engine.decrypt_password(encrypted.decode('utf-8'))

    # --- دوال أرشفة الفحص ---
    def archive_scan_data(self, attacker_id: int, ssid: str, channel: str, mac_address: str, signal_strength: int, clients_data: Dict, scan_type: str = "full_scan") -> int:
        """أرشفة نتائج فحص."""
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO archives (attacker_id, ssid, channel, mac_address, signal_strength, clients_data, scan_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (attacker_id, ssid, channel, mac_address, signal_strength, str(clients_data), scan_type))
        self._conn.commit()
        logger.info(f"Scan data archived for attacker ID {attacker_id}.")
        return cursor.lastrowid

    def get_archives_by_attacker(self, attacker_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """جلب أرشيف الفحص حسب أكسس."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM archives
            WHERE attacker_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (attacker_id, limit))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    # --- دوال إدارة العمليات (الهجمات) ---
    def log_operation(self, attacker_id: int, operation_type: str, target_network: str = None, target_mac: str = None, pid: int = None, status: str = "running", comment: str = "") -> int:
        """تسجيل عملية هجوم."""
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO operations (attacker_id, operation_type, target_network, target_mac, pid, status, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (attacker_id, operation_type, target_network, target_mac, pid, status, comment))
        self._conn.commit()
        logger.info(f"Operation '{operation_type}' logged for attacker ID {attacker_id}.")
        return cursor.lastrowid

    def update_operation_status(self, operation_id: int, status: str, end_time: datetime = None) -> bool:
        """تحديث حالة عملية."""
        cursor = self._conn.cursor()
        if end_time:
            cursor.execute("""
                UPDATE operations
                SET status = ?, end_time = ?
                WHERE id = ?
            """, (status, end_time, operation_id))
        else:
            cursor.execute("""
                UPDATE operations
                SET status = ?
                WHERE id = ?
            """, (status, operation_id))
        self._conn.commit()
        logger.info(f"Operation ID {operation_id} status updated to '{status}'.")
        return cursor.rowcount > 0

    def get_running_operations(self) -> List[Dict[str, Any]]:
        """جلب العمليات الجارية."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT o.*, a.name as attacker_name
            FROM operations o
            JOIN attackers a ON o.attacker_id = a.id
            WHERE o.status = 'running'
            ORDER BY o.start_time DESC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    # --- دوال مساعدة ---
    def close(self):
        """إغلاق الاتصال."""
        if self._conn:
            self._conn.close()
            logger.info("Database connection closed.")
