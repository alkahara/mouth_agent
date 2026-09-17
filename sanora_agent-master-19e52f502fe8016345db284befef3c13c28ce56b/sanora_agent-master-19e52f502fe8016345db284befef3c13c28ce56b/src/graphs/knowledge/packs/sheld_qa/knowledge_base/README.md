# Sheld QA 知识库

将 Sheld 团队的常见问答、流程指南、政策说明等资料以 Markdown/纯文本形式置于本目录。后续运行 `pack.yaml` 的索引流程时，会将这些文件切分并构建向量库。

建议结构：

```
knowledge_base/
  onboarding.md
  product_policies/
    pricing.md
    sla.md
```

> 如需删除向量缓存，可清空 `vector_cache/` 后重新构建。
