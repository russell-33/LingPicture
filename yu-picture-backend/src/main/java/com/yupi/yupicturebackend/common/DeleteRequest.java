package com.yupi.yupicturebackend.common;

import lombok.Data;

import java.io.Serializable;

/**
 * 用于通用的删除请求类
 */
@Data
public class DeleteRequest implements Serializable {
    private Long id;
    private static final long serialVersionId = 1L;
}
