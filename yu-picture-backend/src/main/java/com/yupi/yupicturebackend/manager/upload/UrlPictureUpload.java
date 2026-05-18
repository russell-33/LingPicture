package com.yupi.yupicturebackend.manager.upload;

import cn.hutool.core.io.FileUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.http.HttpResponse;
import cn.hutool.http.HttpUtil;
import cn.hutool.http.Method;
import com.yupi.yupicturebackend.exception.BusinessException;
import com.yupi.yupicturebackend.exception.ErrorCode;
import com.yupi.yupicturebackend.exception.ThrowUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.File;
import java.io.IOException;
import java.net.MalformedURLException;
import java.net.URL;
import java.util.Arrays;
import java.util.List;

/**
 * url文件上传
 */
@Service
@Slf4j
public class UrlPictureUpload extends PictureUploadTemplate {
    @Override
    protected void processFile(Object inputSource, File file) throws IOException {
        String url = (String) inputSource;
        HttpUtil.downloadFile(url, file);
    }

    @Override
    protected String getOriginalFilename(Object inputSource) {
        return FileUtil.mainName((String) inputSource);
    }

    @Override
    protected void validPicture(Object inputSource) {
        String strUrl = (String) inputSource;
        //校验非空
        ThrowUtils.throwIf(StrUtil.isBlank(strUrl), ErrorCode.PARAMS_ERROR, "url为空");
        //校验url格式
        try {
            new URL(strUrl);
        } catch (MalformedURLException e) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "url为空");
        }
        //校验url协议
        ThrowUtils.throwIf(!strUrl.startsWith("http://") && !strUrl.startsWith("https://"),
                ErrorCode.PARAMS_ERROR, "仅支持Http或者https协议的文件地址");
        //发送head请求 验证文件是否存在
        HttpResponse response = null;
        try {
            response = HttpUtil.createRequest(Method.HEAD, strUrl).execute();
            //仅对能获取到的信息做校验
            if (!response.isOk()) return;
            //校验文件类型
            String contentType = response.header("Content-Type");

            log.debug(contentType);
            if (StrUtil.isNotBlank(contentType)) {
                final List<String> ALLOW_FORMAT_LIST = Arrays.asList("image/jpeg", "image/png", "image/webp", "image/jpg");
                ThrowUtils.throwIf(!ALLOW_FORMAT_LIST.contains(contentType.toLowerCase()), ErrorCode.PARAMS_ERROR, "文件格式错误");
            }
            //校验文件大小
            String contentLength = response.header("Content-Length");
            if (StrUtil.isNotBlank(contentLength)) {
                try {
                    long fileSize = Long.parseLong(contentLength);
                    final long ONE_M = 1024 * 1024;
                    ThrowUtils.throwIf(fileSize > ONE_M * 2, ErrorCode.PARAMS_ERROR, "文件大小不能超过2MB");
                } catch (NumberFormatException e) {
                    throw new BusinessException(ErrorCode.PARAMS_ERROR, "文件大小格式异常");
                }
            }
        } finally {
            //关闭流
            if (response != null) response.close();
        }
    }
}
