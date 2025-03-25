import argparse
import os
import sys
import logging
from typing import Dict, Any, Optional, List, Callable, Union

# ANSI color codes for terminal output
class Style:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'
    
    @staticmethod
    def style(text: str, fg: Optional[str] = None) -> str:
        """Apply a color style to text."""
        if not fg:
            return text
        
        if fg == 'red':
            return f"{Style.RED}{text}{Style.RESET}"
        elif fg == 'green':
            return f"{Style.GREEN}{text}{Style.RESET}"
        elif fg == 'yellow':
            return f"{Style.YELLOW}{text}{Style.RESET}"
        else:
            return text


def echo(message: str) -> None:
    """Print a message to stdout."""
    print(message)


def secho(message: str, fg: Optional[str] = None) -> None:
    """Print a styled message to stdout."""
    print(Style.style(message, fg))


def create_progressbar(iterable: List[Any], label: str, 
                      show_eta: bool = True) -> 'ProgressBar':
    """Create a simple progress bar."""
    return ProgressBar(iterable, label, show_eta)


class ClickException(Exception):
    """Exception that will be handled by the CLI."""
    
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)
        
    def show(self) -> None:
        """Print the exception message to stderr."""
        sys.stderr.write(f"Error: {self.message}\n")


class ProgressBar:
    """A simple progress bar for command-line interfaces."""
    
    def __init__(self, iterable: List[Any], label: str, show_eta: bool = True) -> None:
        self.iterable = iterable
        self.label = label
        self.show_eta = show_eta
        self.total = len(iterable)
        self.current = 0
        
    def __enter__(self) -> 'ProgressBar':
        print(f"{self.label}...")
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        print("")  # Newline after progress is done
        
    def __iter__(self) -> 'ProgressBar':
        return self
    
    def __next__(self) -> Any:
        if self.current >= self.total:
            raise StopIteration
            
        item = self.iterable[self.current]
        self.current += 1
        
        # Simple progress indicator
        percent = int((self.current / self.total) * 100)
        sys.stdout.write(f"\r{self.label}: {percent}% ({self.current}/{self.total})")
        sys.stdout.flush()
        
        return item


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Set up mirroring of repositories from GitLab to GitHub."
    )
    
    parser.add_argument('--version', action='store_true',
                        help='Show the version and exit')
    parser.add_argument('--github-token', help='GitHub authentication token')
    parser.add_argument('--gitlab-token', help='GitLab authentication token')
    parser.add_argument('--github-user', help='GitHub username. If not provided, your GitLab username will be used by default.')
    parser.add_argument('--dry-run', action='store_true',
                        help='If enabled, a summary will be printed and no mirrors will be created.')
    parser.add_argument('--no-dry-run', action='store_false', dest='dry_run', 
                       help='Execute mirror creation (not just dry run)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('--use-glab', action='store_true',
                       help='Use glab CLI to perform operations')
    parser.add_argument('--no-use-glab', action='store_false', dest='use_glab',
                       help='Do not use glab CLI for operations')
    parser.add_argument('--save-config', action='store_true',
                        help='Save current options to config file')
    parser.add_argument('--config-path', 
                       help='Path to config file (default: ~/.gitlab_mirror_maker)')
    parser.add_argument('--glab-path', default='glab',
                       help='Path to glab executable (default: "glab")')
    parser.add_argument('--glab-mirror-direction', choices=['push', 'pull'],
                       help='Mirror direction when using glab CLI')
    parser.add_argument('--glab-allow-divergence', action='store_true',
                       help='Allow divergent refs when using glab CLI')
    parser.add_argument('--no-glab-allow-divergence', action='store_false', dest='glab_allow_divergence',
                       help='Do not allow divergent refs when using glab CLI')
    parser.add_argument('--glab-protected-branches-only', action='store_true',
                       help='Mirror only protected branches when using glab CLI')
    parser.add_argument('--no-glab-protected-branches-only', action='store_false', dest='glab_protected_branches_only',
                       help='Mirror all branches, not just protected ones')
    parser.add_argument('repo', nargs='?',
                       help='Specific repository to mirror (optional)')
    
    # Check for environment variables with MIRRORMAKER_ prefix
    for action in parser._actions:
        if action.dest != 'help' and not action.dest.startswith('_'):
            env_var = f"MIRRORMAKER_{action.dest.upper()}"
            if env_var in os.environ:
                # For boolean flags, any value means True
                if isinstance(action, argparse._StoreTrueAction):
                    parser.set_defaults(**{action.dest: True})
                else:
                    parser.set_defaults(**{action.dest: os.environ[env_var]})
    
    return parser.parse_args()


def tabulate(data: List[List[Any]], headers: List[str]) -> str:
    """Create a simple ASCII table from data."""
    if not data or not headers:
        return ""
    
    # Find the maximum width needed for each column
    col_widths = [len(h) for h in headers]
    for row in data:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))
    
    # Create the header row
    result = []
    header = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    result.append(header)
    
    # Add a separator line
    separator = "-+-".join("-" * w for w in col_widths)
    result.append(separator)
    
    # Add data rows
    for row in data:
        row_str = " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
        result.append(row_str)
    
    return "\n".join(result)
