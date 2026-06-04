"""
📂 AeroCage-XV5 - Group Repository Module
Version: 8.1.0 | Status: Active

الوصف:
    طبقة الوصول للبيانات المتخصصة في إدارة "المجموعات" (Groups).
    توفر واجهة آمنة وموحدة للتعامل مع جداول المجموعات وعلاقتها بالمهاجمين.

المسؤوليات:
    - إنشاء، تعديل، وحذف المجموعات.
    - منع تكرار أسماء المجموعات.
    - جلب إحصائيات دقيقة عن كل مجموعة (عدد الأعضاء).
    - ربط وفصل المجموعات عن المهاجمين.

المكتبات المعتمدة:
    - core.database: DatabaseManager
    - utils.logger: get_logger
"""

import logging
from typing import Optional, List, Dict, Any

from core.database import DatabaseManager, DatabaseError
from utils.logger import get_logger

# إعداد السجلات
logger = get_logger(__name__)


class RepositoryError(Exception):
    """استثناء مخصص لأخطاء المستودع."""
    pass


class GroupRepository:
    """
    📂 مستودع إدارة المجموعات.
    يدير عمليات CRUD للمجموعات مع التحقق من التكرار والعلاقات.
    """

    def __init__(self, db_manager: DatabaseManager = None):
        """
        تهيئة المستودع.

        Args:
            db_manager (DatabaseManager, optional): مثيل مدير قاعدة البيانات.
        """
        self.db = db_manager or DatabaseManager()
        logger.info("GroupRepository initialized.")

    def create_group(self, name: str, description: str = None) -> int:
        """
        إضافة مجموعة جديدة.

        Args:
            name (str): اسم المجموعة (يجب أن يكون فريداً).
            description (str, optional): وصف المجموعة.

        Returns:
            int: معرف المجموعة الجديدة.

        Raises:
            RepositoryError: إذا كان الاسم مكرراً أو حدث خطأ في قاعدة البيانات.
        """
        try:
            # التحقق من تكرار الاسم
            if self._group_name_exists(name):
                raise RepositoryError(f"Group name '{name}' already exists.")

            logger.info(f"Creating new group: {name}")
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO groups (name, description) VALUES (?, ?)",
                    (name, description)
                )
                group_id = cursor.lastrowid
                logger.info(f"Group created with ID: {group_id}")
                return group_id

        except RepositoryError:
            raise
        except DatabaseError as e:
            logger.error(f"Database error creating group: {e}")
            raise RepositoryError(f"Failed to create group: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating group: {e}")
            raise RepositoryError(f"Internal error creating group: {e}")

    def get_group_by_id(self, group_id: int) -> Optional[Dict[str, Any]]:
        """
        جلب تفاصيل مجموعة معينة.

        Args:
            group_id (int): معرف المجموعة.

        Returns:
            dict أو None: بيانات المجموعة.
        """
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return dict(row)
        except Exception as e:
            logger.error(f"Failed to fetch group {group_id}: {e}")
            raise RepositoryError(f"Error fetching group: {e}")

    def get_all_groups(self) -> List[Dict[str, Any]]:
        """
        جلب قائمة بجميع المجموعات مع عدد الأعضاء لكل مجموعة.

        Returns:
            list: قائمة بالمجموعات مع إحصائيات الأعضاء.
        """
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        g.id, 
                        g.name, 
                        g.description, 
                        g.created_at,
                        COUNT(a.id) as member_count
                    FROM groups g
                    LEFT JOIN attackers a ON g.id = a.group_id
                    GROUP BY g.id
                    ORDER BY g.created_at DESC
                """)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch all groups: {e}")
            raise RepositoryError(f"Error fetching groups: {e}")

    def update_group(self, group_id: int, name: str = None, description: str = None) -> bool:
        """
        تحديث بيانات مجموعة.

        Args:
            group_id (int): معرف المجموعة.
            name (str, optional): الاسم الجديد.
            description (str, optional): الوصف الجديد.

        Returns:
            bool: True إذا نجح التحديث.

        Raises:
            RepositoryError: إذا لم توجد المجموعة أو كان الاسم مكرراً (إذا تم تغييره).
        """
        try:
            # التحقق من وجود المجموعة
            if not self._group_exists(group_id):
                raise RepositoryError(f"Group {group_id} not found.")

            # إذا تم تغيير الاسم، تحقق من عدم التكرار (باستثناء المجموعة الحالية)
            if name:
                if self._group_name_exists(name, exclude_id=group_id):
                    raise RepositoryError(f"Group name '{name}' already exists.")

            # تحديد الحقول التي سيتم تحديثها
            updates = []
            params = []
            if name:
                updates.append("name = ?")
                params.append(name)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            params.append(group_id)

            if not updates:
                logger.warning(f"No updates provided for group {group_id}.")
                return True

            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"UPDATE groups SET {', '.join(updates)} WHERE id = ?",
                    tuple(params)
                )
                if cursor.rowcount == 0:
                    raise RepositoryError("No changes made or group not found.")
            
            logger.info(f"Group {group_id} updated successfully.")
            return True

        except RepositoryError:
            raise
        except DatabaseError as e:
            logger.error(f"Database error updating group: {e}")
            raise RepositoryError(f"Failed to update group: {e}")
        except Exception as e:
            logger.error(f"Unexpected error updating group: {e}")
            raise RepositoryError(f"Internal error updating group: {e}")

    def delete_group(self, group_id: int) -> bool:
        """
        حذف مجموعة.
        ملاحظة: يجب التأكد من عدم وجود أعضاء قبل استدعاء هذه الدالة مباشرة،
        أو استخدام `update_group_members_to_null` من `attacker_repository` أولاً.

        Args:
            group_id (int): معرف المجموعة.

        Returns:
            bool: True إذا نجح الحذف.

        Raises:
            RepositoryError: إذا لم توجد المجموعة.
        """
        try:
            if not self._group_exists(group_id):
                raise RepositoryError(f"Group {group_id} not found.")

            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM groups WHERE id = ?", (group_id,))
                if cursor.rowcount == 0:
                    raise RepositoryError("Group not found or already deleted.")
            
            logger.info(f"Group {group_id} deleted successfully.")
            return True

        except RepositoryError:
            raise
        except DatabaseError as e:
            logger.error(f"Database error deleting group: {e}")
            raise RepositoryError(f"Failed to delete group: {e}")
        except Exception as e:
            logger.error(f"Unexpected error deleting group: {e}")
            raise RepositoryError(f"Internal error deleting group: {e}")

    def get_group_members(self, group_id: int) -> List[Dict[str, Any]]:
        """
        جلب قائمة أعضاء مجموعة معينة (بدون كلمة المرور).

        Args:
            group_id (int): معرف المجموعة.

        Returns:
            list: قائمة بالمهاجمين التابعين للمجموعة.
        """
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, ip_address, mac_address, username, hostname, status, last_seen
                    FROM attackers
                    WHERE group_id = ?
                """, (group_id,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch members for group {group_id}: {e}")
            raise RepositoryError(f"Error fetching members: {e}")

    # --- دوال مساعدة (Helpers) ---

    def _group_exists(self, group_id: int) -> bool:
        """التحقق من وجود مجموعة بمعرفها."""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM groups WHERE id = ? LIMIT 1", (group_id,))
                return cursor.fetchone() is not None
        except:
            return False

    def _group_name_exists(self, name: str, exclude_id: int = None) -> bool:
        """
        التحقق من تكرار اسم مجموعة.

        Args:
            name (str): اسم المجموعة.
            exclude_id (int, optional): معرف مجموعة لاستثنائه من التحقق (للتحديث).

        Returns:
            bool: True إذا كان الاسم مكرراً.
        """
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                if exclude_id:
                    cursor.execute(
                        "SELECT 1 FROM groups WHERE name = ? AND id != ? LIMIT 1",
                        (name, exclude_id)
                    )
                else:
                    cursor.execute("SELECT 1 FROM groups WHERE name = ? LIMIT 1", (name,))
                return cursor.fetchone() is not None
        except:
            return False

# --- دالة مساعدة لإنشاء مثيل ---
def get_group_repository() -> GroupRepository:
    """Factory function لإنشاء مثيل GroupRepository مهيأ."""
    return GroupRepository()
