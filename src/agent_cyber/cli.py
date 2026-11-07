"""Command-line entry points."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from . import __version__
from .config import (
    ConfigError,
    api_key_status,
    data_dir,
    load_config,
    save_default_config,
    store_api_key,
    update_api_config,
)
from .skills import SkillLoader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-cyber",
        description="Agent Cyber — terminal-native authorized security assistant.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    init = subparsers.add_parser("init", help="Create the default configuration file.")
    init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing configuration file.",
    )

    subparsers.add_parser("setup", help="Interactively configure the provider.")
    subparsers.add_parser("config", help="Show configuration and API-key status.")
    subparsers.add_parser("skills", help="List installed skills.")
    subparsers.add_parser("test", help="Send a tiny request to verify the API configuration.")
    subparsers.add_parser("chat", help="Start the terminal UI (default).")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        target = save_default_config(overwrite=args.force)
        print(f"Configuration: {target}")
        print()
        print("Next steps:")
        print("  1. Edit the file and set your provider's base_url and model.")
        print("  2. Set the API key in your environment:")
        if sys.platform == "win32":
            print('       setx OPENAI_API_KEY "sk-..."')
            print("     Open a new terminal after setx.")
        else:
            print("       export OPENAI_API_KEY='sk-...'")
            print("     Add it to your shell profile to persist.")
        print("  3. Run: agent-cyber")
        return

    if args.command == "setup":
        try:
            config = load_config()
        except ConfigError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        if not config.config_path:
            print("Configuration path is missing.", file=sys.stderr)
            raise SystemExit(1)

        print("Agent Cyber — provider setup")
        print("Press Enter to keep the value in brackets.\n")
        try:
            base_url = input(f"Base URL [{config.api.base_url}]: ").strip() or config.api.base_url
            model = input(f"Model [{config.api.model}]: ").strip() or config.api.model
            key_env = (
                input(f"API key environment variable [{config.api.api_key_env}]: ").strip()
                or config.api.api_key_env
            )
        except (EOFError, KeyboardInterrupt):
            print("\nSetup cancelled.")
            return

        if sys.stdin.isatty():
            try:
                key = getpass.getpass("API key (leave empty to skip): ").strip()
            except (EOFError, KeyboardInterrupt):
                key = ""
        else:
            print("Non-interactive session: skipping the hidden key prompt.")
            key = ""

        try:
            updated = update_api_config(
                config.config_path,
                base_url=base_url,
                model=model,
                api_key_env=key_env,
            )
        except ConfigError as exc:
            print(f"Could not save configuration: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

        print(f"\nConfiguration saved: {updated}")
        config = load_config()
        if key:
            if store_api_key(key, key_env):
                print("API key stored in the OS keychain.")
            else:
                os.environ["AGENT_CYBER_API_KEY"] = key
                print(
                    "Keyring unavailable: the key is set for this process only. "
                    "Install the secure extra or set it in your environment:"
                )
                if sys.platform == "win32":
                    print('  setx AGENT_CYBER_API_KEY "<your-key>"')
                else:
                    print('  export AGENT_CYBER_API_KEY="<your-key>"')
        elif not api_key_status(config).startswith("set"):
            print(
                "No key stored. Set your provider key in the environment before "
                "running the app."
            )
        print("\nNext: agent-cyber test")
        return

    if args.command == "config":
        try:
            config = load_config()
        except ConfigError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        print(f"Config file: {config.config_path}")
        print(f"Base URL:    {config.api.base_url}")
        print(f"Model:       {config.api.model}")
        print(f"Key env:     {config.api.api_key_env}")
        print(f"Key status:  {api_key_status(config)}")
        print(f"Data dir:    {config.data_path}")
        print(f"Reports:     {(config.data_path or data_dir()) / 'reports'}")
        return

    if args.command == "skills":
        loader = SkillLoader()
        skills = loader.load_all()
        if not skills:
            print("No skills installed.")
        for skill in skills.values():
            print(f"{skill.id:20} {skill.name} — {skill.description}")
        if loader.errors:
            print("\nWarnings:", file=sys.stderr)
            for error in loader.errors:
                print(f"  - {error}", file=sys.stderr)
        return

    if args.command == "test":
        try:
            config = load_config()
        except ConfigError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        from .provider import OpenAICompatibleProvider, ProviderError

        provider = OpenAICompatibleProvider(config.api)

        async def check() -> str:
            chunks: list[str] = []
            async for chunk in provider.stream(
                [{"role": "user", "content": "Reply with the single word: OK"}]
            ):
                chunks.append(chunk)
            return "".join(chunks).strip()

        try:
            answer = asyncio.run(check())
        except ProviderError as exc:
            print(f"Provider check failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        print(f"Provider OK — {config.api.base_url} / {config.api.model}")
        print(f"Response: {answer[:200]}")
        return

    # Default command: chat.
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        print("Run `agent-cyber init` first.", file=sys.stderr)
        raise SystemExit(1) from exc

    try:
        from .app import AgentCyberApp
    except ImportError as exc:
        print(f"Could not load the terminal UI: {exc}", file=sys.stderr)
        print("Install dependencies with: pip install -e .", file=sys.stderr)
        raise SystemExit(1) from exc

    try:
        AgentCyberApp(config).run()
    except KeyboardInterrupt:
        print("\nBye.")


if __name__ == "__main__":
    main()
