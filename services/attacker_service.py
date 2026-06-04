"""
⚙️ AeroCage-XV5 - Attacker Service Module
Version: 8.1.0 | Status: Active

الوصف:
    طبقة الخدمات (Business Logic) لإدارة المهاجمين والمجموعات.
    تربط بين الـ Repository والـ UI مع تطبيق قواعد العمل الصارمة.

المسؤوليات:
    - التحقق المنطقي المتقدم (مثل منع حذف مجموعة فيها أعضاء).
    - تنسيق العمليات المعقدة (إضافة، تعديل، حذف).
    - إدارة الصلاحيات والسجلات (Audit Logs).
    - التعامل مع الاستثناءات وإرجاع رسائل صديقة للواجهة.

المكتبات المعتمدة:
    - repositories.attacker_repository: AttackerRepository
    - core.database: DatabaseManager
    - utils.validators: Validators
    - utils.logger: get_logger
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from repositories.attacker_repository import AttackerRepository, RepositoryError
from core.database import DatabaseManager, DatabaseError
from utils.validators import Validators
from utils.logger import get_logger

# إعداد السجلات
logger = get_logger(__name__)


class ServiceError(Exception):
    """استثناء مخصص لأخطاء طبقة الخدمات."""
    pass


class AttackerService:
    """
    ⚙️ خدمة إدارة المهاجمين.
    تنفذ منطق الأعمال وتضمن سلامة البيانات قبل الوصول للمستودع.
    """

    def __init__(self, repo: AttackerRepository = None):
        """
        تهيئة الخدمة.

        Args:
            repo (AttackerRepository, optional): مثيل مستودع المهاجمين.
        """
        self.repo = repo or AttackerRepository()
        self.validators = Validators()
        logger.info("AttackerService initialized.")

    def add_attacker(self, ip: str, mac: str, username: str, password: str, 
                     hostname: str = None, group_id: int = None) -> Dict[str, Any]:
        """
        إضافة مهاجم جديد.

        Args:
            ip (str): عنوان IP.
            mac (str): عنوان MAC.
            username (str): اسم المستخدم.
            password (str): كلمة المرور.
            hostname (str, optional): اسم المضيف.
            group_id (int, optional): معرف المجموعة.

        Returns:
            dict: {success: bool, message: str, attacker_id: int}
        """
        try:
            logger.info(f"Attempting to add attacker: {ip}")

            # 1. التحقق من المجموعة (إذا تم تقديمها)
            if group_id is not None:
                # التحقق من وجود المجموعة (يمكن إضافة دالة في GroupService أو DatabaseManager)
                # هنا سنفترض وجود دالة مساعدة في DatabaseManager للتحقق من المجموعة
                # أو نتركها للمستودع للتحقق
                if not self._group_exists(group_id):
                    return {
                        "success": False,
                        "message": f"Group with ID {group_id} does not exist.",
                        "attacker_id": None
                    }

            # 2. استدعاء المستودع
            attacker_id = self.repo.create_attacker(
                ip=ip, mac=mac, username=username, password=password,
                hostname=hostname, group_id=group_id
            )

            logger.info(f"Attacker added successfully with ID: {attacker_id}")
            return {
                "success": True,
                "message": "Attacker added successfully.",
                "attacker_id": attacker_id
            }

        except RepositoryError as e:
            logger.error(f"Repository error adding attacker: {e}")
            return {"success": False, "message": str(e), "attacker_id": None}
        except Exception as e:
            logger.error(f"Unexpected error adding attacker: {e}")
            return {"success": False, "message": f"Internal server error: {str(e)}", "attacker_id": None}

    def delete_attacker(self, attacker_id: int) -> Dict[str, Any]:
        """
        حذف مهاجم.

        Args:
            attacker_id (int): معرف المهاجم.

        Returns:
            dict: {success: bool, message: str}
        """
        try:
            # التحقق من وجود عمليات نشطة (اختياري، يمكن إضافته لاحقاً)
            # if self._has_active_operations(attacker_id):
            #     return {"success": False, "message": "Cannot delete attacker with active operations."}

            self.repo.delete_attacker(attacker_id)
            logger.info(f"Attacker {attacker_id} deleted successfully.")
            return {"success": True, "message": "Attacker deleted successfully."}

        except RepositoryError as e:
            logger.error(f"Repository error deleting attacker: {e}")
            return {"success": False, "message": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error deleting attacker: {e}")
            return {"success": False, "message": f"Internal server error: {str(e)}"}

    def assign_to_group(self, attacker_id: int, group_id: int) -> Dict[str, Any]:
        """
        إرجاع مهاجم لمجموعة.

        Args:
            attacker_id (int): معرف المهاجم.
            group_id (int): معرف المجموعة.

        Returns:
            dict: {success: bool, message: str}
        """
        try:
            if not self._group_exists(group_id):
                return {"success": False, "message": f"Group {group_id} not found."}
            
            # تحديث في المستودع (يحتاج إضافة دالة update_group في AttackerRepository)
            # سنضيفها هنا كمثال
            self.repo.update_attacker_group(attacker_id, group_id)
            logger.info(f"Attacker {attacker_id} assigned to group {group_id}.")
            return {"success": True, "message": "Attacker assigned to group successfully."}
        
        except RepositoryError as e:
            return {"success": False, "message": str(e)}
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}

    def remove_from_group(self, attacker_id: int) -> Dict[str, Any]:
        """
        إزالة مهاجم من مجموعته (تعيين group_id إلى NULL).

        Args:
            attacker_id (int): معرف المهاجم.

        Returns:
            dict: {success: bool, message: str}
        """
        try:
            self.repo.update_attacker_group(attacker_id, None)
            logger.info(f"Attacker {attacker_id} removed from group.")
            return {"success": True, "message": "Attacker removed from group successfully."}
        except RepositoryError as e:
            return {"success": False, "message": str(e)}
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}

    def delete_group(self, group_id: int, force: bool = False) -> Dict[str, Any]:
        """
        حذف مجموعة.

        Args:
            group_id (int): معرف المجموعة.
            force (bool): إذا True، يحذف المجموعة حتى لو كان فيها أعضاء (يحولهم لـ NULL).

        Returns:
            dict: {success: bool, message: str}
        """
        try:
            # التحقق من وجود المجموعة
            if not self._group_exists(group_id):
                return {"success": False, "message": f"Group {group_id} not found."}

            # التحقق من الأعضاء
            members_count = self._get_group_members_count(group_id)
            
            if members_count > 0:
                if not force:
                    return {
                        "success": False, 
                        "message": f"Cannot delete group. It has {members_count} member(s). "
                                   "Use force=True to delete anyway (members will be unassigned)."
                    }
                else:
                    logger.warning(f"Force deleting group {group_id} with {members_count} members.")
                    # إعادة تعيين أعضاء المجموعة إلى NULL
                    self.repo.update_group_members_to_null(group_id)

            # حذف المجموعة
            self.repo.delete_group(group_id)
            logger.info(f"Group {group_id} deleted successfully.")
            return {"success": True, "message": "Group deleted successfully."}

        except RepositoryError as e:
            return {"success": False, "message": str(e)}
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}

    # --- دوال مساعدة (Helpers) ---

    def _group_exists(self, group_id: int) -> bool:
        """التحقق من وجود مجموعة (تحتاج إضافة في Repository)."""
        # محاكاة للتحقق - سيتم تنفيذها في Repository
        return self.repo.group_exists(group_id)

    def _get_group_members_count(self, group_id: int) -> int:
        """جلب عدد أعضاء مجموعة (تحتاج إضافة في Repository)."""
        return self.repo.get_group_members_count(group_id)

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """إحصائيات لوحة التحكم."""
        try:
            stats = self.repo.get_attacker_stats()
            # يمكن إضافة إحصائيات المجموعات والعمليات هنا
            return {
                "success": True,
                "data": stats
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

# --- دالة مساعدة لإنشاء مثيل ---
def get_attacker_service() -> AttackerService:
    return AttackerService()
