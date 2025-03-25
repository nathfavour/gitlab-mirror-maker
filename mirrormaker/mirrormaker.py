import click
import requests
import logging
import os
from typing import List, Dict, Any, Optional
from tabulate import tabulate
from . import __version__
from . import gitlab
from . import github
from . import config
from . import glab_cli


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.command(context_settings={'auto_envvar_prefix': 'MIRRORMAKER'})
@click.version_option(version=__version__)
@click.option('--github-token', help='GitHub authentication token')
@click.option('--gitlab-token', help='GitLab authentication token')
@click.option('--github-user', help='GitHub username. If not provided, your GitLab username will be used by default.')
@click.option('--dry-run/--no-dry-run', default=None, help="If enabled, a summary will be printed and no mirrors will be created.")
@click.option('--verbose', '-v', is_flag=True, help="Enable verbose logging")
@click.option('--use-glab/--no-use-glab', default=None, help="Use glab CLI to perform operations")
@click.option('--save-config', is_flag=True, help="Save current options to config file")
@click.option('--config-path', help="Path to config file (default: ~/.gitlab_mirror_maker)")
@click.option('--glab-path', help="Path to glab executable (default: 'glab')")
@click.option('--glab-mirror-direction', type=click.Choice(['push', 'pull']), help="Mirror direction when using glab CLI")
@click.option('--glab-allow-divergence/--no-glab-allow-divergence', default=None, help="Allow divergent refs when using glab CLI")
@click.option('--glab-protected-branches-only/--no-glab-protected-branches-only', default=None, help="Mirror only protected branches when using glab CLI")
@click.argument('repo', required=False)
def mirrormaker(github_token: Optional[str], gitlab_token: Optional[str], github_user: Optional[str], 
                dry_run: Optional[bool], verbose: bool, repo: Optional[str] = None,
                use_glab: Optional[bool] = None, save_config: bool = False, config_path: Optional[str] = None,
                glab_path: Optional[str] = None, glab_mirror_direction: Optional[str] = None,
                glab_allow_divergence: Optional[bool] = None, glab_protected_branches_only: Optional[bool] = None) -> None:
    """
    Set up mirroring of repositories from GitLab to GitHub.

    By default, mirrors for all repositories owned by the user will be set up.

    If the REPO argument is given, a mirror will be set up for that repository
    only. REPO can be either a simple project name ("myproject"), in which case
    its namespace is assumed to be the current user, or the path of a project
    under a specific namespace ("mynamespace/myproject").
    
    Configuration is loaded from ~/.gitlab_mirror_maker if it exists. Command-line
    arguments override values from the config file.
    """
    try:
        # Override config path if provided
        if config_path:
            config.config.config_file = os.path.expanduser(config_path)
            config.config.load_config()
        
        # Update config with CLI options
        use_glab_cli = use_glab if use_glab is not None else config.config.get("use_glab_cli")
        
        if glab_path:
            config.config.update(glab_path=glab_path)
        
        # Update glab mirror options
        glab_mirror_options = config.config.get("glab_mirror_options", {})
        if glab_mirror_direction:
            glab_mirror_options["direction"] = glab_mirror_direction
        if glab_allow_divergence is not None:
            glab_mirror_options["allow_divergence"] = glab_allow_divergence
        if glab_protected_branches_only is not None:
            glab_mirror_options["protected_branches_only"] = glab_protected_branches_only
        config.config.update(glab_mirror_options=glab_mirror_options)
        
        # Update other settings
        config.config.update(
            github_token=github_token,
            gitlab_token=gitlab_token,
            github_user=github_user,
            verbose=verbose,
            dry_run=dry_run,
            use_glab_cli=use_glab_cli
        )
        
        # Save config if requested
        if save_config:
            config.config.save_config()
            logger.info(f"Configuration saved to {config.config.config_file}")
            if not repo:  # Exit if just saving config without performing any operations
                return
        
        # Set up logging
        if verbose or config.config.get("verbose"):
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Ensure required tokens are available
        github_token = github_token or config.config.get("github_token")
        gitlab_token = gitlab_token or config.config.get("gitlab_token")
        
        if not github_token:
            raise click.ClickException("GitHub token is required. Provide it via --github-token or in config file.")
        
        if not gitlab_token and not use_glab_cli:
            raise click.ClickException("GitLab token is required when not using glab CLI. Provide it via --gitlab-token or in config file.")
        
        # Set up GitHub and GitLab tokens
        github.token = github_token
        github.user = github_user or config.config.get("github_user")
        gitlab.token = gitlab_token
        
        # Check if glab CLI is available if it's being used
        if use_glab_cli:
            if not glab_cli.is_glab_available():
                logger.warning("glab CLI is not available. Falling back to API mode.")
                use_glab_cli = False
            else:
                logger.info("Using glab CLI for GitLab operations")
        
        # Get GitLab repositories
        if repo:
            logger.info(f"Getting GitLab repository: {repo}")
            if use_glab_cli:
                gitlab_repo = glab_cli.get_repo_by_path(repo)
                if gitlab_repo:
                    gitlab_repos = [gitlab_repo]
                else:
                    raise click.ClickException(f"Repository {repo} not found")
            else:
                gitlab_repos = [gitlab.get_repo_by_shorthand(repo)]
        else:
            logger.info('Getting public GitLab repositories')
            if use_glab_cli:
                gitlab_repos = glab_cli.get_repos()
            else:
                gitlab_repos = gitlab.get_repos()
            
            if not gitlab_repos:
                logger.info('There are no public repositories in your GitLab account.')
                return
        
        # Get GitHub repositories
        logger.info('Getting public GitHub repositories')
        github_repos = github.get_repos()
        
        # Find actions and perform them
        actions = find_actions_to_perform(gitlab_repos, github_repos, use_glab_cli)
        print_summary_table(actions)
        perform_actions(actions, dry_run or config.config.get("dry_run", False), use_glab_cli)
        
        logger.info('Done!')
    
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise click.ClickException(str(e))


def find_actions_to_perform(gitlab_repos: List[Dict[str, Any]], 
                           github_repos: List[Dict[str, Any]],
                           use_glab_cli: bool = False) -> List[Dict[str, Any]]:
    """Goes over provided repositories and figure out what needs to be done to create missing mirrors.

    Args:
     - gitlab_repos: List of GitLab repositories.
     - github_repos: List of GitHub repositories.
     - use_glab_cli: Whether to use glab CLI.

    Returns:
     - actions: List of actions necessary to perform on a GitLab repo to create a mirror
                eg: {'gitlab_repo: '', 'create_github': True, 'create_mirror': True}
    """

    actions = []
    with click.progressbar(gitlab_repos, label='Checking mirrors status', show_eta=False) as bar:
        for gitlab_repo in bar:
            action = check_mirror_status(gitlab_repo, github_repos, use_glab_cli)
            actions.append(action)

    return actions


def check_mirror_status(gitlab_repo: Dict[str, Any], 
                        github_repos: List[Dict[str, Any]],
                        use_glab_cli: bool = False) -> Dict[str, Any]:
    """Checks if given GitLab repository has a mirror created among the given GitHub repositories. 

    Args:
     - gitlab_repo: GitLab repository.
     - github_repos: List of GitHub repositories.
     - use_glab_cli: Whether to use glab CLI.

    Returns:
     - action: Action necessary to perform on a GitLab repo to create a mirror (see find_actions_to_perform())
    """

    action = {'gitlab_repo': gitlab_repo, 'create_github': True, 'create_mirror': True}

    try:
        if use_glab_cli:
            mirrors = glab_cli.get_mirrors(gitlab_repo["id"])
        else:
            mirrors = gitlab.get_mirrors(gitlab_repo)
        
        if gitlab.mirror_target_exists(github_repos, mirrors):
            action['create_github'] = False
            action['create_mirror'] = False
            return action

        github_username = github.user or gitlab_repo.get('namespace', {}).get('path', gitlab_repo.get('owner', {}).get('username', ''))
        if github.repo_exists(github_repos, f"{github_username}/{gitlab_repo['path']}"):
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


def perform_actions(actions: List[Dict[str, Any]], dry_run: bool, use_glab_cli: bool = False) -> None:
    """Creates GitHub repositories and configures GitLab mirrors where necessary. 

    Args:
     - actions: List of actions to perform, either creating GitHub repo and/or configuring GitLab mirror.
     - dry_run (bool): When True the actions are not performed.
     - use_glab_cli: Whether to use glab CLI.
    """

    if dry_run:
        logger.info('Run without the --dry-run flag to create missing repositories and mirrors.')
        return

    with click.progressbar(actions, label='Creating mirrors', show_eta=False) as bar:
        for action in bar:
            try:
                gitlab_repo = action["gitlab_repo"]
                github_username = github.user or gitlab_repo.get('namespace', {}).get('path', 
                                                                gitlab_repo.get('owner', {}).get('username', ''))
                
                # Create GitHub repository if needed
                if action["create_github"]:
                    logger.debug(f"Creating GitHub repo for {gitlab_repo['path_with_namespace']}")
                    github.create_repo(gitlab_repo)
                
                # Create mirror if needed
                if action["create_mirror"]:
                    logger.debug(f"Setting up mirror for {gitlab_repo['path_with_namespace']}")
                    
                    if use_glab_cli:
                        # Construct GitHub URL for the mirror
                        github_url = f"https://github.com/{github_username}/{gitlab_repo['path']}.git"
                        
                        # Use glab CLI to set up the mirror
                        success = glab_cli.setup_mirror(
                            gitlab_repo['path_with_namespace'],
                            github_url
                        )
                        
                        if not success:
                            logger.warning(f"Failed to set up mirror using glab CLI, falling back to API")
                            gitlab.create_mirror(gitlab_repo, github.token, github_username)
                    else:
                        # Use GitLab API to set up the mirror
                        gitlab.create_mirror(gitlab_repo, github.token, github_username)
            except Exception as e:
                logger.error(f"Error performing actions for {action['gitlab_repo']['path_with_namespace']}: {str(e)}")


if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter, unexpected-keyword-arg
    mirrormaker()
