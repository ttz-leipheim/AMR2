
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import yaml


class RouteLogger:

    
    def __init__(self, log_dir: str = "logs"):
      
        """
        Initialises the RouteLogger with a log directory.

        Parameters
        ----------
        log_dir : str, optional
            The directory where the log files will be stored. Defaults to "logs".
        """
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Timestamp für diese Session
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Log-Dateien
        self.json_log_file = self.log_dir / f"route_{self.session_id}.json"
        self.text_log_file = self.log_dir / f"route_{self.session_id}.log"
        self.yaml_log_file = self.log_dir / f"route_{self.session_id}.yaml"
        
        # Route-Daten sammeln
        self.route_data = {
            "session_id": self.session_id,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "route_name": None,
            "robot": {},
            "steps": [],
            "status_snapshots": [],
            "errors": [],
            "success": False
        }
        
        # Text-Logger konfigurieren
        self._setup_text_logger()
    
    def _setup_text_logger(self):
        
        """
        Sets up the text logger with a file handler and a formatter.
        
        Creates a logger with the name "route_<session_id>" and sets its level to DEBUG.
        Creates a file handler that logs to the file specified by self.text_log_file, sets its level to DEBUG.
        Creates a formatter that formats the log messages as "<timestamp> | <levelname> | <message>" and sets the date format to "%Y-%m-%d %H:%M:%S".
        Sets the formatter of the file handler and adds the file handler to the logger.
        """
        
        self.text_logger = logging.getLogger(f"route_{self.session_id}")
        self.text_logger.setLevel(logging.DEBUG)
        
        # File Handler
        fh = logging.FileHandler(self.text_log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        fh.setFormatter(formatter)
        self.text_logger.addHandler(fh)
    
    def set_route_info(self, route_name: str, robot_config: dict):
        

        """
        Sets the route information for the current session.

        :param route_name: The name of the route.
        :type route_name: str
        :param robot_config: The configuration of the robot.
        :type robot_config: dict
        """
    
        self.route_data["route_name"] = route_name
        self.route_data["robot"] = {
            "name": robot_config.get("name", "Unknown"),
            "ip": robot_config.get("ip", "Unknown"),
            "port": robot_config.get("arcl_port", 7171)
        }
        
        self.text_logger.info("=" * 80)
        self.text_logger.info(f"ROUTE: {route_name}")
        self.text_logger.info(f"ROBOTER: {self.route_data['robot']['name']} @ {self.route_data['robot']['ip']}")
        self.text_logger.info("=" * 80)
    
    def log_step_start(self, step_num: int, step_name: str, action: str, goal: str = None):
        
        """
        Logs the start of a step.

        :param step_num: The number of the step.
        :type step_num: int
        :param step_name: The name of the step.
        :type step_name: str
        :param action: The action performed in the step.
        :type action: str
        :param goal: The goal of the step, if applicable.
        :type goal: str, optional
        """
        
        step_data = {
            "step_number": step_num,
            "step_name": step_name,
            "action": action,
            "goal": goal,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "duration_seconds": None,
            "status_before": None,
            "status_after": None,
            "success": None,
            "error": None
        }
        
        self.route_data["steps"].append(step_data)
        
        self.text_logger.info("")
        self.text_logger.info(f">>> SCHRITT {step_num}: {step_name}")
        self.text_logger.info(f"    Aktion: {action}" + (f" | Ziel: {goal}" if goal else ""))
    
    def log_step_end(self, step_num: int, success: bool, error: str = None):
        
        
        """
        Logs the end of a step.

        :param step_num: The number of the step.
        :type step_num: int
        :param success: Whether the step was successful.
        :type success: bool
        :param error: The error message, if the step failed.
        :type error: str, optional
        """
        
        if step_num <= len(self.route_data["steps"]):
            step = self.route_data["steps"][step_num - 1]
            step["end_time"] = datetime.now().isoformat()
            step["success"] = success
            step["error"] = error
            
            # Berechne Dauer
            start = datetime.fromisoformat(step["start_time"])
            end = datetime.fromisoformat(step["end_time"])
            step["duration_seconds"] = (end - start).total_seconds()
            
            status = "✓ ERFOLG" if success else "✗ FEHLER"
            self.text_logger.info(f"    {status} | Dauer: {step['duration_seconds']:.1f}s")
            
            if error:
                self.text_logger.error(f"    Fehler: {error}")
                self.route_data["errors"].append({
                    "step": step_num,
                    "error": error,
                    "timestamp": datetime.now().isoformat()
                })
    
    def log_status_snapshot(self, status: Dict[str, Any], label: str = "Status"):
        
        """
        Logs a status snapshot with a label.

        Parameters
        ----------
        status : Dict[str, Any]
            The status data to log.
        label : str, optional
            The label for the status snapshot. Defaults to "Status".
        """

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "label": label,
            "status": status
        }
        
        self.route_data["status_snapshots"].append(snapshot)
        
        # Schreibe wichtige Felder ins Text-Log
        self.text_logger.info(f"    [{label}]")
        important_fields = [
            "Status", "DockingState", "StateOfCharge",
            "Location", "ExtendedStatusForHumans"
        ]
        
        for field in important_fields:
            if field in status:
                self.text_logger.info(f"      {field}: {status[field]}")
    
    def log_message(self, message: str, level: str = "INFO"):
        
        """
        Logs a message with a specified level.

        Parameters
        ----------
        message : str
            The message to log.
        level : str, optional
            The level of the message. Can be one of "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL". Defaults to "INFO".

        Notes
        -----
        The level is case-insensitive.
        If the level is not recognized, it will default to "INFO".
        """
        level_map = {
            "DEBUG": self.text_logger.debug,
            "INFO": self.text_logger.info,
            "WARNING": self.text_logger.warning,
            "ERROR": self.text_logger.error,
            "CRITICAL": self.text_logger.critical
        }
        
        log_func = level_map.get(level.upper(), self.text_logger.info)
        log_func(f"    {message}")
    
    def finalize(self, success: bool):
 
        """
        Finalizes the logging and writes out the results to a JSON and YAML log file.

        Parameters
        ----------
        success : bool
            Whether the route was completed successfully.

        Returns
        -------
        dict
            A dictionary containing information about the execution of the route, including the session ID, the paths to the log files, and whether the route was completed successfully.
        """
        self.route_data["end_time"] = datetime.now().isoformat()
        self.route_data["success"] = success
        
        # Berechne Gesamtdauer
        start = datetime.fromisoformat(self.route_data["start_time"])
        end = datetime.fromisoformat(self.route_data["end_time"])
        total_duration = (end - start).total_seconds()
        self.route_data["total_duration_seconds"] = total_duration
        
        # Statistiken
        successful_steps = sum(1 for s in self.route_data["steps"] if s.get("success") == True)
        total_steps = len(self.route_data["steps"])
        
        self.text_logger.info("")
        self.text_logger.info("=" * 80)
        self.text_logger.info(f"ROUTE ABGESCHLOSSEN: {'ERFOLGREICH' if success else 'FEHLGESCHLAGEN'}")
        self.text_logger.info(f"Schritte: {successful_steps}/{total_steps} erfolgreich")
        self.text_logger.info(f"Gesamtdauer: {total_duration:.1f}s")
        self.text_logger.info(f"Fehler: {len(self.route_data['errors'])}")
        self.text_logger.info("=" * 80)
        
        # Schreibe strukturierte Logs
        self._write_json_log()
        self._write_yaml_log()
        
        return {
            "session_id": self.session_id,
            "json_log": str(self.json_log_file),
            "text_log": str(self.text_log_file),
            "yaml_log": str(self.yaml_log_file),
            "success": success,
            "duration": total_duration
        }
    
    def _write_json_log(self):
        
        """
        Writes the route data to a JSON log file.

        This function writes the self.route_data dictionary to a JSON file
        specified by self.json_log_file. The file is overwritten and the
        JSON data is formatted with indentation of 2 spaces and ensures
        ASCII encoding.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        with open(self.json_log_file, 'w', encoding='utf-8') as f:
            json.dump(self.route_data, f, indent=2, ensure_ascii=False)
    
    def _write_yaml_log(self):
        
        """
        Writes the route data to a YAML log file.

        This function writes the self.route_data dictionary to a YAML file
        specified by self.yaml_log_file. The file is overwritten and the
        YAML data is formatted with block style and ensures ASCII encoding.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """

        with open(self.yaml_log_file, 'w', encoding='utf-8') as f:
            yaml.dump(self.route_data, f, default_flow_style=False, allow_unicode=True)
