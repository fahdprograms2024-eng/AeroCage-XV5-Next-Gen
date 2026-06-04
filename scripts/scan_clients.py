#!/usr/bin/env python3
"""
File Name: scripts/scan_clients.py
Version: 8.0.1 [AeroCage Next Gen - Dynamic Discovery]
Description: Scans for active processes (Airserv, Aireplay) by inspecting /proc and ps output.
             NO hardcoded ports. Returns PIDs for dynamic killing.
"""

import json
import re
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.ssh_connector import SSHConnector
from core.security import SecurityEngine
from utils.logger import AeroLogger

logger = AeroLogger.get_logger()

class WirelessScanner:
    def __init__(self, ip: str, user: str, password: str):
        self.ip = ip
        self.user = user
        self.password = password
        self.connector = SSHConnector(ip, user, password)

    def execute_scan(self) -> dict:
        """
        فحص شامل: زبائن، انترفيسات، وعمليات نشطة (بدون افتراض بورتات).
        """
        result = {
            "success": False,
            "device_info": {},
            "wireless_status": [],
            "clients": [],
            "active_services": [], # قائمة الخدمات النشطة (Airserv, Aireplay) مع PIDs
            "errors": []
        }

        if not self.connector.connect():
            result["errors"].append("فشل الاتصال بالأكسس عبر SSH.")
            return result

        try:
            # 1. أمر واحد لجلب كل شيء
            # نستخدم `ps -ef` للحصول على PID واسم العملية كاملة
            # نستخدم `iw dev` للانترفيسات
            # نستخدم `iw dev wlan0 station dump` للزبائن
            commands = [
                "echo '===RELEASE===' && cat /etc/openwrt_release 2>/dev/null",
                "echo '===WIFI_STATUS===' && ubus call network.wireless status 2>/dev/null",
                "echo '===CLIENTS===' && iw dev wlan0 station dump 2>/dev/null",
                "echo '===INTERFACES===' && iw dev 2>/dev/null",
                # الأمر الأهم: جلب كل العمليات النشطة
                "echo '===ALL_PROCESSES===' && ps -ef 2>/dev/null",
                # فحص المنافذ فقط كـ "معلومة إضافية" (وليس للكشف عن الخدمة)
                "echo '===OPEN_PORTS===' && ss -tlnp 2>/dev/null | head -20",
            ]

            full_cmd = "; ".join(commands)
            raw_output = self.connector.execute_one_shot(full_cmd)

            if not raw_output:
                result["errors"].append("لم يتم استلام بيانات.")
                return result

            # 2. تحليل البيانات
            result["success"] = True
            result["device_info"] = self._parse_device_info(raw_output)
            result["wireless_status"] = self._parse_wireless_status(raw_output)
            result["clients"] = self._parse_clients(raw_output)
            
            # 3. الكشف الديناميكي عن الخدمات النشطة (Dynamic Process Discovery)
            result["active_services"] = self._discover_active_services(raw_output)

        except Exception as e:
            logger.exception(f"خطأ أثناء الفحص: {e}")
            result["errors"].append(str(e))
        finally:
            self.connector.close()

        return result

    def _discover_active_services(self, raw_output: str) -> list:
        """
        البحث في قائمة العمليات عن: aireplay-ng, aireplay, airserv-ng, airodump-ng
        واستخراج PID, BSSID (إن وجد)، والأمر الكامل.
        """
        services = []
        lines = raw_output.split('\n')
        
        # نمط البحث عن العمليات
        patterns = {
            "aireplay": r"aireplay-ng\s+.*?(-a\s+([0-9A-Fa-f:]{17}))?",
            "airserv": r"airserv-ng\s+.*?(-d\s+(\S+))?", # قد يكون مختلفاً حسب النسخة
            "airodump": r"airodump-ng\s+.*?(-c\s+(\d+))?\s+.*?(-I\s+(\S+))?", # مثال
            "reaver": r"reaver\s+.*?(-b\s+([0-9A-Fa-f:]{17}))?"
        }

        # نستخدم ps -ef output format: USER PID PPID ... CMD
        # نمط مبسط لاستخراج PID والأمر
        ps_pattern = re.compile(r"^\S+\s+(\d+)\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(.*)$")

        for line in lines:
            if not line.strip():
                continue
            
            # محاولة استخراج PID و CMD من ps -ef
            match = ps_pattern.match(line)
            if not match:
                continue
            
            pid = match.group(1)
            cmd = match.group(2)
            
            # البحث عن العمليات المهمة
            found_type = None
            target_info = {}

            if "aireplay-ng" in cmd:
                found_type = "aireplay"
                # استخراج BSSID
                bssid_match = re.search(r"-a\s+([0-9A-Fa-f:]{17})", cmd)
                if bssid_match:
                    target_info["target_bssid"] = bssid_match.group(1)
            
            elif "airserv-ng" in cmd:
                found_type = "airserv"
                # استخراج البورت أو الجهاز إذا وجد
                port_match = re.search(r"-p\s+(\d+)", cmd)
                if port_match:
                    target_info["port"] = port_match.group(1)
                iface_match = re.search(r"-d\s+(\S+)", cmd)
                if iface_match:
                    target_info["interface"] = iface_match.group(1)

            elif "airodump-ng" in cmd:
                found_type = "airodump"
                iface_match = re.search(r"-I\s+(\S+)", cmd)
                if iface_match:
                    target_info["monitor_iface"] = iface_match.group(1)
                channel_match = re.search(r"-c\s+(\d+)", cmd)
                if channel_match:
                    target_info["channel"] = channel_match.group(1)

            if found_type:
                services.append({
                    "pid": int(pid),
                    "type": found_type,
                    "command": cmd.strip(),
                    "target_info": target_info,
                    "status": "running"
                })

        return services

    def _parse_device_info(self, raw_output: str) -> dict:
        # ... (نفس الكود السابق)
        release_match = re.search(r"===RELEASE===(.*?)(?====|$)", raw_output, re.DOTALL)
        if release_match:
            text = release_match.group(1)
            info = {"model": "Unknown", "version": "Unknown"}
            m = re.search(r"Model:\s*(.+)", text)
            if m: info["model"] = m.group(1).strip()
            m = re.search(r"OpenWrt\s*([^\\n]+)", text)
            if m: info["version"] = m.group(1).strip()
            return info
        return {}

    def _parse_wireless_status(self, raw_output: str) -> list:
        # ... (نفس الكود السابق)
        status_match = re.search(r"===WIFI_STATUS===(.*?)(?====|$)", raw_output, re.DOTALL)
        if status_match:
            try:
                return json.loads(status_match.group(1).strip())
            except:
                return [{"raw": status_match.group(1)[:200]}]
        return []

    def _parse_clients(self, raw_output: str) -> list:
        # ... (نفس الكود السابق)
        clients_match = re.search(r"===CLIENTS===(.*?)(?====|$)", raw_output, re.DOTALL)
        if clients_match:
            text = clients_match.group(1)
            clients = []
            current = {}
            for line in text.split('\n'):
                if 'Station' in line:
                    if current: clients.append(current)
                    m = re.search(r'Station\s*([0-9A-Fa-f:]+)', line)
                    if m: current = {"mac": m.group(1), "signal": 0, "rate": 0}
                elif 'signal:' in line and current:
                    m = re.search(r'signal:\s*(-?\d+)', line)
                    if m: current["signal"] = int(m.group(1))
                elif 'rx bitrate:' in line and current:
                    m = re.search(r'rx bitrate:\s*([0-9.]+)', line)
                    if m: current["rate"] = float(m.group(1))
            if current: clients.append(current)
            return clients
        return []

    # --- دالة جديدة: قتل عملية محددة ---
    def kill_process(self, pid: int) -> dict:
        """
        قتل عملية محددة (PID) باستخدام SSH.
        returns: {"success": bool, "message": str}
        """
        if not self.connector.connect():
            return {"success": False, "message": "فشل الاتصال."}
        
        try:
            # أمر قتل قوي: kill -9 (SIGKILL)
            # نستخدم `kill -9` مباشرة لأنه أسرع وأقوى في البيئات المغلقة
            cmd = f"kill -9 {pid}"
            output = self.connector.execute_one_shot(cmd)
            
            # التحقق من النتيجة
            if "No such process" in output or "No such process" in output.lower():
                return {"success": True, "message": f"العملية {pid} لم تكن موجودة أصلاً."}
            elif "Permission denied" in output:
                return {"success": False, "message": "لا توجد صلاحية لقتل العملية."}
            else:
                # نفترض النجاح إذا لم يرد خطأ صريح
                return {"success": True, "message": f"تم قتل العملية {pid} بنجاح."}
        except Exception as e:
            return {"success": False, "message": str(e)}
        finally:
            self.connector.close()

# --- اختبار تجريبي ---
if __name__ == "__main__":
    TEST_IP = "192.168.1.1"
    TEST_USER = "root"
    TEST_PASS = "password"

    scanner = WirelessScanner(TEST_IP, TEST_USER, TEST_PASS)
    
    print("🔍 جاري الفحص...")
    data = scanner.execute_scan()
    
    print(json.dumps(data, indent=2))
    
    if data["success"] and data["active_services"]:
        print("\n⚠️ تم العثور على عمليات نشطة:")
        for svc in data["active_services"]:
            print(f"  - PID: {svc['pid']} | Type: {svc['type']} | Target: {svc['target_info']}")
            # اختبار القتل (اختياري)
            # res = scanner.kill_process(svc['pid'])
            # print(f"   Kill Result: {res['message']}")
