package com.yupi.yupicturebackend.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.yupi.yupicturebackend.config.AiConfig;
import com.yupi.yupicturebackend.config.AiInternalAuth;
import com.yupi.yupicturebackend.exception.BusinessException;
import com.yupi.yupicturebackend.exception.ErrorCode;
import com.yupi.yupicturebackend.manager.auth.SpaceUserAuthManager;
import com.yupi.yupicturebackend.manager.auth.model.SpaceUserPermissionConstant;
import com.yupi.yupicturebackend.model.entity.AgentSession;
import com.yupi.yupicturebackend.model.entity.Picture;
import com.yupi.yupicturebackend.model.entity.Space;
import com.yupi.yupicturebackend.model.entity.User;
import com.yupi.yupicturebackend.service.AgentContextService;
import com.yupi.yupicturebackend.service.PictureService;
import com.yupi.yupicturebackend.service.SpaceService;
import com.yupi.yupicturebackend.service.UserService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import javax.annotation.Resource;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.Objects;

import static com.yupi.yupicturebackend.exception.ThrowUtils.throwIf;

@RestController
@RequestMapping("/ai")
@Slf4j
public class AiController {
    @Resource
    private AiConfig aiConfig;
    @Resource
    private RestTemplate aiRestTemplate;
    @Resource
    private AiInternalAuth aiInternalAuth;
    @Resource
    private UserService userService;
    @Resource
    private SpaceService spaceService;
    @Resource
    private PictureService pictureService;
    @Resource
    private SpaceUserAuthManager spaceUserAuthManager;
    @Resource
    private AgentContextService agentContextService;

    private final ObjectMapper objectMapper = new ObjectMapper();
    private static final int AI_STREAM_CONNECT_TIMEOUT_MS = 5000;
    private static final int AI_STREAM_READ_TIMEOUT_MS = 300000;

    private String buildAiUrl(String path) {
        return aiConfig.getUrl() + path;
    }

    /**
     * 转发 SSE 流式请求到 AI 服务
     */
    private void proxyStream(String aiPath, String body, HttpServletResponse response) {
        response.setContentType("text/event-stream");
        response.setCharacterEncoding("UTF-8");
        try {
            URI uri = new URI(buildAiUrl(aiPath));
            HttpURLConnection conn = (HttpURLConnection) uri.toURL().openConnection();
            conn.setRequestMethod(HttpMethod.POST.name());
            conn.setRequestProperty(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE);
            aiInternalAuth.addInternalToken(conn);
            conn.setConnectTimeout(AI_STREAM_CONNECT_TIMEOUT_MS);
            conn.setReadTimeout(AI_STREAM_READ_TIMEOUT_MS);
            conn.setDoOutput(true);

            byte[] bodyBytes = body == null ? new byte[0] : body.getBytes(StandardCharsets.UTF_8);
            if (bodyBytes.length > 0) {
                conn.getOutputStream().write(bodyBytes);
            }

            int status = conn.getResponseCode();
            if (status >= 400) {
                response.setStatus(status);
                InputStream errorStream = conn.getErrorStream();
                String message = errorStream == null ? "AI 服务调用失败" : new String(errorStream.readAllBytes(), StandardCharsets.UTF_8);
                writeStreamError(response.getOutputStream(), message);
                return;
            }

            try (InputStream is = conn.getInputStream();
                 OutputStream os = response.getOutputStream()) {
                byte[] buffer = new byte[4096];
                int bytesRead;
                while ((bytesRead = is.read(buffer)) != -1) {
                    os.write(buffer, 0, bytesRead);
                    os.flush();
                }
            }
        } catch (Exception e) {
            log.error("SSE proxy error", e);
            try {
                writeStreamError(response.getOutputStream(), e.getMessage());
            } catch (IOException ignored) {
            }
        }
    }

    @PostMapping("/agent/run/stream")
    public void agentRunStream(@RequestBody String body, HttpServletRequest request, HttpServletResponse response) {
        User loginUser = userService.getLoginUser(request);
        assertSpacePermission(body, loginUser, SpaceUserPermissionConstant.PICTURE_VIEW);
        proxyStream("/api/v1/agent/run/stream", enrichBodyWithUserId(body, loginUser), response);
    }

    @GetMapping("/agent/messages")
    public ResponseEntity<String> getAgentMessages(@RequestParam String sessionId, HttpServletRequest request) {
        User loginUser = userService.getLoginUser(request);
        String url = buildAiUrl("/api/v1/agent/messages/" + sessionId + "?user_id=" + loginUser.getId());
        HttpHeaders headers = buildInternalHeaders();
        HttpEntity<Void> entity = new HttpEntity<>(headers);
        try {
            ResponseEntity<String> aiResponse = aiRestTemplate.exchange(url, HttpMethod.GET, entity, String.class);
            return jsonResponse(aiResponse);
        } catch (RestClientException e) {
            log.error("获取 Agent 消息历史失败", e);
            return ResponseEntity.ok("{\"messages\":[]}");
        }
    }

    @PostMapping("/picture/auto-tag/{pictureId}")
    public ResponseEntity<String> pictureAutoTag(@PathVariable Long pictureId, @RequestBody String body,
                                                 HttpServletRequest request) {
        User loginUser = userService.getLoginUser(request);
        assertPicturePermission(pictureId, body, loginUser, SpaceUserPermissionConstant.PICTURE_EDIT);
        String url = buildAiUrl("/api/v1/picture/auto-tag/" + pictureId);
        HttpEntity<String> entity = new HttpEntity<>(enrichBodyWithUserId(body, loginUser), buildInternalHeaders());
        ResponseEntity<String> aiResponse = postToAi(url, entity);
        return jsonResponse(aiResponse);
    }

    // ========== 内部端点（仅供 Python AI 服务调用） ==========

    @GetMapping("/internal/context/session-summary")
    public ResponseEntity<String> getSessionSummary(@RequestParam String sessionId,
                                                    HttpServletRequest request) {
        aiInternalAuth.validateInternalRequest(request);
        AgentSession session = agentContextService.getSessionSummary(sessionId);
        String summary = session != null ? session.getSummary() : "";
        return ResponseEntity.ok("{\"code\":0,\"data\":{\"summary\":\"" + escapeJson(summary) + "\"}}");
    }

    @PostMapping("/internal/context/session-summary")
    public ResponseEntity<String> upsertSessionSummary(@RequestBody String body,
                                                       HttpServletRequest request) {
        aiInternalAuth.validateInternalRequest(request);
        try {
            JsonNode root = objectMapper.readTree(body);
            String sessionId = root.path("session_id").asText("");
            Long userId = root.path("user_id").asLong(0);
            Long spaceId = root.path("space_id").asLong(0);
            String title = root.path("title").asText("");
            String summary = root.path("summary").asText("");
            agentContextService.upsertSessionSummary(sessionId, userId, spaceId > 0 ? spaceId : null, title, summary);
            return ResponseEntity.ok("{\"code\":0,\"message\":\"ok\"}");
        } catch (Exception e) {
            log.error("upsertSessionSummary failed, body={}", body, e);
            return ResponseEntity.badRequest().body("{\"code\":400,\"message\":\"参数错误\"}");
        }
    }

    @PostMapping("/internal/context/operation-log")
    public ResponseEntity<String> appendOperationLog(@RequestBody String body,
                                                     HttpServletRequest request) {
        aiInternalAuth.validateInternalRequest(request);
        try {
            JsonNode root = objectMapper.readTree(body);
            agentContextService.appendOperationLog(
                    root.path("session_id").asText(""),
                    root.path("user_id").asLong(0),
                    root.path("space_id").asLong(0),
                    root.path("operation_type").asText(""),
                    root.path("tool_name").asText(""),
                    root.path("target_ids").asText(""),
                    root.path("request_text").asText(""),
                    root.path("result_summary").asText(""),
                    root.path("status").asText("SUCCESS")
            );
            return ResponseEntity.ok("{\"code\":0,\"message\":\"ok\"}");
        } catch (Exception e) {
            log.error("appendOperationLog failed, body={}", body, e);
            return ResponseEntity.badRequest().body("{\"code\":400,\"message\":\"参数错误\"}");
        }
    }

    private static String escapeJson(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r");
    }

    private ResponseEntity<String> postToAi(String url, HttpEntity<String> entity) {
        try {
            return aiRestTemplate.postForEntity(url, entity, String.class);
        } catch (HttpStatusCodeException e) {
            String body = e.getResponseBodyAsString(StandardCharsets.UTF_8);
            log.warn("AI service returned error, status={}, body={}", e.getStatusCode(), body);
            return ResponseEntity.status(e.getStatusCode())
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body);
        } catch (RestClientException e) {
            log.error("AI service request failed", e);
            throw new BusinessException(ErrorCode.SYSTEM_ERROR, "AI 服务调用失败：" + e.getMessage());
        }
    }

    private ResponseEntity<String> jsonResponse(ResponseEntity<String> aiResponse) {
        return ResponseEntity.status(aiResponse.getStatusCode())
                .contentType(MediaType.APPLICATION_JSON)
                .body(aiResponse.getBody());
    }

    private HttpHeaders buildInternalHeaders() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        aiInternalAuth.addInternalToken(headers);
        return headers;
    }

    private void writeStreamError(OutputStream outputStream, String message) throws IOException {
        String payload = objectMapper.writeValueAsString(Map.of(
                "type", "error",
                "message", message == null ? "AI 服务调用失败" : message
        ));
        outputStream.write(("data: " + payload + "\n\n").getBytes(StandardCharsets.UTF_8));
        outputStream.flush();
    }

    private String enrichBodyWithUserId(String body, User loginUser) {
        try {
            ObjectNode root = (ObjectNode) objectMapper.readTree(body);
            root.put("user_id", loginUser.getId());
            return objectMapper.writeValueAsString(root);
        } catch (Exception e) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "请求体格式错误");
        }
    }

    private void assertSpacePermission(String body, User loginUser, String permission) {
        Long spaceId = extractSpaceId(body);
        throwIf(spaceId == null || spaceId <= 0, ErrorCode.PARAMS_ERROR, "请选择空间后再使用 AI 助手");
        Space space = spaceService.getById(spaceId);
        throwIf(space == null, ErrorCode.NOT_FOUND_ERROR, "空间不存在");
        List<String> permissions = spaceUserAuthManager.getPermissionList(space, loginUser);
        throwIf(!permissions.contains(permission), ErrorCode.NO_AUTH_ERROR, "无权访问该空间");
    }

    private void assertPicturePermission(Long pictureId, String body, User loginUser, String permission) {
        throwIf(pictureId == null || pictureId <= 0, ErrorCode.PARAMS_ERROR, "图片不存在");
        Picture picture = pictureService.getById(pictureId);
        throwIf(picture == null, ErrorCode.NOT_FOUND_ERROR, "图片不存在");

        Long requestSpaceId = extractSpaceId(body);
        if (picture.getSpaceId() != null) {
            throwIf(requestSpaceId == null || !picture.getSpaceId().equals(requestSpaceId),
                    ErrorCode.NO_AUTH_ERROR, "图片不属于当前空间");
            Space space = spaceService.getById(picture.getSpaceId());
            throwIf(space == null, ErrorCode.NOT_FOUND_ERROR, "空间不存在");
            List<String> permissions = spaceUserAuthManager.getPermissionList(space, loginUser);
            throwIf(!permissions.contains(permission), ErrorCode.NO_AUTH_ERROR, "无权编辑该图片");
            return;
        }

        throwIf(requestSpaceId != null && requestSpaceId > 0, ErrorCode.NO_AUTH_ERROR, "图片不属于当前空间");
        boolean isOwnerOrAdmin = Objects.equals(picture.getUserId(), loginUser.getId()) || userService.isAdmin(loginUser);
        throwIf(!isOwnerOrAdmin, ErrorCode.NO_AUTH_ERROR, "无权编辑该图片");
    }

    private Long extractSpaceId(String body) {
        try {
            JsonNode root = objectMapper.readTree(body);
            JsonNode value = root.has("space_id") ? root.get("space_id") : root.get("spaceId");
            if (value == null || value.isNull()) {
                return null;
            }
            String raw = value.asText();
            if (raw == null || raw.isBlank()) {
                return null;
            }
            return Long.valueOf(raw);
        } catch (Exception e) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "space_id 参数错误");
        }
    }
}
