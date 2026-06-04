"""
🔐 AeroCage-XV5 - SSH Service Module
Version: 8.1.0 | Status: Active

الوصف:
    خدمة إدارة اتصالات SSH وتنفيذ العمليات البعيدة.
    تربط بين `SSHConnector` و `AttackerRepository` لتنفيذ الأوامر بأمان.

المسؤوليات:
    - اختبار اتصال الأجهزة (Test Connection).
    - تنفيذ الأوامر البعيدة (مثل فحص الزبائن، بدء الهجمات).
    - التعامل مع `scripts/scan_clients.py` (نقل وتنفيذ).
    - معالجة الأخطاء وتحويلها لرسائل صديقة.

المكتبات المعتمدة:
    - core.ssh_connector: SSHConnector, SSHError
    - repositories.attacker_repository: AttackerRepository
    - core.security: SecurityEngine (لفك التشفير)
    - utils.logger
"""

import logging
import os
import tempfile
from typing import Dict, Any, Tuple, Optional

from core.ssh_connector import SSHConnector, SSHError
from repositories.attacker_repository import AttackerRepository, RepositoryError
from core.security import SecurityEngine
from utils.logger import get_logger

logger = get_logger(__name__)

# المسار المحلي لملف scan_clients.py (يفترض وجوده في مجلد scripts)
LOCAL_SCAN_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "scan_clients.py")
REMOTE_SCAN_SCRIPT_PATH = "/tmp/scan_clients.py"

class ServiceError(Exception):
    """استثناء مخصص لأخطاء الخدمة."""
    pass


class SSHService:
    """
    🔐 خدمة إدارة SSH والعمليات البعيدة.
    """

    def __init__(self, attacker_repo: AttackerRepository = None):
        """
        تهيئة الخدمة.

        Args:
            attacker_repo (AttackerRepository, optional): مستودع المهاجمين.
        """
        self.repo = attacker_repo or AttackerRepository()
        self.security = SecurityEngine()
        logger.info("SSHService initialized.")

    def test_connection(self, attacker_id: int) -> Dict[str, Any]:
        """
        اختبار اتصال SSH بمهاجم معين.

        Args:
            attacker_id (int): معرف المهاجم.

        Returns:
            dict: {success: bool, message: str, status: str}
        """
        try:
            # جلب البيانات
            attacker = self.repo.get_attacker_by_id(attacker_id)
            if not attacker:
                return {"success": False, "message": "Attacker not found.", "status": "error"}

            # فك تشفير كلمة المرور
            password = self.security.decrypt_password(attacker['password'])

            logger.info(f"Testing SSH connection to {attacker['ip_address']}...")
            
            with SSHConnector(
                hostname=attacker['ip_address'],
                username=attacker['username'],
                password=password,
                timeout=10
            ) as ssh:
                # تنفيذ أمر بسيط للتحقق
                exit_code, stdout, stderr = ssh.execute_command("echo 'Connection OK'")
                if exit_code == 0:
                    logger.info(f"SSH connection successful to {attacker['ip_address']}.")
                    return {
                        "success": True, 
                        "message": "Connection successful.", 
                        "status": "online"
                    }
                else:
                    return {
                        "success": False, 
                        "message": f"Command failed: {stderr}", 
                        "status": "error"
                    }

        except SSHError as e:
            logger.error(f"SSH error: {e}")
            return {"success": False, "message": str(e), "status": "offline"}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"success": False, "message": f"Error: {str(e)}", "status": "error"}

    def scan_clients(self, attacker_id: int) -> Dict[str, Any]:
        """
        تشغيل سكربت فحص الزبائن (scan_clients.py) على الجهاز البعيد.

        Args:
            attacker_id (int): معرف المهاجم.

        Returns:
            dict: {success: bool, data: dict (JSON output), message: str}
        """
        try:
            # جلب البيانات
            attacker = self.repo.get_attacker_by_id(attacker_id)
            if not attacker:
                return {"success": False, "message": "Attacker not found."}

            password = self.security.decrypt_password(attacker['password'])
            
            # التحقق من وجود الملف محلياً
            if not os.path.exists(LOCAL_SCAN_SCRIPT_PATH):
                return {"success": False, "message": f"Scan script not found at {LOCAL_SCAN_SCRIPT_PATH}"}

            logger.info(f"Deploying scan_clients.py to {attacker['ip_address']}...")

            with SSHConnector(
                hostname=attacker['ip_address'],
                username=attacker['username'],
                password=password,
                timeout=15
            ) as ssh:
                # 1. رفع الملف
                ssh.upload_file(LOCAL_SCAN_SCRIPT_PATH, REMOTE_SCAN_SCRIPT_PATH)
                
                # 2. تنفيذ السكربت
                # نستخدم python3 أو python حسب النظام، مع تمرير خيارات إن لزم
                command = f"python3 {REMOTE_SCAN_SCRIPT_PATH}"
                exit_code, stdout, stderr = ssh.execute_command(command, timeout=60)

                if exit_code == 0:
                    # محاولة تحليل المخرجات كـ JSON
                    try:
                        import json
                        # التنظيف: إزالة أحرف السطر الزائدة
                        clean_output = stdout.strip()
                        data = json.loads(clean_output)
                        logger.info(f"Scan completed successfully for {attacker['ip_address']}.")
                        return {"success": True, "data": data, "message": "Scan completed."}
                    except json.JSONDecodeError:
                        # إذا لم يكن JSON، نرجع النص كما هو
                        logger.warning("Scan output was not valid JSON.")
                        return {"success": True, "data": {"raw_output": stdout}, "message": "Scan completed (raw output)."}
                else:
                    logger.error(f"Scan script failed: {stderr}")
                    return {"success": False, "message": f"Script failed: {stderr}", "data": {}}

        except SSHError as e:
            return {"success": False, "message": f"SSH Error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in scan: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}

    def execute_custom_command(self, attacker_id: int, command: str, timeout: int = 30) -> Dict[str, Any]:
        """
        تنفيذ أمر مخصص (للاختبار أو المهام الخاصة).

        Args:
            attacker_id (int): معرف المهاجم.
            command (str): الأمر.
            timeout (int): وقت الانتظار.

        Returns:
            dict: {success: bool, output: str, error: str, exit_code: int}
        """
        try:
            attacker = self.repo.get_attacker_by_id(attacker_id)
            if not attacker:
                return {"success": False, "message": "Attacker not found."}

            password = self.security.decrypt_password(attacker['password'])

            with SSHConnector(
                hostname=attacker['ip_address'],
                username=attacker['username'],
                password=password,
                timeout=10
            ) as ssh:
                exit_code, stdout, stderr = ssh.execute_command(command, timeout=timeout)
                return {
                    "success": exit_code == 0,
                    "output": stdout,
                    "error": stderr,
                    "exit_code": exit_code
                }

        except SSHError as e:
            return {"success": False, "message": f"SSH Error: {str(e)}"}
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}

    def cleanup_scan_script(self, attacker_id: int) -> Dict[str, Any]:
        """
        حذف ملف السكربت المؤقت من الجهاز البعيد.

        Args:
            attacker_id (int): معرف المهاجم.

        Returns:
            dict: {success: bool, message: str}
        """
        try:
            attacker = self.repo.get_attacker_by_id(attacker_id)
            if not attacker:
                return {"success": False, "message": "Attacker not found."}

            password = self.security.decrypt_password(attacker['password'])

            with SSHConnector(
                hostname=attacker['ip_address'],
                username=attacker['username'],
                password=password,
                timeout=10
            ) as ssh:
                ssh.execute_command(f"rm -f {REMOTE_SCAN_SCRIPT_PATH}")
                return {"success": True, "message": "Cleanup completed."}

        except Exception as e:
            return {"success": False, "message": f"Cleanup error: {str(e)}"}

# --- دالة مساعدة ---
def get_ssh_service() -> SSHService:
    return SSHService()
