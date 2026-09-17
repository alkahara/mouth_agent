# Sheld QA 知识库 API - curl 测试命令

## 1. 健康检查
```bash
curl -s "http://localhost:8080/health" | python3 -m json.tool
```

## 2. 查看元数据文件（本地）
```bash
cat src/graphs/knowledge/packs/sheld_qa/vector_cache/chunks_metadata.json | python3 -m json.tool
```

## 3. 列出所有文档名
```bash
cat src/graphs/knowledge/packs/sheld_qa/vector_cache/chunks_metadata.json | python3 -c "import sys, json; [print(f) for f in json.load(sys.stdin)['documents'].keys()]"
```

## 4. 获取文档切片信息（PDF）
```bash
curl -s "http://localhost:8080/v1/knowledge/sheld_qa/documents/ce153482_20251113_220519.pdf/chunks" | python3 -m json.tool
```

## 5. 获取文档切片信息（DOCX）
```bash
curl -s "http://localhost:8080/v1/knowledge/sheld_qa/documents/31d7d890_20251113_220433.docx/chunks" | python3 -m json.tool
```

## 6. 获取文档切片（只看前 50 行）
```bash
curl -s "http://localhost:8080/v1/knowledge/sheld_qa/documents/ce153482_20251113_220519.pdf/chunks" | python3 -m json.tool | head -50
```

## 7. 重建知识库
```bash
curl -X POST "http://localhost:8080/v1/knowledge/sheld_qa/rebuild"
```

## 8. 重建知识库（格式化输出）
```bash
curl -s -X POST "http://localhost:8080/v1/knowledge/sheld_qa/rebuild" | python3 -m json.tool
```

## 9. 查看文档基本信息（不看 chunks 详情）
```bash
curl -s "http://localhost:8080/v1/knowledge/sheld_qa/documents/ce153482_20251113_220519.pdf/chunks" | python3 -c "import sys, json; d=json.load(sys.stdin)['data']; print(f\"文件: {d['file_name']}\n总字符: {d['document_info']['total_chars']}\n切片数: {d['document_info']['total_chunks']}\")"
```

## 10. 统计所有文档的切片数
```bash
cat src/graphs/knowledge/packs/sheld_qa/vector_cache/chunks_metadata.json | python3 -c "import sys, json; data=json.load(sys.stdin); total=sum(d['total_chunks'] for d in data['documents'].values()); print(f'总切片数: {total}')"
```

---

## 快速测试流程

### 步骤 1：健康检查
```bash
curl -s "http://localhost:8080/health" | python3 -m json.tool
```

### 步骤 2：查看有哪些文档
```bash
cat src/graphs/knowledge/packs/sheld_qa/vector_cache/chunks_metadata.json | python3 -c "import sys, json; [print(f) for f in json.load(sys.stdin)['documents'].keys()]"
```

### 步骤 3：查询某个文档的切片
```bash
# 替换 <FILE_NAME> 为实际文件名
curl -s "http://localhost:8080/v1/knowledge/sheld_qa/documents/<FILE_NAME>/chunks" | python3 -m json.tool | head -60
```

### 步骤 4：重建知识库
```bash
curl -s -X POST "http://localhost:8080/v1/knowledge/sheld_qa/rebuild" | python3 -m json.tool
```
