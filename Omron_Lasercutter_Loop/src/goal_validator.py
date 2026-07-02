

from typing import Tuple, List, Dict, Optional
import re
import time
from src.rich_ui import RobotUI


class GoalValidator:

    
    def __init__(self, connection, config: Dict = None):
        """
        Initialises the GoalValidator instance with the given configuration.

        :param connection: The established ARCL connection.
        :param config: The configuration dictionary containing the necessary ARCL connection and goal validation settings.
        :type config: Dict
        """

        self.connection = connection
        self.config = config or {}
        self.ui = RobotUI()
        
        # Config laden
        self.gv_config = self.config.get('goal_validator', {})
        self.cmd_config = self.gv_config.get('commands', {})
        self.parse_config = self.gv_config.get('parsing', {})
        self.timeout_config = self.gv_config.get('timeouts', {})
        self.validation_config = self.gv_config.get('validation', {})
        self.messages = self.gv_config.get('messages', {})
        self.debug_config = self.gv_config.get('debug', {})
        
        # Regex Patterns kompilieren
        self.goal_patterns = [
            re.compile(self.parse_config.get('goal_patterns', {}).get('primary', r'^\s*Goal:\s+(\S+)'), re.IGNORECASE | re.MULTILINE),
            re.compile(self.parse_config.get('goal_patterns', {}).get('fallback', r'Goal:(\S+)'), re.IGNORECASE | re.MULTILINE)
        ]
        
        self.dock_prefixes = self.parse_config.get('dock_patterns', {}).get('dock_prefix', ['Dock:', 'dock '])
        self.exclude_phrases = self.parse_config.get('exclude_phrases', []) + ['End of goals']
        
        self.available_goals = []
        self.available_docks = []

    def fetch_available_goals(self) -> List[str]:
        
        """
        Fetches the available goals from the robot using the 'getGoals' command.
        If no goals are found, it will attempt to fetch them using the 'getGoalsFallback' command.
        If both attempts fail, it will return an empty list and print an error message.
        The function will also print the fetched goals and their count.
        :return: A list of available goal names.
        :rtype: List[str]
        """
        self.ui.print_info(self.messages.get('fetching_goals', 'Fetching goals...'))
        
        max_retries = self.timeout_config.get('max_retries', 3)
        for attempt in range(max_retries):
            try:
                cmd = self.cmd_config.get('goals', 'getGoals')
                response = self.connection.send_and_receive(cmd, timeout=self.timeout_config.get('command_timeout', 5.0))
                
                goals = self._parse_goals(response)
                
                if goals:
                    self.available_goals = sorted(set(goals))
                    self.ui.print_success(self.messages['goals_found'].format(count=len(self.available_goals)))
                    for goal in self.available_goals:
                        self.ui.print_info(f"  • {goal}")
                    return self.available_goals
                else:
                    self.ui.print_warning(self.messages.get('no_goals', 'Fallback parsing...'))
                    
            except Exception as e:
                self.ui.print_error(f"Attempt {attempt+1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(self.timeout_config.get('retry_delay', 1.0))
        
        self.ui.print_error("Failed to fetch goals after all retries")
        return []

    def fetch_available_docks(self) -> List[str]:
        
        """
        Fetches the available docks from the robot using the 'mapObjectList dock' command.
        If no docks are found, it will use the fallback dock specified in the validation config.
        The function will also print the fetched docks and their count.
        :return: A list of available dock names.
        :rtype: List[str]
        """
        self.ui.print_info(self.messages.get('fetching_docks', 'Fetching docks...'))
        
        try:
            cmd = self.cmd_config.get('docks', 'mapObjectList dock')
            response = self.connection.send_and_receive(cmd, timeout=self.timeout_config.get('command_timeout', 5.0))
            
            docks = self._parse_docks(response)
            
            # Fallback wenn leer
            if not docks:
                fallback = self.validation_config.get('fallback_dock', 'dock')
                docks = [fallback]
                msg = self.messages.get('fallback_used', 'Using fallback')
                self.ui.print_info(msg.format(fallback=fallback, type='dock'))
            
            self.available_docks = sorted(set(docks))
            
            if self.available_docks:
                self.ui.print_success(self.messages['docks_found'].format(count=len(self.available_docks)))
                for dock in self.available_docks:
                    self.ui.print_info(f"  • {dock}")
            else:
                self.ui.print_warning(self.messages.get('no_docks', 'No docks found'))
            
            return self.available_docks
            
        except Exception as e:
            self.ui.print_error(f"Docks fetch failed: {e}")
            self.available_docks = [self.validation_config.get('fallback_dock', 'dock')]
            return self.available_docks

    def _parse_goals(self, response: str) -> List[str]:
        
        """
        Parses the available goals from the robot's response to the 'mapObjectList goal' command.
        It will exclude goals that contain any of the phrases in the `exclude_phrases` attribute.
        It will also use regex patterns from the `goal_patterns` attribute to extract the goal name.
        :param response: The response from the robot to the 'mapObjectList goal' command.
        :type response: str
        :return: A list of available goal names.
        :rtype: List[str]
        """
        goals = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Exclude-Check
            if any(exclude in line for exclude in self.exclude_phrases):
                continue
                
            # Pattern-Matching
            for pattern in self.goal_patterns:
                match = pattern.search(line)
                if match:
                    goal_name = match.group(1).strip()
                    if goal_name and goal_name not in goals:
                        goals.append(goal_name)
                    break
        
        return goals

    def _parse_docks(self, response: str) -> List[str]:
        
        """
        Parses the available docks from the robot's response to the 'mapObjectList dock' command.
        It will exclude docks that contain any of the phrases in the `exclude` attribute.
        It will also use the dock prefixes from the `dock_prefixes` attribute to extract the dock name.
        :param response: The response from the robot to the 'mapObjectList dock' command.
        :type response: str
        :return: A list of available dock names.
        :rtype: List[str]
        """
        docks = []
        exclude = self.parse_config.get('dock_patterns', {}).get('exclude', [])
        
        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            for prefix in self.dock_prefixes:
                if line.startswith(prefix):
                    if prefix == 'Dock:':
                        dock_name = line.replace('Dock:', '').strip()
                    else:
                        dock_name = line.split(prefix, 1)[1].strip()
                    
                    if dock_name and dock_name not in exclude and dock_name not in docks:
                        docks.append(dock_name)
                    break
        
        return docks

    def validate_goal_or_dock(self, name: str) -> Tuple[bool, str]:
        
        """
        Validates if a given name is a goal or a dock.
        :param name: The name to validate.
        :return: A tuple containing a boolean indicating if the name is valid and a string indicating if the name is a goal or a dock.
        :rtype: Tuple[bool, str]
        """
        if name in self.available_goals:
            return (True, "goal")
        if name in self.available_docks:
            return (True, "dock")
        return (False, "unknown")

    def validate_route_config(self, route_config: dict, goal_mapping: dict) -> bool:
        
        """
        Validates if a given route configuration is valid.
        
        It fetches all available goals and docks from the robot, and then checks if all targets in the route configuration exist.
        If any target is missing, it will print an error message.
        
        Additionally, it can be configured to show all available targets on error, and to validate the steps in the route configuration.
        
        :param route_config: The route configuration to validate.
        :type route_config: dict
        :param goal_mapping: A dictionary mapping logical goal names to physical goal names.
        :type goal_mapping: dict
        :return: A boolean indicating if the route configuration is valid.
        :rtype: bool
        """
        self.ui.print_header(self.messages.get('validation_header', 'Goal Validation'))
        
        # Fetch alle Ziele
        self.fetch_available_goals()
        self.fetch_available_docks()
        
        msg = self.messages.get('summary', 'Robot has {goals_count} goals and {docks_count} docks')
        self.ui.print_info(msg.format(
            goals_count=len(self.available_goals),
            docks_count=len(self.available_docks)
        ))
        
        # Sammle verwendete Ziele
        used_targets = set()
        for step in route_config.get('steps', []):
            if 'goto' in step:
                logical_name = step['goto']
                physical_name = goal_mapping.get(logical_name)
                if physical_name:
                    used_targets.add(physical_name)
        
        # Validiere Ziele
        all_valid = True
        for target in sorted(used_targets):
            exists, target_type = self.validate_goal_or_dock(target)
            
            if exists:
                msg = self.messages.get('goal_exists', "✓ '{target}' found ({type})")
                self.ui.print_success(msg.format(target=target, type=target_type))
            else:
                msg = self.messages.get('goal_missing', "✗ '{target}' missing!")
                self.ui.print_error(msg.format(target=target))
                all_valid = False
                
                # Verfügbare zeigen (Config-gesteuert)
                if self.validation_config.get('show_available_on_error', True):
                    self._show_available()
        
        # Schritte validieren (Config-gesteuert)
        if self.validation_config.get('validate_steps', True):
            all_valid = all_valid and self._validate_steps(route_config, goal_mapping)
        
        return all_valid

    def _validate_steps(self, route_config: dict, goal_mapping: dict) -> bool:
       
        """
        Validates all steps in the given route configuration against the goal mapping.
        
        :param route_config: Route configuration dictionary
        :param goal_mapping: Goal mapping dictionary
        :return: True if all steps are valid, False otherwise
        """
        all_valid = True
        for idx, step in enumerate(route_config.get('steps', []), start=1):
            if 'goto' not in step:
                continue
                
            logical_name = step['goto']
            physical_name = goal_mapping.get(logical_name)
            
            if not physical_name:
                msg = self.messages.get('step_missing_mapping', "✗ Step {step}: '{logical}' no mapping!")
                self.ui.print_error(msg.format(step=idx, logical=logical_name))
                all_valid = False
                continue
            
            exists, target_type = self.validate_goal_or_dock(physical_name)
            if exists:
                msg = self.messages.get('step_exists', "✓ Step {step}: '{physical}' found ({type})")
                self.ui.print_success(msg.format(step=idx, physical=physical_name, type=target_type))
            else:
                msg = self.messages.get('step_missing_goal', "✗ Step {step}: '{physical}' NOT found!")
                self.ui.print_error(msg.format(step=idx, physical=physical_name))
                all_valid = False
        
        return all_valid

    def _show_available(self):
        
        """
        Prints all available goals and docks to the console.
        """
        
        self.ui.print_info("Verfügbare Goals:")
        for goal in self.available_goals:
            self.ui.print_info(f"  • {goal}")
        
        if self.available_docks:
            self.ui.print_info("Verfügbare Docks:")
            for dock in self.available_docks:
                self.ui.print_info(f"  • {dock}")

    def debug_raw_response(self):
        
        """
        Prints the raw response of the 'getGoals' and 'mapObjectList dock' commands to the console.
        Useful for debugging purposes.
        """
        if not self.debug_config.get('show_raw_response', False):
            return
            
        # Goals Debug
        self.ui.print_header("DEBUG: Raw getGoals Response")
        try:
            response = self.connection.send_and_receive(
                self.cmd_config.get('goals', 'getGoals'), 
                timeout=self.timeout_config.get('command_timeout', 5.0)
            )
            self._debug_response("GOALS", response)
        except Exception as e:
            self.ui.print_error(f"Goals debug failed: {e}")
        
        # Docks Debug
        self.ui.print_header("DEBUG: Raw Docks Response")
        try:
            response = self.connection.send_and_receive(
                self.cmd_config.get('docks', 'mapObjectList dock'),
                timeout=self.timeout_config.get('command_timeout', 5.0)
            )
            self._debug_response("DOCKS", response)
        except Exception as e:
            self.ui.print_error(f"Docks debug failed: {e}")

    def _debug_response(self, title: str, response: str):
        
        """
        Prints debug information for the given title and response.
        
        :param title: Title of the debug information
        :param response: Response string to be printed
        """
        
        self.ui.print_info(f"Länge: {len(response)} Zeichen")
        self.ui.print_info(f"Zeilen: {len(response.splitlines())} Zeilen")
        
        print("\n" + "="*60)
        print(title.upper() + ":")
        print("="*60)
        print(response)
        print("="*60)
        
        if self.debug_config.get('show_hex_dump', False):
            max_bytes = self.debug_config.get('max_hex_bytes', 200)
            hex_data = response[:max_bytes].encode('utf-8').hex()
            print("\nHEX-DUMP (first {} bytes):".format(max_bytes))
            for i in range(0, len(hex_data), 32):
                print(hex_data[i:i+32])
