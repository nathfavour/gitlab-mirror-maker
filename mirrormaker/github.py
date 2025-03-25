import requests
import sys
import logging
from typing import List, Dict, Any, Optional
from pprint import pprint

# Set up logging
logger = logging.getLogger(__name__)

# GitHub user authentication token
token = ''

# GitHub username (under this user namespace the mirrors will be created)
user = ''


class GitHubError(Exception):
    """Exception raised for GitHub API errors."""
    pass


def get_repos() -> List[Dict[str, Any]]:
    """Finds all public GitHub repositories (which are not forks) of authenticated user.

    Returns:
     - List of public GitHub repositories.
    
    Raises:
     - GitHubError: If the GitHub API request fails.
    """

    url = 'https://api.github.com/user/repos?type=public'
    headers = {'Authorization': f'Bearer {token}'}

    repos = []
    try:
        while url:
            logger.debug(f"Fetching GitHub repos from: {url}")
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            repos.extend(r.json())
            # handle pagination
            url = r.links.get("next", {}).get("url", None)
            
        logger.debug(f"Found {len(repos)} GitHub repositories")
        # Return only non forked repositories
        return [x for x in repos if not x['fork']]
    except requests.exceptions.RequestException as e:
        logger.error(f"GitHub API error: {str(e)}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response: {e.response.text}")
        raise GitHubError(f"Failed to fetch GitHub repositories: {str(e)}")


def repo_exists(github_repos: List[Dict[str, Any]], repo_slug: str) -> bool:
    """Checks if a repository with a given slug exists among the public GitHub repositories.

    Args:
     - github_repos: List of GitHub repositories.
     - repo_slug: Repository slug (usually in a form of path with a namespace, eg: "username/reponame").

    Returns:
     - True if repository exists, False otherwise.
    """
    logger.debug(f"Checking if GitHub repo exists: {repo_slug}")
    return any(repo['full_name'] == repo_slug for repo in github_repos)


def create_repo(gitlab_repo: Dict[str, Any]) -> Dict[str, Any]:
    """Creates GitHub repository based on a metadata from given GitLab repository.

    Args:
     - gitlab_repo: GitLab repository which metadata (ie. name, description etc.) is used to create the GitHub repo.

    Returns:
     - JSON representation of created GitHub repo.
     
    Raises:
     - GitHubError: If the GitHub API request fails.
    """

    url = 'https://api.github.com/user/repos'
    headers = {'Authorization': f'Bearer {token}'}

    description = gitlab_repo.get("description", "") or ""
    
    data = {
        'name': gitlab_repo['path'],
        'description': f'{description} [mirror]',
        'homepage': gitlab_repo['web_url'],
        'private': False,
        'has_wiki': False,
        'has_projects': False
    }

    try:
        logger.info(f"Creating GitHub repository: {data['name']}")
        r = requests.post(url, json=data, headers=headers, timeout=30)
        r.raise_for_status()
        logger.info(f"GitHub repository created: {data['name']}")
        return r.json()
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response:
            logger.error(f"GitHub API error: {e.response.text}")
            pprint(e.response.json(), stream=sys.stderr)
        raise GitHubError(f"Failed to create GitHub repository: {str(e)}")
