#!/bin/bash
# Sheld QA 知识库切片 API 测试脚本（curl 版本）

API_BASE_URL="http://localhost:8080"
PACK_ID="sheld_qa"

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_section() {
    echo ""
    echo "============================================================"
    echo "  $1"
    echo "============================================================"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# ==================== 测试 0: 健康检查 ====================
test_health_check() {
    print_section "测试 0: 健康检查"

    print_info "请求 URL: ${API_BASE_URL}/health"

    response=$(curl -s -w "\n%{http_code}" "${API_BASE_URL}/health")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -eq 200 ]; then
        print_success "服务正常运行"
        echo "$body" | python3 -m json.tool
        return 0
    else
        print_error "服务异常 (状态码: $http_code)"
        print_warning "请先启动服务: python run_server.py"
        return 1
    fi
}

# ==================== 测试 1: 查看元数据文件 ====================
test_get_metadata() {
    print_section "测试 1: 查看切片元数据文件"

    metadata_path="../packs/${PACK_ID}/vector_cache/chunks_metadata.json"

    if [ ! -f "$metadata_path" ]; then
        print_error "元数据文件不存在: $metadata_path"
        print_warning "请先启动服务生成向量库"
        return 1
    fi

    print_success "元数据文件存在: $metadata_path"

    # 提取关键信息
    pack_id=$(cat "$metadata_path" | python3 -c "import sys, json; print(json.load(sys.stdin)['pack_id'])")
    generated_at=$(cat "$metadata_path" | python3 -c "import sys, json; print(json.load(sys.stdin)['generated_at'])")
    doc_count=$(cat "$metadata_path" | python3 -c "import sys, json; print(len(json.load(sys.stdin)['documents']))")

    echo "📦 Pack ID: $pack_id"
    echo "📅 生成时间: $generated_at"
    echo "📄 文档数量: $doc_count"
    echo ""

    # 列出所有文档
    print_info "文档列表:"
    cat "$metadata_path" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for idx, (file_name, doc_data) in enumerate(data['documents'].items(), 1):
    print(f'  {idx}. {file_name}')
    print(f'     - 总字符数: {doc_data[\"total_chars\"]}')
    print(f'     - 切片数量: {doc_data[\"total_chunks\"]}')
    print(f'     - 处理时间: {doc_data[\"processed_at\"]}')
    print()
"

    # 返回第一个文档名（用于后续测试）
    cat "$metadata_path" | python3 -c "import sys, json; print(list(json.load(sys.stdin)['documents'].keys())[0])"
}

# ==================== 测试 2: 获取文档切片 ====================
test_get_document_chunks() {
    local file_name="$1"

    print_section "测试 2: 获取文档切片 - $file_name"

    url="${API_BASE_URL}/v1/knowledge/${PACK_ID}/documents/${file_name}/chunks"
    print_info "请求 URL: $url"

    response=$(curl -s -w "\n%{http_code}" "$url")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "📊 状态码: $http_code"
    echo ""

    if [ "$http_code" -ne 200 ]; then
        print_error "请求失败"
        echo "$body"
        return 1
    fi

    # 检查 success 字段
    success=$(echo "$body" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))")

    if [ "$success" != "True" ]; then
        print_error "API 返回失败"
        echo "$body" | python3 -m json.tool
        return 1
    fi

    print_success "请求成功"
    echo ""

    # 解析并显示关键信息
    echo "$body" | python3 -c "
import sys, json

data = json.load(sys.stdin)['data']

print('📄 文档信息:')
print(f'  - 文件名: {data[\"file_name\"]}')
print(f'  - Pack ID: {data[\"pack_id\"]}')
doc_info = data['document_info']
print(f'  - 总字符数: {doc_info[\"total_chars\"]}')
print(f'  - 切片数量: {doc_info[\"total_chunks\"]}')
print(f'  - 处理时间: {doc_info[\"processed_at\"]}')
print()

print('⚙️  切片配置:')
config = data['chunking_config']
print(f'  - 分段规则: {config[\"segmentation_rule\"]}')
print(f'  - Chunk 大小: {config[\"chunk_size\"]}')
print(f'  - 重叠大小: {config[\"overlap\"]}')
print(f'  - 分隔符: {config[\"separator\"]}')
print()

print('📑 切片列表（前 3 个）:')
chunks = data['chunks'][:3]
for chunk in chunks:
    print(f'  - Chunk {chunk[\"sequence\"]}:')
    print(f'    ID: {chunk[\"chunk_id\"]}')
    print(f'    字符数: {chunk[\"char_count\"]}')
    print(f'    位置: {chunk[\"start_pos\"]} - {chunk[\"end_pos\"]}')
    print(f'    页码映射: {chunk.get(\"page_mapping\", \"N/A\")}')
    content_preview = chunk['content'][:100] + '...' if len(chunk['content']) > 100 else chunk['content']
    print(f'    内容预览: {content_preview}')
    print()

# Parent Page 兼容性验证
all_chunks = data['chunks']
single_page = [c for c in all_chunks if c.get('page_mapping') and len(c.get('page_mapping', [])) == 1]
cross_page = [c for c in all_chunks if c.get('page_mapping') and len(c.get('page_mapping', [])) > 1]

print('🔍 Parent Page 兼容性验证:')
print(f'  - 单页切片: {len(single_page)} 个 (会触发 parent page)')
print(f'  - 跨页切片: {len(cross_page)} 个 (保持原样)')

if cross_page:
    print()
    print('  跨页切片示例:')
    for chunk in cross_page[:2]:
        print(f'    - Chunk {chunk[\"sequence\"]}: 跨页 {chunk[\"page_mapping\"]}')
"
}

# ==================== 测试 3: 重建知识库 ====================
test_rebuild_knowledge_pack() {
    print_section "测试 3: 重建知识库（热更新）"

    url="${API_BASE_URL}/v1/knowledge/${PACK_ID}/rebuild"
    print_info "请求 URL: $url"
    print_warning "注意: 这会触发向量库重建，可能需要几分钟"
    echo ""

    # 交互式确认
    if [ -z "$SKIP_CONFIRM" ]; then
        read -p "是否继续？(y/N): " confirm
        if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
            print_info "跳过重建测试"
            return 0
        fi
    fi

    print_info "开始重建..."

    response=$(curl -s -w "\n%{http_code}" -X POST "$url" --max-time 300)
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "📊 状态码: $http_code"
    echo ""

    if [ "$http_code" -ne 200 ]; then
        print_error "请求失败"
        echo "$body"
        return 1
    fi

    # 检查 success 字段
    success=$(echo "$body" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))")

    if [ "$success" != "True" ]; then
        print_error "重建失败"
        echo "$body" | python3 -m json.tool
        return 1
    fi

    print_success "重建成功"
    echo ""

    # 显示重建结果
    echo "$body" | python3 -c "
import sys, json

result = json.load(sys.stdin)['data']

print('📊 重建结果:')
print(f'  - Pack ID: {result[\"pack_id\"]}')
print(f'  - App ID: {result[\"app_id\"]}')
print(f'  - 重建时间: {result[\"rebuilt_at\"]}')

if 'stats' in result and result['stats']:
    stats = result['stats']
    if 'total_chunks' in stats:
        print(f'  - 总切片数: {stats[\"total_chunks\"]}')
"
}

# ==================== 主测试流程 ====================
main() {
    echo "============================================================"
    echo "  Sheld QA 知识库切片 API 测试（curl 版本）"
    echo "============================================================"

    # 测试 0: 健康检查
    if ! test_health_check; then
        print_error "服务未运行，退出测试"
        exit 1
    fi

    # 测试 1: 查看元数据文件
    first_file=$(test_get_metadata)

    if [ -z "$first_file" ]; then
        print_error "元数据文件不存在，请先启动服务生成向量库"
        exit 1
    fi

    # 测试 2: 获取文档切片
    if [ -n "$first_file" ]; then
        test_get_document_chunks "$first_file"
    else
        print_warning "没有文档可供测试"
    fi

    # 测试 3: 重建知识库（可选）
    test_rebuild_knowledge_pack

    print_section "测试完成"
    print_success "所有测试已完成"
}

# ==================== 快速命令（不运行主流程） ====================
# 如果脚本带参数，则执行对应的快速命令

case "$1" in
    health)
        # 快速健康检查
        curl -s "${API_BASE_URL}/health" | python3 -m json.tool
        ;;

    metadata)
        # 快速查看元数据
        metadata_path="../packs/${PACK_ID}/vector_cache/chunks_metadata.json"
        if [ -f "$metadata_path" ]; then
            cat "$metadata_path" | python3 -m json.tool
        else
            echo "元数据文件不存在: $metadata_path"
            exit 1
        fi
        ;;

    chunks)
        # 快速查询文档切片
        if [ -z "$2" ]; then
            echo "用法: $0 chunks <file_name>"
            echo "示例: $0 chunks ce153482_20251113_220519.pdf"
            exit 1
        fi
        curl -s "${API_BASE_URL}/v1/knowledge/${PACK_ID}/documents/$2/chunks" | python3 -m json.tool
        ;;

    rebuild)
        # 快速重建（跳过确认）
        echo "正在重建知识库..."
        curl -s -X POST "${API_BASE_URL}/v1/knowledge/${PACK_ID}/rebuild" --max-time 300 | python3 -m json.tool
        ;;

    list)
        # 列出所有文档
        metadata_path="../packs/${PACK_ID}/vector_cache/chunks_metadata.json"
        if [ -f "$metadata_path" ]; then
            cat "$metadata_path" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('可用文档列表:')
for idx, file_name in enumerate(data['documents'].keys(), 1):
    print(f'{idx}. {file_name}')
"
        else
            echo "元数据文件不存在"
            exit 1
        fi
        ;;

    help|--help|-h)
        echo "Sheld QA 知识库切片 API 测试脚本"
        echo ""
        echo "用法:"
        echo "  $0                    运行完整测试流程"
        echo "  $0 health             健康检查"
        echo "  $0 metadata           查看元数据文件"
        echo "  $0 list               列出所有文档"
        echo "  $0 chunks <file>      查询指定文档的切片"
        echo "  $0 rebuild            重建知识库（跳过确认）"
        echo ""
        echo "示例:"
        echo "  $0 chunks ce153482_20251113_220519.pdf"
        echo "  $0 rebuild"
        ;;

    *)
        # 运行主测试流程
        main
        ;;
esac
