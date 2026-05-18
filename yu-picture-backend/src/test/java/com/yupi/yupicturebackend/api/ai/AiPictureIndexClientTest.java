package com.yupi.yupicturebackend.api.ai;

import com.yupi.yupicturebackend.config.AiConfig;
import com.yupi.yupicturebackend.config.AiInternalAuth;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.client.RestTemplate;

import java.util.Arrays;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AiPictureIndexClientTest {

    @Test
    void removePictureIndexCallsAiDeleteEndpointWithInternalToken() {
        RestTemplate restTemplate = mock(RestTemplate.class);
        when(restTemplate.exchange(
                eq("http://ai.test/api/v1/rag/picture/index/123?space_id=456"),
                eq(HttpMethod.DELETE),
                org.mockito.ArgumentMatchers.<HttpEntity<Void>>any(),
                eq(String.class)
        )).thenReturn(ResponseEntity.ok("{\"ok\":true}"));

        AiConfig aiConfig = new AiConfig();
        aiConfig.setUrl("http://ai.test/");
        aiConfig.setInternalToken("test-token");

        AiInternalAuth aiInternalAuth = new AiInternalAuth();
        ReflectionTestUtils.setField(aiInternalAuth, "aiConfig", aiConfig);

        AiPictureIndexClient client = new AiPictureIndexClient();
        ReflectionTestUtils.setField(client, "aiRestTemplate", restTemplate);
        ReflectionTestUtils.setField(client, "aiConfig", aiConfig);
        ReflectionTestUtils.setField(client, "aiInternalAuth", aiInternalAuth);

        client.removePictureIndex(123L, 456L);

        ArgumentCaptor<HttpEntity<Void>> entityCaptor = ArgumentCaptor.forClass(HttpEntity.class);
        verify(restTemplate).exchange(
                eq("http://ai.test/api/v1/rag/picture/index/123?space_id=456"),
                eq(HttpMethod.DELETE),
                entityCaptor.capture(),
                eq(String.class)
        );
        assertEquals("test-token", entityCaptor.getValue().getHeaders().getFirst(AiInternalAuth.INTERNAL_TOKEN_HEADER));
    }

    @Test
    void upsertPictureIndexSendsLatestMetadataDescriptionToAiBuildIndex() {
        RestTemplate restTemplate = mock(RestTemplate.class);
        when(restTemplate.postForEntity(
                eq("http://ai.test/api/v1/rag/picture/build-index"),
                org.mockito.ArgumentMatchers.<HttpEntity<Map<String, Object>>>any(),
                eq(String.class)
        )).thenReturn(ResponseEntity.ok("{\"indexed\":1,\"errors\":[]}"));

        AiConfig aiConfig = new AiConfig();
        aiConfig.setUrl("http://ai.test/");
        aiConfig.setInternalToken("test-token");

        AiInternalAuth aiInternalAuth = new AiInternalAuth();
        ReflectionTestUtils.setField(aiInternalAuth, "aiConfig", aiConfig);

        AiPictureIndexClient client = new AiPictureIndexClient();
        ReflectionTestUtils.setField(client, "aiRestTemplate", restTemplate);
        ReflectionTestUtils.setField(client, "aiConfig", aiConfig);
        ReflectionTestUtils.setField(client, "aiInternalAuth", aiInternalAuth);

        client.upsertPictureIndex(
                123L,
                456L,
                "红色赛车",
                "赛道上的红色赛车",
                "素材",
                Arrays.asList("汽车", "自定义标签"),
                "https://img.test/1.webp"
        );

        ArgumentCaptor<HttpEntity<Map<String, Object>>> entityCaptor = ArgumentCaptor.forClass(HttpEntity.class);
        verify(restTemplate).postForEntity(
                eq("http://ai.test/api/v1/rag/picture/build-index"),
                entityCaptor.capture(),
                eq(String.class)
        );

        HttpEntity<Map<String, Object>> entity = entityCaptor.getValue();
        assertEquals("test-token", entity.getHeaders().getFirst(AiInternalAuth.INTERNAL_TOKEN_HEADER));
        Map<String, Object> body = entity.getBody();
        assertEquals(456L, body.get("space_id"));
        assertEquals(List.of(123L), body.get("picture_ids"));
        assertEquals(List.of("https://img.test/1.webp"), body.get("image_urls"));
        assertEquals(List.of("红色赛车"), body.get("picture_names"));
        String description = ((List<String>) body.get("descriptions")).get(0);
        assertTrue(description.contains("红色赛车"));
        assertTrue(description.contains("赛道上的红色赛车"));
        assertTrue(description.contains("汽车,自定义标签"));
        assertTrue(description.contains("素材"));
    }
}
