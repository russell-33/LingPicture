package com.yupi.yupicturebackend.model.dto.user;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

/**
 * 用户登录请求
 */
@Data
@AllArgsConstructor
@NoArgsConstructor
public class UserLoginRequest implements Serializable {

    private static final long serialVersionUID = 4026171486997492503L;
    private String userAccount;
    private String userPassword;

}