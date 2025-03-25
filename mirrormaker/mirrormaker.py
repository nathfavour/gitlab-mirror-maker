import click
import requests
import logging
from typing import List, Dict, Any, Optional
from tabulate import tabulate
from . import __version__
from . import gitlab
from . import github


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.command(context_settings={'auto_envvar_prefix': 'MIRRORMAKER'})
@click.version_option(version=__version__)
@click.option('--github-token', required=True, help='GitHub authentication token')
@click.option('--gitlab-token', required=True, help='GitLab authentication token')
@click.option('--github-user', help='GitHub username. If not provided, your GitLab username will be used by default.')
@click.option('--dry-run/--no-dry-run', default=False, help="If enabled, a summary will be printed and no mirrors will be created.")
@click.option('--verbose', '-v', is_flag=True, help="Enable verbose logging")
@click.argument('repo', required=False)
def mirrormaker(github_token: str, gitlab_token: str, github_user: Optional[str], 
                dry_run: bool, verbose: bool, repo: Optional[str] = None) -> None:
    """
    Set up mirroring of repositories from GitLab to GitHub.

    By default, mirrors for all repositories owned by the user will be set up.

    If the REPO argument is given, a mirror will be set up for that repository
    only. REPO can be either a simple project name ("myproject"), in which case
    its namespace is assumed to be the current user, or the path of a project
    under a specific namespace ("mynamespace/myproject").
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        github.token = github_token
        github.user = github_user
        gitlab.token = gitlab_token

        if repo:
            logger.info(f"Getting GitLab repository: {repo}")
            gitlab_repos = [gitlab.get_repo_by_shorthand(repo)]
        else:
            logger.info('Getting public GitLab repositories')
            gitlab_repos = gitlab.get_repos()
            if not gitlab_repos:
                logger.info('There are no public repositories in your GitLab account.')
                return

        logger.info('Getting public GitHub repositories')
        github_repos = github.get_repos()

        actions = find_actions_to_perform(gitlab_repos, github_repos)

        print_summary_table(actions)

        perform_actions(actions, dry_run)

        logger.info('Done!')
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise click.ClickException(str(e))


def find_actions_to_perform(gitlab_repos: List[Dict[str, Any]], 
                           github_repos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Goes over provided repositories and figure out what needs to be done to create missing mirrors.

    Args:
     - gitlab_repos: List of GitLab repositories.
     - github_repos: List of GitHub repositories.

    Returns:
     - actions: List of actions necessary to perform on a GitLab repo to create a mirror
                eg: {'gitlab_repo: '', 'create_github': True, 'create_mirror': True}
    """

    actions = []
    with click.progressbar(gitlab_repos, label='Checking mirrors status', show_eta=False) as bar:
        for gitlab_repo in bar:
            action = check_mirror_status(gitlab_repo, github_repos)
            actions.append(action)

    return actions


def check_mirror_status(gitlab_repo: Dict[str, Any], 
                        github_repos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Checks if given GitLab repository has a mirror created among the given GitHub repositories. 

    Args:
     - gitlab_repo: GitLab repository.
     - github_repos: List of GitHub repositories.

    Returns:
     - action: Action necessary to perform on a GitLab repo to create a mirror (see find_actions_to_perform())
    """

    action = {'gitlab_repo': gitlab_repo, 'create_github': True, 'create_mirror': True}

    try:
        mirrors = gitlab.get_mirrors(gitlab_repo)
        if gitlab.mirror_target_exists(github_repos, mirrors):
            action['create_github'] = False
            action['create_mirror'] = False
            return action

        if github.repo_exists(github_repos, f"{github.user or gitlab_repo['namespace']['path']}/{gitlab_repo['path']}"):
            action['create_github'] = False
    except Exception as e:
        logger.error(f"Error checking mirror status for {gitlab_repo['path_with_namespace']}: {str(e)}")
        
    return action


def print_summary_table(actions: List[Dict[str, Any]]) -> None:
    """Prints a table summarizing whether mirrors are already created or missing
    """

    logger.info('Your mirrors status summary:')

    created = click.style(u'\u2714 created', fg='green')
    missing = click.style(u'\u2718 missing', fg='red')

    headers = ['GitLab repo', 'GitHub repo', 'Mirror']
    summary = []

    for action in actions:
        row = [action["gitlab_repo"]["path_with_namespace"]]
        row.append(missing) if action["create_github"] else row.append(created)
        row.append(missing) if action["create_mirror"] else row.append(created)
        summary.append(row)

    summary.sort()

    click.echo(tabulate(summary, headers) + '\n')


def perform_actions(actions: List[Dict[str, Any]], dry_run: bool) -> None:
    """Creates GitHub repositories and configures GitLab mirrors where necessary. 

    Args:
     - actions: List of actions to perform, either creating GitHub repo and/or configuring GitLab mirror.
     - dry_run (bool): When True the actions are not performed.
    """

    if dry_run:
        logger.info('Run without the --dry-run flag to create missing repositories and mirrors.')
        return

    with click.progressbar(actions, label='Creating mirrors', show_eta=False) as bar:
        for action in bar:
            try:
                if action["create_github"]:
                    logger.debug(f"Creating GitHub repo for {action['gitlab_repo']['path_with_namespace']}")
                    github.create_repo(action["gitlab_repo"])

                if action["create_mirror"]:
                    logger.debug(f"Setting up mirror for {action['gitlab_repo']['path_with_namespace']}")
                    gitlab.create_mirror(action["gitlab_repo"], github.token, github.user)
            except Exception as e:
                logger.error(f"Error performing actions for {action['gitlab_repo']['path_with_namespace']}: {str(e)}")


if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter, unexpected-keyword-arg
    mirrormaker()
