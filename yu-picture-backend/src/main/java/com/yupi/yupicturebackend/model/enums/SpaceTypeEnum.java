package com.yupi.yupicturebackend.model.enums;

import cn.hutool.core.util.ObjectUtil;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.extern.slf4j.Slf4j;

/**
 * 空间类型枚举类
 */
@Slf4j
@Getter
@AllArgsConstructor
public enum SpaceTypeEnum {

    PRIVATE("私有空间", 0),
    TEAM("团队空间", 1);

    private final String text;
    private final int value;

    //根据值获取枚举
    public static SpaceTypeEnum getEnumByValue(Integer value) {
        if (ObjectUtil.isEmpty(value)) {
            return null;
        }
        for (SpaceTypeEnum pictureReviewStatusEnum : SpaceTypeEnum.values()) {
            if (pictureReviewStatusEnum.getValue() == (value)) return pictureReviewStatusEnum;
        }
        return null;
    }


}
