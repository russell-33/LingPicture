package com.yupi.yupicturebackend.service.impl;

import cn.dev33.satoken.stp.StpUtil;
import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.collection.CollUtil;
import cn.hutool.core.util.ObjectUtil;
import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yupi.yupicturebackend.constant.UserConstant;
import com.yupi.yupicturebackend.manager.auth.StpKit;
import com.yupi.yupicturebackend.model.enums.UserRoleEnum;
import com.yupi.yupicturebackend.exception.ErrorCode;
import com.yupi.yupicturebackend.model.dto.user.UserAddRequest;
import com.yupi.yupicturebackend.model.dto.user.UserQueryRequest;
import com.yupi.yupicturebackend.model.entity.User;
import com.yupi.yupicturebackend.model.vo.LoginUserVO;
import com.yupi.yupicturebackend.model.vo.UserVO;
import com.yupi.yupicturebackend.service.UserService;
import com.yupi.yupicturebackend.mapper.UserMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.DigestUtils;

import javax.servlet.http.HttpServletRequest;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

import static com.yupi.yupicturebackend.exception.ThrowUtils.throwIf;

/**
 * @author cass.
 * @description 针对表【user(用户)】的数据库操作Service实现
 * @createDate 2026-01-30 15:16:18
 */
@Service
@Slf4j
public class UserServiceImpl extends ServiceImpl<UserMapper, User>
        implements UserService {
    /**
     * 用户注册
     *
     * @param userAccount
     * @param userPassword
     * @param checkPassword
     * @return
     */
    @Override
    @Transactional
    public long userRegister(String userAccount, String userPassword, String checkPassword) {
        //校验数据
        throwIf(StrUtil.hasBlank(userAccount, userPassword, checkPassword), ErrorCode.PARAMS_ERROR, "参数为空");
        throwIf(userAccount.length() < 4, ErrorCode.PARAMS_ERROR, "用户账号过短");
        throwIf(userPassword.length() < 8 || checkPassword.length() < 8, ErrorCode.PARAMS_ERROR, "密码过短");
        throwIf(!userPassword.equals(checkPassword), ErrorCode.PARAMS_ERROR, "两次密码不一致");
        //查询是否有相同数据
        LambdaQueryWrapper<User> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(User::getUserAccount, userAccount);
        long count = count(wrapper);
        throwIf(count > 0, ErrorCode.PARAMS_ERROR, "用户名已存在");
        //加密密码
        String encryptedPassword = getEncryptedPassword(userPassword);
        //插入数据
        User user = new User();
        user.setUserAccount(userAccount);
        user.setUserPassword(encryptedPassword);
        user.setUserName("无名");
        user.setUserRole(UserRoleEnum.USER.getValue());
        boolean saveResult = save(user);
        throwIf(!saveResult, ErrorCode.SYSTEM_ERROR, "注册失败，数据库错误");
        return user.getId();
    }

    @Override
    public LoginUserVO userLogin(String userAccount, String userPassword, HttpServletRequest request) {
        //校验数据
        throwIf(StrUtil.hasBlank(userAccount, userPassword), ErrorCode.PARAMS_ERROR, "参数为空");
        throwIf(userAccount.length() < 4, ErrorCode.PARAMS_ERROR, "用户账号错误");
        throwIf(userPassword.length() < 8, ErrorCode.PARAMS_ERROR, "密码过短");
        //加密用户密码
        String encryptedPassword = getEncryptedPassword(userPassword);
        //查询数据库
        LambdaQueryWrapper<User> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(User::getUserAccount, userAccount).eq(User::getUserPassword, encryptedPassword);
        User user = getOne(wrapper);
        if (user == null) log.info("user login failed,userAccount can not match userPassword");
        throwIf(user == null, ErrorCode.PARAMS_ERROR, "用户不存在或密码错误");
        //保存用户的登录状态
        request.getSession().setAttribute(UserConstant.USER_LOGIN_STATE, user);
        //保存登录态到sa-token，便于空间鉴权时使用
        StpKit.SPACE.login(user.getId());
        StpKit.SPACE.getSession().set(UserConstant.USER_LOGIN_STATE, user);
        return getLoginUserVO(user);
    }

    /**
     * 获得加密后的密码
     *
     * @param password 用户密码
     * @return 加密后的密码
     */
    @Override
    public String getEncryptedPassword(String password) {
        //加盐 混淆密码
        final String SALT = "yupi";
        return DigestUtils.md5DigestAsHex(StrUtil.bytes(password + SALT));
    }

    /**
     * 获取脱敏用户
     *
     * @param user 用户
     * @return 脱敏后的用户信息
     */
    @Override
    public LoginUserVO getLoginUserVO(User user) {
        if (user == null) return null;
        return BeanUtil.copyProperties(user, LoginUserVO.class);
    }

    /**
     * 返回currentUser
     *
     * @param request
     * @return
     */
    @Override
    public User getLoginUser(HttpServletRequest request) {
        User user = (User) request.getSession().getAttribute(UserConstant.USER_LOGIN_STATE);
        throwIf(user == null || user.getId() == null, ErrorCode.NOT_LOGIN_ERROR);
        //不用缓存(session中的user)，使用数据库中最新的数据
        User currentUser = getById(user.getId());
        throwIf(currentUser == null, ErrorCode.NOT_LOGIN_ERROR);
        return currentUser;
    }

    /**
     * 获取用户信息
     *
     * @param user
     * @return
     */
    @Override
    public UserVO getUserVO(User user) {
        if (user == null) return null;
        return BeanUtil.copyProperties(user, UserVO.class);
    }

    /**
     * 获取用户列表
     *
     * @param userList
     * @return
     */
    @Override
    public List<UserVO> getUserVOList(List<User> userList) {
        if (CollUtil.isEmpty(userList)) {
            return new ArrayList<>();
        }
        return userList.stream()
                .map(this::getUserVO)
                .collect(Collectors.toList());
    }

    @Override
    public boolean userLogout(HttpServletRequest request) {
        User user = (User) request.getSession().getAttribute(UserConstant.USER_LOGIN_STATE);
        throwIf(user == null || user.getId() == null, ErrorCode.OPERATION_ERROR);
        request.getSession().setAttribute(UserConstant.USER_LOGIN_STATE, null);
        return true;
    }

    @Override
    public QueryWrapper<User> getQueryWrapper(UserQueryRequest userQueryRequest) {
        throwIf(userQueryRequest == null, ErrorCode.PARAMS_ERROR, "请求参数为空");
        Long id = userQueryRequest.getId();
        String userName = userQueryRequest.getUserName();
        String userAccount = userQueryRequest.getUserAccount();
        String userProfile = userQueryRequest.getUserProfile();
        String userRole = userQueryRequest.getUserRole();
//        int current = userQueryRequest.getCurrent();
//        int pageSize = userQueryRequest.getPageSize();
        String sortField = userQueryRequest.getSortField();
        String sortOrder = userQueryRequest.getSortOrder();

        QueryWrapper<User> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq(ObjectUtil.isNotEmpty(id), "id", id);
        queryWrapper.like(ObjectUtil.isNotEmpty(userName), "userName", userName);
        queryWrapper.like(ObjectUtil.isNotEmpty(userAccount), "userAccount", userAccount);
        queryWrapper.like(ObjectUtil.isNotEmpty(userProfile), "userProfile", userProfile);
        queryWrapper.eq(ObjectUtil.isNotEmpty(userRole), "userRole", userRole);
        queryWrapper.orderBy(StrUtil.isNotEmpty(sortField), sortOrder.equals("ascend"), sortField);

        return queryWrapper;
    }

    @Override
    public Long addUser(UserAddRequest userAddRequest) {
        User user = BeanUtil.copyProperties(userAddRequest, User.class);
        String encryptedPassword = getEncryptedPassword(UserConstant.DEFAULT_PASSWORD);
        user.setUserPassword(encryptedPassword);
        boolean save = save(user);
        throwIf(!save, ErrorCode.OPERATION_ERROR);
        return user.getId();
    }

    @Override
    public boolean isAdmin(User user) {
        return user != null && UserRoleEnum.ADMIN.getValue().equals(user.getUserRole());
    }
}




