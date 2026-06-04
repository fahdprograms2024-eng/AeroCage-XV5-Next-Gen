#!/usr/bin/env python3
"""
File Name: scripts/scan_clients.py
Version: 8.0.0 [AeroCage Next Gen]
Description: Unified client scanner module.
             Connects to OpenWRT device, extracts wireless status, clients, 
             checks for active Airserv/Aireplay attacks, and returns JSON.
             Uses proven SSH and Parser logic from legacy code.
"""

import json
import re
import sys
import os
import time

# إضافة المسار للجذر للمشروع (للاستيراد من core و utils)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.ssh_connector import SSHConnector  # من الكود القديم المجرّب
from core.security import SecurityEngine    # من الإصدار الجديد
from services.report_parser import ReportParser # من الكود القديم المجرّب
from utils.logger import AeroLogger

logger = AeroLogger.get_logger()

class WirelessScanner:
    """
    ماسح لاسلكي موحد يجمع بيانات الزبائن، الانترفيسات، ويكشف الهجمات.
    """

    def __init__(self, ip: str, user: str, password: str):
        self.ip = ip
        self.user = user
        self.password = password
        self.security = SecurityEngine()
        # فك تشفير كلمة المرور إذا كانت مشفرة (في حالة الاستخدام من قاعدة البيانات)
        # لكن هنا نمررها مباشرة كما هي من الواجهة
        self.connector = SSHConnector(ip, user, password)
        self.parser = ReportParser()

    def execute_scan(self, check_airserv: bool = True, check_attacks: bool = True) -> dict:
        """
        تنفيذ الفحص الكامل وإرجاع النتائج كقاموس JSON.
        """
        result = {
            "success": False,
            "device_info": {},
            "wireless_status": [],
            "clients": [],
            "airserv_detected": [],
            "attacks_detected": [],
            "errors": []
        }

        if not self.connector.connect():
            result["errors"].append("فشل الاتصال بالأكسس عبر SSH.")
            return result

        try:
            # 1. بناء الأمر الموحد (One-Shot Command)
            # نجمع كل المعلومات المطلوبة في أمر واحد لتقليل زمن الـ RTT
            commands = [
                "echo '===RELEASE===' && cat /etc/openwrt_release 2>/dev/null",
                "echo '===UPTIME===' && cat /proc/uptime 2>/dev/null",
                "echo '===WIFI_STATUS===' && ubus call network.wireless status 2>/dev/null",
                "echo '===CLIENTS===' && hostapd-cli -i wlan0 status 2>/dev/null || iw dev wlan0 station dump 2>/dev/null",
                "echo '===INTERFACES===' && iw dev 2>/dev/null",
            ]

            # إضافة أوامر الفحص الاختياري
            if check_airserv:
                # فحص المنافذ الشائعة لـ Airserv (666, 777, etc.)
                # نستخدم netstat أو ss إذا توفر، وإلا نستخدم lsof
                commands.append("echo '===AIRSERV_PORTS===' && (ss -tlnp 2>/dev/null | grep -E ':(666|777|888|999) ' || netstat -tlnp 2>/dev/null | grep -E ':(666|777|888|999) ' || echo 'No ports found')")
            
            if check_attacks:
                # فحص عمليات aireplay-ng النشطة
                commands.append("echo '===AIREPLAY_PROCESSES===' && ps | grep -i aireplay | grep -v grep || echo 'No aireplay processes'")

            full_cmd = "; ".join(commands)

            logger.info(f"إرسال أمر فحص شامل إلى {self.ip}...")
            raw_output = self.connector.execute_one_shot(full_cmd)

            if not raw_output:
                result["errors"].append("لم يتم استلام بيانات من الجهاز.")
                return result

            # 2. تحليل البيانات باستخدام ReportParser
            parsed_data = self.parser.extract_sections(raw_output)
            
            # ملء النتائج
            result["success"] = True
            result["device_info"] = self._parse_device_info(parsed_data.get("RELEASE", ""))
            result["wireless_status"] = self._parse_wireless_status(parsed_data.get("WIFI_STATUS", ""))
            result["clients"] = self._parse_clients(parsed_data.get("CLIENTS", ""))
            
            if check_airserv:
                result["airserv_detected"] = self._parse_airserv(parsed_data.get("AIRSERV_PORTS", ""))
            
            if check_attacks:
                result["attacks_detected"] = self._parse_attacks(parsed_data.get("AIREPLAY_PROCESSES", ""))

            logger.info(f"تم استلام وتحليل البيانات من {self.ip} بنجاح.")

        except Exception as e:
            logger.exception(f"خطأ أثناء الفحص: {e}")
            result["errors"].append(str(e))
        finally:
            self.connector.close()

        return result

    def _parse_device_info(self, release_text: str) -> dict:
        """استخراج معلومات الجهاز من نصوص الـ release."""
        info = {"model": "Unknown", "version": "Unknown", "target": "Unknown"}
        if "Model" in release_text:
            match = re.search(r'Model:\s*(.+)', release_text)
            if match: info["model"] = match.group(1).strip()
        if "OpenWrt Version" in release_text:
            match = re.search(r'OpenWrt\s*([^\\n]+)', release_text)
            if match: info["version"] = match.group(1).strip()
        if "Target" in release_text:
            match = re.search(r'Target:\s*(.+)', release_text)
            if match: info["target"] = match.group(1).strip()
        return info

    def _parse_wireless_status(self, status_text: str) -> list:
        """
        تحليل حالة الـ wireless (ubus output).
        يعيد قائمة بالانترفيسات والترددات.
        """
        # هذا يحتاج لتنقيح حسب مخرجات ubus الفعلية
        # سنستخدم Regex بسيط لاستخراج أسماء الـ interfaces والترددات
        interfaces = []
        # مثال: {"radio0": {"up": true, "channel": 6, "frequency": 2437, ...}}
        # سنحاول استخراج البيانات الخام كـ JSON إذا أمكن، أو نصياً
        try:
            # محاولة تحليل كـ JSON إذا كان المخرجات JSON
            data = json.loads(status_text)
            for radio, details in data.items():
                interfaces.append({
                    "radio": radio,
                    "up": details.get("up", False),
                    "channel": details.get("channel", "N/A"),
                    "frequency": details.get("frequency", "N/A"),
                    "type": "managed" if details.get("mode") == "AP" else "monitor"
                })
        except json.JSONDecodeError:
            # إذا فشل JSON، نعيد النص الخام ليتم معالجته لاحقاً أو نستخدم Regex
            # (يمكن تطوير هذا الجزء لاحقاً)
            interfaces.append({"raw": status_text[:200]})
        return interfaces

    def _parse_clients(self, clients_text: str) -> list:
        """
        تحليل بيانات الزبائن (من hostapd-cli أو iw).
        يعيد قائمة بـ {mac, signal, rate, auth}
        """
        clients = []
        # نمط بسيط لاستخراج MAC و Signal
        # يعتمد على مخرجات `iw dev wlan0 station dump`
        lines = clients_text.split('\n')
        current_client = {}
        for line in lines:
            if 'Station' in line:
                if current_client: clients.append(current_client)
                match = re.search(r'Station\s*([0-9A-Fa-f:]+)', line)
                if match:
                    current_client = {"mac": match.group(1), "signal": 0, "rate": 0}
            elif 'signal:' in line:
                match = re.search(r'signal:\s*(-?\d+)', line)
                if match: current_client["signal"] = int(match.group(1))
            elif 'rx bitrate:' in line:
                match = re.search(r'rx bitrate:\s*([0-9.]+)', line)
                if match: current_client["rate"] = float(match.group(1))
        
        if current_client: clients.append(current_client)
        return clients

    def _parse_airserv(self, ports_text: str) -> list:
        """فحص المنافذ لاكتشاف سيرفر Airserv."""
        detected = []
        # البحث عن منافذ 666, 777, 888, 999
        ports = re.findall(r':(\d+)\s', ports_text)
        for port in ports:
            if port in ['666', '777', '888', '999']:
                detected.append({"port": port, "service": "Airserv?", "status": "active"})
        return detected

    def _parse_attacks(self, process_text: str) -> list:
        """فحص العمليات لاكتشاف هجمات aireplay."""
        attacks = []
        lines = process_text.split('\n')
        for line in lines:
            if 'aireplay-ng' in line and 'grep' not in line:
                # استخراج PID و BSSID إذا أمكن
                match = re.search(r'(\d+)\s+.*aireplay-ng.*(-a\s*([0-9A-Fa-f:]+))?', line)
                if match:
                    pid = match.group(1)
                    bssid = match.group(3) if match.group(3) else "Unknown"
                    attacks.append({"pid": pid, "target_bssid": bssid, "cmd": line.strip()})
        return attacks

# --- اختبار تجريبي (Main Block) ---
if __name__ == "__main__":
    # بيانات اختبار (يمكن تغييرها)
    TEST_IP = "192.168.1.1"
    TEST_USER = "root"
    TEST_PASS = "your_password"

    print("🚀 بدء فحص تجريبي...")
    scanner = WirelessScanner(TEST_IP, TEST_USER, TEST_PASS)
    result = scanner.execute_scan(check_airserv=True, check_attacks=True)
    
    print("\n📊 النتائج (JSON):")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result["success"]:
        print("\n✅ الفحص نجح!")
        if result["airserv_detected"]:
            print(f"⚠️ تم اكتشاف سيرفر Airserv على المنافذ: {[p['port'] for p in result['airserv_detected']]}")
        if result["attacks_detected"]:
            print(f"⚠️ تم اكتشاف هجمات جارية: {len(result['attacks_detected'])} عملية")
    else:
        print("\n❌ فشل الفحص:")
        for err in result["errors"]:
            print(f" - {err}")
