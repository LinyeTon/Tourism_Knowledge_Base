from pydantic import BaseModel, Field
from typing import List

class IngestionEntityExtractor(BaseModel):
    content_type: str = Field(
        description="判断这段文本的核心类型，必须是以下之一：景点攻略、线路推荐、酒店信息、美食推荐、交通指南"
    )
    region_name: str = Field(description="文本涵盖的城市或地区名称，例如：成都、杭州")
    scenic_names: List[str] = Field(default=[], description="文本中具体提及的景点或景区名称，如：宽窄巷子、西湖")
    hotel_names: List[str] = Field(default=[], description="文本中具体提及的酒店、民宿、住宿名称")
    restaurant_names: List[str] = Field(default=[], description="文本中具体提及的餐厅、饭店或特色美食小吃名称，如：火锅、龙抄手")
    route_names: List[str] = Field(default=[], description="文本中是否包含特定的旅游线路名称，如：成都三日游、环湖骑行线")