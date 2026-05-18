package com.yupi.yupicturebackend.constant;

import java.util.Arrays;
import java.util.List;

/**
 * 图片分类和标签选项。
 */
public interface PictureTagCategoryConstant {

    List<String> TAG_LIST = Arrays.asList(
            "抽象", "动物", "动漫", "卡通", "CGI", "网络朋克", "幻想", "游戏",
            "女性", "男性", "风景", "中世纪", "网红事物", "MMD", "音乐", "自然",
            "像素艺术", "放松", "复古", "科幻", "运动", "科技", "电视节目", "汽车",
            "未指定样式"
    );

    List<String> CATEGORY_LIST = Arrays.asList("模板", "电商", "表情包", "素材", "海报", "其他");
}
