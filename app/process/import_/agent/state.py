# 导入流程全局主图state
# 属性
# 提供创建state的方法
import copy
import json
from typing import TypedDict, Dict, List

from app.shared.runtime.logger import logger


class ImportGraphState(TypedDict):

    # 每次调用流程的标识
    task_id: str

    # 文件状态判断
    is_md_read_enabled: bool
    is_doc_read_enabled: bool

    # 地址路径内容
    local_file_path : str # 存储要解析文件的地址 pdf md
    local_dir:str # 存储生成的md的文件  pdf -> md
    md_path:str  # 专门存储md地址
    doc_path:str # 专门存储pdf地址
    file_title: str # 存储文件名 没有后缀  ergouzi.pdf  ergouzi

    # 文本和切块内容
    md_content: str # 读取md的内容,用于切片
    item_name: str # 模型识别的一个文档对应的主体
    # raw_chunks: list # 原始切块内容
    chunks : list  # 当前存储切块内容
    embeddings_content: list # 存储带有向量的切块内容

    # 主体识别与元数据（核心：由 LLM 动态提取或后台定义）
    # content_type: str  # 内容类型：景点介绍/线路推荐/酒店信息/美食推荐/交通指南/文化民俗
    # region_name: str  # 地区/城市（如：成都、杭州）

    # 动态实体槽位（用于后续检索的精准匹配标签）
    # extracted_entities: Dict[str, List[str]]
    # 从文本中提取的实体字典：
    # {
    #   "scenic_name": ["武侯祠", "锦里"],
    #   "hotel_name": [],
    #   "restaurant_name": ["陈麻婆豆腐"]
    # }

# 提供下对外快速创建的方法
# 模版
default_state:ImportGraphState = {
    "task_id": "",
    "is_md_read_enabled": False,
    "is_doc_read_enabled": False,
    "local_file_path": "",
    "local_dir": "",
    "md_path": "",
    "doc_path": "",
    "file_title": "",
    "md_content": "",
    # "item_name": dict(),
    "item_name": "",
    # "raw_chunks": [],
    "chunks": [],
    "embeddings_content": [],
    # "content_type": "",
    # "region_name": "",
    # "extracted_entities": {}
}

# 提供一个方法,可以返回我们state 并且可以根据传入参数进行对象的属性修改
#  1. 方法() -> default_state 2. 方法(参数) -> default_state (task_id = 传入参数) -> default_state
# 方法(task_id=007,local_file_path="./md.pdf")
def create_default_state(**overriders) -> ImportGraphState:
    """
    :param overriders:  传入的参数 key = x  key = x 转成字典,方便调用update方法修改
    :return:  每次返回是基于模版创建的新的字典对象
    """
    # copy [深 和 浅 copy]
    # 深 copy.deepcopy
    # 浅 copy.copy | dict(字典) | 字典.copy()
    copy_state = copy.deepcopy(default_state)
    # 更新
    #  ** {task_id:xx , local_file_path=}  -> 解构 -> task_id = x  , local_file_path=
    # **overriders -> task_id = x  , local_file_path= -> {task_id:xx , local_file_path=}
    copy_state.update(overriders)
    return copy_state

def get_default_state() -> ImportGraphState:
    """
    返回一个新的状态实例，避免全局变量污染。
    """
    return copy.deepcopy(default_state)


if __name__ == '__main__':
    state = create_default_state(task_id="task_007")
    logger.info(f"测试复制方法: \n {json.dumps(state, ensure_ascii=False, indent=4)}")

    state1 = get_default_state()
    logger.info(f"测试复制方法: \n {json.dumps(state1, ensure_ascii=False, indent=4)}")
