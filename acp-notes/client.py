"""最小但双向的 ACP Client。

默认连接本目录的教学 Agent；加 --agent qwen 后改为启动 ``qwen --acp``。
真实 Agent 能在 prompt 期间反向调用 Client，因此不能只读取自己的 response。
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent.resolve()

# 协议文本与保存到 ``> invoke.md`` 的日志统一使用 UTF-8。Windows 的 GBK
# 控制台无法表示部分 Agent 输出（例如 ⚠），会导致 print() 中断整个会话。
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def qwen_acp_command() -> list[str]:
    """返回可由 subprocess 直接启动的 Qwen ACP 命令。"""
    # PowerShell 会把 qwen 解析为 qwen.ps1，但 CreateProcess 不能执行 .ps1。
    # npm 同时安装的 .cmd 包装器才是 Windows 上 subprocess 的正确入口。
    executable = shutil.which("qwen.cmd") if sys.platform == "win32" else shutil.which("qwen")
    if executable is None:
        raise FileNotFoundError(
            "未找到 Qwen Code。请先执行：npm install -g @qwen-code/qwen-code@latest"
        )
    return [executable, "--acp"]


class AcpClient:
    def __init__(self, command: list[str], cwd: Path):
        self.cwd = cwd.resolve()
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def send(self, message: dict) -> None:
        print("CLIENT ->", json.dumps(message, ensure_ascii=False))
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def respond(self, request_id, result) -> None:
        self.send({"jsonrpc": "2.0", "id": request_id, "result": result})

    def error(self, request_id, code: int, message: str) -> None:
        self.send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": code, "message": message},
            }
        )

    def path_in_workspace(self, raw_path: str) -> Path:
        """只允许 Agent 经 ACP 读取/写入 session cwd 之内的路径。"""
        path = Path(raw_path).resolve(strict=False)
        try:
            path.relative_to(self.cwd)
        except ValueError as exc:
            raise PermissionError(f"路径超出工作区：{path}") from exc
        return path

    def choose_permission(self, params: dict) -> dict:
        tool = params.get("toolCall", {})
        print(f"\nAgent 请求权限：{tool.get('title', '未命名操作')}")
        print(json.dumps(tool.get("rawInput", {}), ensure_ascii=False, indent=2))
        options = params.get("options", [])
        for index, option in enumerate(options, 1):
            print(f"  {index}. {option['name']} ({option['kind']})")
        answer = input("选择编号（直接回车=拒绝）：").strip()
        selected = None
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            selected = options[int(answer) - 1]
        if selected is None:
            selected = next(
                (item for item in options if item["kind"] == "reject_once"), options[-1]
            )
        return {"outcome": {"outcome": "selected", "optionId": selected["optionId"]}}

    @staticmethod
    def confirm_write(path: Path) -> bool:
        answer = input(f"\nAgent 要写入 {path}；输入 y 确认：").strip().lower()
        return answer in {"y", "yes"}

    def handle_agent_request(self, message: dict) -> None:
        """处理 Agent -> Client 的 JSON-RPC request，并保持 prompt 回合继续流动。"""
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params", {})
        try:
            if method == "session/request_permission":
                self.respond(request_id, self.choose_permission(params))
            elif method == "fs/read_text_file":
                path = self.path_in_workspace(params["path"])
                lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
                start = max(params.get("line", 1) - 1, 0)
                limit = params.get("limit")
                content = "".join(lines[start:] if limit is None else lines[start : start + limit])
                self.respond(request_id, {"content": content})
            elif method == "fs/write_text_file":
                path = self.path_in_workspace(params["path"])
                if not self.confirm_write(path):
                    raise PermissionError("用户拒绝写入文件")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(params["content"], encoding="utf-8")
                self.respond(request_id, None)
            else:
                self.error(request_id, -32601, f"Client 不支持的方法：{method}")
        except (OSError, KeyError, PermissionError) as exc:
            self.error(request_id, -32000, str(exc))

    def read_until_response(self, request_id: int) -> dict:
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("Agent 提前退出；请检查 stderr 中的日志和认证状态")
            message = json.loads(line)
            print("AGENT  ->", json.dumps(message, ensure_ascii=False))

            # Agent 的 request / notification 必须先处理，不能被误当作 response。
            if "method" in message:
                if "id" in message:
                    self.handle_agent_request(message)
                continue
            if message.get("id") == request_id:
                return message

    def request(self, request_id: int, method: str, params: dict) -> dict:
        self.send(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        )
        response = self.read_until_response(request_id)
        if "error" in response:
            raise RuntimeError(response["error"])
        return response["result"]

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", choices=("learning", "qwen"), default="learning")
    parser.add_argument("--cwd", type=Path, default=ROOT, help="允许 Agent 访问的工作区")
    parser.add_argument("--prompt", default="你好，ACP！")
    args = parser.parse_args()

    command = (
        [sys.executable, str(ROOT / "agent.py")]
        if args.agent == "learning"
        else qwen_acp_command()
    )
    client = AcpClient(command, args.cwd)
    try:
        client.request(
            0,
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": True, "writeTextFile": True}
                },
                "clientInfo": {
                    "name": "learning-client",
                    "title": "ACP 学习用 Client",
                    "version": "0.2.0",
                },
            },
        )
        session = client.request(
            1, "session/new", {"cwd": str(client.cwd), "mcpServers": []}
        )
        client.request(
            2,
            "session/prompt",
            {
                "sessionId": session["sessionId"],
                "prompt": [{"type": "text", "text": args.prompt}],
            },
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
