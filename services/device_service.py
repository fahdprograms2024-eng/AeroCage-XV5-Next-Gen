"""
File Name: device_service.py
Version: 1.0.0 | Status: Active
Purpose: Business Logic Layer for Device Management.
         Bridges DeviceRepository and SSHConnector to perform real operations.
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

# Import layers
from repositories.device_repository import DeviceRepository
from core.ssh_connector import SSHConnector, SSHError
from core.security import validate_ip_address, validate_mac_address # إذا لزم الأمر
from utils.logger import get_logger

logger = get_logger(__name__)

class DeviceService:
    """
    Service class handling device business logic.
    Manages registration, scanning, status updates, and group assignments.
    """

    def __init__(self):
        self.repository = DeviceRepository()
        # Note: SSHConnector is instantiated per operation to avoid state issues
        # It is not stored as a class member for a single global connection.

    # --- Validation Helpers ---

    def _validate_device_input(self, name: str, ip: str) -> Tuple[bool, str]:
        """Validates basic device input."""
        if not name or not name.strip():
            return False, "Device name is required."
        if not ip or not validate_ip_address(ip):
            return False, "Invalid IP address format."
        return True, ""

    # --- Device Registration & Management ---

    def register_device(self, name: str, ip: str, username: str = 'root', password: str = None, group_name: str = None) -> Dict[str, Any]:
        """
        Registers a new device.
        1. Validates input.
        2. Checks if IP exists.
        3. Creates group if needed (optional logic).
        4. Saves to DB (password encrypted).
        """
        # 1. Validate
        is_valid, error_msg = self._validate_device_input(name, ip)
        if not is_valid:
            return {"success": False, "error": error_msg}

        # 2. Check Duplicate IP
        existing = self.repository.get_device_by_ip(ip)
        if existing:
            return {"success": False, "error": f"Device with IP {ip} already exists."}

        # 3. Handle Group (Optional: Auto-create if not exists, or require ID)
        # For simplicity, we assume group_name is used to find or create.
        # Let's find or create group logic here if needed.
        # For now, we'll just pass None or find ID.
        group_id = None
        if group_name:
            groups = self.repository.get_all_groups()
            found = False
            for g in groups:
                if g == group_name:
                    group_id = g
                    found = True
                    break
            if not found:
                # Create group on the fly
                group_id = self.repository.create_group(group_name)
                if not group_id:
                    return {"success": False, "error": f"Failed to create group '{group_name}'."}

        # 4. Create Device
        device_id = self.repository.create_device(name, ip, username, password, group_id)
        
        if device_id:
            logger.info(f"Device registered: {name} ({ip})")
            return {"success": True, "device_id": device_id, "error": None}
        else:
            return {"success": False, "error": "Database error during registration."}

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """
        Retrieves all devices with decrypted passwords removed from output (security).
        Returns a list of device dictionaries.
        """
        devices_raw = self.repository.get_all_devices()
        devices = []
        for d in devices_raw:
            # d structure: (id, name, ip, user, pass_enc, group_id, group_name, status, bands)
            devices.append({
                "id": d,
                "name": d,
                "ip": d,
                "user": d,
                "group_id": d,
                "group_name": d,
                "status": d,
                "bands": d
            })
        return devices

    def get_device_by_id(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single device by ID."""
        d = self.repository.get_device_by_id(device_id)
        if not d:
            return None
        return {
            "id": d, "name": d, "ip": d, "user": d,
            "group_id": d, "group_name": d, "status": d, "bands": d
        }

    # --- Real-time Operations ---

    def scan_device(self, device_id: str) -> Dict[str, Any]:
        """
        Attempts to connect to the device via SSH to verify status.
        Updates the database with the result (Online/Offline).
        """
        # 1. Fetch Device Data
        device = self.repository.get_device_by_id(device_id)
        if not device:
            return {"success": False, "error": "Device not found."}
        
        # device tuple: (id, name, ip, user, pass_enc, group_id, group_name, status, bands)
        dev_id, name, ip, user, pass_enc, group_id, group_name, current_status, bands = device
        
        if not ip:
            return {"success": False, "error": "Device has no IP."}

        # 2. Get Password (Decrypt Temporarily)
        password = None
        if pass_enc:
            from core.security import decrypt_data
            try:
                password = decrypt_data(pass_enc)
            except Exception as e:
                logger.error(f"Failed to decrypt password for {name}: {e}")
                password = None

        # 3. Attempt SSH Connection
        is_reachable = False
        try:
            logger.info(f"Scanning device: {name} ({ip})...")
            
            # Use context manager for automatic cleanup
            with SSHConnector(hostname=ip, username=user, password=password, timeout=5) as ssh:
                # If we are here, connection succeeded
                is_reachable = True
                # Optional: Run a quick command to verify shell
                exit_code, stdout, stderr = ssh.execute_command("echo 'alive'", timeout=5)
                if exit_code != 0:
                    logger.warning(f"Command failed on {ip}, but SSH connected.")
                    # Still consider it reachable if SSH connected

        except SSHError as e:
            logger.warning(f"SSH scan failed for {name} ({ip}): {e}")
            is_reachable = False
        except Exception as e:
            logger.error(f"Unexpected error scanning {name}: {e}")
            is_reachable = False

        # 4. Update Status in DB
        new_status = "Online" if is_reachable else "Offline"
        if new_status != current_status:
            self.repository.update_device_status(device_id, new_status)
            logger.info(f"Device {name} status updated: {current_status} -> {new_status}")
        
        return {
            "success": True,
            "device_id": device_id,
            "status": new_status,
            "message": "Scan completed."
        }

    def scan_all_devices(self) -> List[Dict[str, Any]]:
        """Scans all devices in parallel (conceptually, sequentially for now)."""
        devices = self.get_all_devices()
        results = []
        for dev in devices:
            res = self.scan_device(dev["id"])
            results.append(res)
        return results

    def update_device_status_manually(self, device_id: str, status: str) -> bool:
        """Manually update device status (e.g., set to Maintenance)."""
        valid_statuses = ["Online", "Offline", "Maintenance", "Scanning"]
        if status not in valid_statuses:
            return False
        return self.repository.update_device_status(device_id, status)

    def delete_device(self, device_id: str) -> bool:
        """Deletes a device from the repository."""
        return self.repository.delete_device(device_id)

    # --- Group Operations ---

    def create_group(self, name: str) -> Dict[str, Any]:
        """Creates a new group."""
        group_id = self.repository.create_group(name)
        if group_id:
            return {"success": True, "group_id": group_id}
        return {"success": False, "error": "Group creation failed (name might be duplicate)."}

    def get_all_groups(self) -> List[Dict[str, Any]]:
        """Returns list of groups."""
        groups = self.repository.get_all_groups()
        return [{"id": g, "name": g} for g in groups]
