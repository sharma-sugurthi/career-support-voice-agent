"""Tests for the one-step setup/start scripts (no execution, structure only)."""
import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

SHELL_SCRIPTS = ["setup.sh", "start.sh", "Start Career Coach.command"]
BATCH_SCRIPTS = ["setup.bat", "start.bat"]


class TestScriptsExist:
    def test_shell_scripts_exist_and_are_executable(self):
        for name in SHELL_SCRIPTS:
            path = ROOT / name
            assert path.exists(), f"{name} is missing"
            mode = path.stat().st_mode
            assert mode & stat.S_IXUSR, f"{name} is not executable - run: chmod +x '{name}'"

    def test_batch_scripts_exist(self):
        for name in BATCH_SCRIPTS:
            assert (ROOT / name).exists(), f"{name} is missing (Windows users need it)"


class TestShellSyntax:
    def test_shell_scripts_parse(self):
        for name in SHELL_SCRIPTS:
            result = subprocess.run(
                ["bash", "-n", str(ROOT / name)], capture_output=True, text=True
            )
            assert result.returncode == 0, f"{name} has a syntax error:\n{result.stderr}"


class TestFriendlyErrors:
    """Non-technical users must never see a bare traceback as the first error."""

    def test_start_checks_setup_ran(self):
        content = (ROOT / "start.sh").read_text()
        assert "setup.sh" in content, "start.sh must tell users to run setup.sh first"

    def test_start_checks_livekit_config(self):
        content = (ROOT / "start.sh").read_text()
        for key in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
            assert key in content, f"start.sh does not handle {key}"

    def test_start_does_not_require_speech_keys(self):
        """Auto mode: missing AssemblyAI/Cartesia keys are VALID (local
        fallback), so start.sh must not hard-fail on them."""
        content = (ROOT / "start.sh").read_text()
        assert 'check_key "ASSEMBLYAI_API_KEY"' not in content
        assert 'check_key "CARTESIA_API_KEY"' not in content

    def test_start_supports_local_livekit(self):
        content = (ROOT / "start.sh").read_text()
        assert "localhost" in content, "start.sh must recognize a local LIVEKIT_URL"
        assert "bin/livekit-server" in content, "start.sh must launch the local server"
        assert "--dev" in content

    def test_start_shows_the_running_mode(self):
        assert "show_mode.py" in (ROOT / "start.sh").read_text(), (
            "start.sh should print which pieces run local vs cloud"
        )

    def test_setup_installs_local_livekit(self):
        content = (ROOT / "setup.sh").read_text()
        assert "livekit-server" in content
        assert "ws://localhost:7880" in content
        assert "devkey" in content

    def test_windows_scripts_support_local_livekit(self):
        assert "livekit-server.exe" in (ROOT / "start.bat").read_text()
        assert "ws://localhost:7880" in (ROOT / "setup.bat").read_text()

    def test_error_messages_name_the_fix(self):
        content = (ROOT / "start.sh").read_text()
        assert ".env.local" in content, (
            "error messages must name the exact file the user has to edit"
        )

    def test_setup_mentions_all_signup_links(self):
        content = (ROOT / "setup.sh").read_text()
        for url in ("cloud.livekit.io", "assemblyai.com", "cartesia.ai", "ollama.com"):
            assert url in content, f"setup.sh should link users to {url}"

    def test_command_launcher_delegates_to_start(self):
        content = (ROOT / "Start Career Coach.command").read_text()
        assert "start.sh" in content
