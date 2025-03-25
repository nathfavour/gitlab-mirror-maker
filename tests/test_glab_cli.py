import pytest
import subprocess
import json
from unittest import mock
from mirrormaker import glab_cli, config


@mock.patch('subprocess.run')
def test_is_glab_available(mock_run):
    """Test checking if glab CLI is available."""
    # Mock subprocess.run to return success
    mock_run.return_value = mock.Mock(returncode=0)
    
    assert glab_cli.is_glab_available() is True
    
    # Mock subprocess.run to return failure
    mock_run.return_value = mock.Mock(returncode=1)
    
    assert glab_cli.is_glab_available() is False
    
    # Mock subprocess.run to raise an exception
    mock_run.side_effect = Exception("Command not found")
    
    assert glab_cli.is_glab_available() is False


@mock.patch('subprocess.run')
def test_run_glab_command(mock_run):
    """Test running a glab CLI command."""
    # Mock successful command
    mock_run.return_value = mock.Mock(
        returncode=0,
        stdout="Command output",
        stderr=""
    )
    
    output, returncode = glab_cli.run_glab_command(["test", "command"])
    
    assert output == "Command output"
    assert returncode == 0
    mock_run.assert_called_with(
        ["glab", "test", "command"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False
    )
    
    # Mock failed command
    mock_run.return_value = mock.Mock(
        returncode=1,
        stdout="",
        stderr="Command failed"
    )
    
    output, returncode = glab_cli.run_glab_command(["test", "command"])
    
    assert output == ""
    assert returncode == 1


@mock.patch('mirrormaker.glab_cli.run_glab_command')
def test_setup_mirror(mock_run_command):
    """Test setting up a mirror using glab CLI."""
    # Mock successful command
    mock_run_command.return_value = ("Mirror created", 0)
    
    assert glab_cli.setup_mirror("user/repo", "https://github.com/user/repo.git") is True
    
    # Check the command that was run
    args = mock_run_command.call_args[0][0]
    assert "repo" in args
    assert "mirror" in args
    assert "user/repo" in args
    assert "--url" in args
    assert "https://github.com/user/repo.git" in args
    
    # Mock failed command
    mock_run_command.return_value = ("Mirror creation failed", 1)
    
    assert glab_cli.setup_mirror("user/repo", "https://github.com/user/repo.git") is False


@mock.patch('mirrormaker.glab_cli.run_glab_command')
def test_get_repos(mock_run_command):
    """Test getting repositories using glab CLI."""
    # Mock successful command
    mock_repos = [
        {"id": 1, "path_with_namespace": "user/repo1"},
        {"id": 2, "path_with_namespace": "user/repo2"}
    ]
    mock_run_command.return_value = (json.dumps(mock_repos), 0)
    
    repos = glab_cli.get_repos()
    
    assert len(repos) == 2
    assert repos[0]["path_with_namespace"] == "user/repo1"
    
    # Mock failed command
    mock_run_command.return_value = ("", 1)
    
    repos = glab_cli.get_repos()
    
    assert repos == []


@mock.patch('mirrormaker.glab_cli.run_glab_command')
def test_get_repo_by_path(mock_run_command):
    """Test getting repository information using glab CLI."""
    # Mock successful command
    mock_repo = {"id": 1, "path_with_namespace": "user/repo1"}
    mock_run_command.return_value = (json.dumps(mock_repo), 0)
    
    repo = glab_cli.get_repo_by_path("user/repo1")
    
    assert repo is not None
    assert repo["path_with_namespace"] == "user/repo1"
    
    # Mock failed command
    mock_run_command.return_value = ("", 1)
    
    repo = glab_cli.get_repo_by_path("user/nonexistent")
    
    assert repo is None


@mock.patch('mirrormaker.glab_cli.run_glab_command')
def test_get_mirrors(mock_run_command):
    """Test getting mirrors for a repository using glab CLI."""
    # Mock successful command with mirrors
    mock_mirrors = [
        {"url": "https://github.com/user/repo1.git"}
    ]
    mock_run_command.return_value = (json.dumps(mock_mirrors), 0)
    
    mirrors = glab_cli.get_mirrors(1)
    
    assert len(mirrors) == 1
    assert mirrors[0]["url"] == "https://github.com/user/repo1.git"
    
    # Mock successful command with no mirrors
    mock_run_command.return_value = ("[]", 0)
    
    mirrors = glab_cli.get_mirrors(1)
    
    assert mirrors == []
    
    # Mock failed command
    mock_run_command.return_value = ("", 1)
    
    mirrors = glab_cli.get_mirrors(1)
    
    assert mirrors == []
