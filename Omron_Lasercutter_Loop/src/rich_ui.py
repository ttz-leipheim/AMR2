from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.live import Live
from rich import box
import time

console = Console()

class RobotUI:

    
    @staticmethod
    def print_header(title: str):

        """
        Prints a header with the given title.

        :param title: Title of the header
        :type title: str
        """
        console.print(Panel.fit(
            f"[bold cyan]{title}[/bold cyan]",
            border_style="cyan",
            box=box.DOUBLE
        ))
    
    @staticmethod
    def print_step(step_num: int, total_steps: int, description: str):

        """
        Prints a step with the given number, total steps and description.

        :param step_num: Number of the step
        :type step_num: int
        :param total_steps: Total number of steps
        :type total_steps: int
        :param description: Description of the step
        :type description: str
        """
        console.print(f"\n[bold yellow]>>> Schritt {step_num}/{total_steps}:[/bold yellow] {description}")
    
    @staticmethod
    def print_success(message: str):
    
        """
        Prints a success message with the given text.

        :param message: Text of the success message
        :type message: str
        """
        console.print(f"[bold green]✓[/bold green] {message}")
    
    @staticmethod
    def print_error(message: str):

        """
        Prints an error message with the given text.

        :param message: Text of the error message
        :type message: str
        """
        console.print(f"[bold red]✗[/bold red] {message}")
    
    @staticmethod
    def print_warning(message: str):

        """
        Prints a warning message with the given text.

        :param message: Text of the warning message
        :type message: str
        """
        console.print(f"[bold yellow]⚠[/bold yellow] {message}")
    
    @staticmethod
    def print_info(message: str):

        """
        Prints an information message with the given text.

        :param message: Text of the information message
        :type message: str
        """
        console.print(f"[cyan]ℹ[/cyan] {message}")
    
    @staticmethod
    def print_status_table(status: dict):

        """
        Prints a table with the first 10 entries of the given status dictionary.

        :param status: Dictionary containing the status of the robot
        :type status: dict
        """
        table = Table(title="Roboter-Status", box=box.ROUNDED)
        table.add_column("Parameter", style="cyan", no_wrap=True)
        table.add_column("Wert", style="green")
        
        for key, value in list(status.items())[:10]:  # Erste 10 Einträge
            table.add_row(key, str(value))
        
        console.print(table)
    
    @staticmethod
    def wait_with_spinner(message: str, duration: float):

        """
        Waits for the given duration while displaying a status message with a spinner.

        :param message: Text of the status message
        :type message: str
        :param duration: Duration to wait in seconds
        :type duration: float
        """
        with console.status(f"[bold cyan]{message}[/bold cyan]", spinner="dots"):
            time.sleep(duration)
