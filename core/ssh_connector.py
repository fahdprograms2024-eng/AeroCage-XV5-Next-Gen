"""
🔌 AeroCage-XV5 - SSH Connector Module
Version: 8.1.1 | Status: Active
core/ssh_connector.py
الوصف:
    طبقة تجريد للاتصال عبر SSH باستخدام Paramiko.
    توفر اتصالاً آمناً، مع إدارة للـ Timeouts، ومعالجة للأخطاء،
    وتنفيذ الأوامر مع التعامل الآمن مع المخرجات.

المسؤوليات:
    - إنشاء اتصالات SSH آمنة.
    - تنفيذ الأوامر البسيطة والمعقدة.
    - التعامل مع المفاتيح وكلمات المرور.
    - معالجة الأخطاء الشائعة (Auth Failed, Timeout, Connection Refused).
    - دعم Keep-Alive للاتصالات الطويلة.

المكتبات المعتمدة:
    - paramiko
    - utils.logger
    - core.security (اختياري)
"""

import paramiko
import logging
import time
import socket
from typing import Tuple, Optional, Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)


class SSHError(Exception):
    """استثناء مخصص لأخطاء SSH."""
    pass


class SSHConnector:
    """
    🔌 محرك اتصال SSH آمن ومحسّن.
    """

    def __init__(self, hostname: str, username: str, password: str = None, 
                 port: int = 22, timeout: int = 10, key_filename: str = None, keepalive: int = 30):
        """
        تهيئة محول SSH.

        Args:
            hostname (str): عنوان IP أو اسم المضيف.
            username (str): اسم المستخدم.
            password (str, optional): كلمة المرور (غير مشفرة).
            port (int): منفذ SSH (الافتراضي 22).
            timeout (int): وقت الانتظار للاتصال (ثواني).
            key_filename (str, optional): مسار مفاتيح SSH الخاصة.
            keepalive (int): فاصل Keep-Alive (ثواني، 0 لتعطيله).
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.key_filename = key_filename
        self.keepalive = keepalive
        self.client: Optional[paramiko.SSHClient] = None

    def is_connected(self) -> bool:
        """تحقق مما إذا كان الاتصال نشطاً وآمناً."""
        if not self.client:
            return False
        try:
            return self.client.get_transport().is_active()
        except Exception:
            return False

    def connect(self) -> bool:
        """
        إنشاء اتصال SSH.

        Returns:
            bool: True إذا نجح الاتصال.

        Raises:
            SSHError: إذا فشل الاتصال.
        """
        if self.is_connected():
            logger.debug(f"Already connected to {self.hostname}.")
            return True

        try:
            logger.info(f"Initiating SSH connection to {self.hostname}:{self.port}...")
            
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # محاولة الاتصال
            self.client.connect(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                password=self.password,
                key_filename=self.key_filename,
                timeout=self.timeout,
                allow_agent=False,
                look_for_keys=False
            )
            
            # تفعيل Keep-Alive إذا تم تحديده
            if self.keepalive > 0:
                self.client.get_transport().set_keepalive(self.keepalive)
            
            logger.info(f"SSH connection established to {self.hostname}.")
            return True

        except paramiko.AuthenticationException:
            logger.error(f"Authentication failed for {self.username}@{self.hostname}.")
            raise SSHError("Authentication failed. Check username/password or key.")
        except paramiko.SSHException as e:
            logger.error(f"SSH configuration error: {e}")
            raise SSHError(f"SSH configuration error: {e}")
        except socket.timeout:
            logger.error(f"Connection timed out for {self.hostname}.")
            raise SSHError("Connection timed out.")
        except Exception as e:
            logger.error(f"Unexpected error connecting to {self.hostname}: {e}")
            raise SSHError(f"Connection failed: {e}")

    def execute_command(self, command: str, timeout: int = 30) -> Tuple[int, str, str]:
        """
        تنفيذ أمر على الجهاز البعيد.

        Args:
            command (str): الأمر المراد تنفيذه.
            timeout (int): وقت الانتظار للأمر (ثواني).

        Returns:
            tuple: (exit_code, stdout, stderr)

        Raises:
            SSHError: إذا لم يكن الاتصال نشطاً أو حدث خطأ.
        """
        if not self.is_connected():
            raise SSHError("Not connected. Call connect() first.")

        try:
            logger.debug(f"Executing command on {self.hostname}: {command[:50]}...")
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            
            # التحقق من حالة النقل أثناء التنفيذ
            if not self.client.get_transport().is_active():
                raise SSHError("Transport disconnected during command execution.")
            
            exit_code = stdout.channel.recv_exit_status()
            std_out = stdout.read().decode('utf-8', errors='replace')
            std_err = stderr.read().decode('utf-8', errors='replace')

            if exit_code != 0:
                logger.warning(f"Command failed on {self.hostname} with exit code {exit_code}: {std_err}")

            return exit_code, std_out, std_err

        except Exception as e:
            logger.error(f"Error executing command: {e}")
            raise SSHError(f"Command execution failed: {e}")

    def upload_file(self, local_path: str, remote_path: str):
        """
        رفع ملف إلى الجهاز البعيد (SFTP).

        Args:
            local_path (str): المسار المحلي.
            remote_path (str): المسار البعيد.

        Raises:
            SSHError: إذا فشل الرفع.
        """
        if not self.is_connected():
            raise SSHError("Not connected.")

        try:
            sftp = self.client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            logger.info(f"File uploaded: {local_path} -> {remote_path}")
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            raise SSHError(f"File upload failed: {e}")

    def download_file(self, remote_path: str, local_path: str):
        """
        تنزيل ملف من الجهاز البعيد (SFTP).

        Args:
            remote_path (str): المسار البعيد.
            local_path (str): المسار المحلي.

        Raises:
            SSHError: إذا فشل التنزيل.
        """
        if not self.is_connected():
            raise SSHError("Not connected.")

        try:
            sftp = self.client.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
            logger.info(f"File downloaded: {remote_path} -> {local_path}")
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            raise SSHError(f"File download failed: {e}")

    def close(self):
        """إغلاق الاتصال."""
        if self.client:
            try:
                self.client.close()
                logger.info(f"SSH connection closed for {self.hostname}.")
            except Exception as e:
                logger.error(f"Error closing SSH connection: {e}")
            finally:
                self.client = None

    def __enter__(self):
        """Context Manager: الدخول."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context Manager: الخروج."""
        self.close()
