"""
口腔分诊 V2 - Flows 层

导入所有流程以触发 FlowRegistry 注册。
"""

from .bleeding_flow import BleedingFlow

__all__ = ["BleedingFlow"]
