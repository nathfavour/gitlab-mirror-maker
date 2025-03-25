import subprocess
import shlex
import logging
import json
from typing import Dict, Any, List, Optional, Tuple, Union
from . import config

logger = logging.getLogger(__name__)

class GlabCliError(Exception):
    """Exception raised for glab CLI errors."""
    pass


def is_glab_available() -> bool:
    """Check if glab CLI is available in the system."""
    glab_path = config.config.get("glab_path")
    try:
        result = subprocess.run([glab_path, "--version"], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True,
                               check=False)
        return result.returncode == 0
    except Exception as e:
        logger.debug(f"Error checking glab CLI: {str(e)}")
        return False


def run_glab_command(args: List[str]) -> Tuple[str, int]:
    """Run a glab CLI command and return the output."""
    glab_path = config.config.get("glab_path")
    cmd = [glab_path] + args
    
    logger.debug(f"Running command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True,
                               check=False)
        
        if result.returncode != 0:
            logger.error(f"glab command failed with error code {result.returncode}: {result.stderr}")
        
        return result.stdout.strip(), result.returncode
    except Exception as e:
        logger.error(f"Error executing glab command: {str(e)}")
        raise GlabCliError(f"Failed to execute glab command: {str(e)}")


def setup_mirror(gitlab_repo_path: str, github_url: str) -> bool:
    """Setup a mirror using glab CLI.
    
    Args:
        gitlab_repo_path: The path of the GitLab repo (e.g., 'username/repo')
        github_url: The target GitHub repo URL (e.g., 'https://github.com/username/repo.git')
        
    Returns:
        bool: True if successful, False otherwise
    """
    mirror_options = config.config.get("glab_mirror_options", {})
    
    args = ["repo", "mirror", gitlab_repo_path, "--url", github_url]
    
    # Add mirror options
    if mirror_options.get("allow_divergence", False):
        args.append("--allow-divergence")
    
    if mirror_options.get("protected_branches_only", False):
        args.append("--protected-branches-only")
    
    direction = mirror_options.get("direction", "push")
    args.extend(["--direction", direction])
    
    if mirror_options.get("enabled", True):
        args.append("--enabled")
    
    try:
        output, return_code = run_glab_command(args)
        if return_code == 0:
            logger.info(f"Successfully set up mirror for {gitlab_repo_path} to {github_url}")
            return True
        else:
            logger.error(f"Failed to set up mirror: {output}")
            return False
    except GlabCliError as e:
        logger.error(f"Error setting up mirror: {str(e)}")
        return False


def get_repos() -> List[Dict[str, Any]]:
    """Get all repositories using glab CLI."""
    try:
        # Using glab api to get repositories (similar to the API endpoint)
        output, return_code = run_glab_command(["api", "projects?visibility=public&owned=true&archived=false", "--paginate"])
        
        if return_code != 0:
            logger.error("Failed to get repositories using glab CLI")
            return []
        
        return json.loads(output)
    except Exception as e:
        logger.error(f"Error getting repositories with glab CLI: {str(e)}")
        return []


def get_repo_by_path(repo_path: str) -> Optional[Dict[str, Any]]:
    """Get repository information using glab CLI.
    
    Args:
        repo_path: The path of the repo (e.g., 'username/repo')
        
    Returns:
        Dict or None: Repository information if found
    """
    try:
        encoded_path = repo_path.replace("/", "%2F")
        output, return_code = run_glab_command(["api", f"projects/{encoded_path}"])
        
        if return_code != 0:
            logger.error(f"Failed to get repository {repo_path} using glab CLI")
            return None
        
        return json.loads(output)
    except Exception as e:
        logger.error(f"Error getting repository with glab CLI: {str(e)}")
        return None


def get_mirrors(repo_id: int) -> List[Dict[str, Any]]:
    """Get all mirrors for a repository using glab CLI.
    
    Args:
        repo_id: The ID of the repository
        
    Returns:
        List: List of mirrors
    """
    try:
        output, return_code = run_glab_command(["api", f"projects/{repo_id}/remote_mirrors"])
        
        if return_code != 0:
            logger.error(f"Failed to get mirrors for repository ID {repo_id} using glab CLI")
            return []
        
        return json.loads(output)
    except Exception as e:
        logger.error(f"Error getting mirrors with glab CLI: {str(e)}")
        return []
