import os
import json
import time
import threading
import subprocess
import requests
from datetime import datetime
from pathlib import Path

class IdleDetectorExtension:
    """
    A global extension that monitors ComfyUI idle status and automatically shuts down idle pods
    """
    
    def __init__(self):
        self.status_dir = Path.home() / ".custom_pod_stats"
        self.status_file = self.status_dir / "status"
        self.shutdown_endpoint = os.getenv("SHUTDOWN_ENDPOINT", "https://your-api.com/shutdown")
        self.check_interval = int(os.getenv("IDLE_CHECK_INTERVAL", "30"))  # 5 minutes
        self.idle_threshold = int(os.getenv("IDLE_THRESHOLD", "900"))  # 15 minutes
        self.monitor_thread = None
        self.running = False
        
        # Ensure status directory exists
        self.status_dir.mkdir(exist_ok=True)
        
        # Initialize status file and start monitoring
        self._update_status("active")
        self.start_monitoring()
        print("Idle Detector Extension initialized and monitoring started")

    def _update_status(self, status):
        """Update the status file with current status and timestamp"""
        status_data = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat() if status == "active" else self._get_last_active()
        }
        
        try:
            with open(self.status_file, 'w') as f:
                json.dump(status_data, f)
        except Exception as e:
            print(f"Error updating status file: {e}")

    def _get_status(self):
        """Read current status from file"""
        try:
            if self.status_file.exists():
                with open(self.status_file, 'r') as f:
                    return json.load(f)
            return {"status": "active", "timestamp": datetime.now().isoformat(), "last_active": datetime.now().isoformat()}
        except Exception as e:
            print(f"Error reading status file: {e}")
            return {"status": "active", "timestamp": datetime.now().isoformat(), "last_active": datetime.now().isoformat()}

    def _get_last_active(self):
        """Get the last active timestamp"""
        status_data = self._get_status()
        return status_data.get("last_active", datetime.now().isoformat())

    def _get_current_pod_id(self):
        """Get current RunPod ID using multiple fallback methods"""
        
        # Method 1: Check RunPod metadata file (preferred)
        try:
            metadata_file = Path("/runpod-volume/runpod.json")
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    pod_id = metadata.get("podId")
                    if pod_id:
                        print(f"Found pod ID from metadata file: {pod_id}")
                        return pod_id
        except Exception as e:
            print(f"Error reading RunPod metadata file: {e}")
        
        # Method 2: Check hostname (sometimes set to pod ID)
        try:
            import socket
            hostname = socket.gethostname()
            # RunPod pod IDs are typically alphanumeric, check if hostname looks like one
            if len(hostname) > 8 and hostname.replace('-', '').isalnum():
                print(f"Using hostname as pod ID: {hostname}")
                return hostname
        except Exception as e:
            print(f"Error getting hostname: {e}")
        
        # Method 3: Check environment variable (if manually set)
        env_pod_id = os.getenv("RUNPOD_POD_ID")
        if env_pod_id and env_pod_id != "unknown":
            print(f"Found pod ID from environment variable: {env_pod_id}")
            return env_pod_id
        
        # Method 4: Fallback to runpod CLI (original method)
        try:
            result = subprocess.run(
                ["runpod", "get", "pod"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'Pod ID:' in line or 'ID:' in line:
                        pod_id = line.split(':')[-1].strip()
                        print(f"Found pod ID from RunPod CLI: {pod_id}")
                        return pod_id
        except Exception as e:
            print(f"Error using RunPod CLI: {e}")
        
        print("Could not determine pod ID, using 'unknown'")
        return "unknown"

    def _call_shutdown_endpoint(self, pod_id):
        """Call the shutdown endpoint with pod ID"""
        try:
            params = {"podId": pod_id}
            response = requests.get(self.shutdown_endpoint, params=params, timeout=30)
            print(f"Shutdown endpoint called for pod {pod_id}. Response: {response.status_code}")
            return response.status_code == 200
        except Exception as e:
            print(f"Error calling shutdown endpoint: {e}")
            return False

    def _monitor_loop(self):
        """Main monitoring loop that runs in background thread"""
        print(f"Starting idle monitoring loop (check every {self.check_interval}s, shutdown after {self.idle_threshold}s idle)")
        
        while self.running:
            try:
                status_data = self._get_status()
                current_status = status_data.get("status", "active")
                last_active_str = status_data.get("last_active", datetime.now().isoformat())
                
                last_active = datetime.fromisoformat(last_active_str.replace('Z', '+00:00').replace('+00:00', ''))
                now = datetime.now()
                
                if current_status == "idle":
                    idle_duration = (now - last_active).total_seconds()
                    print(f"Pod idle for {idle_duration/60:.1f} minutes (threshold: {self.idle_threshold/60:.1f} minutes)")
                    
                    if idle_duration >= self.idle_threshold:
                        print(f"Pod has been idle for {idle_duration/60:.1f} minutes. Initiating shutdown...")
                        pod_id = self._get_current_pod_id()
                        if self._call_shutdown_endpoint(pod_id):
                            print("Shutdown initiated successfully")
                        else:
                            print("Failed to initiate shutdown")
                        break
                else:
                    print(f"Pod status: {current_status}")
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(self.check_interval)

    def start_monitoring(self):
        """Start the monitoring thread"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            print("Pod idle monitoring started")

    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            print("Pod idle monitoring stopped")

    def set_active(self):
        """Set status to active - called by frontend"""
        self._update_status("active")

    def set_idle(self):
        """Set status to idle - called by frontend"""
        self._update_status("idle")

    def get_status_data(self):
        """Get current status data"""
        return self._get_status()


# Global extension instance
idle_detector = IdleDetectorExtension()
