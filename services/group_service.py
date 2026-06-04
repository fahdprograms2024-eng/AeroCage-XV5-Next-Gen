"""
📂 AeroCage-XV5 - Group Service Module
Version: 8.1.0 | Status: Active

الوصف:
    طبقة الخدمات (Business Logic) لإدارة المجموعات (Groups).
    تنفذ منطق الأعمال المتعلق بالمجموعات وتضمن تطبيق قواعد الأمان والبيانات.

المسؤوليات:
    - إنشاء، تعديل، وحذف المجموعات مع التحقق من الصلاحيات.
    - تطبيق قاعدة "الحذف الصارم" (منع الحذف إذا كانت المجموعة تحتوي على أعضاء).
    - إدارة العلاقات بين المجموعات والمهاجمين (Assign/Unassign).
    - تقديم بيانات مجمعة وإحصائيات للواجهة (UI).

المكتبات المعتمدة:
    - repositories.group_repository: GroupRepository
    - repositories.attacker_repository: AttackerRepository
    - utils.logger: get_logger
"""

import logging
from typing import Optional, List, Dict, Any

from repositories.group_repository import GroupRepository, RepositoryError as GroupRepoError
from repositories.attacker_repository import AttackerRepository, RepositoryError as AttackerRepoError
from utils.logger import get_logger

# إعداد السجلات
logger = get_logger(__name__)


class ServiceError(Exception):
    """استثناء مخصص لأخطاء طبقة الخدمات."""
    pass


class GroupService:
    """
    📂 خدمة إدارة المجموعات.
    تنسق العمليات المعقدة وتطبق قواعد العمل الصارمة.
    """

    def __init__(self, group_repo: GroupRepository = None, attacker_repo: AttackerRepository = None):
        """
        تهيئة الخدمة.

        Args:
            group_repo (GroupRepository, optional): مستودع المجموعات.
            attacker_repo (AttackerRepository, optional): مستودع المهاجمين.
        """
        self.group_repo = group_repo or GroupRepository()
        self.attacker_repo = attacker_repo or AttackerRepository()
        logger.info("GroupService initialized.")

    def create_group(self, name: str, description: str = None) -> Dict[str, Any]:
        """
        إنشاء مجموعة جديدة.

        Args:
            name (str): اسم المجموعة.
            description (str, optional): وصف المجموعة.

        Returns:
            dict: {success: bool, message: str, group_id: int}
        """
        try:
            if not name or len(name.strip()) < 2:
                return {"success": False, "message": "Group name must be at least 2 characters.", "group_id": None}

            group_id = self.group_repo.create_group(name.strip(), description)
            logger.info(f"Group '{name}' created with ID: {group_id}")
            return {"success": True, "message": "Group created successfully.", "group_id": group_id}

        except GroupRepoError as e:
            logger.error(f"Repository error creating group: {e}")
            return {"success": False, "message": str(e), "group_id": None}
        except Exception as e:
            logger.error(f"Unexpected error creating group: {e}")
            return {"success": False, "message": f"Internal error: {str(e)}", "group_id": None}

    def update_group(self, group_id: int, name: str = None, description: str = None) -> Dict[str, Any]:
        """
        تحديث بيانات مجموعة.

        Args:
            group_id (int): معرف المجموعة.
            name (str, optional): الاسم الجديد.
            description (str, optional): الوصف الجديد.

        Returns:
            dict: {success: bool, message: str}
        """
        try:
            # جلب المجموعة للتحقق من وجودها
            group = self.group_repo.get_group_by_id(group_id)
            if not group:
                return {"success": False, "message": f"Group {group_id} not found."}

            # إذا تم تغيير الاسم، التحقق من أنه جديد (يتم ذلك داخل الـ Repository)
            updated_name = name if name else group['name']
            updated_desc = description if description is not None else group.get('description')

            self.group_repo.update_group(group_id, updated_name, updated_desc)
            logger.info(f"Group {group_id} updated.")
            return {"success": True, "message": "Group updated successfully."}

        except GroupRepoError as e:
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
            group = self.group_repo.get_group_by_id(group_id)
            if not group:
                return {"success": False, "message": f"Group {group_id} not found."}

            # التحقق من الأعضاء
            members_count = self.group_repo.get_group_members_count(group_id)
            
            if members_count > 0:
                if not force:
                    logger.warning(f"Attempted to delete group {group_id} with {members_count} members without force.")
                    return {
                        "success": False, 
                        "message": f"Cannot delete group '{group['name']}'. It has {members_count} member(s). "
                                   "Please remove members first or use force=True to unassign them and delete."
                    }
                else:
                    logger.warning(f"Force deleting group {group_id} ({group['name']}) with {members_count} members.")
                    # إعادة تعيين الأعضاء إلى NULL
                    self.attacker_repo.update_group_members_to_null(group_id)

            # حذف المجموعة
            self.group_repo.delete_group(group_id)
            logger.info(f"Group {group_id} deleted successfully.")
            return {"success": True, "message": "Group deleted successfully."}

        except GroupRepoError as e:
            return {"success": False, "message": str(e)}
        except AttackerRepoError as e:
            return {"success": False, "message": f"Error managing members: {str(e)}"}
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}

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
            # التحقق من وجود المهاجم
            attacker = self.attacker_repo.get_attacker_by_id(attacker_id)
            if not attacker:
                return {"success": False, "message": f"Attacker {attacker_id} not found."}

            # التحقق من وجود المجموعة
            group = self.group_repo.get_group_by_id(group_id)
            if not group:
                return {"success": False, "message": f"Group {group_id} not found."}

            self.attacker_repo.update_attacker_group(attacker_id, group_id)
            logger.info(f"Attacker {attacker_id} assigned to group {group_id}.")
            return {"success": True, "message": "Attacker assigned to group successfully."}

        except AttackerRepoError as e:
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
            # التحقق من وجود المهاجم
            attacker = self.attacker_repo.get_attacker_by_id(attacker_id)
            if not attacker:
                return {"success": False, "message": f"Attacker {attacker_id} not found."}

            if attacker.get('group_id') is None:
                return {"success": False, "message": "Attacker is not in any group."}

            self.attacker_repo.update_attacker_group(attacker_id, None)
            logger.info(f"Attacker {attacker_id} removed from group.")
            return {"success": True, "message": "Attacker removed from group successfully."}

        except AttackerRepoError as e:
            return {"success": False, "message": str(e)}
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}

    def get_group_details(self, group_id: int) -> Dict[str, Any]:
        """
        جلب تفاصيل مجموعة مع قائمة الأعضاء.

        Args:
            group_id (int): معرف المجموعة.

        Returns:
            dict: {success: bool, data: dict (group info + members)}
        """
        try:
            group = self.group_repo.get_group_by_id(group_id)
            if not group:
                return {"success": False, "message": f"Group {group_id} not found."}

            members = self.group_repo.get_group_members(group_id)
            
            # دمج البيانات
            result = group
            result['members'] = members
            result['member_count'] = len(members)

            return {"success": True, "data": result}

        except GroupRepoError as e:
            return {"success": False, "message": str(e)}
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}

    def get_all_groups(self) -> Dict[str, Any]:
        """
        جلب جميع المجموعات مع إحصائيات الأعضاء.

        Returns:
            dict: {success: bool, data: list}
        """
        try:
            groups = self.group_repo.get_all_groups()
            return {"success": True, "data": groups}
        except GroupRepoError as e:
            return {"success": False, "message": str(e)}
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}

# --- دالة مساعدة لإنشاء مثيل ---
def get_group_service() -> GroupService:
    """Factory function لإنشاء مثيل GroupService مهيأ."""
    return GroupService()
