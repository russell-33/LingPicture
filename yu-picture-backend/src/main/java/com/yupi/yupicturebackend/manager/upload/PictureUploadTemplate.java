package com.yupi.yupicturebackend.manager.upload;

import cn.hutool.core.collection.CollUtil;
import cn.hutool.core.date.DateUtil;
import cn.hutool.core.io.FileTypeUtil;
import cn.hutool.core.io.FileUtil;
import cn.hutool.core.util.NumberUtil;
import cn.hutool.core.util.RandomUtil;
import cn.hutool.crypto.SecureUtil;
import cn.hutool.http.HttpResponse;
import cn.hutool.http.HttpUtil;
import cn.hutool.http.Method;
import com.qcloud.cos.COSClient;

import com.qcloud.cos.model.PutObjectResult;
import com.qcloud.cos.model.ciModel.persistence.CIObject;
import com.qcloud.cos.model.ciModel.persistence.ImageInfo;
import com.qcloud.cos.model.ciModel.persistence.ProcessResults;
import com.yupi.yupicturebackend.config.CosClientConfig;
import com.yupi.yupicturebackend.exception.BusinessException;
import com.yupi.yupicturebackend.exception.ErrorCode;
import com.yupi.yupicturebackend.manager.CosManager;
import com.yupi.yupicturebackend.model.dto.file.UploadPictureResult;
import lombok.extern.slf4j.Slf4j;

import javax.annotation.Resource;
import java.io.File;
import java.io.IOException;
import java.util.Arrays;
import java.util.Date;
import java.util.List;

@Slf4j
public abstract class PictureUploadTemplate {
    @Resource
    private CosClientConfig cosClientConfig;

    @Resource
    private CosManager cosManager;

    /**
     * 生成临时文件
     *
     * @param inputSource
     * @param file
     */
    protected abstract void processFile(Object inputSource, File file) throws IOException;

    /**
     * 获取输入源的原始文件名
     *
     * @param inputSource
     * @return
     */
    protected abstract String getOriginalFilename(Object inputSource);

    /**
     * 校验输入源
     *
     * @param inputSource
     */
    protected abstract void validPicture(Object inputSource);

    /**
     * 上传图片到COS
     *
     * @param inputSource
     * @param uploadPathPrefix
     * @return
     */
    public UploadPictureResult uploadPictureResult(Object inputSource, String uploadPathPrefix) {
        //1 校验图片
        validPicture(inputSource);
        //可以做
        //1.1计算文件指纹
//        String md5 = SecureUtil.md5()
        //1.2查询数据库 是否存在
        //1.3若存在 无需上传到cos 直接返回
        //1.4若不存在 继续

        //2 图片上传地址
        String uuid = RandomUtil.randomString(16);
        String originalFilename = getOriginalFilename(inputSource);
        String suffix = FileUtil.getSuffix(originalFilename);


        final List<String> ALLOW_SUFFIX_LIST =
                Arrays.asList("jpeg", "png", "webp", "jpg");

        String uploadFileName = String.format("%s_%s.%s", DateUtil.formatDate(new Date()), uuid,
                suffix);
        if (inputSource instanceof String && !ALLOW_SUFFIX_LIST.contains(suffix)) {
            //需要拼接文件的后缀
            //head请求只获得响应头
            HttpResponse response = HttpUtil.createRequest(Method.HEAD, (String) inputSource).execute();
            String contentType = response.header("Content-Type");
            String[] split = contentType.split("/");
            suffix = split[1];

            uploadFileName = String.format("%s_%s.%s", DateUtil.formatDate(new Date()), uuid,
                    suffix);
        }

        String uploadPath = String.format("/%s/%s", uploadPathPrefix, uploadFileName);
        //3 解析结果并返回
        File file = null;
        try {
            file = File.createTempFile(uploadPath, null);
            //获取临时文件到服务器
            processFile(inputSource, file);
            //上传图片到对象存储
            PutObjectResult putObjectResult = cosManager.putPictureObject(uploadPath, file);
            //获取图片信息对象
            ImageInfo imageInfo = putObjectResult.getCiUploadResult().getOriginalInfo().getImageInfo();
            ProcessResults processResults = putObjectResult.getCiUploadResult().getProcessResults();
            List<CIObject> objectList = processResults.getObjectList();
            if (CollUtil.isNotEmpty(objectList)) {
                //获取压缩后得到的结果
                CIObject compressCIObject = objectList.get(0);
                //缩略图默认是压缩图
                CIObject thumbnailCIobject = compressCIObject;
                //有缩略图才会去获取
                if (objectList.size() > 1) thumbnailCIobject = objectList.get(1);
                return buildResult(originalFilename, compressCIObject, thumbnailCIobject, imageInfo);
            }
            return getUploadPictureResult(uploadPath, originalFilename, file, imageInfo);
        } catch (IOException e) {
            log.error("图片上传到对象存储失败", e);
            throw new BusinessException(ErrorCode.SYSTEM_ERROR);
        } finally {
            deleteCachedFile(file);
        }
        //清理临时文件
    }

    /**
     * 封装返回结果
     *
     * @param originalFilename
     * @param compressCIObject
     * @return
     */
    private UploadPictureResult buildResult(String originalFilename, CIObject compressCIObject, CIObject thumbnailCIobject, ImageInfo imageInfo) {
        //封装返回结果
        UploadPictureResult uploadPictureResult = new UploadPictureResult();
        //设置压缩后的原图地址
        uploadPictureResult.setUrl(cosClientConfig.getHost() + "/" + compressCIObject.getKey());
        //设置缩略图
        uploadPictureResult.setThumbnailUrl(cosClientConfig.getHost() + "/" + thumbnailCIobject.getKey());
        uploadPictureResult.setPicName(FileUtil.mainName(originalFilename));
        uploadPictureResult.setPicSize(compressCIObject.getSize().longValue());
        uploadPictureResult.setPicWidth(compressCIObject.getWidth());
        uploadPictureResult.setPicHeight(compressCIObject.getHeight());
        uploadPictureResult.setPicColor(imageInfo.getAve());
        uploadPictureResult.setPicScale(NumberUtil.round(compressCIObject.getWidth() * 1.0 / compressCIObject.getHeight(), 2).doubleValue());
        uploadPictureResult.setPicFormat(compressCIObject.getFormat());
        return uploadPictureResult;
    }

    /**
     * 封装返回结果
     *
     * @param uploadPath
     * @param originalFilename
     * @param file
     * @param imageInfo
     * @return
     */
    private UploadPictureResult getUploadPictureResult(String uploadPath, String originalFilename, File file, ImageInfo imageInfo) {
        //封装返回结果
        UploadPictureResult uploadPictureResult = new UploadPictureResult();
        uploadPictureResult.setUrl(cosClientConfig.getHost() + "/" + uploadPath);
        uploadPictureResult.setPicName(FileUtil.mainName(originalFilename));
        uploadPictureResult.setPicColor(imageInfo.getAve());
        uploadPictureResult.setPicSize(FileUtil.size(file));
        uploadPictureResult.setPicWidth(imageInfo.getWidth());
        uploadPictureResult.setPicHeight(imageInfo.getHeight());
        uploadPictureResult.setPicScale(NumberUtil.round(imageInfo.getWidth() * 1.0 / imageInfo.getHeight(), 2).doubleValue());
        uploadPictureResult.setPicFormat(imageInfo.getFormat());
        return uploadPictureResult;
    }


    /**
     * 清理临时文件
     *
     * @param file
     */
    public static void deleteCachedFile(File file) {
        if (file != null) {
            //删除临时文件
            boolean deleteResult = file.delete();
            if (!deleteResult) {
                log.error("file delete error uploadPath = {}", file.getAbsoluteFile());
            }
        }
    }


}
