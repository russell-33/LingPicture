package com.yupi.yupicturebackend.exception;

/**
 * 异常处理工具类
 */
public class ThrowUtils {
    /**
     * 条件成立抛异常
     *
     * @param condition
     * @param runtimeException
     */
    public static void throwIf(boolean condition, RuntimeException runtimeException) {
        if (condition) {
            throw runtimeException;
        }
    }

    public static void throwIf(boolean condition, ErrorCode errorCode) {
        throwIf(condition, new BusinessException(errorCode));
    }

    public static void throwIf(boolean condition, ErrorCode errorCode, String msg) {
        throwIf(condition, new BusinessException(errorCode, msg));
    }
}
