package com.yupi.yupicturebackend.config;

import com.yupi.yupicturebackend.exception.BusinessException;
import com.yupi.yupicturebackend.exception.ErrorCode;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import javax.annotation.Resource;
import javax.servlet.http.HttpServletRequest;
import java.net.HttpURLConnection;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

@Component
public class AiInternalAuth {

    public static final String INTERNAL_TOKEN_HEADER = "X-Internal-Token";
    public static final String INTERNAL_USER_HEADER = "X-Internal-User-Id";

    @Resource
    private AiConfig aiConfig;

    public void addInternalToken(HttpHeaders headers) {
        headers.set(INTERNAL_TOKEN_HEADER, aiConfig.getInternalToken());
    }

    public void addInternalUser(HttpHeaders headers, Long userId) {
        if (userId != null) {
            headers.set(INTERNAL_USER_HEADER, String.valueOf(userId));
        }
    }

    public void addInternalToken(HttpURLConnection connection) {
        connection.setRequestProperty(INTERNAL_TOKEN_HEADER, aiConfig.getInternalToken());
    }

    public void validateInternalRequest(HttpServletRequest request) {
        String expected = aiConfig.getInternalToken();
        String actual = request.getHeader(INTERNAL_TOKEN_HEADER);
        if (!StringUtils.hasText(expected) || !StringUtils.hasText(actual) || !constantTimeEquals(expected, actual)) {
            throw new BusinessException(ErrorCode.NO_AUTH_ERROR, "内部调用 token 无效");
        }
    }

    public Long getRequiredInternalUserId(HttpServletRequest request) {
        String rawUserId = request.getHeader(INTERNAL_USER_HEADER);
        if (!StringUtils.hasText(rawUserId)) {
            throw new BusinessException(ErrorCode.NO_AUTH_ERROR, "缺少内部用户上下文");
        }
        try {
            return Long.valueOf(rawUserId);
        } catch (NumberFormatException e) {
            throw new BusinessException(ErrorCode.NO_AUTH_ERROR, "内部用户上下文无效");
        }
    }

    private boolean constantTimeEquals(String expected, String actual) {
        return MessageDigest.isEqual(
                expected.getBytes(StandardCharsets.UTF_8),
                actual.getBytes(StandardCharsets.UTF_8)
        );
    }
}
