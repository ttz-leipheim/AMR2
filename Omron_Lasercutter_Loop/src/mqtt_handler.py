"""
MQTT Handler & MQTTRouteExecutor wrapper for OMRON LD Robot Control
"""

import sys
import json
import time
import ssl
from typing import Dict, Any, Optional

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("❌ Fehler: Das Paket 'paho-mqtt' ist nicht installiert.")
    print("   Bitte installieren Sie es mit: pip install paho-mqtt")
    sys.exit(1)

from src.route_handler import RouteExecutor
from src.rich_ui import RobotUI


class RestartCycleException(Exception):
    """Exception to signal a cycle restart triggered via MQTT."""
    pass


class DockRequestedException(Exception):
    """Exception raised when an explicit dock/charge command is received via MQTT."""
    pass


class MqttDirectTaskException(Exception):
    """Exception raised to execute a direct, single task on-demand."""
    def __init__(self, task_name: str):
        self.task_name = task_name
        super().__init__(f"Direct MQTT task requested: {task_name}")


class MQTTHandler:
    def __init__(self, config: Dict[str, Any], ui: RobotUI):
        self.config = config
        self.ui = ui
        
        # Load MQTT configuration
        mqtt_config = config.get('mqtt', {})
        self.broker = mqtt_config.get('broker', 'localhost')
        self.port = mqtt_config.get('port', 1883)
        self.client_id = mqtt_config.get('client_id', 'omron_amr_client')
        self.username = mqtt_config.get('username', '').strip()
        self.password = mqtt_config.get('password', '').strip()
        
        topics = mqtt_config.get('topics', {})
        self.cmd_topic = topics.get('command', 'robot/command')
        self.status_topic = topics.get('status', 'robot/status')
        
        # Automatically enable TLS if using secure port 8883 or if specified in config
        self.use_tls = mqtt_config.get('tls', self.port == 8883)
        
        # State management flags
        self._is_stopped = True
        self._restart_requested = False
        self._dock_requested = False
        self._step_mode_active = False
        self._direct_task: Optional[str] = None
        self._stop_start_time = None
        self._docked_timeout = False
        
        # Client initialization supporting both paho-mqtt v1.x and v2.x APIs
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=self.client_id)
        except AttributeError:
            self.client = mqtt.Client(client_id=self.client_id)
            
        # Configure TLS/SSL encryption for secure brokers (like HiveMQ Cloud)
        if self.use_tls:
            try:
                self.client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
            except AttributeError:
                try:
                    self.client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
                except Exception:
                    self.client.tls_set()  # Default fallback
            
        if self.username:
            self.client.username_pw_set(self.username, self.password)
            
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc, *args, **kwargs):
        if rc == 0:
            self.ui.print_success(f"✓ Connected to MQTT Broker: {self.broker}:{self.port}")
            self.client.subscribe(self.cmd_topic)
            self.ui.print_info(f"Subscribed to command topic: {self.cmd_topic}")
            self.publish_status(None, state="WAITING_FOR_ORDER")
        else:
            self.ui.print_error(f"✗ MQTT Connection failed with result code: {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode('utf-8').strip().lower()
            self.ui.print_info(f"✉ MQTT message received on '{msg.topic}': '{payload}'")
            
            # 1. Normal Start/Resume
            if payload in ('start', 'order', 'run'):
                self._is_stopped = False
                self._step_mode_active = False
                self._dock_requested = False
                self._direct_task = None
                self.ui.print_success("▶ MQTT: START/ORDER command received. Resuming route execution.")
                
            # 2. Pause/Stop at Goal
            elif payload in ('stop', 'pause'):
                self._is_stopped = True
                self._stop_start_time = time.time()
                self._docked_timeout = False
                self.ui.print_warning("⏸ MQTT: STOP command received. Waiting at the next goal.")
                
            # 3. Full Cycle Restart
            elif payload == 'restart':
                self._restart_requested = True
                self.ui.print_warning("🔄 MQTT: RESTART command received. Interrupting current cycle.")
                
            # 4. Immediate Dock/Charge
            elif payload in ('dock', 'charge'):
                self._dock_requested = True
                self._is_stopped = True
                self.ui.print_warning("🔌 MQTT: Immediate DOCK/CHARGE requested. Interrupting active execution...")
                
            # 5. Single Step Trigger
            elif payload in ('step', 'next'):
                self._step_mode_active = True
                self._is_stopped = False
                self.ui.print_info("⏭ MQTT: STEP command received. Executing next single step...")
                
            # 6. Direct Task Subprocess (e.g. task:load_plates)
            elif payload.startswith("task:"):
                target_task = payload.split(":", 1)[1].strip()
                self._direct_task = target_task
                self.ui.print_info(f"🎛 MQTT: Direct TASK requested for '{target_task}'...")
                
            else:
                self.ui.print_warning(f"⚠ MQTT: Unknown payload '{payload}'")
        except Exception as e:
            self.ui.print_error(f"Error handling MQTT message: {e}")

    def connect(self) -> bool:
        try:
            self.ui.print_info(f"Connecting to MQTT Broker at {self.broker}:{self.port}...")
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
            self.ui.print_info("MQTT background loop started.")
            return True
        except Exception as e:
            self.ui.print_error(f"✗ Could not connect to MQTT Broker: {e}")
            return False

    def disconnect(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
            self.ui.print_info("Disconnected cleanly from MQTT Broker.")
        except Exception:
            pass

    def is_stopped(self) -> bool:
        return self._is_stopped

    def check_and_wait_for_order(self, executor: 'MQTTRouteExecutor'):
        """Checks for stops, timeouts, and raises custom exceptions to interrupt/redirect the AMR."""
        # Check if direct dock was requested
        if self._dock_requested:
            self._dock_requested = False
            raise DockRequestedException("Explicit dock requested via MQTT")

        # Check if direct task was requested
        if self._direct_task:
            task_name = self._direct_task
            self._direct_task = None
            raise MqttDirectTaskException(task_name)

        if self._restart_requested:
            self._restart_requested = False
            raise RestartCycleException("Cycle restart requested via MQTT.")

        if not self._is_stopped:
            return

        # Start measuring waiting time
        if self._stop_start_time is None:
            self._stop_start_time = time.time()
            
        self._docked_timeout = False
        self.ui.print_warning("⏸ AMR is in STOPPED state. Waiting for an MQTT command...")
        
        while self._is_stopped:
            # Check for immediate interrupts during wait state
            if self._dock_requested:
                self._dock_requested = False
                raise DockRequestedException("Explicit dock requested via MQTT while stopped")

            if self._direct_task:
                task_name = self._direct_task
                self._direct_task = None
                raise MqttDirectTaskException(task_name)

            if self._restart_requested:
                self._restart_requested = False
                raise RestartCycleException("Cycle restart requested via MQTT while waiting.")

            # If user triggered "next/step" while we were waiting
            if self._step_mode_active:
                break

            elapsed = time.time() - self._stop_start_time
            
            # 10 minutes timeout (600 seconds)
            if elapsed >= 600 and not self._docked_timeout:
                self.ui.print_warning("⏰ 10 minutes timeout reached with no new order. Returning to charging station...")
                self.publish_log("Timeout of 10 minutes reached. Navigating to charging station.")
                executor._dock()
                self._docked_timeout = True
                self.publish_status(executor, state="DOCKED_TIMEOUT")
            
            self.publish_status(executor)
            time.sleep(2.0)
            
        # Reset state once resumed
        self._stop_start_time = None
        self._docked_timeout = False

    def publish_status(self, executor: Optional['MQTTRouteExecutor'], step: Optional[Dict] = None, idx: Optional[int] = None, step_success: Optional[bool] = None, state: Optional[str] = None):
        """Publishes the current AMR and execution status over MQTT as JSON."""
        try:
            status_data = {}
            if executor:
                status_data = executor._get_status()
            
            if state:
                current_state = state
            elif self._is_stopped:
                current_state = "DOCKED_TIMEOUT" if self._docked_timeout else "WAITING_FOR_ORDER"
            else:
                current_state = "RUNNING"

            payload = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "robot_name": self.config.get('robot', {}).get('name', 'Robot'),
                "state": current_state,
                "battery": status_data.get("StateOfCharge", status_data.get("BatteryVoltage", "Unknown")),
                "location": status_data.get("Location", "Unknown"),
                "extended_status": status_data.get("ExtendedStatusForHumans", "Unknown"),
                "arcl_status": status_data.get("Status", "Unknown")
            }
            
            if step and idx is not None:
                payload["last_completed_step"] = {
                    "index": idx,
                    "description": step.get("description", ""),
                    "action": "goto" if "goto" in step else step.get("action", step.get("task", "unknown")),
                    "success": step_success
                }
                
            self.client.publish(self.status_topic, json.dumps(payload), qos=1)
        except Exception as e:
            self.ui.print_error(f"Failed to publish MQTT status: {e}")

    def publish_log(self, message: str):
        try:
            payload = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "robot_name": self.config.get('robot', {}).get('name', 'Robot'),
                "log": message
            }
            self.client.publish(self.status_topic, json.dumps(payload), qos=1)
        except Exception as e:
            self.ui.print_error(f"Failed to publish MQTT log: {e}")


class MQTTRouteExecutor(RouteExecutor):
    """Subclass that wraps RouteExecutor step execution to intercept steps with MQTT checkpoints."""
    def __init__(self, connection, config: Dict, mqtt_handler: MQTTHandler):
        super().__init__(connection, config)
        self.mqtt_handler = mqtt_handler
        
        # Override and wrap the original step_executor execute method
        orig_execute = self.step_executor.execute
        
        def wrapped_execute(step: Dict, idx: int) -> bool:
            # Check for stopped or restart state before proceeding to next step
            self.mqtt_handler.check_and_wait_for_order(self)
            
            # Run the core logic of the step
            res = orig_execute(step, idx)
            
            # Publish progress update
            self.mqtt_handler.publish_status(self, step, idx, res)
            
            # If step-by-step mode was triggered, pause again immediately after this step completes
            if self.mqtt_handler._step_mode_active:
                self.mqtt_handler._step_mode_active = False
                self.mqtt_handler._is_stopped = True
                
            return res
            
        self.step_executor.execute = wrapped_execute