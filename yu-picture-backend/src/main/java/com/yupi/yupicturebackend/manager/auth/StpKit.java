package com.yupi.yupicturebackend.manager.auth;

import cn.dev33.satoken.stp.StpLogic;
import cn.dev33.satoken.stp.StpUtil;
import org.springframework.stereotype.Component;

@Component
public class StpKit {
    public static final String SPACE_TYPE = "space";

    /**
     * 默认原生回话对象 暂且未使用
     */
    public static final StpLogic DEFAULT = StpUtil.stpLogic;

    /**
     * space会话对象，管理space表所有的登录 权限认证
     */
    public static final StpLogic SPACE = new StpLogic(SPACE_TYPE);
}
