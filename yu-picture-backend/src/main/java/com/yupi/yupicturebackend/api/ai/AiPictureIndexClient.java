package com.yupi.yupicturebackend.api.ai;

import com.yupi.yupicturebackend.config.AiConfig;
import com.yupi.yupicturebackend.config.AiInternalAuth;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import javax.annotation.Resource;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

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

    public void upsertPictureIndex(Long pictureId,
                                   Long spaceId,
                                   String name,
                                   String introduction,
                                   String category,
                                   List<String> tags,
                                   String imageUrl) {
        if (pictureId == null || pictureId <= 0) {
            return;
        }
        long indexSpaceId = spaceId == null ? 0L : spaceId;
        String url = trimTrailingSlash(aiConfig.getUrl()) + "/api/v1/rag/picture/build-index";
        String tagText = tags == null ? "" : String.join(",", tags);
        String description = String.format("%s：%s。标签：%s。分类：%s。",
                nullToEmpty(name), nullToEmpty(introduction), tagText, nullToEmpty(category));

        Map<String, Object> body = new HashMap<>();
        body.put("space_id", indexSpaceId);
        body.put("picture_ids", List.of(pictureId));
        body.put("image_urls", List.of(nullToEmpty(imageUrl)));
        body.put("picture_names", List.of(nullToEmpty(name)));
        body.put("descriptions", List.of(description));

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        aiInternalAuth.addInternalToken(headers);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);
        try {
            aiRestTemplate.postForEntity(url, entity, String.class);
        } catch (RestClientException e) {
            log.warn("刷新 AI 图片索引失败，pictureId={}, spaceId={}, error={}", pictureId, indexSpaceId, e.getMessage());
            throw e;
        }
    }

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
            throw e;
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

    private String nullToEmpty(String text) {
        return text == null ? "" : text;
    }
}
