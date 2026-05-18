package com.yupi.yupicturebackend.api.ai;

import com.yupi.yupicturebackend.config.AiConfig;
import com.yupi.yupicturebackend.config.AiInternalAuth;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import javax.annotation.Resource;

/**
 * AI 图片索引客户端。
 */
@Component
@Slf4j
public class AiPictureIndexClient {

    @Resource
    private RestTemplate aiRestTemplate;

    @Resource
    private AiConfig aiConfig;

    @Resource
    private AiInternalAuth aiInternalAuth;

    @Async
    public void removePictureIndex(Long pictureId, Long spaceId) {
        if (pictureId == null || pictureId <= 0) {
            return;
        }
        long indexSpaceId = spaceId == null ? 0L : spaceId;
        String url = trimTrailingSlash(aiConfig.getUrl())
                + "/api/v1/rag/picture/index/" + pictureId
                + "?space_id=" + indexSpaceId;

        HttpHeaders headers = new HttpHeaders();
        aiInternalAuth.addInternalToken(headers);
        HttpEntity<Void> entity = new HttpEntity<>(headers);
        try {
            aiRestTemplate.exchange(url, HttpMethod.DELETE, entity, String.class);
        } catch (RestClientException e) {
            log.warn("清理 AI 图片索引失败，pictureId={}, spaceId={}, error={}", pictureId, indexSpaceId, e.getMessage());
        }
    }

    private String trimTrailingSlash(String url) {
        if (url == null || url.isBlank()) {
            return "";
        }
        while (url.endsWith("/")) {
            url = url.substring(0, url.length() - 1);
        }
        return url;
    }
}
