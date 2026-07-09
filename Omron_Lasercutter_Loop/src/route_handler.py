"""
Route Executor - EMERGENCY DOCK → SYS.EXIT(0)
"""

import sys  # ← WICHTIG!
import time
from typing import Dict
from src.rich_ui import RobotUI
from src.enhanced_logger import RouteLogger
from src.I_O_handler import ConfirmButtonTask


class RouteExecutor:
    def __init__(self, connection, config: dict):
        """
        Initialises the RouteExecutor instance with the given configuration.

        :param connection: The established ARCL connection.
        :param config: The configuration dictionary containing the necessary ARCL connection and route executor settings.
        :type config: Dict
        """
        
        self.connection = connection
        self.config = config
        self.ui = RobotUI()
        self.goal_mapping = config['goals']
        
        # Route Executor Config laden
        self.re_config = config.get('route_executor', {})
        self.nav_config = self.re_config.get('navigation', {})
        self.dock_config = self.re_config.get('dock', {})
        self.door_config = self.re_config.get('door_check', {})
        self.voice_config = self.re_config.get('voice', {})
        self.status_config = self.re_config.get('status_parsers', {})
        self.reset_commands = self.re_config.get('reset_commands', [])
        self.macro_config = self.re_config.get('macros', {})
        
        # Logger initialisieren
        self.logger = RouteLogger(log_dir=config.get('logging', {}).get('directory', "logs"))
        self.logger.set_route_info(
            route_name=config['route']['name'],
            robot_config=config['robot']
        )
        
        self.step_executor = StepExecutor(
            executor=self, connection=self.connection, config=self.config,
            ui=self.ui, confirm_button_task=ConfirmButtonTask(self.connection, self.ui, config)
        )
        # FALLBACK: Letztes Ziel merken
        self._current_target_goal = None  # Logical name (lasercutter/nacharbeit)

    def execute_route(self) -> bool:

        """
        Executes the given route and logs the result.

        :return: True if the route was executed successfully, False otherwise.
        """
        route = self.config['route']
        steps = route['steps']

        self.ui.print_info(f"Starte Route: {route['name']}")
        self.ui.print_info(f"Schritte: {len(steps)}\n")

        start_status = self._get_status()
        self.logger.log_status_snapshot(start_status, "Start-Status")

        success_count = 0
        for idx, step in enumerate(steps, start=1):
            step_desc = step.get('description', f'Schritt {idx}')
            action = 'goto' if 'goto' in step else step.get('action', 'unknown')
            goal = self.goal_mapping.get(step.get('goto')) if 'goto' in step else None

            self.logger.log_step_start(idx, step_desc, action, goal)
            self.ui.print_info(f"Schritt {idx}/{len(steps)}: {step_desc}")

            step_success = self.step_executor.execute(step, idx)
            self.logger.log_step_end(idx, step_success)

            if step_success:
                            success_count += 1
                            self.ui.print_success(f"✓ Schritt {idx} erfolgreich\n")
                            if idx == len(steps):
                                self.logger.log_status_snapshot(self._get_status(), f"Nach Schritt {idx}")
                            else:
                                self.ui.print_error(f"✗ Schritt {idx} fehlgeschlagen!\n")
                                self.logger.log_status_snapshot(self._get_status(), f"Fehler nach Schritt {idx}")
                            
                            # 🚨 EMERGENCY CHECK → DOCK & RETURN TO STANDBY (KEIN SYS.EXIT!)
                            if self._should_emergency_dock():
                                
                                dock_success = self._emergency_dock()
                                self.logger.finalize(dock_success)
                                
                                if dock_success:
                                    self.ui.print_success("✅ Emergency Dock OK!")
                                    self.ui.print_info("💤 Robot parked on dock. Returning to standby.")
                                else:
                                    self.ui.print_error("❌ Emergency Dock failed!")
                                
                                return False  # Übergibt Kontrolle zurück an die Endlosschleife in main.py
                            
                            # Normale Fehlerbehandlung
                            if not self.config.get('execution', {}).get('continue_on_error', False):
                                self.ui.print_warning("⚠ Route abgebrochen (kein Emergency)")
                                break

        route_success = success_count == len(steps)
        self.logger.finalize(route_success)
        return route_success
    
    def _should_emergency_dock(self) -> bool:

        """Returns True if the robot should emergency dock, False otherwise.

        The robot should emergency dock if the battery voltage is below the configured threshold.
        Additionally, the emergency return feature can be enabled to force the robot to return to the dock when the battery is critical.
        """

        safety = self.config.get('safety', {})
        
        # Nur noch auf konfiguriertes "emergency_return" reagieren
        emergency_return = safety.get('emergency_return', {}).get('enabled', False)
        
        if emergency_return:
            self.ui.print_warning("⚠ Manueller Emergency-Return aktiviert!")
            return True

        return False
    def _emergency_dock(self) -> bool:
        
        """
        Executes an emergency dock command to return the robot to the dock.

        If the dock is not enabled, it will print an error message and return False.
        If the status query is enabled, it will attempt to fetch the status of the dock.
        If the dock command fails, it will print an error message and return False.
        If the robot is not docked within the specified timeout, it will print a warning message and return True.
        If the robot is successfully docked, it will print a success message and return True.
        :return: A boolean indicating if the emergency dock was successful
        :rtype: bool
        """
        if not self.dock_config.get('enabled', True):
            self.ui.print_error("Dock deaktiviert → Emergency fehlgeschlagen!")
            return False

        self.ui.print_info("🚪 Fahre zur Ladestation...")
        self.ui.print_info(self.voice_config['dock']['emergency'])

        # Dock-Befehl direkt senden
        cmd = self.dock_config['command']
        try:
            response = self.connection.send_and_receive(cmd, timeout=5.0)
            self.ui.print_success("✅ Dock-Befehl gesendet!")
        except Exception as e:
            self.ui.print_error(f"❌ Dock-Befehl fehlgeschlagen: {e}")
            return False

        # Warte auf Docking (MAX 2 Minuten)
        if self.dock_config.get('auto_charge', True):
            dock_timeout = self.dock_config.get('emergency_timeout', 600)
            if self._wait_for_dock(dock_timeout):
                self.ui.print_success("🔌 Erfolgreich gedockt & lädt!")
                return True

        self.ui.print_warning("⚠ Docking-Timeout, aber Befehl gesendet")
        return True  # Erfolgreich auch bei Timeout
    


    def _dock(self) -> bool:
        
        """
        Executes a dock command to dock the robot.

        If the dock is not enabled, it will print a warning message and return True.
        If the dock command fails, it will print an error message and return False.
        If the robot is not docked within the specified timeout, it will print a warning message and return True.
        If the robot is successfully docked, it will print a success message and return True.
        :return: A boolean indicating if the dock was successful
        :rtype: bool
        """
        self.ui.print_info(self.voice_config['dock']['starting'])
        
        if not self.dock_config.get('enabled', True):
            self.ui.print_warning("Dock deaktiviert")
            return True

        cmd = self.dock_config.get('command', 'dock')
        response = self.connection.send_and_receive(cmd, timeout=self.nav_config.get('goto_timeout', 2.0))
        
        if any(err in response.lower() for err in self.status_config['dock_indicators']['error']):
            self.ui.print_error(f"Dock-Fehler: {response.strip()}")
            return False
            
        return self._wait_for_dock(self.dock_config.get('timeout', 60))

    def _wait_for_dock(self, timeout: int) -> bool:
        
        """
        Waits for the robot to dock within the specified timeout period.
        
        It will query the robot's status every 2 seconds and check if the docking
        state is either successful or an error. If the docking state is successful,
        it will print a success message and return True. If the docking state is an error,
        it will print a warning message and return True. If the timeout period is exceeded
        without the robot docking, it will print a warning message and return True.
        :param timeout: The timeout period in seconds
        :type timeout: int
        :return: A boolean indicating if the robot was successfully docked
        :rtype: bool
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self._get_status()
            docking_state = status.get('DockingState', '').lower()
            
            if any(ind in docking_state for ind in self.status_config['dock_indicators']['success']):
                self.ui.print_success(self.voice_config['dock']['success'])
                return True
                
            if any(ind in docking_state for ind in self.status_config['dock_indicators']['error']):
                self.ui.print_warning("Docking fehlgeschlagen, aber nicht kritisch")
                return True
                
            time.sleep(self.dock_config.get('check_interval', 2.0))
        
        self.ui.print_warning(self.voice_config['dock']['timeout'])
        return True

    def _navigate_to_goal(self, goal_name: str, wait_after: int = None) -> bool:
        
        """
        Navigates to a given goal using the 'goto' command.
        
        It will first check if the goal already exists and if so, it will print a success message and return True.
        If the goal does not exist, it will print an error message and return False.
        If the goal exists, it will send the 'goto' command to the robot and wait for the robot to arrive at the goal.
        If the robot arrives at the goal, it will print a success message and return True.
        If the robot does not arrive at the goal within the specified timeout period, it will print an error message and return False.
        
        :param goal_name: The name of the goal to navigate to
        :param wait_after: The time to wait after arriving at the goal
        :type goal_name: str
        :type wait_after: int
        :return: A boolean indicating if the navigation to the goal was successful
        :rtype: bool
        """
        self.ui.print_info(f"→ {goal_name}")
        wait_after = wait_after or self.nav_config.get('wait_after_arrival_default', 0)
        
        # Dock-Spezialfall
        if goal_name.lower() == "dock":
            return self._dock()

        status = self._get_status()
        if self._is_at_goal(status, goal_name.lower()):
            self.ui.print_info(self.voice_config['navigation']['already_there'])
            time.sleep(wait_after)
            return True

        #  MERKE AKTUELLES ZIEL für Fallback
        self._current_target_goal = goal_name

        # goto ausführen
        response = self.connection.send_and_receive(
            f"goto {goal_name}", 
            timeout=self.nav_config.get('goto_timeout', 2.0)
        )
        
        if "does not exist" in response.lower():
            self.ui.print_error(f"Goal {goal_name} existiert nicht!")
            return False

        # Auf Ankunft warten
        timeout = self.nav_config.get('timeout', 90)
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self._get_status()
            state_lower = status.get("ExtendedStatusForHumans", "").lower()
            status_lower = status.get("Status", "").lower()

            # Erfolg?
            if any(ind in status_lower or ind in state_lower 
                   for ind in self.status_config['success_indicators']):
                self.ui.print_success("✓ Angekommen")
                time.sleep(wait_after)
                self._current_target_goal = None  # Ziel erreicht → Reset
                return True

            # Fehler?
            # Fallback-Trigger: "Failed going to Path"
            if any(ind in status_lower or ind in state_lower 
                   for ind in ['failed going to path', 'failed going to goal']):
                
                self.ui.print_warning(f"⚠ PATH FEHLER für {goal_name} → RETRY Fallback!")
                
                # 🔄 1. Reset-Commands (stoppen/stornieren)
                for reset_cmd in self.reset_commands:
                    try:
                        self.connection.send_and_receive(reset_cmd, timeout=1.0)
                    except:
                        pass
                
                # 🔄 2. ZURÜCK ZUM GESPEICHERTEN ZIEL
                if self._current_target_goal:
                    self.ui.print_info(f"🔄 Retry: {self._current_target_goal}")
                    time.sleep(1.0)  # Pause nach Reset

                    return self._navigate_to_goal(self._current_target_goal, wait_after)
                
                return False
            
            if any(ind in status_lower or ind in state_lower 
                   for ind in self.status_config['error_indicators']):
                self.ui.print_error(self.voice_config['navigation']['failed'])
                
                # Tür-Logik für Nacharbeit
                if "nacharbeit" in goal_name.lower():
                    door_step = {
                        "door_goal": self.door_config.get('makerspace_outside_goal', 'makerspace_outside'),
                        "direction": "inside_to_outside",
                        "timeout": self.door_config['navigation_timeout']
                    }
                    if self._check_door(door_step):
                        return self._navigate_to_goal(goal_name, wait_after)
                return False

            time.sleep(self.nav_config.get('check_interval', 0.4))

        self.ui.print_error(f"{self.voice_config['navigation']['timeout']} {timeout}s")
        return False

    def _check_door(self, step: dict) -> bool:
        
        """
        Checks if a door goal exists and if so, attempts to navigate to the door goal
        until it is successfully opened or the maximum number of retries is exceeded.
        
        :param step: The door step configuration dictionary
        :return: A boolean indicating if the door was successfully opened
        :rtype: bool
        """
        
        door_goal = self.goal_mapping.get(step.get("door_goal"))
        if not door_goal:
            self.ui.print_error(f"Tür-Goal '{step.get('door_goal')}' nicht gefunden!")
            return False

        max_retries = self.door_config.get('max_retries', 10)
        for attempt in range(max_retries):
            if self._door_attempt(door_goal, step.get('timeout', 20)):
                return True
            self._handle_closed_door(step.get('direction', 'outside_to_inside'))
            time.sleep(self.door_config.get('retry_delay', 1.0))
        return False

    def _door_attempt(self, door_goal: str, timeout: int) -> bool:
        
        """
        Attempts to navigate to a given door goal until it is successfully opened or the maximum number of retries is exceeded.
        
        It will send the 'goto' command to the robot with the given door goal and wait for the robot to arrive at the goal.
        If the robot arrives at the goal, it will print a success message and return True.
        If the robot does not arrive at the goal within the specified timeout period, it will print an error message and return False.
        
        :param door_goal: The name of the door goal to navigate to
        :type door_goal: str
        :param timeout: The time to wait for the robot to arrive at the door goal
        :type timeout: int
        :return: A boolean indicating if the navigation to the door goal was successful
        :rtype: bool
        """
        response = self.connection.send_and_receive(f"goto {door_goal}", timeout=2.0)
        if "cannot find path" in response.lower():
            return False
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self._get_status()
            if any(ind in status.get("Status", "").lower() 
                   for ind in self.status_config['success_indicators']):
                self.ui.print_success(self.voice_config['door']['open'])
                return True
            time.sleep(0.7)
        return False

    def _handle_closed_door(self, direction: str) -> None:
        
        """
        Handles a closed door by printing a warning message and announcing it to the user via speech output.
        
        It will use the given direction to select the appropriate warning message from the voice configuration.
        If the direction is not found in the voice configuration, it will use the default message for the outside_to_inside direction.
        After announcing the warning, it will wait for the specified door wait time before continuing.
        
        :param direction: The direction of the door (outside_to_inside or inside_to_outside)
        :type direction: str
        """
        texts = self.voice_config.get('door_closed', {})
        text = texts.get(direction, texts.get('outside_to_inside', 'Tür öffnen'))
        self.ui.print_warning(self.voice_config['door']['blocked'])
        self._say(text)
        time.sleep(self.door_config.get('door_wait_time', 5))

    def _say(self, text: str) -> None:
        
        """
        Attempts to say the given text via the robot's speech output.

        If the say command fails, it will simply ignore the error and continue.
        :param text: The text to be spoken
        :type text: str
        :rtype: None
        """
        try:
            self.connection.send_and_receive(f'say "{text}"', timeout=1.0)
        except:
            pass

    def _get_status(self) -> Dict:
        
        """
        Retrieves the current status of the robot as a dictionary.

        The status is queried by sending the 'status' command to the robot.
        The response is then parsed into a dictionary where each key is a
        parameter name and the value is the parameter value.

        If the query fails, an empty dictionary is returned.

        :return: The current status of the robot as a dictionary
        :rtype: Dict
        """
        try:
            response = self.connection.send_and_receive("status", timeout=1.5)
            status = {}
            for line in response.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    status[key.strip()] = value.strip()
            return status
        except:
            return {}

    def _is_at_goal(self, status: Dict, goal_lower: str) -> bool:
        """
        Checks if the robot is at the given goal.

        It checks the "Status" and "ExtendedStatusForHumans" parameters in the robot's status
        for the keywords "arrived" and "done driving" respectively. If any of these keywords
        are found and the goal name is in the status, it returns True.

        :param status: The current status of the robot as a dictionary
        :type status: Dict
        :param goal_lower: The goal name to check for, in lowercase
        :type goal_lower: str
        :return: A boolean indicating if the robot is at the goal
        :rtype: bool
        """
        ext = status.get("ExtendedStatusForHumans", "").lower()
        stat = status.get("Status", "").lower()
        return (("arrived" in stat or "done driving" in ext) and goal_lower in stat)


class StepExecutor:
    def __init__(self, executor, connection, config, ui: RobotUI, confirm_button_task):
        """
        Initialises the StepExecutor instance with the given configuration.

        :param executor: The RouteExecutor instance.
        :param connection: The established ARCL connection.
        :param config: The configuration dictionary containing the necessary ARCL connection and route executor settings.
        :param ui: The RobotUI instance.
        :param confirm_button_task: The ConfirmButtonTask instance.
        :type confirm_button_task: ConfirmButtonTask
        """
        self.executor = executor
        self.connection = connection
        self.config = config
        self.ui = ui
        self.goal_mapping = config["goals"]
        self.confirm_button_task = confirm_button_task

        self.handlers = {
            "goto": self._handle_goto,
            "wait": self._handle_wait,
            "action": self._handle_action,
            "task": self._handle_task,
        }

    def execute(self, step: dict, step_num: int) -> bool:
        
        
        # Dock-Spezialfall
        """
        Executes a step according to the given configuration.

        This method will try to execute the given step by looking for specific keys
        in the step configuration. If a key is found, the corresponding handler
        method will be called. If no known key is found, an error message
        will be displayed.

        Parameters
        ----------
        step : dict
            The configuration for the step
        step_num : int
            The number of the step

        Returns
        -------
        bool
            A boolean indicating if the step was executed successfully
        """

        if "goto" in step and step["goto"].lower() == "dock":
            return self.executor._dock()
        
        # PRIORISIERT nach vorhandenen Keys (wie ursprüngliche Config!)
        if "goto" in step:
            return self._handle_goto(step)
        if "task" in step:
            return self._handle_task(step)
        if "action" in step:
            return self._handle_action(step)
        if "wait" in step:
            return self._handle_wait(step)
        
        # Fehlerfall
        self.ui.print_error(f"✗ Schritt {step_num}: Unbekannter Typ! Keys: {list(step.keys())}")
        self.ui.print_info(f"  Step-Content: {step}")
        return False

    def _handle_goto(self, step: dict) -> bool:
        
        """
        Handles a 'goto' step.

        This method will try to navigate the robot to the goal specified by the logical name.
        If the goal is not found in the goal mapping, an error message will be printed.

        Parameters
        ----------
        step : dict
            The configuration for the step

        Returns
        -------
        bool
            A boolean indicating if the step was executed successfully
        """
        logical_name = step['goto']
        physical_name = self.goal_mapping.get(logical_name)
        
        if not physical_name:
            self.ui.print_error(f"✗ Goal '{logical_name}' nicht gefunden!")
            return False

        wait_after = step.get('wait', 0)
        success = self.executor._navigate_to_goal(physical_name, wait_after)
        
        # ✅ KORREKT: Sprachausgabe nach Ankunft
        if success:
            voice_cfg = self.executor.voice_config
            voice_key = f"{logical_name}_arrived"
            
            if voice_key in voice_cfg:
                self.executor._say(voice_cfg[voice_key])
                self.ui.print_info(f"💬 Gesagt: {voice_cfg[voice_key][:50]}...")
            elif 'lasercutter' in logical_name:
                self.executor._say(voice_cfg.get('lasercutter_arrived', ''))
            elif 'nacharbeit' in logical_name:
                self.executor._say(voice_cfg.get('nacharbeit_arrived', ''))
            else:
                self.ui.print_info("ℹ Keine Sprachausgabe für dieses Goal definiert")
        
        return success


    def _handle_wait(self, step: dict) -> bool:
        """
        Handles a 'wait' step.

        This method will wait for the specified duration.

        Parameters
        ----------
        step : dict
            The configuration for the step

        Returns
        -------
        bool
            A boolean indicating if the step was executed successfully
        """
        duration = step.get("duration", step.get("wait", 5))
        self.ui.print_info(f"⏳ Warte {duration}s...")
        time.sleep(duration)
        return True

    def _handle_action(self, step: dict) -> bool:
        """
        Handles an 'action' step.

        This method will check the action name and call the corresponding handler method.

        Parameters
        ----------
        step : dict
            The configuration for the step

        Returns
        -------
        bool
            A boolean indicating if the step was executed successfully
        """

        action_name = step['action']
        if action_name == 'check_door':
            return self.executor._check_door(step)
        elif action_name == 'dock':
            return self.executor._dock()
        elif action_name == 'backout_nacharbeit':
            macro_name = self.executor.macro_config.get('backout_nacharbeit', 'BackoutNacharbeit')
            return self.executor._run_macro(macro_name)
        elif action_name == 'wait':
            return self.executor._wait(step.get('duration', 5))
        else:
            self.ui.print_warning(f"⚠ Unbekannte Action: {action_name}")
            return False

    def _handle_task(self, step: dict) -> bool:
        
        """
        Handles a 'task' step.

        This method will check the task name and call the corresponding handler method.

        Parameters
        ----------
        step : dict
            The configuration for the step

        Returns
        -------
        bool
            A boolean indicating if the step was executed successfully
        """
        task_name = step["task"]
        tasks_cfg = self.config.get("tasks", {})
        
        if task_name not in tasks_cfg:
            self.ui.print_error(f"✗ Task '{task_name}' nicht definiert!")
            return False
        
        task_cfg = tasks_cfg[task_name]
        task_type = task_cfg.get("type", "confirm_button")
        
        if task_type == "confirm_button":
            return self.confirm_button_task.run(task_cfg)
        else:
            self.ui.print_error(f"✗ Unbekannter Task-Typ: {task_type}")
            return False
