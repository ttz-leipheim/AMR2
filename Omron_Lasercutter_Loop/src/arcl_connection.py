"""
ARCLConnection - 100% Config-gesteuert + Robust
"""

import socket
import time
from typing import Optional, Dict


class ARCLConnection:
    
    def __init__(self, config: Dict):
        """
        Initialisiert the ARCLConnection instance with the given configuration.

        :param config: The configuration dictionary containing the necessary ARCL connection settings.
        :type config: Dict
        """

        self.config = config
        self.arcl_config = config.get('arcl_connection', {})
        self.socket_config = self.arcl_config.get('socket', {})
        self.login_config = self.arcl_config.get('login', {})
        self.receive_config = self.arcl_config.get('receive', {})
        self.log_config = self.arcl_config.get('logging', {})
        self.messages = self.arcl_config.get('messages', {})
        
        # Robot Config
        robot_cfg = config.get('robot', {})
        self.ip = robot_cfg.get('ip')
        self.port = robot_cfg.get('arcl_port', 7171)
        self.password = robot_cfg.get('arcl_password', 'adept')
        self.connect_timeout = robot_cfg.get('connection_timeout', 10)
        
        self.socket = None
        self.connected = False

    def connect(self) -> bool:
 
        """
        Establishes a connection to the ARCL robot at the specified IP and port.

        :return: True if the connection was established successfully, False otherwise.
        :rtype: bool
        """
        msg = self.messages.get('connecting', 'Connecting to {ip}:{port}...')
        print(msg.format(ip=self.ip, port=self.port))
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.socket_config.get('connect_timeout', 10))
            self.socket.connect((self.ip, self.port))
            
            # Banner empfangen
            banner = self._receive_data(
                timeout=self.socket_config.get('receive_timeout_default', 1.0)
            )
            
            if self.log_config.get('show_banner', True):
                print(f"Banner: {banner[:100]}")
            
            # Password-Login?
            banner_lower = banner.lower()
            pw_indicators = self.login_config.get('password_required_indicators', [])
            if any(ind in banner_lower for ind in pw_indicators):
                msg = self.messages.get('login_prompt', 'Sending password...')
                print(msg)
                
                self.socket.sendall((self.password + "\r\n").encode("utf-8"))
                response = self._receive_data(
                    timeout=self.socket_config.get('receive_timeout_default', 1.0)
                )
                
                if self.log_config.get('show_login_response', True):
                    print(f"Login-Response: {response[:200]}")
                
                # Login-Erfolg prüfen
                success_indicators = self.login_config.get('login_success_indicators', [])
                failure_indicators = self.login_config.get('login_failure_indicators', [])
                
                response_lower = response.lower()
                if any(ind in response_lower for ind in failure_indicators):
                    msg = self.messages.get('login_failed', '✗ Password incorrect!')
                    print(msg)
                    return False
                
                if (any(ind in response_lower for ind in success_indicators) or 
                    len(response) > self.login_config.get('response_min_length', 10)):
                    msg = self.messages.get('login_success', '✓ Login successful')
                    print(msg)
                    self.connected = True
                    return True
            
            # Kein Password nötig
            self.connected = True
            return True
            
        except socket.timeout:
            msg = self.messages.get('timeout', '✗ Timeout at {ip}:{port}')
            print(msg.format(ip=self.ip, port=self.port))
            return False
        except ConnectionRefusedError:
            msg = self.messages.get('connection_refused', '✗ Connection refused')
            print(msg)
            return False
        except Exception as e:
            print(f"✗ Connection error: {e}")
            return False

    def _receive_data(self, timeout: float = None) -> str:

        """
        Empfängt Daten vom Socket.

        :param timeout: Optional timeout in Sekunden (Standard: 1 Sekunde)
        :return: Empfangene Daten als String
        """
        
        if not self.socket:
            return ""
        
        timeout = timeout or self.socket_config.get('receive_timeout_default', 1.0)
        full = ""
        end_time = time.time() + timeout
        self.socket.settimeout(timeout)
        
        max_loops = self.receive_config.get('max_receive_loops', 50)
        loop_count = 0
        
        end_indicators = self.receive_config.get('end_indicators', [])
        
        while time.time() < end_time and loop_count < max_loops:
            try:
                chunk = self.socket.recv(self.socket_config.get('buffer_size', 8192))
                if not chunk:
                    break
                
                text = chunk.decode("utf-8", errors="ignore")
                full += text
                
                # Early exit bei End-Indikatoren
                if any(ind in full for ind in end_indicators):
                    break
                    
            except socket.timeout:
                break
            except Exception:
                break
            
            loop_count += 1
        
        return full.strip()

    def send_and_receive(self, command: str, timeout: float = None) -> str:
        """
        Sende einen Befehl an den Socket und empfängt die Antwort.

        :param command: Der zu sendende Befehl als String
        :param timeout: Optionaler Timeout in Sekunden (Standard: 2 Sekunden)
        :return: Die empfangene Daten als String
        :raises Exception: Wenn keine Verbindung hergestellt wurde oder ein Fehler auftritt
        """
        if not self.socket:
            raise Exception("No connection established")
        
        timeout = timeout or self.socket_config.get('command_timeout_default', 2.0)
        
        # Config-gesteuertes Logging
        if (self.log_config.get('show_commands', True) and 
            command.lower() not in self.log_config.get('exclude_commands', [])):
            print(f"Sende: {command}")
        
        try:
            self.socket.sendall((command + "\r\n").encode("utf-8"))
            return self._receive_data(timeout=timeout)
            
        except Exception as e:
            msg = self.messages.get('send_error', "Error on '{command}': {error}")
            raise Exception(msg.format(command=command, error=e))

    def disconnect(self):
  
        """
        Disconnects from the ARCL robot and closes the socket.

        :return: None
        :rtype: None
        """
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            
            self.socket = None
            self.connected = False
            msg = self.messages.get('disconnected', 'Connection closed')
            print(msg)

    def is_connected(self) -> bool:
        
        """
        Checks if the connection to the ARCL robot is established.

        :return: True if the connection is established, False otherwise.
        :rtype: bool
        """
        return self.connected and self.socket is not None

    def reconnect(self, max_attempts: int = 3) -> bool:
        
        """
        Reconnects to the ARCL robot with a maximum of {max_attempts} attempts.

        :param max_attempts: The maximum number of reconnect attempts (default: 3)
        :return: True if the reconnection was successful, False otherwise
        :rtype: bool
        """
        self.disconnect()
        
        for attempt in range(max_attempts):
            print(f"Reconnect attempt {attempt + 1}/{max_attempts}")
            if self.connect():
                return True
            time.sleep(2.0)
        
        return False
