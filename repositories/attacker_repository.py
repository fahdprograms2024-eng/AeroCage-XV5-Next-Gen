"""
🛡️ AeroCage-XV5 - Attacker Repository Module
Version: 8.1.0 | Status: Active

الوصف:
    طبقة الوصول للبيانات المتخصصة في إدارة "المهاجمين" (Attackers).
    تعمل كواجهة آمنة بين طبقة الخدمات (Services) وطبقة قاعدة البيانات (Database).

المسؤوليات:
    - التحقق الصارم من صحة بيانات المهاجم (IP, MAC, Username).
    - منع التكرار قبل الوصول لقاعدة البيانات.
    - التعامل مع الأخطاء وتحويلها لاستثناءات موحدة.
    - تسجيل جميع العمليات في السجلات (Audit Logs).

المكتبات المعتمدة:
    - core.database: DatabaseManager
    - core.security: SecurityEngine
    - utils.validators: Validators
    - utils.logger: get_logger
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from core.database import DatabaseManager, DatabaseError
from core.security import SecurityEngine
from utils.validators import Validators
from utils.logger import get_logger

# إعداد السجلات
logger = get_logger(__name__)


class RepositoryError(Exception):
    """استثناء مخصص لأخطاء المستودع (Repository Layer)."""
    pass


class AttackerRepository:
    """
    🛡️ مستودع بيانات المهاجمين.
    يدير عمليات CRUD للمهاجمين مع تطبيق قواعد التحقق والأمان.
    """

    def __init__(self, db_manager: DatabaseManager = None):
        """
        تهيئة المستودع.

        Args:
            db_manager (DatabaseManager, optional): مثيل مدير قاعدة البيانات.
        """
        self.db = db_manager or DatabaseManager()
        self.validators = Validators()
        self.security = SecurityEngine()
        logger.info("AttackerRepository initialized.")

    def create_attacker(self, ip: str, mac: str, username: str, password: str, 
                        hostname: str = None, group_id: int = None) -> int:
        """
        إضافة مهاجم جديد بعد التحقق من صحة البيانات.

        Args:
            ip (str): عنوان IP.
            mac (str): عنوان MAC.
            username (str): اسم المستخدم.
            password (str): كلمة المرور.
            hostname (str, optional): اسم المضيف.
            group_id (int, optional): معرف المجموعة.

        Returns:
            int: معرف المهاجم الجديد.

        Raises:
            RepositoryError: إذا فشلت العملية أو كانت البيانات غير صحيحة.
        """
        try:
            # 1. التحقق من صحة البيانات
            if not self.validators.validate_ip(ip):
                raise RepositoryError(f"Invalid IP address: {ip}")
            if not self.validators.validate_mac(mac):
                raise RepositoryError(f"Invalid MAC address: {mac}")
            if not username or len(username) < 3:
                raise RepositoryError("Username must be at least 3 characters.")
            if not password:
                raise RepositoryError("Password cannot be empty.")

            # 2. التحقق من التكرار (مزدوج: في الذاكرة ثم في قاعدة البيانات)
            # نستخدم try-except هنا لأن DatabaseManager قد يرفع استثناء إذا وجد التكرار
            try:
                existing = self.db._attacker_exists(ip) or self.db._attacker_exists(mac)
                if existing:
                    raise RepositoryError("Attacker with this IP or MAC already exists.")
            except DatabaseError as e:
                raise RepositoryError(f"Database check failed: {e}")

            # 3. الإدراج
            logger.info(f"Creating new attacker: {ip} ({mac})")
            attacker_id = self.db.add_attacker(
                ip=ip,
                mac=mac,
                username=username,
                password=password,
                hostname=hostname,
                group_id=group_id
            )

            logger.info(f"Attacker created successfully with ID: {attacker_id}")
            return attacker_id

        except RepositoryError:
            raise
        except Exception as e:
            logger.error(f"Failed to create attacker: {e}")
            raise RepositoryError(f"Internal error creating attacker: {e}")

    def get_attacker_by_id(self, attacker_id: int) -> Optional[Dict[str, Any]]:
        """
        جلب تفاصيل مهاجم معين.

        Args:
            attacker_id (int): معرف المهاجم.

        Returns:
            dict أو None: بيانات المهاجم (مع كلمة المرور المفككة).
        """
        try:
            logger.debug(f"Fetching attacker details for ID: {attacker_id}")
            attacker = self.db.get_attacker_by_id(attacker_id)
            if attacker:
                logger.info(f"Attacker fetched: {attacker['ip_address']}")
            return attacker
        except Exception as e:
            logger.error(f"Failed to fetch attacker {attacker_id}: {e}")
            raise RepositoryError(f"Error fetching attacker: {e}")

    def get_all_attackers(self, status_filter: str = None) -> List[Dict[str, Any]]:
        """
        جلب قائمة بجميع المهاجمين.

        Args:
            status_filter (str, optional): فلترة حسب الحالة (online, offline).

        Returns:
            list: قائمة ببيانات المهاجمين (بدون كلمات المرور).
        """
        try:
            attackers = self.db.get_all_attackers()
            if status_filter:
                # فلترة في الذاكرة (لأن قاعدة البيانات قد لا تدعم فلترة الحالة بفعالية في جميع الحالات)
                # أو يمكن تعديل الاستعلام في DatabaseManager
                attackers = [a for a in attackers if a.get('status') == status_filter]
            
            logger.debug(f"Retrieved {len(attackers)} attackers.")
            return attackers
        except Exception as e:
            logger.error(f"Failed to fetch all attackers: {e}")
            raise RepositoryError(f"Error fetching attackers: {e}")

    def update_attacker_status(self, attacker_id: int, new_status: str) -> bool:
        """
        تحديث حالة المهاجم (online/offline).

        Args:
            attacker_id (int): معرف المهاجم.
            new_status (str): الحالة الجديدة.

        Returns:
            bool: True إذا نجح التحديث.
        """
        valid_statuses = ['online', 'offline', 'maintenance']
        if new_status not in valid_statuses:
            raise RepositoryError(f"Invalid status: {new_status}. Must be one of {valid_statuses}")

        try:
            logger.info(f"Updating attacker {attacker_id} status to: {new_status}")
            self.db.update_attacker_status(attacker_id, new_status)
            return True
        except Exception as e:
            logger.error(f"Failed to update status for attacker {attacker_id}: {e}")
            raise RepositoryError(f"Error updating status: {e}")

    def delete_attacker(self, attacker_id: int) -> bool:
        """
        حذف مهاجم.

        Args:
            attacker_id (int): معرف المهاجم.

        Returns:
            bool: True إذا نجح الحذف.
        """
        try:
            # التحقق من وجود عمليات نشطة (اختياري، يعتمد على سياسة النظام)
            # يمكن إضافة دالة check_active_operations هنا
            
            logger.info(f"Deleting attacker with ID: {attacker_id}")
            self.db.delete_attacker(attacker_id)
            logger.info(f"Attacker {attacker_id} deleted successfully.")
            return True
        except DatabaseError as e:
            if "not found" in str(e).lower():
                logger.warning(f"
