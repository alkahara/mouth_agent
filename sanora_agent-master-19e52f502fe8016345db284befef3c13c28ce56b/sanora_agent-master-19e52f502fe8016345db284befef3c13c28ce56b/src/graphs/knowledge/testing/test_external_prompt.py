#!/usr/bin/env python3
"""测试知识库支持外部传入 system/user prompt 的功能"""

import json
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import requests


class ExternalPromptTester:
    """测试外部 prompt 功能的客户端"""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        api_key: str = "lg-sheld-qa-key-12345",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def test_without_system_prompt(self):
        """测试场景1: 不传 system message，使用配置文件的 prompt"""
        print("\n" + "=" * 60)
        print("测试场景1: 不传 system message（使用 pack.yaml 配置的 prompt）")
        print("=" * 60)

        payload = {
            "messages": [
                {"role": "user", "content": "迪士尼VIP通道需要额外付费吗？"}
            ],
            "model": "sheld_qa_knowledge",
            "stream": False,
        }

        response = self._send_request(payload)
        if response:
            print(f"✅ 响应成功")
            print(f"回答: {response}")
        else:
            print("❌ 请求失败")

    def test_with_system_prompt(self):
        """测试场景2: 传入自定义 system message"""
        print("\n" + "=" * 60)
        print("测试场景2: 传入自定义 system message（优先级更高）")
        print("=" * 60)

        # 自定义 system prompt，明确指示回答风格
        custom_system_prompt = """你是一个专业的旅游顾问助手。
请用简洁、专业的语气回答用户的问题。
回答时请先说"作为旅游顾问，"然后再回答问题。
保持回答简短，控制在3句话以内。"""

        payload = {
            "messages": [
                {"role": "system", "content": custom_system_prompt},
                {"role": "user", "content": "迪士尼VIP通道需要额外付费吗？"},
            ],
            "model": "sheld_qa_knowledge",
            "stream": False,
        }

        response = self._send_request(payload)
        if response:
            print(f"✅ 响应成功")
            print(f"回答: {response}")

            # 检查是否使用了外部 prompt（应该包含"作为旅游顾问，"）
            if "作为旅游顾问" in response:
                print("✅ 验证通过: 使用了外部传入的 system prompt")
            else:
                print("⚠️  未能验证是否使用了外部 prompt（可能需要检查回答内容）")
        else:
            print("❌ 请求失败")

    def _send_request(self, payload: dict) -> str | None:
        """发送请求并返回响应内容"""
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            # 提取回答内容
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                print(f"响应格式异常: {json.dumps(data, ensure_ascii=False, indent=2)}")
                return None

        except requests.exceptions.RequestException as exc:
            print(f"❌ 请求失败: {exc}")
            if hasattr(exc, "response") and exc.response is not None:
                print(f"状态码: {exc.response.status_code}")
                print(f"响应内容: {exc.response.text}")
            return None


def main():
    print("🧪 开始测试知识库外部 prompt 功能")
    print("=" * 60)

    tester = ExternalPromptTester()

    # 测试1: 不传 system message
    tester.test_without_system_prompt()

    # 测试2: 传入 system message
    tester.test_with_system_prompt()

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
