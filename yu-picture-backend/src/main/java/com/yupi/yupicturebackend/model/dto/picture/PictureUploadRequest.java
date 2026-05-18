package com.yupi.yupicturebackend.model.dto.picture;

import lombok.Data;

import java.io.Serializable;
import java.util.List;

@Data
public class PictureUploadRequest implements Serializable {

    /**
     * 图片 id（用于修改）
     */
    private Long id;

    /**
     * 图片url
     */
    private String fileUrl;


    /**
     * 图片名称
     */
    private String picName;

    /**
     * tags
     */
    private List<String> tags;

    /**
     * 空间id
     */
    private Long spaceId;

    private static final long serialVersionUID = 1L;
}
