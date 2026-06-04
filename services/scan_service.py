# في ملف services/scan_service.py

import re
from datetime import datetime
from typing import List, Dict

class NetworkScanner:
    """
    محرك فحص الشبكات المستمد من الأكواد الباشية (v8.2.0)
    يقوم بتحليل البيانات الخام وتصنيفها وأرشفتها.
    """

    # تصنيف المنافسين (مستخرج من كودك)
    COMPETITORS_KEYWORDS = ["تواصل", "سوا", "ابوعبيدة", "ابو عبيده", "TWASUL"]
    MY_NETWORK_KEYWORDS = ["Fahd_Net"]

    def parse_raw_scan(self, scan_output: str) -> List[Dict]:
        """
        تحويل مخرجات iwinfo الخام إلى قائمة من dictionaries منظمة.
        (نسخة محسنة من كود awk في سكربتاتك)
        """
        networks = []
        current = {}
        
        # محاكاة منطق awk في الكود الباشي
        for line in scan_output.splitlines():
            line = line.strip()
            if not line:
                continue
            
            if "Address:" in line:
                current['mac'] = line.split(":").strip()
            elif "ESSID:" in line:
                ssid = line.split("ESSID:").strip().strip('"')
                current['ssid'] = ssid if ssid else "[Hidden_SSID]"
            elif "Channel:" in line:
                current['channel'] = line.split(":").strip()
            elif "Signal:" in line:
                signal = line.split(":").strip()
                # إذا اكتملت البيانات، نضيفها للقائمة
                if all(k in current for k in ['mac', 'ssid', 'channel', 'signal']):
                    networks.append(current)
                    current = {} # إعادة تعيين
                else:
                    current['signal'] = signal
        
        return networks

    def classify_network(self, ssid: str) -> str:
        """
        تصنيف الشبكة بناءً على المنطق الموجود في سكربتاتك.
        Returns: "MY_NETWORK", "COMPETITOR", "OTHER"
        """
        if any(k in ssid for k in self.MY_NETWORK_KEYWORDS):
            return "MY_NETWORK"
        if any(k in ssid for k in self.COMPETITORS_KEYWORDS):
            return "COMPETITOR"
        return "OTHER"

    def calculate_congestion(self, networks: List[Dict]) -> Dict[int, Dict]:
        """
        حساب الازدحام لكل قناة (منطق show_percentages.sh)
        """
        channels = {}
        for net in networks:
            ch = int(net['channel'])
            if ch not in channels:
                channels[ch] = {'count': 0, 'nets': []}
            channels[ch] ['count'] += 1
            channels[ch] ['nets'].append(net['ssid'])
        
        total = len(networks)
        result = {}
        for ch, data in channels.items():
            percentage = (data['count'] * 100) // total if total > 0 else 0
            # تحديد اللون/الحالة
            status = "LOW"
            if percentage > 30: status = "CRITICAL"
            elif percentage > 15: status = "WARNING"
            
            result[ch] = {
                "count": data['count'],
                "percentage": percentage,
                "status": status,
                "networks": data['nets']
            }
        return result

    def archive_scan(self, networks: List[Dict], device_id: str, db_path: str):
        """
        أرشفة النتائج مع حفظ تاريخ أول ظهور (منطق الكود الباشي).
        """
        # تمثيل قاعدة البيانات البسيطة (يمكن استبداله بـ SQLite لاحقاً)
        import json
        import os
        
        if not os.path.exists(db_path):
            history = []
        else:
            with open(db_path, 'r') as f:
                history = json.load(f)
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for net in networks:
            mac = net['mac']
            # البحث إذا كان هذا الـ MAC موجوداً مسبقاً
            existing = next((item for item in history if item['mac'] == mac), None)
            
            if existing:
                # تحديث آخر وقت ظهور فقط
                existing['last_seen'] = now
                existing['signal_history'].append({"time": now, "signal": net['signal']})
            else:
                # شبكة جديدة: تسجيل وقت أول ظهور
                history.append({
                    "mac": mac,
                    "ssid": net['ssid'],
                    "channel": net['channel'],
                    "first_seen": now,
                    "last_seen": now,
                    "signal_history": [{"time": now, "signal": net['signal']}],
                    "classification": self.classify_network(net['ssid'])
                })
        
        # حفظ البيانات
        with open(db_path, 'w') as f:
            json.dump(history, f, indent=4)
        
        return len(history)
