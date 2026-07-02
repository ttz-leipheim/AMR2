# Globales Display-Handler
class DisplayLogger:
    def __init__(self, conn):
        """
        Initialisiert the DisplayLogger object with a connection to the robot

        Parameters
        ----------
        conn : Connection
            The connection to the robot

        Returns
        -------
        None
        """
        self.conn = conn
    
    def info(self, msg): 
        """
        Logs an informational message to the terminal and the robot display.

        Parameters
        ----------
        msg : str
            The message to be logged

        Returns
        -------
        None
        """
        print(f"ℹ️  {msg}")           # Terminal
        self.conn.send(f'displayText "ℹ️ {msg[:25]}"')  # Display
    
    def success(self, msg):
        """
        Logs a success message to the terminal and the robot display.

        Parameters
        ----------
        msg : str
            The message to be logged

        Returns
        -------
        None
        """
        print(f"✅ {msg}")
        self.conn.send(f'displayText "✅ {msg[:25]}"')
    
    def error(self, msg):
        """
        Logs an error message to the terminal and the robot display.

        Parameters
        ----------
        msg : str
            The message to be logged

        Returns
        -------
        None
        """
        print(f"❌ {msg}")
        self.conn.send(f'displayMessage "❌ {msg[:20]}"')

