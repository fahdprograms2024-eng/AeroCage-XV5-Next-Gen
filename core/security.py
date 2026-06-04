"""
File Name: core/security.py
Version: 8.0.0 [AeroCage Next Gen - Sovereign Security Engine]
Description: Hardened Symmetrical Encryption, Environment Health-Check, and Privileges Guard.
             - Fixes TOCTOU vulnerabilities using atomic file creation (O_EXCL).
             - Guarantees resource cleanup using native context managers.
             - Secure key generation with strict permission enforcement (0o600).
             - Compatible with Kali Linux and OpenWRT environments.
"""

import os
import logging
import stat
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
import tempfile

logger = logging.getLogger("AeroCage.Security")


class SecurityEngine:
    """
    محرك التشفير المحصن عملياتياً.
    يمنع هجمات السباق الزمني (TOCTOU) ويضمن تنظيف الموارد تلقائياً.
    """

    def __init__(self):
        """تهيئة المسارات وبناء مفتاح التشفير بأمان تام."""
        self.project_root = Path(__file__).resolve().parent.parent
        
        # التحقق من متغير البيئة للمسار المخصص
        vault_env = os.environ.get("AEROCAGE_VAULT_PATH")
        if vault_env:
            resolved_path = Path(vault_env).resolve()
            # حماية من Path Traversal: يجب أن يكون داخل المشروع أو أبويه
            try:
                resolved_path.relative_to(self.project_root.parent)
                self.vault_dir = resolved_path
            except ValueError:
                logger.critical(f"Security Alert: Vault path traversal detected. Reverting to default.")
                self.vault_dir = self.project_root / "data" / "hard_vault"
        else:
            self.vault_dir = self.project_root / "data" / "hard_vault"

        self.key_path = self.vault_dir / ".master.key"
        
        # تحميل أو توليد المفتاح
        self._key = self._load_or_generate_key()
        self.cipher = Fernet(self._key)

    def _load_or_generate_key(self) -> bytes:
        """
        تحميل المفتاح أو توليده ذرياً لمنع TOCTOU.
        يستخدم O_CREAT | O_EXCL لضمان إنشاء الملف فقط إذا لم يكن موجوداً،
        مما يمنع التداخل بين العمليات.
        """
        try:
            # 1. محاولة تحميل المفتاح الحالي
            if self.key_path.exists():
                try:
                    key_data = self.key_path.read_bytes()
                    if len(key_data) == 44: # طول مفتاح Fernet القياسي
                        logger.debug("Master key loaded successfully.")
                        return key_data
                    else:
                        logger.warning("Corrupted master key detected. Regenerating.")
                        # حذف المفتاح التالف لضمان عدم استخدامه
                        self.key_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to read existing key: {e}. Regenerating.")

            # 2. إنشاء المجلد الحاضن بصلاحيات صارمة
            self.vault_dir.mkdir(parents=True, exist_ok=True)
            # ضمان صلاحيات المجلد (0o700)
            os.chmod(str(self.vault_dir), stat.S_IRWXU)

            # 3. توليد مفتاح جديد
            new_key = Fernet.generate_key()

            # 4. إنشاء الملف بشكل ذري وآمن (Atomic & Secure)
            # نستخدم tempfile.NamedTemporaryFile مع rename لضمان الذرية
            # أو نستخدم os.open مع O_EXCL
            flags = os.O_CREAT | os.O_WRONLY | os.O_EXCL # O_EXCL يضمن الفشل إذا كان الملف موجوداً
            mode = stat.S_IRUSR | stat.S_IWUSR # 0o600

            file_descriptor = None
            try:
                # فتح الملف مع ضمان عدم وجوده مسبقاً
                file_descriptor = os.open(str(self.key_path), flags, mode)
                
                # كتابة المفتاح
                with os.fdopen(file_descriptor, "wb") as f:
                    f.write(new_key)
                
                # fdopen يغلق الـ descriptor تلقائياً عند خروج الـ with
                # لذا لا نحتاج لإغلاقه يدوياً هنا، ولا نحتاج لـ finally لإغلاقه
                file_descriptor = None 
                
                # ضبط الصلاحيات مرة أخرى للتأكد (في حالة وجود race condition نادر)
                os.chmod(str(self.key_path), mode)
                
                logger.info("Master encryption key atomically generated and secured.")
                return new_key

            except FileExistsError:
                # حدث نادر جداً إذا تم إنشاء الملف بين الفحص والكتابة
                logger.warning("Key file created by another process during generation. Retrying load.")
                return self._load_or_generate_key()
            except Exception as e:
                logger.exception(f"Critical failure during key generation: {e}")
                raise RuntimeError("Security subsystem failed to generate master key.") from e
            finally:
                # إغلاق آمن في حالة فشل عملية الكتابة قبل إغلاق fdopen
                if file_descriptor is not None:
                    try:
                        os.close(file_descriptor)
                    except Exception:
                        pass # تم تجاهل الخطأ، fdopen قد يكون أغلقه بالفعل

        except Exception as e:
            logger.exception("Security Engine Failure during master key sequence.")
            raise RuntimeError("Core security subsystem unhandled failure.") from e

    def encrypt_password(self, plain_password: str) -> str:
        """تشفير كلمة السر."""
        if not plain_password:
            raise ValueError("Password payload cannot be empty.")
        try:
            return self.cipher.encrypt(plain_password.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.exception("Encryption failed.")
            raise RuntimeError("Encryption subsystem error.") from e

    def decrypt_password(self, encrypted_password: str) -> str:
        """فك تشفير كلمة السر."""
        if not encrypted_password:
            raise ValueError("Encrypted password payload cannot be empty.")
        try:
            return self.cipher.decrypt(encrypted_password.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            logger.error("Decryption failed: Invalid or corrupted token.")
            raise ValueError("Invalid token or corrupted data.")
        except Exception as e:
            logger.exception("Decryption failed due to internal error.")
            raise RuntimeError("Decryption subsystem error.") from e


class SystemGuard:
    """حارس البيئة المسؤول عن التحقق من الصلاحيات والملفات."""

    @classmethod
    def enforce_privileges(cls, module_name: str, allow_rootless: bool = False) -> None:
        """
        التحقق من صلاحيات الـ Root.
        إذا كان allow_rootless=True، يسمح بالتشغيل بدون root (مفيد لاختبارات OpenWRT أو Docker).
        """
        if not allow_rootless and os.geteuid() != 0:
            msg = f"CRITICAL: Module [{module_name}] requires root privileges. Run with sudo."
            logger.critical(msg)
            raise PermissionError(msg)
        logger.info(f"Privileges verified for: {module_name}")

    @classmethod
    def check_environment(cls, required_dirs: list = None) -> None:
        """فحص سلامة المجلدات الحيوية."""
        project_root = Path(__file__).resolve().parent.parent
        default_dirs = [
            project_root / "core",
            project_root / "modules",
            project_root / "logs",
            project_root / "data",
        ]
        dirs_to_check = required_dirs if required_dirs else default_dirs

        for path in dirs_to_check:
            if not path.exists():
                msg = f"Critical Environment Fault: Mandatory path '{path}' is missing."
                logger.error(msg)
                raise FileNotFoundError(msg)
        
        logger.info("Environment health-check passed.")

    @staticmethod
    def verify_dependencies(tools: list) -> bool:
        """التحقق من وجود الأدوات الخارجية."""
        import shutil
        missing = []
        for tool in tools:
            if shutil.which(tool) is None:
                missing.append(tool)
        
        if missing:
            logger.error(f"Missing dependencies: {missing}")
            return False
        logger.info("All external dependencies verified.")
        return True


# تهيئة الكائنات
security_engine = SecurityEngine()
system_guard = SystemGuard()
