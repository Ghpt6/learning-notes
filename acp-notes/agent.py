"""一个零依赖、教学用途的 ACP v1 Agent。

stdin/stdout 使用逐行 JSON-RPC；stdout 只能输出协议消息，调试信息请写 stderr。
"""

import json
import sys
import uuid


PROTOCOL_VERSION = 1
sessions: dict[str, dict] = {}
initialized = False

# ACP 的 JSON 文本应以 UTF-8 传输；Windows 控制台的默认代码页不适合作为协议编码。
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")


def send(message: dict) -> None:
    """将一条 JSON-RPC 消息写到 stdout，并立即送出。"""
    print(json.dumps(message, ensure_ascii=False), flush=True)


def respond(request_id, result) -> None:
    send({"jsonrpc": "2.0", "id": request_id, "result": result})


def error(request_id, code: int, message: str) -> None:
    send(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
    )


def update(session_id: str, message_id: str, text: str) -> None:
    """Agent 通过通知把同一条消息的多个文本块流式发给 Client。"""
    send(
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "messageId": message_id,
                    "content": {"type": "text", "text": text},
                },
            },
        }
    )


def handle(request: dict) -> None:
    global initialized

    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    if request.get("jsonrpc") != "2.0":
        error(request_id, -32600, "只接受 JSON-RPC 2.0 消息")
        return

    if method == "initialize":
        initialized = True
        client_version = params.get("protocolVersion", PROTOCOL_VERSION)
        chosen_version = min(client_version, PROTOCOL_VERSION)
        respond(
            request_id,
            {
                "protocolVersion": chosen_version,
                "agentCapabilities": {"promptCapabilities": {}},
                "agentInfo": {
                    "name": "learning-echo-agent",
                    "title": "ACP 学习用 Echo Agent",
                    "version": "0.1.0",
                },
                "authMethods": [],
            },
        )
        return

    if not initialized:
        error(request_id, -32002, "请先调用 initialize")
        return

    if method == "session/new":
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        sessions[session_id] = {"cwd": params.get("cwd", "")}
        respond(request_id, {"sessionId": session_id})
        return

    if method == "session/prompt":
        session_id = params.get("sessionId")
        if session_id not in sessions:
            error(request_id, -32001, "未知的 sessionId")
            return

        # ACP prompt 是 ContentBlock 数组；本例仅读取 Text 块。
        user_text = "".join(
            block.get("text", "")
            for block in params.get("prompt", [])
            if block.get("type") == "text"
        )
        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        update(session_id, message_id, "这是第 1 个流式文本块。\n")
        update(
            session_id,
            message_id,
            f"这是第 2 个流式文本块：你说的是“{user_text}”。\n会话 ID：`{session_id}`",
        )
        # 收到此 response，Client 就知道本轮 prompt 已结束。
        respond(request_id, {"stopReason": "end_turn"})
        return

    if method == "session/cancel":
        # 本例是同步、瞬时完成的；保留该通知分支以展示 ACP 的取消入口。
        return

    if request_id is not None:
        error(request_id, -32601, f"不支持的方法：{method}")


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            handle(json.loads(line))
        except json.JSONDecodeError:
            error(None, -32700, "无效 JSON")
        except Exception as exc:  # 教学示例中显式回传未知错误。
            print(f"agent error: {exc}", file=sys.stderr, flush=True)
            error(None, -32603, "Agent 内部错误")


if __name__ == "__main__":
    main()
