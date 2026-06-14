import sys
import time
import json

from app.shared.runtime.logger import node_log
from app.rag.query.rrf_service import fuse_by_rrf
from app.shared.utils.task_utils import add_done_task, add_running_task

@node_log("node_rrf")
def node_rrf(state):
    """
    节点功能：Reciprocal Rank Fusion
    将多路召回的结果（向量、HyDE、Web）进行加权融合排序。
    """
    add_running_task(state["session_id"], sys._getframe().f_code.co_name, state.get("is_stream"))
    time.sleep(0.5)
    state = fuse_by_rrf(state)
    add_done_task(state['session_id'], sys._getframe().f_code.co_name, state.get("is_stream"))
    return state


if __name__ == "__main__":
    mock_state = {
        "session_id": "test_rrf_session",
        "is_stream": False,
        "original_query": "成都有什么好吃的？",
        "rewritten_query": "成都美食推荐？",
        # "item_names": {"content_type": "美食推荐", "region_name": "成都"},
        "item_name": json.dumps(["美食推荐", "成都"], ensure_ascii=False)
    }

    from app.process.query.agent.nodes.node_search_embedding import node_search_embedding
    from app.process.query.agent.nodes.node_search_embedding_hyde import node_search_embedding_hyde

    emb_res = node_search_embedding(mock_state)
    hyde_res = node_search_embedding_hyde(mock_state)
    mock_state["embedding_chunks"] = emb_res.get("embedding_chunks") or []
    mock_state["hyde_embedding_chunks"] = hyde_res.get("hyde_embedding_chunks") or []

    result = node_rrf(mock_state)
    print(result)