import requests
import json
import time

# --- 配置参数 ---
# Ollama 的默认 API 地址
OLLAMA_API_URL = "http://localhost:11434/api/chat"
# 您要使用的本地模型名称（必须是您用 ollama pull 命令下载的）
MODEL_NAME = "llama3"


def call_local_llm(messages: list) -> str:
    """
    调用 Ollama API 与本地大模型进行交互。
    参数: messages - 包含完整对话历史的列表。
    返回: 模型生成的文本回复。
    """
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,  # 为了简单起见，我们先设置为非流式传输
    }

    print("🤖 正在连接本地模型...")
    try:
        response = requests.post(OLLAMA_API_URL, headers=headers, json=payload)
        response.raise_for_status()  # 检查 HTTP 错误

        data = response.json()
        # Ollama 返回的数据结构是 data['message']['content']
        if "message" in data and "content" in data["message"]:
            return data["message"]["content"].strip()
        else:
            return "模型返回数据格式错误，请检查 API 响应。"

    except requests.exceptions.ConnectionError:
        print("\n--- [❌ 错误] ---")
        print("无法连接到 Ollama 服务。请确保：")
        print("1. Ollama 服务已在后台运行。")
        print(f"2. API 地址是否正确: {OLLAMA_API_URL}")
        return ""
    except requests.exceptions.HTTPError as e:
        print(f"\n--- [❌ 错误] ---")
        print(f"HTTP 请求失败，状态码：{e.response.status_code}。")
        print("请检查模型名称是否正确或服务器配置是否有误。")
        return ""
    except Exception as e:
        print(f"\n--- [❌ 错误] ---")
        print(f"发生未知错误：{e}")
        return ""


def chat_loop():
    """
    主聊天循环，负责维护对话历史和与模型交互。
    """
    # 初始化会话历史 (Memory)
    conversation_history = [
        {
            "role": "system",
            "content": "你是一个乐于助人的AI助理，请保持语气友好且专业。",
        },
    ]

    print("========================================")
    print(f"🧠 Agent 启动成功！已连接模型: {MODEL_NAME}")
    print("请输入您的问题或指令，输入 'exit' 或 'quit' 退出程序。")
    print("----------------------------------------")

    while True:
        # 获取用户输入
        user_input = input("\n👤 你: ").strip()

        if not user_input:
            continue

        # 检查退出指令
        if user_input.lower() in ["exit", "quit"]:
            print("👋 感谢使用，程序已退出。")
            break

        # 1. 更新对话历史：将用户的输入添加到历史记录中
        conversation_history.append({"role": "user", "content": user_input})

        # 2. 调用模型获取回复 (传入完整的历史记录)
        llm_response = call_local_llm(conversation_history)

        if llm_response:
            # 3. 打印模型的回复
            print(f"\n🤖 AI 回复:\n{llm_response}")

            # 4. 更新对话历史：将模型的回复也添加到历史记录中，供下次使用
            conversation_history.append({"role": "assistant", "content": llm_response})

        # 可选：如果内存过大，可以实现历史消息的截断机制（例如只保留最近10轮）
        # if len(conversation_history) > 25:
        #     # 保留 system message 和最近 N-1 条记录
        #     conversation_history = conversation_history[1:] + [{"role": "system", "content": "..."}]


if __name__ == "__main__":
    chat_loop()
