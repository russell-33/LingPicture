package com.yupi.yupicturebackend.model.enums;

import cn.hutool.core.util.ObjectUtil;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.extern.slf4j.Slf4j;

/**
 * 图片审核状态枚举
 */
@Slf4j
@Getter
@AllArgsConstructor
public enum PictureReviewStatusEnum {


    REVIEWING("待审核", 0),
    PASS("通过", 1),
    REJECT("拒绝", 2);

    private final String text;

    private final int value;

    //根据值获取枚举
    public static PictureReviewStatusEnum getEnumByValue(Integer value) {
        if (ObjectUtil.isEmpty(value)) {
            return null;
        }
        for (PictureReviewStatusEnum pictureReviewStatusEnum : PictureReviewStatusEnum.values()) {
            if (pictureReviewStatusEnum.getValue() == (value)) return pictureReviewStatusEnum;
        }
        return null;
    }


}
