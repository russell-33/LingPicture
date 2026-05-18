package com.yupi.yupicturebackend.model.dto.space.analyze;

import lombok.Data;

import java.io.Serializable;

/**
 * 通用空间分析请求
 */
@Data
public class SpaceAnalyzeRequest implements Serializable {
    private static final long serialVersionUID = 1006753366543373933L;
    /**
     * 空间id
     */
    private Long spaceId;
    /**
     * 是否查询公共图库
     */
    private boolean queryPublic;
    /**
     * 是否查询所有图库
     */
    private boolean queryAll;


}
