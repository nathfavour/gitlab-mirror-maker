import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "use_glab_cli": False,
    "glab_path": "glab",
    "glab_mirror_options": {
        "allow_divergence": False,
        "direction": "push",
        "protected_branches_only": False,
        "enabled": True
    },
    "github_token": "",
    "gitlab_token": "",
    "github_user": "",
    "verbose": False,
    "dry_run": False
}


class Config:
    """Configuration handler for GitLab Mirror Maker."""
    
    def __init__(self) -> None:
        self.config: Dict[str, Any] = DEFAULT_CONFIG.copy()
        self.config_file = Path.home() / '.gitlab_mirror_maker'
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from the config file if it exists."""
        if self.config_file.exists():
            try:
                logger.debug(f"Loading config from {self.config_file}")
                with open(self.config_file, 'r') as f:
                    file_config = json.load(f)
                    self.config.update(file_config)
                logger.debug("Config loaded successfully")
            except Exception as e:
                logger.error(f"Error loading config file: {str(e)}")
                logger.warning(f"Using default configuration")
        else:
            logger.debug(f"Config file {self.config_file} not found, using defaults")
    
    def save_config(self) -> None:
        """Save current configuration to the config file."""
        try:
            logger.debug(f"Saving config to {self.config_file}")
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.debug("Config saved successfully")
        except Exception as e:
            logger.error(f"Error saving config file: {str(e)}")
    
    def update(self, **kwargs: Any) -> None:
        """Update configuration with new values."""
        for key, value in kwargs.items():
            if key in self.config and value is not None:
                self.config[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.config.get(key, default)
    
    def get_dict(self) -> Dict[str, Any]:
        """Get the entire configuration as a dictionary."""
        return self.config.copy()


# Global configuration instance
config = Config()
