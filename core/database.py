"""
🗄️ AeroCage-XV5 - Core Database Module
Version: 8.1.0 | Status: Active

الوصف:
    طبقة الوصول إلى قاعدة البيانات (Data Access Layer) مع إدارة التشفير،
    التحقق من البيانات، ومنع الثغرات الأمنية (SQL Injection, TOCTOU).

المسؤوليات:
    - إنشاء وإدارة جدول قاعدة البيانات (SQLite).
    - تشفير/فك تشفير كلمات المرور باستخدام SecurityEngine.
    - تنفيذ عمليات CRUD مع التحقق من الصحة.
    - إدارة جلسات قاعدة البيانات بأمان (Context Managers).

المكتبات المعتمدة:
    - sqlite3: محرك قاعدة البيانات.
    - cryptography: للتشفير (عبر SecurityEngine).
    - utils.logger: لتسجيل الأحداث.
"""

import sqlite3
import os
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

# استيراد محركات الأمان والسجلات
from core.security import SecurityEngine
from utils.logger import get_logger

# إعداد السجلات
logger = get_logger(__name__)

# المسار إلى قاعدة البيانات
DB_PATH = Path(__file__).parent.parent / "data" / "aerocage.db"

# ضمان وجود المجلد
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class DatabaseError(Exception):
    """استثناء مخصص لأخطاء قاعدة البيانات."""
    pass


class DatabaseManager:
    """
    🗄️ مدير قاعدة البيانات الرئيسي.
    يوفر واجهة آمنة ومنظمة للتعامل مع SQLite.
    """

    def __init__(self, db_path: Path = DB_PATH):
        """
        تهيئة مدير قاعدة البيانات.

        Args:
            db_path (Path): مسار ملف قاعدة البيانات.
        """
        self.db_path = db_path
        self.security = SecurityEngine()
        self._ensure_db_exists()
        logger.info(f"Database initialized at: {self.db_path}")

    def _ensure_db_exists(self):
        """
        إنشاء قاعدة البيانات والجداول إذا لم تكن موجودة.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # تمكين Foreign Keys
                cursor.execute("PRAGMA foreign_keys = ON;")
                
                # جدول المهاجمين (Attackers)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS attackers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip_address TEXT UNIQUE NOT NULL,
                        mac_address TEXT UNIQUE NOT NULL,
                        hostname TEXT,
                        username TEXT NOT NULL,
                        password_enc BLOB NOT NULL,
                        group_id INTEGER,
                        status TEXT DEFAULT 'offline',
                        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
                    );
                """)

                # جدول المجموعات (Groups)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS groups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # جدول الأرشيف (Archives) - سجل الفحص التاريخي
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS archives (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        attacker_id INTEGER NOT NULL,
                        scan_data BLOB NOT NULL, -- JSON مشفر أو ثنائي
                        scan_type TEXT NOT NULL, -- 'clients', 'networks', 'attacks'
                        scan_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (attacker_id) REFERENCES attackers(id) ON DELETE CASCADE
                    );
                """)

                # جدول العمليات (Operations) - سجل الهجمات
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS operations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        attacker_id INTEGER NOT NULL,
                        target_ssid TEXT,
                        target_bssid TEXT,
                        channel INTEGER,
                        operation_type TEXT NOT NULL, -- 'deauth', 'monitor', 'scan'
                        status TEXT DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
                        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        end_time TIMESTAMP,
                        error_log TEXT,
                        FOREIGN KEY (attacker_id) REFERENCES attackers(id) ON DELETE CASCADE
                    );
                """)

                conn.commit()
                logger.info("Database schema verified and created.")

        except sqlite3.Error as e:
            logger.error(f"Database initialization failed: {e}")
            raise DatabaseError(f"Failed to initialize database: {e}")

    @contextmanager
    def _get_connection(self):
        """
        سياق لإدارة اتصال قاعدة البيانات بأمان.
        يضمن إغلاق الاتصال حتى في حالة حدوث أخطاء.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row # السماح بالوصول بالأعمدة باسمها
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise DatabaseError(f"Database operation failed: {e}")
        finally:
            if conn:
                conn.close()
                logger.debug("Database connection closed.")

    # --- عمليات المهاجمين (Attackers) ---

    def add_attacker(self, ip: str, mac: str, username: str, password: str, 
                     hostname: str = None, group_id: int = None) -> int:
        """
        إضافة مهاجم جديد مع تشفير كلمة المرور.

        Args:
            ip (str): عنوان IP.
            mac (str): عنوان MAC.
            username (str): اسم المستخدم.
            password (str): كلمة المرور (نص صريح).
            hostname (str, optional): اسم المضيف.
            group_id (int, optional): معرف المجموعة.

        Returns:
            int: معرف المهاجم الجديد.
        """
        # التحقق من التكرار
        if self._attacker_exists(ip) or self._attacker_exists(mac):
            raise DatabaseError("Attacker with same IP or MAC already exists.")

        # تشفير كلمة المرور
        encrypted_pass = self.security.encrypt_password(password)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO attackers (ip_address, mac_address, username, password_enc, hostname, group_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ip, mac, username, encrypted_pass, hostname, group_id))
            return cursor.lastrowid

    def get_attacker_by_id(self, attacker_id: int) -> Optional[Dict[str, Any]]:
        """
        جلب تفاصيل مهاجم معين مع فك تشفير كلمة المرور.

        Args:
            attacker_id (int): معرف المهاجم.

        Returns:
            dict أو None: بيانات المهاجم (مع كلمة المرور المفككة).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM attackers WHERE id = ?", (attacker_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            data = dict(row)
            # فك تشفير كلمة المرور
            data['password'] = self.security.decrypt_password(data['password_enc'])
            del data['password_enc'] # إزالة الحقل المشفر من النتيجة
            return data

    def get_all_attackers(self) -> List[Dict[str, Any]]:
        """
        جلب قائمة بجميع المهاجمين (بدون كلمات المرور).

        Returns:
            list: قائمة بالمهاجمين.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, ip_address, mac_address, username, hostname, status, last_seen FROM attackers")
            return [dict(row) for row in cursor.fetchall()]

    def update_attacker_status(self, attacker_id: int, status: str):
        """تحديث حالة المهاجم (online/offline)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE attackers SET status = ?, last_seen = CURRENT_TIMESTAMP WHERE id = ?
            """, (status, attacker_id))

    def delete_attacker(self, attacker_id: int):
        """حذف مهاجم (يتم حذف الأرشيف والعمليات المرتبطة تلقائياً)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attackers WHERE id = ?", (attacker_id,))
            if cursor.rowcount == 0:
                raise DatabaseError("Attacker not found.")

    def _attacker_exists(self, identifier: str) -> bool:
        """التحقق من وجود IP أو MAC."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM attackers WHERE ip_address = ? OR mac_address = ? LIMIT 1
            """, (identifier, identifier))
            return cursor.fetchone() is not None

    # --- عمليات المجموعات (Groups) ---

    def add_group(self, name: str, description: str = None) -> int:
        """إضافة مجموعة جديدة."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO groups (name, description) VALUES (?, ?)", (name, description))
            return cursor.lastrowid

    def get_groups(self) -> List[Dict[str, Any]]:
        """جلب جميع المجموعات."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM groups")
            return [dict(row) for row in cursor.fetchall()]

    # --- عمليات الأرشيف (Archives) ---

    def add_archive(self, attacker_id: int, scan_data: str, scan_type: str):
        """
        إضافة سجل أرشيف (بيانات الفحص).
        scan_data يجب أن يكون نصاً (JSON) أو بيانات ثنائية.
        """
        # يمكن تشفير scan_data هنا إذا كان حساساً
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO archives (attacker_id, scan_data, scan_type) VALUES (?, ?, ?)
            """, (attacker_id, scan_data, scan_type))

    def get_archives(self, attacker_id: int) -> List[Dict[str, Any]]:
        """جلب أرشيف مهاجم معين."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM archives WHERE attacker_id = ? ORDER BY scan_timestamp DESC
            """, (attacker_id,))
            return [dict(row) for row in cursor.fetchall()]

    # --- عمليات العمليات (Operations) ---

    def create_operation(self, attacker_id: int, op_type: str, target_ssid: str = None, 
                         target_bssid: str = None, channel: int = None) -> int:
        """إنشاء سجل عملية جديدة."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO operations (attacker_id, operation_type, target_ssid, target_bssid, channel, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            """, (attacker_id, op_type, target_ssid, target_bssid, channel))
            return cursor.lastrowid

    def update_operation_status(self, op_id: int, status: str, error_log: str = None):
        """تحديث حالة عملية."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status in ['completed', 'failed']:
                cursor.execute("""
                    UPDATE operations SET status = ?, end_time = CURRENT_TIMESTAMP, error_log = ? WHERE id = ?
                """, (status, error_log, op_id))
            else:
                cursor.execute("""
                    UPDATE operations SET status = ? WHERE id = ?
                """, (status, op_id))

    def get_active_operations(self, attacker_id: int = None) -> List[Dict[str, Any]]:
        """جلب العمليات النشطة."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if attacker_id:
                cursor.execute("""
                    SELECT * FROM operations WHERE attacker_id = ? AND status IN ('pending', 'running')
                """, (attacker_id,))
            else:
                cursor.execute("""
                    SELECT * FROM operations WHERE status IN ('pending', 'running')
                """)
            return [dict(row) for row in cursor.fetchall()]

# --- دالة مساعدة لتهيئة قاعدة البيانات عند البدء ---
def init_db():
    """تهيئة قاعدة البيانات عند تشغيل التطبيق."""
    try:
        db_manager = DatabaseManager()
        logger.info("Database system ready.")
        return db_manager
    except Exception as e:
        logger.critical(f"Critical database failure: {e}")
        raise
