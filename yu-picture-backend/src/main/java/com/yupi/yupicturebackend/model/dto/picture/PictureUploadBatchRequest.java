package com.yupi.yupicturebackend.model.dto.picture;

import lombok.Data;

import java.io.Serializable;
import java.util.List;

/**
 * 批量导入图片请求
 */
@Data
public class PictureUploadBatchRequest implements Serializable {

    /**
     * 搜索词
     */
    private String searchText;
    /**
     * 抓取数量
     */
    private Integer count = 10;

    /**
     * 图片名称的前缀
     */
    private String namePrefix;

    /**
     * 图片的标签
     */
    private List<String> tags;

    private static final long serialVersionUID = 1L;
}
