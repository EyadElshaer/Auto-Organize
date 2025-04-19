from PyQt5.QtWidgets import QWidget, QVBoxLayout

class BaseTab(QWidget):
    """Base class for all tabs in the application"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)
        
    def save_settings(self, config):
        """
        Save tab-specific settings to the config
        
        Args:
            config: The application configuration dictionary
        """
        pass
        
    def load_settings(self, config):
        """
        Load tab-specific settings from the config
        
        Args:
            config: The application configuration dictionary
        """
        pass 