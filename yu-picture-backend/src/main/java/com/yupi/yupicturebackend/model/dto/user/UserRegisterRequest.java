package com.yupi.yupicturebackend.model.dto.user;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

/**
 * 用户登注册请求
 */
@Data
@AllArgsConstructor
@NoArgsConstructor
public class UserRegisterRequest implements Serializable {

    private static final long serialVersionUID = 8735650154179439661L;
    private String userAccount;
    private String userPassword;
    private String checkPassword;

}
