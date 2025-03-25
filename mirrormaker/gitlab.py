import requests
import logging
from typing import List, Dict, Any, Optional, Tuple

# Set up logging
logger = logging.getLogger(__name__)

# GitLab user authentication token
token = ''


class GitLabError(Exception):
    """Exception raised for GitLab API errors."""
    pass


def get_repos() -> List[Dict[str, Any]]:
    """Finds all public GitLab repositories of authenticated user.

    Returns:
     - List of public GitLab repositories.
    
    Raises:
     - GitLabError: If the GitLab API request fails.
    """

    url = 'https://gitlab.com/api/v4/projects?visibility=public&owned=true&archived=false'
    headers = {'Authorization': f'Bearer {token}'}

    try:
        logger.debug("Fetching GitLab repositories")
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        repos = r.json()
        logger.debug(f"Found {len(repos)} public GitLab repositories")
        return repos
    except requests.exceptions.RequestException as e:
        logger.error(f"GitLab API error: {str(e)}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response: {e.response.text}")
        raise GitLabError(f"Failed to fetch GitLab repositories: {str(e)}")


def get_user() -> Dict[str, Any]:
    """Gets information about the authenticated GitLab user.
    
    Returns:
     - User information dictionary.
     
    Raises:
     - GitLabError: If the GitLab API request fails.
    """
    url = 'https://gitlab.com/api/v4/user'
    headers = {'Authorization': f'Bearer {token}'}

    try:
        logger.debug("Fetching GitLab user information")
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"GitLab API error: {str(e)}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response: {e.response.text}")
        raise GitLabError(f"Failed to fetch GitLab user information: {str(e)}")


def get_repo_by_shorthand(shorthand: str) -> Dict[str, Any]:
    """Gets a GitLab repository by its shorthand name.
    
    Args:
     - shorthand: Repository shorthand (either "project" or "namespace/project")
     
    Returns:
     - Repository information dictionary.
     
    Raises:
     - GitLabError: If the GitLab API request fails.
    """
    if "/" not in shorthand:
        user = get_user()["username"]
        namespace, project = user, shorthand
    else:
        namespace, project = shorthand.rsplit("/", maxsplit=1)

    project_id = requests.utils.quote("/".join([namespace, project]), safe="")

    url = f'https://gitlab.com/api/v4/projects/{project_id}'
    headers = {'Authorization': f'Bearer {token}'}

    try:
        logger.debug(f"Fetching GitLab repository: {shorthand}")
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"GitLab API error: {str(e)}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response: {e.response.text}")
        raise GitLabError(f"Failed to fetch GitLab repository {shorthand}: {str(e)}")


def get_mirrors(gitlab_repo: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Finds all configured mirrors of GitLab repository.

    Args:
     - gitlab_repo: GitLab repository.

    Returns:
     - List of mirrors.
     
    Raises:
     - GitLabError: If the GitLab API request fails.
    """

    url = f'https://gitlab.com/api/v4/projects/{gitlab_repo["id"]}/remote_mirrors'
    headers = {'Authorization': f'Bearer {token}'}

    try:
        logger.debug(f"Fetching mirrors for repository: {gitlab_repo['path_with_namespace']}")
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        mirrors = r.json()
        logger.debug(f"Found {len(mirrors)} mirrors")
        return mirrors
    except requests.exceptions.RequestException as e:
        logger.error(f"GitLab API error: {str(e)}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response: {e.response.text}")
        raise GitLabError(f"Failed to fetch mirrors for repository {gitlab_repo['path_with_namespace']}: {str(e)}")


def mirror_target_exists(github_repos: List[Dict[str, Any]], mirrors: List[Dict[str, Any]]) -> bool:
    """Checks if any of the given mirrors points to any of the public GitHub repositories.

    Args:
     - github_repos: List of GitHub repositories.
     - mirrors: List of mirrors configured for a single GitLab repository.

    Returns:
     - True if any of the mirror points to an existing GitHub repository, False otherwise.
    """

    for mirror in mirrors:
        if any(mirror.get('url') and mirror.get('url').endswith(f'{repo["full_name"]}.git') for repo in github_repos):
            return True

    return False


def create_mirror(gitlab_repo: Dict[str, Any], github_token: str, github_user: Optional[str]) -> Dict[str, Any]:
    """Creates a push mirror of GitLab repository.

    For more details see: 
    https://docs.gitlab.com/ee/user/project/repository/repository_mirroring.html#pushing-to-a-remote-repository-core

    Args:
     - gitlab_repo: GitLab repository to mirror.
     - github_token: GitHub authentication token.
     - github_user: GitHub username under whose namespace the mirror will be created (defaults to GitLab username if not provided).

    Returns:
     - JSON representation of created mirror.
     
    Raises:
     - GitLabError: If the GitLab API request fails.
    """

    url = f'https://gitlab.com/api/v4/projects/{gitlab_repo["id"]}/remote_mirrors'
    headers = {'Authorization': f'Bearer {token}'}

    # If github-user is not provided use the gitlab username
    if not github_user:
        github_user = gitlab_repo.get('owner', {}).get('username', '')

    data = {
        'url': f'https://{github_user}:{github_token}@github.com/{github_user}/{gitlab_repo["path"]}.git',
        'enabled': True
    }

    try:
        logger.info(f"Creating mirror for repository: {gitlab_repo['path_with_namespace']} to GitHub: {github_user}/{gitlab_repo['path']}")
        r = requests.post(url, json=data, headers=headers, timeout=30)
        r.raise_for_status()
        logger.info(f"Mirror created successfully")
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"GitLab API error: {str(e)}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response: {e.response.text}")
        raise GitLabError(f"Failed to create mirror for repository {gitlab_repo['path_with_namespace']}: {str(e)}")
