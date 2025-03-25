import os
import json
import tempfile
from pathlib import Path
from unittest import mock
from mirrormaker import config


def test_config_defaults():
    """Test that the default configuration is set correctly."""
    test_config = config.Config()
    assert test_config.config == config.DEFAULT_CONFIG


def test_config_load():
    """Test loading configuration from a file."""
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        test_config = {
            "github_token": "test-token",
            "use_glab_cli": True
        }
        json.dump(test_config, f)
        config_path = f.name
    
    try:
        # Create a config instance with the temp file as the config file
        with mock.patch.object(Path, 'home', return_value=Path(os.path.dirname(config_path))):
            test_config = config.Config()
            test_config.config_file = Path(config_path)
            test_config.load_config()
            
            # Check that the config was loaded correctly
            assert test_config.get("github_token") == "test-token"
            assert test_config.get("use_glab_cli") is True
            # Check that other defaults are still in place
            assert "glab_path" in test_config.get_dict()
    finally:
        # Clean up the temporary file
        os.unlink(config_path)


def test_config_update():
    """Test updating the configuration."""
    test_config = config.Config()
    test_config.update(github_token="new-token", dry_run=True)
    
    assert test_config.get("github_token") == "new-token"
    assert test_config.get("dry_run") is True


def test_config_save(tmp_path):
    """Test saving the configuration to a file."""
    config_file = tmp_path / ".gitlab_mirror_maker"
    
    test_config = config.Config()
    test_config.config_file = config_file
    test_config.update(github_token="save-test-token")
    test_config.save_config()
    
    # Check that the file was created
    assert config_file.exists()
    
    # Load the file and check the content
    with open(config_file, 'r') as f:
        saved_config = json.load(f)
    
    assert saved_config["github_token"] == "save-test-token"
