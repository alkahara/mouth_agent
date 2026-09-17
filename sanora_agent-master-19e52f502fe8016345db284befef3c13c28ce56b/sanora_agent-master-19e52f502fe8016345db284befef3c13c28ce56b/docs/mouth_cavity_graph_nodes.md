## MouthCavityKnowledge 节点职责

- **triage**：对最新会话消息进行槽位提取与流程决策，解析术后时间、症状描述等字段，并返回 `kind` 指引后续节点。
- **ask**：当仍需补全槽位时触发，读出 `decision.question`，向患者发起下一条明确询问，保障收集流程持续推进。
- **guidance**：在需即时给出护理建议且继续追问时使用，调用 `_deliver_guidance` 查询知识库生成指引文案，可附加 `followup_question` 追问复诊状态。
- **final**：当槽位足够输出诊断时执行 `_compose_final_response`，返回整合后的风险评估与终局建议，并在日志打印 `risk_level=…` 方便调试。
- **fallback**：若流程决策失败或缺乏关键信息时进入的兜底节点，输出默认提示“请描述更多细节”，避免会话陷入死循环或沉默。

### 知识库调用流程

- Pack 配置：`pack.yaml` 描述了 mouth_cavity 知识包的检索器、重排序器与 LLM，`mouth_cavity_graph` 在 `_create_graph()` 中通过 `self.pack.build_graph()` 生成 `agentic_guidance_graph`，以供后续复用。
- 调用入口：
  - `guidance` 节点在遇到 `kind: guidance_followup` 时调用 `_deliver_guidance()`，根据当前 `guidance_type` 与 `prompt_hint` 组织提问，触发 pack 中定义的 RAG 子图，拿到护理建议后再拼上一句追问。
  - `final` 节点则在 `_compose_final_response()` 内部再次调用 `_deliver_guidance()`，生成终局建议（附风险说明）。
- 其他节点（如 `triage`、`ask`、`fallback`）不触发知识库检索，只负责路由或提问。


• 知识库查询逻辑

  - 系统启动时，MouthCavityKnowledge 通过 AgenticKnowledgeGraph 找到 mouth_cavity 的 pack；pack 的元数据都定义在 src/graphs/knowledge/packs/
    mouth_cavity/pack.yaml。
  - _create_graph 里执行 self.pack.build_graph(self.llm_provider)，该 pack 会按 pack.yaml 里的 retriever、reranker、LLM 等配置，搭建一条标准的 RAG 子
    图（StateGraph）。
  - 图初始化后存成 self.agentic_guidance_graph，真正调用知识库时走 _deliver_guidance()：
      1. 根据当前分支传入 guidance_type、prompt_hint 等信息组织提问；
      2. 构造 LangGraph 上下文（模型名、thread_id、config_params）；
      3. 调用 self.agentic_guidance_graph.invoke(...)，让 pack 内配置的检索器、重排序、生成器顺序执行，并返回回答；
      4. 如子图执行报错或没有结果，则回退到 fallback_templates。

  简言之，所有检索流程都由 pack 配置决定：改 pack.yaml 就能换数据源、模型或流水线，MouthCavityKnowledge 只负责调度。

  ———

  知识库触发节点
  目前只有两种节点会真的查询知识库：

  1. guidance 节点（src/graphs/knowledge/packs/mouth_cavity/mouth_cavity_graph.py:110）
      - 被 _decide_next_step 选中 kind: "guidance_followup" 时触发，典型场景是问完问题2/3/6后需要先给一轮操作建议再继续追问。
      - 输出流程：_deliver_guidance(..., final_stage=False) → 返回护理指引 -> 拼上一句追问。
  2. final 节点（同文件:134）
      - 当槽位已满足直接定级时进入，_compose_final_response() 内部再次调用 _deliver_guidance(..., final_stage=True) 生成终局建议。
      - 这一版会强调风险等级点，文本末尾加整体总结。

  其他节点情况：

  - triage 只负责填槽/路由，不调用知识库；
  - ask 仅输出问题（附图片选项）；
  - fallback 返回兜底话术，不触发检索。

  因此，口腔 agent 每次查知识库都在 guidance 或 final 这两个节点，背后共享同一套 pack 配置。

  • 是的，整个口腔图的知识库调用都集中在 src/graphs/knowledge/packs/mouth_cavity/mouth_cavity_graph.py 这一份里：

  - _create_graph :62 处先通过 self.pack.build_graph(self.llm_provider) 构造出 agentic_guidance_graph，它本质就是根据 pack.yaml 配好的 RAG 子流程（检
    索器、重排序、生成器等）。
  - 真正“查知识库”的动作发生在 _deliver_guidance()：

    result_state = self.agentic_guidance_graph.invoke(
        initial_state,
        {"configurable": {"thread_id": thread_id}},
        context=context_schema,
    )
    这段代码执行时，会触发 pack 中的检索和生成逻辑，把最终的护理建议返回。这个调用会在下面两处被触发：
      1. guidance 节点（同文件 :114）——遇到 kind: guidance_followup 时，先查知识库拿到建议，再继续追问。
      2. final 节点（同文件 :139）——收尾阶段 _compose_final_response() 里再次调用 _deliver_guidance()，生成终局建议。

  所以 mouth_cavity_graph.py 里的这几个位置就是口腔 Agent 调用知识库的核心代码。


## 
  • self.agentic_guidance_graph.invoke(...) 并不会再去调 AgenticKnowledgeGraph 里的别的方法，它直接落到 LangGraph 的编译图对象 (CompiledGraph) 上执行。
  这个对象是你在 MouthCavityKnowledge._create_graph() 里通过 self.pack.build_graph(self.llm_provider) 拿到的，也就是根据 pack.yaml 生成的 RAG 子流程。

  调用链可以拆成两段：

  1. MouthCavityKnowledge 层
     _deliver_guidance() 构造好初始 state、config、ContextSchema 后，调用

     self.agentic_guidance_graph.invoke(..., context=context_schema)
  2. LangGraph 层
     invoke 是 langgraph.graph.state.CompiledGraph 的方法（LangGraph 内部实现），会按 pack.yaml 定义的节点顺序执行：先跑 retriever、再跑 grade/
     rewrite、最后生成护理建议。这些节点和顺序都来自 mouth_cavity/pack.yaml，AgenticKnowledgeGraph 本身只负责在初始化阶段把知识包的图编译出来。

  因此，在 AgenticKnowledgeGraph 里唯一相关的代码就是 _create_graph 时那句 self.pack.build_graph(...)（见文件 src/graphs/
  agentic_knowledge_graph.py:24），负责生成 CompiledGraph；真正“跑”知识库的是 LangGraph 的 CompiledGraph.invoke()。



  ## 你看到的流程没错，这段就是“官网”的标准 Agentic RAG，我来解释一下为什么 rewrite_question 会挂在 retrieve 后面，以及背后是什么逻辑。

  现状流程（源码 build_agentic_state_graph）

  START
    → generate_query_or_respond       # 先让模型决定：直接回答还是用工具
       ├─(工具)→ retrieve             # 触发检索：ToolNode → 进入 grade_documents
       │     ├─ grade_documents → generate_answer  # 判定检索上下文够好，就直接生成答案
       │     └─ grade_documents → rewrite_question # 判定不够好：走“重写查询”
       │                         └─ rewrite_question → 回到 generate_query_or_respond
       └─(END)                         # 如果模型选择直接回答就结束

  所以 rewrite 节点是在“检索之后、生成答案之前”的位置，用来兜底：先检索一次，如果文档不相关，再触发重写，然后重新走检索流程。这在 LangGraph 官方模板里
  就是这么设计的，目的是避免无谓的重写开销，同时保证有 fallback。

  如果你想实现“先重写再检索”的策略，可以把 rewrite 拆出来放到 generate_query_or_respond 之前，甚至让它根据配置决定是否提前重写。这就回到我们前面讨论的
  方案：为 rewrite 加开关，统一封装 RAG 流程后便可灵活调度。

  总结：

  - 现在 rewrite_question 确实在第一次检索之后才被调用（梯形结构：检索→打分→如果不够好就 rewrite→再走生成/检索）。
  - 这是 LangGraph 官方 Agentic RAG 模板的默认行为，目的是先尝试直接用原问题检索，只有当“grader 觉得无效”时才去改写问题。
  - 如果你要调整成“retriever 之前就做 rewrite”，可以把 rewrite 节点提前，并通过 pack 配置/封装来控制流程。



  ## 那 rewrite_question 和口腔里的 fallback 有什么区别，是否可以去掉一个？


• 二者虽然都叫“兜底”，处理的层级和目标完全不同，不能互相替代：

  1. rewrite_question（RAG 内部的 fallback）
      - 作用域在知识检索流程内部，发生在已经决定“需要查知识库”之后。
      - 如果第一次检索出的文档被 grader 判定“不够相关”，才会触发 rewrite，把用户问题改写后再去检索一次，确保 RAG 能拿到匹配的内容。
      - 这一步没有触及对话流程，只是提高检索质量，成功后仍然由 guidance / final 节点来生成建议。
  2. 口腔图里的 fallback 节点
      - 作用在整体问诊流程的路由层：当槽位不全、判断逻辑没命中任何分支，或者我们还没收集到足够信息时，就落到这个节点，返回一条“请补充信息”的提示。
      - 这时压根还没到“要不要查知识库”的阶段，只是在对话层面兜底，避免流程卡死。

  所以，一个是“检索失败后的补救措施”，另一个是“对话状态不明确时的提示”。两个场景不重合，不能去掉其中任何一个；缺了 rewrite，RAG 有可能拿不到相关文档；
  缺了对话 fallback，用户输入异常时流程会直接崩掉。



  ##
  • grade_documents 的判定非常直白：它把“原始问题 + 本轮检索到的上下文”塞给 grader 模型，让模型回答这段上下文是否足以解答问题，只能回答 yes 或 no。具体
  流程位于 src/graphs/knowledge/pipelines/agentic_graph.py:35 之后：

  1. GradeDocuments dataclass 定义了唯一字段 binary_score（"yes" 或 "no"）。
  2. grade_documents 拿到状态里第一个消息的内容（用户问题）和最后一个消息的内容（检索返回的上下文），把它们填入 prompts.grade。默认的 prompt 在 src/
     graphs/knowledge/pipelines/prompts.py:23 中，文案是：

     判断下列上下文是否能帮助回答问题，若相关回复 yes，否则回复 no。
     上下文：{context}
     问题：{question}
     接着函数自己又补了一句中文提示“请以 JSON 格式回复，例如 {"binary_score": "yes"}。”
  3. 调用 grader_model.with_structured_output(GradeDocuments).invoke(...)，langchain 会强制模型输出符合 dataclass 的 JSON；解析完得到 binary_score。
  4. 如果是 "yes"，流程走 generate_answer；如果是 "no"，则跳到 rewrite_question，也就是触发我们前面说的 fallback，重写问题后重新开始检索。

  总结来说，“判定不好”的标准就是：gr ader 模型判定“上下文无法回答问题”，即 binary_score != "yes"。如果你需要更严或更松，改 prompts.grade（例如引导模型
  只要提到了关键症状就算相关）即可，这个 prompt 可以在 pack.yaml 中自定义；rewrite_question 逻辑本身不用动。



  • 现在的逻辑只判断“有没有回答”而不在第 1 步区分“有诱因 vs 无诱因”，所以只要填了任何内容（哪怕说“没有诱因”）就会直接进入问题 2。思路是先把“有无诱因”存
  入 cause_trigger，后续在生成建议时再利用 matches 去提醒或跳过相关提示；也就是说：

  - 用户答“没有诱因”→ cause_trigger 记录为 no_trigger，图仍继续问术后时间；
  - 用户描述具体诱因→ cause_trigger 记录为 has_trigger 并保存匹配项，同样继续下一问。

  如果你希望【首问】在发现“没有诱因”时给出不同的追问或直接过渡到护理建议，需要在 _decide_next_step 中对 cause_trigger 的 value 做更细的分支。例如：

  1. no_trigger：直接跳到时间问题（当前行为）。
  2. has_trigger：可以立刻提示“先停止XX诱因”，然后再问时间。
  3. 用户答不清楚：继续追问或给“诱因示例”。

  目前的实现相当于“完成记录后继续问时间”，逻辑上是刻意这么设定的。如果你期望“回答‘没有诱因’时不要再问问题 2”，需要提供具体需求（比如直接结束或改问别
  的），我再帮你调整分支规则。