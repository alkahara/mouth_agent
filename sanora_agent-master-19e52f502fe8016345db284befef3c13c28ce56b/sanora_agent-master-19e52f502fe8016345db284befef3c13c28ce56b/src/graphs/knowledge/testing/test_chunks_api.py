"""测试 Sheld QA 知识库切片 API"""

import json
import requests
from pathlib import Path
from typing import Optional


# 配置
API_BASE_URL = "http://localhost:8080"
PACK_ID = "sheld_qa"


def print_section(title: str):
    """打印分隔符"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def test_get_metadata():
    """测试：查看 chunks_metadata.json 文件"""
    print_section("测试 1: 查看切片元数据文件")

    metadata_path = Path(__file__).parent.parent / "packs" / PACK_ID / "vector_cache" / "chunks_metadata.json"

    if not metadata_path.exists():
        print(f"❌ 元数据文件不存在: {metadata_path}")
        return None

    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    print(f"✅ 元数据文件存在")
    print(f"📦 Pack ID: {metadata.get('pack_id')}")
    print(f"📅 生成时间: {metadata.get('generated_at')}")
    print(f"📄 文档数量: {len(metadata.get('documents', {}))}")

    # 列出所有文档
    print(f"\n文档列表:")
    for idx, (file_name, doc_data) in enumerate(metadata.get('documents', {}).items(), 1):
        print(f"  {idx}. {file_name}")
        print(f"     - 总字符数: {doc_data['total_chars']}")
        print(f"     - 切片数量: {doc_data['total_chunks']}")
        print(f"     - 处理时间: {doc_data['processed_at']}")

    return metadata


def test_get_document_chunks(file_name: str):
    """测试：获取文档切片信息 API"""
    print_section(f"测试 2: 获取文档切片 - {file_name}")

    url = f"{API_BASE_URL}/v1/knowledge/{PACK_ID}/documents/{file_name}/chunks"
    print(f"🌐 请求 URL: {url}")

    try:
        response = requests.get(url, timeout=10)
        print(f"📊 状态码: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ 请求失败")
            print(f"响应: {response.text}")
            return None

        data = response.json()

        if not data.get('success'):
            print(f"❌ API 返回失败")
            print(f"错误信息: {data.get('message')}")
            return None

        print(f"✅ 请求成功")

        result = data.get('data', {})
        doc_info = result.get('document_info', {})
        chunking_config = result.get('chunking_config', {})
        chunks = result.get('chunks', [])

        print(f"\n📄 文档信息:")
        print(f"  - 文件名: {result.get('file_name')}")
        print(f"  - Pack ID: {result.get('pack_id')}")
        print(f"  - 总字符数: {doc_info.get('total_chars')}")
        print(f"  - 切片数量: {doc_info.get('total_chunks')}")
        print(f"  - 处理时间: {doc_info.get('processed_at')}")

        print(f"\n⚙️  切片配置:")
        print(f"  - 分段规则: {chunking_config.get('segmentation_rule')}")
        print(f"  - Chunk 大小: {chunking_config.get('chunk_size')}")
        print(f"  - 重叠大小: {chunking_config.get('overlap')}")
        print(f"  - 分隔符: {chunking_config.get('separator')}")

        print(f"\n📑 切片列表（前 3 个）:")
        for chunk in chunks[:3]:
            print(f"  - Chunk {chunk['sequence']}:")
            print(f"    ID: {chunk['chunk_id']}")
            print(f"    字符数: {chunk['char_count']}")
            print(f"    位置: {chunk['start_pos']} - {chunk['end_pos']}")
            print(f"    页码映射: {chunk.get('page_mapping', 'N/A')}")  # 🔍 关键：验证 parent page 兼容
            content_preview = chunk['content'][:100] + '...' if len(chunk['content']) > 100 else chunk['content']
            print(f"    内容预览: {content_preview}")
            print()

        # 🔍 验证 parent page 兼容性
        print(f"\n🔍 Parent Page 兼容性验证:")
        single_page_chunks = [c for c in chunks if c.get('page_mapping') and len(c.get('page_mapping', [])) == 1]
        cross_page_chunks = [c for c in chunks if c.get('page_mapping') and len(c.get('page_mapping', [])) > 1]

        print(f"  - 单页切片: {len(single_page_chunks)} 个 (会触发 parent page)")
        print(f"  - 跨页切片: {len(cross_page_chunks)} 个 (保持原样)")

        if cross_page_chunks:
            print(f"\n  跨页切片示例:")
            for chunk in cross_page_chunks[:2]:
                print(f"    - Chunk {chunk['sequence']}: 跨页 {chunk['page_mapping']}")

        return data

    except requests.exceptions.ConnectionError:
        print(f"❌ 连接失败: 请确保服务正在运行 (python run_server.py)")
        return None
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return None


def test_rebuild_knowledge_pack():
    """测试：重建知识库 API"""
    print_section("测试 3: 重建知识库（热更新）")

    url = f"{API_BASE_URL}/v1/knowledge/{PACK_ID}/rebuild"
    print(f"🌐 请求 URL: {url}")
    print(f"⚠️  注意: 这会触发向量库重建，可能需要几分钟")

    confirm = input("\n是否继续？(y/N): ")
    if confirm.lower() != 'y':
        print("⏭️  跳过重建测试")
        return None

    try:
        print(f"🔨 开始重建...")
        response = requests.post(url, timeout=300)  # 5分钟超时
        print(f"📊 状态码: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ 请求失败")
            print(f"响应: {response.text}")
            return None

        data = response.json()

        if not data.get('success'):
            print(f"❌ 重建失败")
            print(f"错误信息: {data.get('message')}")
            return None

        print(f"✅ 重建成功")

        result = data.get('data', {})
        print(f"\n📊 重建结果:")
        print(f"  - Pack ID: {result.get('pack_id')}")
        print(f"  - App ID: {result.get('app_id')}")
        print(f"  - 重建时间: {result.get('rebuilt_at')}")

        stats = result.get('stats', {})
        if stats:
            print(f"  - 总切片数: {stats.get('total_chunks')}")

        return data

    except requests.exceptions.ConnectionError:
        print(f"❌ 连接失败: 请确保服务正在运行")
        return None
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时: 重建时间过长")
        return None
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return None


def test_health_check():
    """测试：健康检查"""
    print_section("测试 0: 健康检查")

    url = f"{API_BASE_URL}/health"
    print(f"🌐 请求 URL: {url}")

    try:
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            print(f"✅ 服务正常运行")
            data = response.json()
            print(f"📊 状态: {data.get('status')}")
            print(f"📦 可用模型: {', '.join(data.get('available_models', []))}")
            return True
        else:
            print(f"❌ 服务异常 (状态码: {response.status_code})")
            return False

    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到服务")
        print(f"💡 请先启动服务: python run_server.py")
        return False
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False


def main():
    """主测试流程"""
    print("=" * 60)
    print("  Sheld QA 知识库切片 API 测试")
    print("=" * 60)

    # 测试 0: 健康检查
    if not test_health_check():
        print("\n❌ 服务未运行，退出测试")
        return

    # 测试 1: 查看元数据文件
    metadata = test_get_metadata()

    if not metadata:
        print("\n❌ 元数据文件不存在，请先启动服务生成向量库")
        return

    # 测试 2: 获取文档切片
    documents = metadata.get('documents', {})
    if documents:
        first_file = list(documents.keys())[0]
        test_get_document_chunks(first_file)
    else:
        print("\n⚠️  没有文档可供测试")

    # 测试 3: 重建知识库（可选）
    test_rebuild_knowledge_pack()

    print_section("测试完成")
    print("✅ 所有测试已完成")


if __name__ == "__main__":
    main()
