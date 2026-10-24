"""Offline unit and Git integration tests; no paid API requests."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class GitCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Tester")
        self.git("config", "user.email", "tester@example.com")
        Path("tracked.txt").write_text("before\n", encoding="utf-8")
        self.git("add", "tracked.txt")
        self.git("commit", "-qm", "initial")

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.temp.cleanup()

    def git(self, *arguments):
        subprocess.run(["git", *arguments], check=True, capture_output=True)

    def run_cli(self, *arguments):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main.main(list(arguments))
        return code, output.getvalue()

    def fake_response(self, document, finish_reason="stop"):
        response = {"choices": [{"finish_reason": finish_reason,
                    "message": {"content": json.dumps(document, ensure_ascii=False)}}]}
        return io.BytesIO(json.dumps(response).encode("utf-8"))

    def test_no_changes_skips_api_and_key(self):
        with patch.dict(os.environ, {}, clear=True), patch("main.urlopen") as api:
            code, output = self.run_cli("commit")
        self.assertEqual(code, 0)
        self.assertIn("변경 사항이 없습니다", output)
        api.assert_not_called()

    def test_untracked_only_does_not_fabricate_diff(self):
        Path("new.txt").write_text("untracked\n", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True), patch("main.urlopen") as api:
            code, output = self.run_cli("pr")
        self.assertEqual(code, 0)
        self.assertIn("git add", output)
        api.assert_not_called()

    def test_unstaged_commit_one_api_call(self):
        Path("tracked.txt").write_text("after\n", encoding="utf-8")
        with patch.dict(os.environ, {"AI_API_KEY": "test-key"}), \
                patch("main.urlopen", return_value=self.fake_response({"title": "fix: 내용 수정"})) as api:
            code, output = self.run_cli("commit")
        self.assertEqual(code, 0)
        self.assertIn("--- Commit Message ---", output)
        self.assertIn("fix: 내용 수정", output)
        self.assertIn("API 호출: 1회", output)
        api.assert_called_once()
        request = api.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        data = json.loads(request.data)
        self.assertEqual(data["model"], "gpt-4o-mini")
        self.assertEqual(data["max_completion_tokens"], 800)
        self.assertEqual(data["response_format"], {"type": "json_object"})
        self.assertIn("+after", data["messages"][1]["content"])

    def test_staged_pr_and_cli_options(self):
        Path("tracked.txt").write_text("staged\n", encoding="utf-8")
        self.git("add", "tracked.txt")
        answer = {"title": "문서 수정", "why": ["작성 이유"],
                  "what": ["파일 갱신"], "how_to_test": ["내용 확인"]}
        with patch.dict(os.environ, {"AI_API_KEY": "test-key"}), \
                patch("main.urlopen", return_value=self.fake_response(answer)) as api:
            code, output = self.run_cli("pr", "--model", "gpt-4.1-mini",
                                        "--temperature", "0.5", "--max-tokens", "1000")
        self.assertEqual(code, 0)
        for expected in ("--- PR Title ---", "## Why", "## What", "## How to Test", "- 내용 확인"):
            self.assertIn(expected, output)
        data = json.loads(api.call_args.args[0].data)
        self.assertEqual(data["model"], "gpt-4.1-mini")
        self.assertEqual(data["temperature"], 0.5)
        self.assertEqual(data["max_completion_tokens"], 1000)
        self.assertIn("[Staged changes]", data["messages"][1]["content"])

    def test_staged_and_unstaged_changes_collected(self):
        Path("tracked.txt").write_text("staged\n", encoding="utf-8")
        self.git("add", "tracked.txt")
        Path("tracked.txt").write_text("staged\nunstaged\n", encoding="utf-8")
        status, diff = main.collect_changes()
        self.assertTrue(status.strip())
        self.assertIn("[Staged changes]", diff)
        self.assertIn("[Unstaged changes]", diff)
        self.assertIn("+staged", diff)
        self.assertIn("+unstaged", diff)

    def test_missing_key(self):
        Path("tracked.txt").write_text("after\n", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True), patch("main.urlopen") as api:
            code, output = self.run_cli("commit")
        self.assertEqual(code, 1)
        self.assertIn("AI_API_KEY", output)
        api.assert_not_called()

    def test_http_auth_error_does_not_leak_key(self):
        Path("tracked.txt").write_text("after\n", encoding="utf-8")
        error = HTTPError(main.API_URL, 401, "Unauthorized", None, io.BytesIO(b"invalid test-key"))
        with patch.dict(os.environ, {"AI_API_KEY": "test-key"}), \
                patch("main.urlopen", side_effect=error):
            code, output = self.run_cli("commit")
        self.assertEqual(code, 1)
        self.assertIn("HTTP 401", output)
        self.assertNotIn("test-key", output)

    def test_network_error(self):
        Path("tracked.txt").write_text("after\n", encoding="utf-8")
        with patch.dict(os.environ, {"AI_API_KEY": "test-key"}), \
                patch("main.urlopen", side_effect=URLError("offline")):
            code, output = self.run_cli("commit")
        self.assertEqual(code, 1)
        self.assertIn("offline", output)

    def test_malformed_ai_result(self):
        Path("tracked.txt").write_text("after\n", encoding="utf-8")
        invalid_response = io.BytesIO(b'{"choices":[{"finish_reason":"stop","message":{"content":"not json"}}]}')
        with patch.dict(os.environ, {"AI_API_KEY": "test-key"}), \
                patch("main.urlopen", return_value=invalid_response):
            code, output = self.run_cli("pr")
        self.assertEqual(code, 1)
        self.assertIn("응답 형식 오류", output)

    def test_incomplete_generation_rejected(self):
        Path("tracked.txt").write_text("after\n", encoding="utf-8")
        with patch.dict(os.environ, {"AI_API_KEY": "test-key"}), \
                patch("main.urlopen", return_value=self.fake_response({"title": "x"}, "length")):
            code, output = self.run_cli("commit")
        self.assertEqual(code, 1)
        self.assertIn("length", output)

    def test_safe_mode_masks_api_key_and_email(self):
        Path("tracked.txt").write_text("API_KEY=super-secret\nemail=user@example.com\n", encoding="utf-8")
        with patch.dict(os.environ, {"AI_API_KEY": "test-key"}), \
                patch("main.urlopen", return_value=self.fake_response({"title": "chore: 확인"})) as api:
            code, output = self.run_cli("commit", "--safe-mode")
        self.assertEqual(code, 0)
        self.assertIn("Safe Mode", output)
        prompt = json.loads(api.call_args.args[0].data)["messages"][1]["content"]
        self.assertNotIn("super-secret", prompt)
        self.assertNotIn("user@example.com", prompt)
        self.assertIn("[REDACTED]", prompt)

    def test_git_outside_repository(self):
        os.chdir(self.old_cwd)
        with tempfile.TemporaryDirectory() as external:
            os.chdir(external)
            code, output = self.run_cli("commit")
        self.assertEqual(code, 1)
        self.assertIn("Git 실행 실패", output)

    def test_initial_staged_files_before_first_commit(self):
        with tempfile.TemporaryDirectory() as new_dir:
            os.chdir(new_dir)
            self.git("init", "-q")
            Path("first.txt").write_text("first\n", encoding="utf-8")
            self.git("add", "first.txt")
            status, diff = main.collect_changes()
        self.assertTrue(status.strip())
        self.assertIn("+first", diff)


class FormatTests(unittest.TestCase):
    def test_safe_mode_masks_quoted_secrets(self):
        diff = '+API_KEY="a secret with spaces"\n+PASSWORD=plain\n'
        redacted = main.safe_diff(diff)
        self.assertNotIn("a secret with spaces", redacted)
        self.assertNotIn("plain", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_safe_mode_limits_blocks_and_lines(self):
        diff = "\n".join(f"diff --git a/file{i} b/file{i}\n+line" for i in range(12))
        limited = main.safe_diff(diff)
        self.assertIn("remaining diff omitted", limited)
        self.assertNotIn("file10", limited)
        big = main.safe_diff("\n".join(f"line{i}" for i in range(250)))
        self.assertEqual(len(big.splitlines()), 201)

    def test_titles_truncated(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main.print_result("commit", {"title": "a" * 100})
        self.assertIn("a" * 72, output.getvalue())
        self.assertNotIn("a" * 73, output.getvalue())
        self.assertIn("[WARN]", output.getvalue())

    def test_missing_sections_get_checkable_placeholders(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main.print_result("pr", {"title": "문서 업데이트"})
        self.assertIn("## Why\n- 변경 배경 확인 (수동 보완 필요)", output.getvalue())
        self.assertIn("## What\n- 변경 내용 확인 (수동 보완 필요)", output.getvalue())
        self.assertIn("## How to Test\n- 테스트 절차 확인 (수동 보완 필요)", output.getvalue())

    def test_invalid_title_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "유효한 제목"):
            main.print_result("commit", {"title": " "})

    def test_parser_rejects_invalid_parameters(self):
        for arguments in (("commit", "--temperature", "3"), ("pr", "--max-tokens", "0")):
            with self.subTest(arguments=arguments), redirect_stdout(io.StringIO()), \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main.main(list(arguments))
            self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
