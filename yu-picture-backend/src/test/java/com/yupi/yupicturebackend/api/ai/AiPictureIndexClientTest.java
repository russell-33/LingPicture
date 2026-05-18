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

import static org.junit.jupiter.api.Assertions.assertEquals;
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
}
