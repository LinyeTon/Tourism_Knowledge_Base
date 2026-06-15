import re

from app.infra.persistence.history_repository import history_repository
from app.process.query.agent.state import QueryGraphState
from app.shared.runtime.load_prompt import load_prompt
from app.shared.utils.task_utils import add_done_task,add_running_task,push_to_session
from app.shared.utils.sse_utils import SSEEvent
from app.shared.runtime.logger import logger
from app.infra.persistence.history_repository import history_repository
from app.infra.llm.providers import llm_provider
import time
import sys


def check_state_has_answer(state):
    """
    检测是否有answer!
      有返回对应的字符串
    :param state:
    :return:
    """
    answer = state.get("answer")
    if not answer:
        logger.info(f"没有answer,证明有明确的item_names正常返回结果!!")
        return False
    # 我们就的给前端返回数据
    # is_stream = True -> 打字机模型 -> state (final)
    # is_stream = False -> answer -> state
    is_stream = state.get("is_stream", False)

    if is_stream:
        # 流式返回
        # answer "A B C D E F G "
        for ch in answer:
            push_to_session(
                state.get("session_id") , SSEEvent.DELTA , {"delta":ch}
            )
            #time.sleep(0.06)
    return True


def get_data_and_validates(state):
    """
      获取数据并且校验
    :param state:
    :return:
    """
    reranked_docs = state.get("reranked_docs",[])
    item_names = state.get("item_names",[])
    rewritten_query = state.get("rewritten_query")

    if len(reranked_docs) == 0 or len(item_names) == 0 or not rewritten_query:
        logger.info(f"没有reranker_docs,item_names,rewritten_query,请检查参数!!")
        raise ValueError("没有reranker_docs,item_names,rewritten_query,请检查参数!!")

    history = history_repository.list_recent(state.get("session_id"),limit=10)

    return reranked_docs,history,item_names,rewritten_query


def load_prompt_text(reranker_docs, history, item_names, rewritten_query) -> str:
    """
    加载提示词文件! 拼接提示词!
    :param reranker_docs: -> context
    :param history: -> 聊天记录
    :param item_names: ->  关联主体
    :param rewritten_query: -> 问题
    :return:
    """
    # 拼接context  reranker_docs [{title,text,type,url[取图片],score}]
    # 标题: title , 来源: 向量库 / 网络搜索 , reranker模型评分: score \n
    # 内容: xxx
    # \n\n
    context =  ""
    for doc in reranker_docs:
        context += (f"标题: {doc['title']} 来源: {'网络搜索' if doc['type'] == 'web' else '向量库'} , "
                    f"reranker模型评分: {doc['score']} \n"
                    f"内容: {doc['text']}\n\n")
    # history 拼接
    history_text = ""
    final_message_list = [item for item in history if
                          item.get("item_names") and len(item.get('item_names')) > 0]
    if final_message_list and len(final_message_list) > 0:
        # item -> 聊天记录 _id role text rewritten_query ts item_names image_urls
        for index, item in enumerate(final_message_list, start=1):
            history_text += (f"序号:{index},类型:{'提问' if item['role'] == 'user' else '回答'},"
                             f"内容:{item['rewritten_query'] if item['role'] == 'user' else item['text']},"
                             f"关联主体:{','.join(item['item_names'])}\n")
    else:
        history_text = "没有对话记录!"

    # item_names关联
    item_names_text = ",".join(item_names)

    # 加载提示词模版
    prompt_text = load_prompt("answer_out",context = context,history=history_text,
                              item_names=item_names_text,question = rewritten_query)

    return prompt_text


# def call_llm_generate(answer_prompt_text, state):
#     """
#     调用模型生成答案 文本答案
#     :param answer_prompt_text:
#     :param state:
#     :return:
#     """
#     final_answer = ""
#     # 1. 获取模型对象
#     llm_client = llm_provider.chat()
#     # 2. 判断是否是流式调用
#     is_stream = state.get("is_stream", False)
#     if is_stream:
#         # 一段一段文本返回
#         # langchain  init_chat_model()   model  invoke  1 次    stream  1 2 3 4
#         stream = llm_client.stream(answer_prompt_text)
#         for chunk in stream:
#             # 当前段
#             current_content = chunk.content
#             push_to_session(
#                 state.get("session_id") , SSEEvent.DELTA , {"delta":current_content}
#             )
#             final_answer += current_content
#     else:
#         response = llm_client.invoke(answer_prompt_text)
#         final_answer = response.content
#
#     state['answer'] = final_answer


import re


def call_llm_generate(answer_prompt_text, state):
    """
    调用模型生成答案 文本答案
    :param answer_prompt_text:
    :param state:
    :return:
    """
    final_answer = ""
    # 1. 获取模型对象
    llm_client = llm_provider.chat()
    # --- 新增：提取参考内容中真实的 URL 列表，用于防幻觉校验 ---
    valid_urls = set()
    reranked_docs = state.get("reranked_docs", [])
    for doc in reranked_docs:
        if doc.get("url"):
            valid_urls.add(doc["url"])
    # --- 新增：流式缓冲区与校验逻辑 ---
    buffer = ""
    # 匹配 <URL> 的正则
    url_pattern = re.compile(r'<(https?://[^>]+)>')
    # 匹配 【图片】 标记的正则
    image_tag_pattern = re.compile(r'【图片】')

    def process_buffer(is_end=False):
        """
        处理缓冲区里的内容，返回安全可输出的文本
        :param is_end: 是否是流的结尾
        """
        nonlocal buffer
        safe_text = ""
        # 1. 检查是否包含完整的 <URL>
        url_matches = list(url_pattern.finditer(buffer))
        if url_matches:
            last_end = 0
            for match in url_matches:
                # 放行匹配到的 URL 前面的普通文本
                safe_text += buffer[last_end:match.start()]
                extracted_url = match.group(1)
                # 核心校验：如果 URL 在白名单中，放行；否则丢弃（防幻觉）
                if extracted_url in valid_urls:
                    safe_text += match.group(0)  # 保留原始的 <URL>
                # else: 什么都不加，相当于把幻觉 URL 删掉了
                last_end = match.end()
            safe_text += buffer[last_end:url_matches[-1].end()]
            buffer = buffer[url_matches[-1].end():]  # 缓冲区只保留未处理的部分
        # 2. 检查是否包含完整的 【图片】 标记
        tag_matches = list(image_tag_pattern.finditer(buffer))
        if tag_matches:
            last_end = 0
            for match in tag_matches:
                safe_text += buffer[last_end:match.start()]
                # 如果后面没有任何真实 URL 跟随，【图片】标记也没有意义，直接丢弃
                # 如果后面跟着的是白名单 URL，在上面一步已经拼接好了，这里也丢弃【图片】标记本身（或者保留，视你的前端需求）
                # 此处我们选择丢弃【图片】标记，因为前端通常只需要 <img_url>
                last_end = match.end()
            safe_text += buffer[last_end:tag_matches[-1].end()]
            buffer = buffer[tag_matches[-1].end():]
        # 3. 如果流结束了，强制清空缓冲区（不校验，直接输出残余，或者直接丢弃残余）
        if is_end:
            safe_text += buffer
            buffer = ""
        # 4. 如果缓冲区还没闭合，但包含了可能形成 URL 的字符，继续缓冲（不输出）
        #    否则，放行缓冲区内容
        if not is_end and ('<' in buffer or '【' in buffer):
            # 把不含敏感字符的部分放行，只保留敏感部分
            safe_part_len = min(buffer.find('<') if '<' in buffer else len(buffer),
                                buffer.find('【') if '【' in buffer else len(buffer))
            if safe_part_len > 0:
                safe_text += buffer[:safe_part_len]
                buffer = buffer[safe_part_len:]
        elif not is_end:
            # 缓冲区里没有敏感字符，全部放行
            safe_text += buffer
            buffer = ""
        return safe_text

    # 2. 判断是否是流式调用
    is_stream = state.get("is_stream", False)
    if is_stream:
        stream = llm_client.stream(answer_prompt_text)
        for chunk in stream:
            current_content = chunk.content
            # 将新内容加入缓冲区
            buffer += current_content
            # 尝试处理缓冲区，获取可安全输出的文本
            safe_content = process_buffer(is_end=False)
            if safe_content:
                push_to_session(
                    state.get("session_id"), SSEEvent.DELTA, {"delta": safe_content}
                )
            final_answer += safe_content
        # 流结束，刷新缓冲区剩余内容
        remaining_content = process_buffer(is_end=True)
        if remaining_content:
            push_to_session(
                state.get("session_id"), SSEEvent.DELTA, {"delta": remaining_content}
            )
            final_answer += remaining_content
    else:
        response = llm_client.invoke(answer_prompt_text)
        # 非流式直接一次性校验过滤
        final_answer = response.content
        url_matches = url_pattern.finditer(final_answer)
        for match in url_matches:
            if match.group(1) not in valid_urls:
                final_answer = final_answer.replace(match.group(0), '')
        # 清理孤立的【图片】标签
        final_answer = image_tag_pattern.sub('', final_answer)
    state['answer'] = final_answer


def extract_image_urls(reranker_docs, state):
    """
     提取图片 url text 装到列表! 放到state
    :param reranker_docs:
    :param state:
    :return:
    """
    # 1.定义一个正则
    # 2.定义存储数据的列表
    image_urls: list[str] = []
    # 匹配 markdown 图片正则
    reg = re.compile(r"\!\[.*?\]\((.*?)\)")
    # 3.循环 -> url / text
    for doc in reranker_docs:
        url = doc.get("url","")
        text = doc.get("text","")
        # 提取url
        if url and url.endswith((".jpg",".png",".gif",".jpeg",".svg")):
            image_urls.append(url)
        # 提取text
        for image_url in reg.findall(text):
            if image_url not in image_urls:
                image_urls.append(image_url)
    # 4.给state赋值
    state['image_urls'] = image_urls
    return state


def save_history_message(state):
    history_repository.save_message(
        session_id=state.get("session_id"),
        role="assistant",
        text=state.get("answer"),
        rewritten_query=state.get("rewritten_query"),
        item_names=state.get("item_names",[]),
        image_urls=state.get("image_urls",[])
    )


def generate_answer(state: QueryGraphState) -> QueryGraphState:
    """
    答案生成服务：
    1. 检查前置答案（如有追问或拒绝回答，直接输出）
    2. 构建 Prompt（用户问题 + 历史对话 + TopK 文档）
    3. 调用 LLM 生成最终答案（支持流式推送）
    4. 从引用文档中提取图片 URL
    5. 写入 MongoDB 历史记录
    6. 回写 answer 和 image_urls
    """
    # 1. 判断是否有answer内容并且返回对应的状态
    has_answer = check_state_has_answer(state)
    # 2. 如果没有结果,才调用模型进行答案生成
    if not has_answer:
        # 3. 没有结果,获取并且校验参数
        reranker_docs,history,item_names,rewritten_query = get_data_and_validates(state)
        # 4. 拼接提示词的上下文,加载外部的提示词文件
        answer_prompt_text = load_prompt_text(reranker_docs,history,item_names,rewritten_query)

        # 5. 调用模型生成(文本)答案
        call_llm_generate(answer_prompt_text, state)

        # 6. 提取图片列表 -> state[image_urls] = []
        extract_image_urls(reranker_docs,state)

    save_history_message(state)
    return state