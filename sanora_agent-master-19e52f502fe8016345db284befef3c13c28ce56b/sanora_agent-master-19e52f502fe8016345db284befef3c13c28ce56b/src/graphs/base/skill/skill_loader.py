"""
SKILL Loader - 通用 SKILL 加载器

负责加载、解析和管理 SKILL 文件
采用 Claude 官方 SKILL 机制：模型自主调用（Model-Invoked）
"""

import yaml
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillMeta:
    """SKILL 元数据 (Claude 官方格式)"""

    name: str
    enabled_page: str
    enabled_intent: str
    description: str  # 核心匹配字段 - 详细描述"做什么"和"何时用"
    allowed_tools: List[str] = field(default_factory=list)  # 允许使用的工具
    file_path: str = ""


@dataclass
class Skill:
    """完整 SKILL 对象"""

    meta: SkillMeta
    content: str  # Markdown 正文内容

    def get_full_prompt(self) -> str:
        """获取完整的 SKILL prompt（用于注入 System Message）"""
        return f"""# SKILL: {self.meta.name}

{self.meta.description}

---

{self.content}
"""


class SkillLoader:
    """SKILL 加载器 - 通用版本，可供多个 Graph 复用"""

    # 默认 SKILL 目录相对于 src/graphs/
    DEFAULT_SKILLS_DIR = Path(__file__).parent.parent / "skills"

    _cache: Dict[str, Skill] = {}
    _index: Dict[str, SkillMeta] = {}
    _initialized: bool = False
    _skills_dir: Path = None

    @classmethod
    def set_skills_dir(cls, skills_dir: Path) -> None:
        """设置自定义 SKILL 目录"""
        cls._skills_dir = skills_dir
        cls._initialized = False  # 重置以便重新加载

    @classmethod
    def _get_skills_dir(cls) -> Path:
        """获取 skills 目录的绝对路径"""
        if cls._skills_dir:
            return cls._skills_dir
        return cls.DEFAULT_SKILLS_DIR

    @classmethod
    def initialize(cls, skills_dir: Optional[Path] = None) -> None:
        """初始化：扫描 skills 目录，构建索引

        Args:
            skills_dir: 可选的自定义 SKILL 目录路径

        目录结构遵循 Claude 官方 SKILL 格式:
        skills/
        ├── search/
        │   └── SKILL.md
        ├── order/
        │   └── SKILL.md
        └── ...
        """
        # 如果传入新的目录且与当前不同，需要重新初始化
        if skills_dir and skills_dir != cls._skills_dir:
            cls._skills_dir = skills_dir
            cls._cache.clear()
            cls._index.clear()
            cls._initialized = False

        if cls._initialized:
            return

        skills_dir = cls._get_skills_dir()
        if not skills_dir.exists():
            logger.warning(f"SKILL 目录不存在: {skills_dir}")
            skills_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"已创建 SKILL 目录: {skills_dir}")
            cls._initialized = True
            return

        # 扫描子目录中的 SKILL.md 文件 (Claude 官方格式)
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            try:
                meta = cls._parse_frontmatter(skill_file, skill_dir.name)
                if meta:
                    cls._index[meta.name] = meta
                    logger.info(
                        f"✅ 发现 SKILL: {meta.name} ({skill_dir.name}/SKILL.md)"
                    )
            except Exception as e:
                logger.error(f"解析 SKILL 文件失败 {skill_file}: {e}")

        logger.info(f"SKILL 索引构建完成，共 {len(cls._index)} 个 SKILL")
        cls._initialized = True

    @classmethod
    def _parse_frontmatter(cls, file_path: Path, dir_name: str) -> Optional[SkillMeta]:
        """解析 SKILL 文件的 YAML frontmatter (Claude 官方格式)"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.startswith('---'):
            logger.warning(f"SKILL 文件缺少 frontmatter: {file_path}")
            return None

        parts = content.split('---', 2)
        if len(parts) < 3:
            logger.warning(f"SKILL 文件 frontmatter 格式错误: {file_path}")
            return None

        try:
            frontmatter = yaml.safe_load(parts[1])

            # 解析 allowed-tools (支持字符串或列表格式)
            allowed_tools_raw = frontmatter.get('allowed-tools', [])
            if isinstance(allowed_tools_raw, str):
                # 支持 "Read, Grep, Glob" 格式
                allowed_tools = [t.strip() for t in allowed_tools_raw.split(',')]
            else:
                allowed_tools = allowed_tools_raw or []

            return SkillMeta(
                name=frontmatter.get('name', dir_name),
                enabled_page=frontmatter.get('enabled_page', 'all'),
                enabled_intent=frontmatter.get('enabled_intent', 'all'),
                description=frontmatter.get('description', ''),
                allowed_tools=allowed_tools,
                file_path=str(file_path),
            )
        except yaml.YAMLError as e:
            logger.error(f"YAML 解析错误 {file_path}: {e}")
            return None

    @classmethod
    def list_skills(cls) -> List[SkillMeta]:
        """列出所有可用的 SKILL"""
        cls.initialize()
        return list(cls._index.values())

    @classmethod
    def get_skill_names(cls) -> List[str]:
        """获取所有 SKILL 名称"""
        cls.initialize()
        return list(cls._index.keys())

    @classmethod
    def load_skill(cls, skill_name: str) -> Optional[Skill]:
        """加载指定 SKILL"""
        cls.initialize()

        # 检查缓存
        if skill_name in cls._cache:
            return cls._cache[skill_name]

        # 检查索引
        if skill_name not in cls._index:
            logger.warning(f"SKILL 不存在: {skill_name}")
            return None

        meta = cls._index[skill_name]

        try:
            with open(meta.file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取 Markdown 正文（去掉 frontmatter）
            parts = content.split('---', 2)
            body = parts[2].strip() if len(parts) >= 3 else content

            skill = Skill(meta=meta, content=body)
            cls._cache[skill_name] = skill
            logger.info(f"✅ 加载 SKILL: {skill_name}")
            return skill

        except Exception as e:
            logger.error(f"加载 SKILL 失败 {skill_name}: {e}")
            return None

    @classmethod
    def get_skill_prompt(cls, skill_name: str) -> str:
        """获取 SKILL 的完整 prompt"""
        skill = cls.load_skill(skill_name)
        if skill:
            return skill.get_full_prompt()
        return ""

    @classmethod
    def get_skill_tools(cls, skill_name: str) -> List[str]:
        """获取 SKILL 允许使用的工具列表"""
        cls.initialize()
        if skill_name in cls._index:
            return cls._index[skill_name].allowed_tools
        return []

    @classmethod
    def get_skills_meta_by_names(cls, skill_names: List[str]) -> List[SkillMeta]:
        """根据 SKILL 名称列表获取对应的元数据列表

        Args:
            skill_names: SKILL 名称列表

        Returns:
            SkillMeta 对象列表，不存在的 SKILL 会被跳过
        """
        cls.initialize()

        metas = []
        for name in skill_names:
            if name in cls._index:
                metas.append(cls._index[name])
            else:
                logger.warning(f"⚠️ SKILL 不存在: {name}")

        return metas

    @classmethod
    def get_skills_for_selection(cls) -> str:
        """获取所有 SKILL 的描述列表（用于 LLM 选择）"""
        cls.initialize()

        if not cls._index:
            return "没有可用的 SKILL。"

        lines = []
        for name, meta in cls._index.items():
            desc = meta.description.replace('\n', ' ').strip()
            if len(desc) > 200:
                desc = desc[:200] + "..."
            lines.append(f"- {name}: {desc}")

        return "\n".join(lines)

    @classmethod
    def reload(cls) -> None:
        """重新加载所有 SKILL（热更新）"""
        cls._cache.clear()
        cls._index.clear()
        cls._initialized = False
        cls.initialize()
        logger.info("🔄 SKILL 已重新加载")

    @classmethod
    def parse_skill_names_from_llm_output(
        cls, llm_output: str, available_skills: Optional[List[SkillMeta]] = None
    ) -> Optional[List[str]]:
        """从 LLM 输出中解析 SKILL 名称列表

        Args:
            llm_output: LLM 的原始输出文本
            available_skills: 可用的 SKILL 元数据列表，用于验证。
                             如果为 None，则使用当前加载的所有 SKILL

        Returns:
            解析出的有效 SKILL 名称列表，如果没有匹配则返回 None

        示例:
            >>> parse_skill_names_from_llm_output("search, navigation")
            ['search', 'navigation']
            >>> parse_skill_names_from_llm_output("none")
            None
        """
        if not llm_output:
            return None

        # 清理输出：移除引号、反引号、换行符等
        cleaned = (
            llm_output.strip()
            .lower()
            .replace('"', '')
            .replace("'", '')
            .replace('`', '')
            .replace('\n', ',')
            .replace('\r', '')
            .strip()
        )

        # 按逗号分割获取多个 skills
        skill_candidates = [s.strip() for s in cleaned.split(',') if s.strip()]

        # 如果没有候选或者是 "none"，返回 None
        if not skill_candidates or (
            len(skill_candidates) == 1 and skill_candidates[0] == "none"
        ):
            return None

        # 获取可用的 skill names 用于验证
        if available_skills is not None:
            available_names = [skill.name for skill in available_skills]
        else:
            cls.initialize()
            available_names = list(cls._index.keys())

        # 验证每个 skill 是否存在
        valid_skills = []
        for candidate in skill_candidates:
            if candidate == "none":
                continue
            if candidate in available_names:
                valid_skills.append(candidate)
            else:
                logger.warning(f"⚠️ 解析失败：未知的 SKILL '{candidate}'")

        return valid_skills if valid_skills else None

    @classmethod
    def load_skills_from_metadata(cls, skill_metas: List[SkillMeta]) -> List[Skill]:
        """从 SKILL 元数据列表加载完整的 Skill 对象列表

        Args:
            skill_metas: SKILL 元数据列表

        Returns:
            Skill 对象列表，包含元数据和 Markdown 内容
        """
        skills = []
        for meta in skill_metas:
            try:
                # 检查缓存
                if meta.name in cls._cache:
                    skills.append(cls._cache[meta.name])
                    continue

                # 读取文件
                with open(meta.file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 提取 Markdown 正文（去掉 frontmatter）
                parts = content.split('---', 2)
                body = parts[2].strip() if len(parts) >= 3 else content

                skill = Skill(meta=meta, content=body)
                cls._cache[meta.name] = skill
                skills.append(skill)

            except Exception as e:
                logger.error(f"加载 SKILL 失败 {meta.name} ({meta.file_path}): {e}")
                continue

        logger.info(f"✅ 批量加载 {len(skills)}/{len(skill_metas)} 个 SKILL")
        return skills
