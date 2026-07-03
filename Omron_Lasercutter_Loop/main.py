"""
OMRON LD Roboter-Steuerung - Hauptprogramm (100% Config-gesteuert)
"""

import sys
import yaml
import traceback
from pathlib import Path
from typing import Dict, Optional

from src.arcl_connection import ARCLConnection
from src.goal_validator import GoalValidator
from src.rich_ui import RobotUI
from src.mqtt_handler import (
    MQTTHandler, 
    MQTTRouteExecutor, 
    RestartCycleException, 
    DockRequestedException, 
    MqttDirectTaskException
)


def load_config(config_path: str = None) -> Dict:
    """
    Loads a configuration file from a file and returns it.
    """
    default_path = "config/robot_config.yaml"
    config_path = config_path or default_path
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        main_config = config.get('main', {})
        if 'config_path_default' in main_config.get('debug', {}):
            default_path = main_config['debug']['config_path_default']
        
        print(f"✓ Config geladen: {config_path}")
        return config
        
    except FileNotFoundError:
        print(f"❌ Config nicht gefunden: {config_path}")
        print(f"  Verwenden Sie: {default_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ YAML-Fehler: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Laden fehlgeschlagen: {e}")
        sys.exit(1)


def parse_cli_args(config: Dict) -> Dict[str, bool]:
    """
    Parses the command line arguments and returns a dictionary.
    """
    cli_config = config.get('main', {}).get('cli', {})
    args = {
        'debug_goals': False,
        'validate': False, 
        'help': False,
        'skip_validation': False
    }
    
    for arg_name, cli_args in cli_config.items():
        for cli_arg in cli_args:
            if cli_arg in sys.argv:
                args[arg_name] = True
                sys.argv.remove(cli_arg)
    
    return args


def debug_goals(config: Dict):
    """
    Debug function to analyze the available goals from the robot.
    """
    ui = RobotUI()
    messages = config.get('main', {}).get('messages', {})
    
    ui.print_header(messages.get('header', 'DEBUG: Goal-Analyse'))
    
    conn = ARCLConnection(config)
    try:
        if conn.connect():
            ui.print_success(messages.get('connection_success', '✓ Connected'))
            
            validator = GoalValidator(conn, config)
            validator.debug_raw_response()
            
            ui.print_header("Parsing-Test")
            goals = validator.fetch_available_goals()
            
            if goals:
                ui.print_success(f"\n✓ {len(goals)} Goals geparst")
            else:
                ui.print_error("\n✗ Parsing fehlgeschlagen")
        else:
            ui.print_error(messages.get('connection_failed', '✗ Connection failed'))
            
    except Exception as e:
        ui.print_error(f"Debug error: {e}")
        if config.get('main', {}).get('debug', {}).get('show_traceback', True):
            print(traceback.format_exc())
    finally:
        conn.disconnect()


def validate_config(config: Dict) -> bool:
    """
    Validates the configuration by checking target goals on the AMR.
    """
    ui = RobotUI()
    messages = config.get('main', {}).get('messages', {})
    
    ui.print_header(messages.get('validation_header', 'CONFIG VALIDATION'))
    
    conn = ARCLConnection(config)
    try:
        if not conn.connect():
            ui.print_error(messages.get('connection_failed', '✗ Connection failed'))
            return False
        
        ui.print_success(messages.get('connection_success', '✓ Connected'))
        
        goal_mapping = dict(config.get('goals', {}))
        
        validator = GoalValidator(conn, config)
        valid = validator.validate_route_config(config['route'], goal_mapping)
        
        if valid:
            ui.print_success(messages.get('validation_success', '✓✓✓ ALL CHECKS PASSED!'))
            ui.print_info("Bereit für Ausführung: python main.py")
        else:
            ui.print_error(messages.get('validation_failed', '✗ Validation failed'))
            ui.print_warning(messages.get('validation_fix_config', 'Fix config/robot_config.yaml'))
        
        return valid
        
    except Exception as e:
        ui.print_error(f"Validation error: {e}")
        if config.get('main', {}).get('debug', {}).get('show_traceback', True):
            print(traceback.format_exc())
        return False
    finally:
        conn.disconnect()


def execute_route_loop(config: Dict, conn: ARCLConnection, skip_validation: bool) -> int:
    """
    Executes the given route configuration in a loop utilizing MQTT control.
    """
    ui = RobotUI()
    main_config = config.get('main', {})
    messages = main_config.get('messages', {})
    
    route_name = config['route']['name']
    ui.print_info(messages.get('route_info', 'Route: {route_name}').format(route_name=route_name))
    
    # Validierung (Config-gesteuert)
    validation_config = config.get('validation', {})
    force_skip = skip_validation or main_config.get('modes', {}).get('default') == 'execute'
    config_skip = validation_config.get('skip_goal_check', False)
    
    if force_skip or config_skip:
        ui.print_warning(messages.get('skip_validation', '⚠ Skipping validation'))
    else:
        goal_mapping = dict(config.get('goals', {}))
        validator = GoalValidator(conn, config)
        
        if not validator.validate_route_config(config['route'], goal_mapping):
            ui.print_error(messages.get('validation_failed', '✗ Validation failed!'))
            
            if main_config.get('validation', {}).get('continue_on_validation_fail', False):
                ui.print_warning("Continue anyway (config override)")
            elif main_config.get('validation', {}).get('ask_user_on_fail', True):
                resp = input(messages.get('user_prompt', 'Continue anyway? (y/N): '))
                if resp.lower() not in ('j', 'y', 'ja', 'yes'):
                    return 1
            else:
                return 1
    
    # Set up and connect MQTT Handler
    mqtt_handler = MQTTHandler(config, ui)
    if not mqtt_handler.connect():
        ui.print_error("✗ MQTT connection failed - exiting program")
        return 1
    
    # Instantiate custom MQTTRouteExecutor
    executor = MQTTRouteExecutor(conn, config, mqtt_handler)
    ui.print_header("Route Execution (Loop via MQTT)")
    
    loop_config = main_config.get('modes', {})
    unlimited = loop_config.get('loop_cycles_unlimited', True)
    max_cycles = loop_config.get('max_cycles', 100)
    
    try:
        cycle = 0
        while (unlimited or cycle < max_cycles):
            cycle += 1
            msg = messages.get('cycle_start', '=== Cycle {cycle} starts ===')
            ui.print_info(msg.format(cycle=cycle))
            
            try:
                # Publish status prior to starting cycle
                mqtt_handler.publish_status(executor)
                
                success = executor.execute_route()
                
                if success:
                    ui.print_success(messages.get('cycle_success', '✓ Cycle completed'))
                else:
                    ui.print_error(messages.get('cycle_failed', '✗ Cycle failed - aborting'))
                    break
                    
            except RestartCycleException:
                ui.print_warning("🔄 Cycle restart requested via MQTT. Resetting cycle count...")
                cycle = 0
                continue
                
            except DockRequestedException:
                ui.print_warning("🔌 Immediate docking request received via MQTT.")
                executor._dock()
                mqtt_handler._is_stopped = True
                mqtt_handler._docked_timeout = True
                mqtt_handler.publish_status(executor, state="DOCKED_TIMEOUT")
                cycle = 0  # Ready for a fresh cycle on restart
                continue
                
            except MqttDirectTaskException as ex:
                ui.print_warning(f"🎯 Direct MQTT Task triggered: {ex.task_name}")
                
                # Execute direct task action
                task_cfg = executor.config.get("tasks", {}).get(ex.task_name)
                if task_cfg:
                    ui.print_info(f"Direct Task executing for: {ex.task_name}")
                    executor.step_executor.confirm_button_task.run(task_cfg)
                else:
                    ui.print_error(f"Task '{ex.task_name}' not found in configuration configuration!")
                
                # Force back to paused state after executing direct action
                mqtt_handler._is_stopped = True
                mqtt_handler.publish_status(executor, state="WAITING_FOR_ORDER")
                cycle = 0
                continue
                
        return 0
        
    finally:
        mqtt_handler.disconnect()


def print_help(config: Dict):
    ui = RobotUI()
    cli_config = config.get('main', {}).get('cli', {})
    
    ui.print_header("OMRON LD Robot Control")
    print("\nUsage:")
    print("  python main.py                 Normal execution (MQTT Control Mode)")
    
    for mode, args in cli_config.items():
        arg_str = " | ".join(args)
        mode_name = mode.replace('_', '-').upper()
        print(f"  python main.py {arg_str[2:]}    {mode_name}")
    
    print(f"\nConfig: {config.get('main', {}).get('debug', {}).get('config_path_default', 'config/robot_config.yaml')}")
    sys.exit(0)


def main():
    config = load_config()
    args = parse_cli_args(config)
    
    if args['help']:
        print_help(config)
    
    if args['debug_goals']:
        debug_goals(config)
        return
    
    if args['validate']:
        validate_config(config)
        return
    
    skip_validation = args['skip_validation']
    conn = ARCLConnection(config)
    
    try:
        if not conn.connect():
            ui = RobotUI()
            ui.print_error("Connection failed - exiting")
            return 1
        
        return execute_route_loop(config, conn, skip_validation)
        
    except KeyboardInterrupt:
        ui = RobotUI()
        messages = config.get('main', {}).get('messages', {})
        ui.print_warning(messages.get('interrupted', '⚠ Interrupted by user'))
        return 130
        
    except Exception as e:
        ui = RobotUI()
        messages = config.get('main', {}).get('messages', {})
        ui.print_error(messages.get('unexpected_error', '✗ Unexpected error: {error}').format(error=e))
        
        debug_config = config.get('main', {}).get('debug', {})
        if debug_config.get('show_traceback', True):
            print(traceback.format_exc())
        return 1
        
    finally:
        if 'conn' in locals():
            conn.disconnect()
            ui = RobotUI()
            messages = config.get('main', {}).get('messages', {})
            ui.print_info(messages.get('program_end', '\nProgram ended'))


if __name__ == "__main__":
    sys.exit(main())