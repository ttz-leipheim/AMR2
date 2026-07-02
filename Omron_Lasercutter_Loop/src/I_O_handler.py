

import re
import time
import logging
from typing import Optional, Tuple, Dict

class ConfirmButtonTask:
    
    def __init__(self, connection, ui, config: Dict = None):
        """
        Initialises the ConfirmButtonTask instance with the given configuration.

        :param connection: The established ARCL connection.
        :param ui: The RobotUI instance.
        :param config: The configuration dictionary containing the necessary IO handler settings.
        :type config: Dict
        """
        
        self.conn = connection
        self.ui = ui
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Config laden
        self.io_config = self.config.get('io_handler', {})
        self.display_config = self.io_config.get('display', {})
        self.poll_config = self.io_config.get('polling', {})
        self.parse_config = self.io_config.get('parsing', {})
        self.messages = self.io_config.get('messages', {})
        
        # Regex Patterns
        self.input_pattern = re.compile(
            self.parse_config.get('input_query', r'^\s*Input:\s+(\S+)\s+(on|off|true|false)'),
            re.IGNORECASE | re.MULTILINE
        )
        self.inputlist_pattern = re.compile(
            self.parse_config.get('input_list', r'^\s*InputList:\s+(\S+)'),
            re.IGNORECASE | re.MULTILINE
        )
        self.generic_pattern = re.compile(r'^i\d+$')
        
        # 🎛 Polling + Display Parameter
        self.poll_interval = self.poll_config.get('interval', 0.2)
        self.query_timeout = self.poll_config.get('query_timeout', 0.5)
        self.debounce_window = self.poll_config.get('debounce_window', 0.5)
        self.state_timeout = self.poll_config.get('state_timeout', 1.0)
        self.display_enabled = self.display_config.get('enabled', True)
        self.max_display_len = self.display_config.get('max_length', 28)
        
        # Status-Tracking
        self.button_states = {}
        self.flank_detected = {}

    def _display_text(self, message: str, display_type: str = "touchscreen"):
        
        """
        Displays a message on the robot's display.

        Parameters
        ----------
        message : str
            The message to be displayed.
        display_type : str, optional
            The type of display to use. Can be "touchscreen" or "status". Defaults to "touchscreen".

        Returns
        -------
        None

        Raises
        ------
        Exception
            If the display command fails, an exception is raised.
        """

        if not self.display_enabled:
            return
            
        try:
            # Text kürzen (28 Zeichen max!)
            short_msg = message[:self.max_display_len]
            
            if display_type == "touchscreen":
                cmd = f'displayText "{short_msg}"'
            elif display_type == "status":
                cmd = f'displayMessage "{short_msg}"'
            else:
                return
                
            self.conn.send_and_receive(cmd, timeout=0.5)
            self.logger.debug(f"📱 {display_type}: {short_msg}")
            
        except Exception as e:
            self.logger.warning(f"Display fehlgeschlagen: {e}")

    def _clear_display(self):
        
        """
        Clears the robot's display by sending the clearText and clearStatus commands.
        
        Raises
        ------
        Exception
            If the clear command fails, an exception is raised.
        """
        try:
            self.conn.send_and_receive("clearText", timeout=0.5)
            self.conn.send_and_receive("clearStatus", timeout=0.5)
        except:
            pass

    def _get_button_state(self, button_id: str) -> Optional[bool]:
    
        """
        Retrieves the current state of a button.

        If the button state was queried within the last `state_timeout` seconds,
        the cached state is returned. Otherwise, the state is queried from the robot.

        Parameters
        ----------
        button_id : str
            The ID of the button to query

        Returns
        -------
        Optional[bool]
            The current state of the button, or None if the query failed
        """
        current_time = time.time()
        button_key = button_id
        
        if (button_key in self.button_states and 
            current_time - self.button_states[button_key]['timestamp'] < self.state_timeout):
            return self.button_states[button_key]['state']
        
        try:
            response = self.conn.send_and_receive(
                f'inputQuery {button_id}', 
                timeout=self.query_timeout
            )
            result = self._parse_input_state(response)
            state = result[1] if result else None
            
            self.button_states[button_key] = {
                'state': state,
                'timestamp': current_time
            }
            return state
            
        except Exception as e:
            self.logger.error(f"inputQuery '{button_id}' failed: {e}")
            return None

    def _clean_response(self, response: str) -> str:
        """
        Cleans the response from the robot by filtering out unnecessary lines.

        Given a response string from the robot, this function filters out all lines
        except the last line that starts with "Input:" and does not start with
        "InputList:".

        Parameters
        ----------
        response : str
            The response string from the robot

        Returns
        -------
        str
            The cleaned response string
        """
        lines = response.split('\n')
        input_lines = [line for line in lines 
                      if line.strip().startswith('Input:') and not line.strip().startswith('InputList:')]
        return input_lines[-1] if input_lines else response

    def _parse_input_state(self, response: str) -> Optional[Tuple[str, bool]]:
        """
        Parses the given response string to extract the input alias and its state.

        The response string is cleaned by filtering out unnecessary lines and then
        matched against a regex pattern that extracts the input alias and its state.

        If a match is found, the function returns a tuple containing the input alias
        and its state as a boolean. Otherwise, it returns None.

        Parameters
        ----------
        response : str
            The response string from the robot

        Returns
        -------
        Optional[Tuple[str, bool]]
            A tuple containing the input alias and its state, or None if the parsing failed
        """
        clean_resp = self._clean_response(response)
        match = self.input_pattern.search(clean_resp)
        
        if match:
            alias = match.group(1).strip()
            state_str = match.group(2).strip().lower()
            state = state_str in ('on', 'true', '1')
            return (alias, state)
        return None

    def _get_input_list(self) -> list:
        """
        Sends an "inputList" command to the robot and parses the response to
        extract a list of input aliases.

        The function filters out generic input aliases (e.g. i1, i2, ...)
        and returns an empty list if the command fails.

        :return: A list of input aliases
        :rtype: list
        """
        try:
            response = self.conn.send_and_receive("inputList", timeout=2.0)
            inputs = []
            for match in self.inputlist_pattern.finditer(response):
                alias = match.group(1).strip()
                if self.generic_pattern.match(alias):
                    continue
                if alias not in inputs:
                    inputs.append(alias)
            return inputs
        except:
            return []

    def run(self, task_cfg: dict) -> bool:
        
        """
        Executes a confirm button task according to the given configuration.

        The task will wait for the button to be pressed and then confirm the press
        after a debouncing period. If the button is not pressed within the specified
        timeout period, the task will fail.

        The task will display a wait message on the touchscreen and show the button
        name. When the button is pressed, it will show a success message and wait
        for 2 seconds before clearing the display.

        Parameters
        ----------
        task_cfg : dict
            The configuration for the task

        Returns
        -------
        bool
            A boolean indicating if the task was successful
        """
            
        button_id = task_cfg.get("button_id")
        prompt = task_cfg.get("prompt", "")
        timeout = task_cfg.get("timeout", 120)
        
        # Validierung
        if not button_id:
            self.ui.print_error("❌ button_id fehlt!")
            self._display_text("FEHLER: button_id", "status")
            return False
        
        # 📱 DISPLAY START
        self._clear_display()
        wait_msg = f"Warte {button_id}"
        self._display_text(wait_msg, "touchscreen")
        self._display_text("Drueck Button", "status")
        
        # Terminal + Display
        if prompt:
            self.ui.print_info(prompt)
        self.ui.print_info(f"⌛ Warte '{button_id}' ({timeout}s)")
        
        # Input prüfen
        available = self._get_input_list()
        if button_id not in available:
            error_msg = f"'{button_id}' nicht verfügbar"
            self.ui.print_error(error_msg)
            self._display_text("Button Fehler", "touchscreen")
            return False
        
        # 🏁 FLANKEN-ERKENNUNG
        start_time = time.time()
        initial_state = self._get_button_state(button_id)
        elapsed = 0
        
        while time.time() - start_time < timeout:
            current_state = self._get_button_state(button_id)
            elapsed = time.time() - start_time
            current_time = time.time()
            
            if current_state is None:
                time.sleep(0.1)
                continue
            
            # 🔄 Live-Status auf Display
            status_msg = f"Warte...{int(elapsed)}s"
            self._display_text(status_msg, "touchscreen")
            
            # 🚀 FLANKE False→True?
            if (initial_state == False and current_state == True and 
                button_id not in self.flank_detected):
                
                self.flank_detected[button_id] = {
                    'timestamp': current_time,
                    'confirmed': False
                }
                self._display_text("Button erkannt!", "status")
            
            # ✅ Bestätigt nach Debounce?
            elif (button_id in self.flank_detected and 
                  current_time - self.flank_detected[button_id]['timestamp'] >= self.debounce_window):
                
                self.ui.print_success(f"✅ '{button_id}' gedrückt! ({elapsed:.1f}s)")
                self._display_text("ERFOLG!", "touchscreen")
                self._display_text("✓ Bestätigung OK", "status")
                
                # 2s Anzeige → Clear
                time.sleep(2)
                self._clear_display()
                
                # Cleanup
                if button_id in self.flank_detected:
                    del self.flank_detected[button_id]
                return True
            
            # 🧹 Flanke Timeout
            elif (button_id in self.flank_detected and 
                  current_time - self.flank_detected[button_id]['timestamp'] > self.state_timeout):
                del self.flank_detected[button_id]
            
            initial_state = current_state
            time.sleep(self.poll_interval)
        
        # ⏰ TIMEOUT
        self.ui.print_error(f"⏰ Timeout '{button_id}' nach {timeout}s")
        self._display_text("TIMEOUT!", "touchscreen")
        self._display_text("Button nicht!", "status")
        time.sleep(3)
        self._clear_display()
        return False
