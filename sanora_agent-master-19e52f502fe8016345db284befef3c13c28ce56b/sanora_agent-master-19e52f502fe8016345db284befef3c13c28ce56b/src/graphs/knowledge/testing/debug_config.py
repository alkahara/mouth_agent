#!/usr/bin/env python
"""调试 shelad_qa 配置加载"""

from pathlib import Path
from src.graphs.knowledge.config_loader import build_pack_from_config, PACKS_DIR

print(f"PACKS_DIR: {PACKS_DIR}")
print(f"PACKS_DIR exists: {PACKS_DIR.exists()}")

try:
    pack = build_pack_from_config("sheld_qa")
    print(f"\nPack loaded successfully!")
    print(f"Pack ID: {pack.metadata.pack_id}")
    print(f"Display name: {pack.metadata.display_name}")
    print(f"Knowledge base root: {pack.embedding.knowledge_base_root}")
    print(f"Cache dir: {pack.embedding.cache_dir}")
except Exception as e:
    print(f"\nError loading pack: {e}")
    import traceback
    traceback.print_exc()
