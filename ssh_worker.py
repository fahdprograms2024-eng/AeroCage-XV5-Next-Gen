#!/usr/bin/env python3
"""
File Name: ssh_worker.py
Purpose: Non-blocking SSH connection testing.
"""
import subprocess
import time
from PyQt6.QtCore import QThread, pyqtSignal

class SSHWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, ip, user, password):
        super().__init__()
        self.ip = ip
        self.user = user
        self.password = password

    def run(self):
        try:
            # Basic SSH test using paramiko (install with: pip install paramiko)
            import paramiko
            
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
