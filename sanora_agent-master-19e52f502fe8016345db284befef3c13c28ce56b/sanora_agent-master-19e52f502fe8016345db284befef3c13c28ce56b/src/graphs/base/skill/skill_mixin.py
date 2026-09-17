"""
SKILL Mixin - 为 Graph 提供 SKILL 能力

使用方式:
    class MyGraph(SkillMixin, BaseLangGraph):
        async def my_node(self, state, config):
            skill = await self.select_skill_with_llm(user_input, llm)
            prompt = self.get_skill_prompt(skill)
"""

import logging
from typing import Optional, List, Any

from langchain_core.messages import HumanMessage

from .skill_loader import SkillLoader

logger = logging.getLogger(__name__)


class SkillMixin:
    """为 Graph 提供 SKILL 能力的 Mixin 类"""
    
    # 子类可覆盖的默认 SKILL
    DEFAULT_SKILL: str = "search"
    
    def init_skills(self) -> None:
        """初始化 SKILL 加载器"""
        SkillLoader.initialize()
        if hasattr(self, 'logger'):
            self.logger.info(f"✅ SKILL 能力初始化完成，可用 SKILL: {SkillLoader.get_skill_names()}")
    
    def get_skill_names(self) -> List[str]:
        """获取所有可用 SKILL 名称"""
        return SkillLoader.get_skill_names()
    
    def get_skill_prompt(self, skill_name: str) -> str:
        """获取 SKILL 的完整 prompt"""
        return SkillLoader.get_skill_prompt(skill_name)
    
    def get_skill_tools(self, skill_name: str) -> List[str]:
        """获取 SKILL 允许使用的工具列表"""
        return SkillLoader.get_skill_tools(skill_name)
    
    async def select_skill_with_llm(
        self, 
        user_input: str, 
        llm: Any,
        log: Optional[logging.Logger] = None
    ) -> Optional[str]:
        """使用 LLM 选择最匹配的 SKILL (Claude 官方机制)
        
        Args:
            user_input: 用户输入
            llm: LLM 实例
            log: 可选的 logger
            
        Returns:
            选中的 SKILL 名称，如果无匹配返回 None
        """
        log = log or logger
        
        skills_desc = SkillLoader.get_skills_for_selection()
        
        if not skills_desc or skills_desc == "没有可用的 SKILL。":
            log.warning("⚠️ 没有可用的 SKILL")
            return None
        
        prompt = f"""根据用户请求，选择最合适的 SKILL。

可用 SKILL：
{skills_desc}

用户请求：{user_input}

请只输出 SKILL 名称（如 search、order 等），如果没有匹配的 SKILL 则输出 "none"。
注意：只输出 SKILL 名称，不要输出其他内容。"""
        
        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            selected = response.content.strip().lower()
            selected = selected.replace('"', '').replace("'", '').split()[0] if selected else "none"
            
            if selected == "none":
                log.info("🎯 LLM 选择: 无匹配 SKILL")
                return None
            
            available_skills = SkillLoader.get_skill_names()
            if selected in available_skills:
                log.info(f"🎯 LLM 选择 SKILL: {selected}")
                return selected
            else:
                log.warning(f"⚠️ LLM 返回未知 SKILL: {selected}")
                return None
                
        except Exception as e:
            log.error(f"❌ LLM SKILL 选择失败: {e}")
            return None
    
    def get_skill_or_default(self, skill_name: Optional[str]) -> str:
        """获取 SKILL 名称，如果为空则返回默认值"""
        if skill_name:
            return skill_name
        return self.DEFAULT_SKILL
