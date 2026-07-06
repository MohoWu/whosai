from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LocalizedText:
    en: str
    zh_cn: str


@dataclass(frozen=True, slots=True)
class KeywordCategory:
    name: LocalizedText
    keywords: tuple[LocalizedText, ...]


def _text(en: str, zh_cn: str) -> LocalizedText:
    return LocalizedText(en=en, zh_cn=zh_cn)


CANDIDATE_KEYWORD_CATEGORIES = (
    KeywordCategory(
        name=_text("Public places", "公共场所"),
        keywords=(
            _text("airport", "机场"),
            _text("hospital", "医院"),
            _text("library", "图书馆"),
            _text("supermarket", "超市"),
            _text("museum", "博物馆"),
            _text("cinema", "电影院"),
            _text("hotel", "酒店"),
            _text("playground", "游乐场"),
        ),
    ),
    KeywordCategory(
        name=_text("Kitchen", "厨房"),
        keywords=(
            _text("kettle", "水壶"),
            _text("toaster", "烤面包机"),
            _text("fridge", "冰箱"),
            _text("oven", "烤箱"),
            _text("blender", "搅拌机"),
            _text("frying pan", "煎锅"),
            _text("chopping board", "砧板"),
            _text("mug", "马克杯"),
        ),
    ),
    KeywordCategory(
        name=_text("Natural places", "自然景观"),
        keywords=(
            _text("forest", "森林"),
            _text("river", "河流"),
            _text("desert", "沙漠"),
            _text("mountain", "山"),
            _text("waterfall", "瀑布"),
            _text("cave", "洞穴"),
            _text("island", "岛屿"),
            _text("volcano", "火山"),
        ),
    ),
    KeywordCategory(
        name=_text("Weather", "天气"),
        keywords=(
            _text("rain", "雨"),
            _text("snow", "雪"),
            _text("fog", "雾"),
            _text("wind", "风"),
            _text("hail", "冰雹"),
            _text("thunder", "雷声"),
            _text("lightning", "闪电"),
            _text("heatwave", "热浪"),
        ),
    ),
    KeywordCategory(
        name=_text("Travel bag", "旅行随身物品"),
        keywords=(
            _text("passport", "护照"),
            _text("ticket", "票"),
            _text("charger", "充电器"),
            _text("camera", "相机"),
            _text("headphones", "耳机"),
            _text("umbrella", "雨伞"),
            _text("toothbrush", "牙刷"),
            _text("snack", "零食"),
        ),
    ),
    KeywordCategory(
        name=_text("Household objects", "家居用品"),
        keywords=(
            _text("mirror", "镜子"),
            _text("pillow", "枕头"),
            _text("lamp", "台灯"),
            _text("key", "钥匙"),
            _text("clock", "时钟"),
            _text("towel", "毛巾"),
            _text("vacuum", "吸尘器"),
            _text("remote", "遥控器"),
        ),
    ),
    KeywordCategory(
        name=_text("Body reactions", "身体反应"),
        keywords=(
            _text("yawn", "打哈欠"),
            _text("sneeze", "打喷嚏"),
            _text("hiccup", "打嗝"),
            _text("blush", "脸红"),
            _text("shiver", "发抖"),
            _text("cough", "咳嗽"),
            _text("sweat", "出汗"),
            _text("heartbeat", "心跳"),
        ),
    ),
    KeywordCategory(
        name=_text("Ways to move", "移动方式"),
        keywords=(
            _text("walking", "走路"),
            _text("running", "跑步"),
            _text("crawling", "爬行"),
            _text("hopping", "蹦跳"),
            _text("swimming", "游泳"),
            _text("cycling", "骑自行车"),
            _text("climbing", "攀爬"),
            _text("skating", "滑冰"),
        ),
    ),
    KeywordCategory(
        name=_text("Sounds", "声音"),
        keywords=(
            _text("whisper", "耳语"),
            _text("applause", "掌声"),
            _text("laughter", "笑声"),
            _text("footsteps", "脚步声"),
            _text("alarm", "闹铃"),
            _text("siren", "警笛"),
            _text("knock", "敲门声"),
            _text("ringtone", "铃声"),
        ),
    ),
    KeywordCategory(
        name=_text("Textures", "质感"),
        keywords=(
            _text("crunchy", "酥脆"),
            _text("smooth", "光滑"),
            _text("sticky", "黏"),
            _text("fluffy", "蓬松"),
            _text("chewy", "有嚼劲"),
            _text("brittle", "易碎"),
            _text("slimy", "黏滑"),
            _text("grainy", "有颗粒感"),
        ),
    ),
    KeywordCategory(
        name=_text("Everyday annoyances", "日常烦恼"),
        keywords=(
            _text("low battery", "电量不足"),
            _text("lost keys", "钥匙丢了"),
            _text("wet socks", "袜子湿了"),
            _text("traffic jam", "堵车"),
            _text("slow Wi-Fi", "网络很慢"),
            _text("spam call", "骚扰电话"),
            _text("long queue", "排长队"),
            _text("paper cut", "被纸割伤"),
        ),
    ),
    KeywordCategory(
        name=_text("Online life", "网络生活"),
        keywords=(
            _text("password", "密码"),
            _text("meme", "网络梗"),
            _text("video call", "视频通话"),
            _text("notification", "通知"),
            _text("advert", "广告"),
            _text("search", "搜索"),
            _text("emoji", "表情符号"),
            _text("download", "下载"),
        ),
    ),
)
