package com.yupi.yupicturebackend.controller;

import cn.hutool.core.util.RandomUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import com.yupi.yupicturebackend.annotation.AuthCheck;
import com.yupi.yupicturebackend.api.aliyunai.AliYunAiApi;
import com.yupi.yupicturebackend.api.aliyunai.model.CreateOutPaintingTaskResponse;
import com.yupi.yupicturebackend.api.aliyunai.model.GetOutPaintingTaskResponse;
import com.yupi.yupicturebackend.config.AiInternalAuth;
import com.yupi.yupicturebackend.common.BaseResponse;
import com.yupi.yupicturebackend.common.DeleteRequest;
import com.yupi.yupicturebackend.common.ResultUtils;
import com.yupi.yupicturebackend.constant.PictureTagCategoryConstant;
import com.yupi.yupicturebackend.constant.RedisConstant;
import com.yupi.yupicturebackend.constant.UserConstant;
import com.yupi.yupicturebackend.manager.auth.SpaceUserAuthManager;
import com.yupi.yupicturebackend.manager.auth.StpKit;
import com.yupi.yupicturebackend.manager.auth.annotation.SaSpaceCheckPermission;
import com.yupi.yupicturebackend.manager.auth.model.SpaceUserPermissionConstant;
import com.yupi.yupicturebackend.model.enums.PictureReviewStatusEnum;
import com.yupi.yupicturebackend.exception.BusinessException;
import com.yupi.yupicturebackend.exception.ErrorCode;
import com.yupi.yupicturebackend.model.dto.picture.*;
import com.yupi.yupicturebackend.model.entity.Picture;
import com.yupi.yupicturebackend.model.entity.Space;
import com.yupi.yupicturebackend.model.entity.User;
import com.yupi.yupicturebackend.model.vo.PictureTagCategory;
import com.yupi.yupicturebackend.model.vo.PictureVO;
import com.yupi.yupicturebackend.service.PictureService;
import com.yupi.yupicturebackend.service.SpaceService;
import com.yupi.yupicturebackend.service.UserService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.util.DigestUtils;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import javax.annotation.Resource;
import javax.servlet.http.HttpServletRequest;
import java.time.Duration;
import java.util.Date;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.TimeUnit;

import static com.yupi.yupicturebackend.exception.ThrowUtils.throwIf;

@RestController
@RequestMapping("/picture")
@Slf4j
public class PictureController {
    @Resource
    private UserService userService;
    @Resource
    private PictureService pictureService;
    @Resource
    private StringRedisTemplate stringRedisTemplate;
    @Resource
    private SpaceService spaceService;
    @Resource
    private AliYunAiApi aliYunAiApi;
    @Resource
    private SpaceUserAuthManager spaceUserAuthManager;
    @Resource
    private AiInternalAuth aiInternalAuth;
    private final Cache<String, String> LOCAL_CACHE = Caffeine.newBuilder()
            .initialCapacity(1024)
            .maximumSize(10_000L)
            //缓存五分钟后过期
            .expireAfterWrite(Duration.ofMinutes(5))
            .build();

    /**
     * 上传图片（可重新上传）
     */
    @SaSpaceCheckPermission(value = SpaceUserPermissionConstant.PICTURE_UPLOAD)
    @PostMapping("/upload")
    //@AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<PictureVO> uploadPicture(
            @RequestPart("file") MultipartFile multipartFile,
            PictureUploadRequest pictureUploadRequest,
            HttpServletRequest request) {
        User loginUser = userService.getLoginUser(request);
        PictureVO pictureVO = pictureService.uploadPicture(multipartFile, pictureUploadRequest, loginUser);
        return ResultUtils.success(pictureVO);
    }

    /**
     * 通过url上传图片（可重新上传）
     */
    @PostMapping("/upload/url")
    @SaSpaceCheckPermission(value = SpaceUserPermissionConstant.PICTURE_UPLOAD)
    //@AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<PictureVO> uploadPictureByUrl(
            @RequestBody PictureUploadRequest pictureUploadRequest,
            HttpServletRequest request) {
        User loginUser = userService.getLoginUser(request);
        PictureVO pictureVO = pictureService.uploadPicture(pictureUploadRequest.getFileUrl(), pictureUploadRequest, loginUser);
        return ResultUtils.success(pictureVO);
    }

    /**
     * 删除图片
     *
     * @param deleteRequest
     * @param request
     * @return
     */
    @PostMapping("/delete")
    @SaSpaceCheckPermission(value = SpaceUserPermissionConstant.PICTURE_DELETE)
    public BaseResponse<Boolean> deletePicture(@RequestBody DeleteRequest deleteRequest,
                                               HttpServletRequest request) {
        throwIf(deleteRequest == null || deleteRequest.getId() <= 0, ErrorCode.PARAMS_ERROR, "图片不存在");
        User loginUser = userService.getLoginUser(request);
        pictureService.deletePicture(deleteRequest.getId(), loginUser);
        return ResultUtils.success(true);
    }


    /**
     * 更新图片（仅管理员可用）
     */
    @PostMapping("/update")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<Boolean> updatePicture(@RequestBody PictureUpdateRequest pictureUpdateRequest, HttpServletRequest request) {
        if (pictureUpdateRequest == null || pictureUpdateRequest.getId() <= 0) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR);
        }
        // 判断是否存在
        long id = pictureUpdateRequest.getId();
        Picture oldPicture = pictureService.getById(id);
        throwIf(oldPicture == null, ErrorCode.NOT_FOUND_ERROR);
        // 将实体类和 DTO 进行转换
        Picture picture = new Picture();
        BeanUtils.copyProperties(pictureUpdateRequest, picture);
        //补充审核参数
        pictureService.fillReviewParams(picture, userService.getLoginUser(request));
        // 注意将 list 转为 string
        picture.setTags(JSONUtil.toJsonStr(pictureUpdateRequest.getTags()));
        // 数据校验
        pictureService.validPicture(picture);
        // 操作数据库
        boolean result = pictureService.updateById(picture);
        throwIf(!result, ErrorCode.OPERATION_ERROR);
        pictureService.syncPictureIndex(pictureService.getById(id));
        return ResultUtils.success(true);
    }

    /**
     * 根据 id 获取图片（仅管理员可用）
     */
    @GetMapping("/get")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<Picture> getPictureById(long id, HttpServletRequest request) {
        throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        // 查询数据库
        Picture picture = pictureService.getById(id);
        throwIf(picture == null, ErrorCode.NOT_FOUND_ERROR);
        // 获取封装类
        return ResultUtils.success(picture);
    }

    /**
     * 根据 id 获取图片（封装类）
     */
    @GetMapping("/get/vo")
    public BaseResponse<PictureVO> getPictureVOById(long id, HttpServletRequest request) {
        throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        // 查询数据库
        Picture picture = pictureService.getById(id);
        throwIf(picture == null, ErrorCode.NOT_FOUND_ERROR);
        Space space = null;
        //空间校验
        if (picture.getSpaceId() != null) {
            boolean hasPermission = StpKit.SPACE.hasPermission(SpaceUserPermissionConstant.PICTURE_VIEW);
            throwIf(!hasPermission, ErrorCode.NO_AUTH_ERROR);
            //User loginUser = userService.getLoginUser(request);
            //已改为注解鉴权
            //pictureService.checkPictureAuth(picture, loginUser);
            space = spaceService.getById(picture.getSpaceId());
            throwIf(space == null, ErrorCode.PARAMS_ERROR, "空间不存在");
        }
        List<String> permissionList = spaceUserAuthManager.getPermissionList(space, userService.getLoginUser(request));
        // 获取封装类
        PictureVO pictureVO = pictureService.getPictureVO(picture, request);
        pictureVO.setPermissionList(permissionList);
        return ResultUtils.success(pictureVO);
    }

    /**
     * 根据 id 获取图片（内部调用，供 AI 服务回调）
     */
    @GetMapping("/get/vo/internal")
    public BaseResponse<PictureVO> getPictureVOByIdInternal(long id, Long spaceId, HttpServletRequest request) {
        aiInternalAuth.validateInternalRequest(request);
        throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        Picture picture = pictureService.getById(id);
        throwIf(picture == null, ErrorCode.NOT_FOUND_ERROR);
        validateInternalPictureScope(picture, spaceId);
        validateInternalPicturePermission(picture, request, SpaceUserPermissionConstant.PICTURE_VIEW);
        return ResultUtils.success(pictureService.getPictureVO(picture, request));
    }

    /**
     * 分页获取图片列表（仅管理员可用）
     */
    @PostMapping("/list/page")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<Page<Picture>> listPictureByPage(@RequestBody PictureQueryRequest pictureQueryRequest) {
        long current = pictureQueryRequest.getCurrent();
        long size = pictureQueryRequest.getPageSize();
        // 查询数据库
        Page<Picture> picturePage = pictureService.page(new Page<>(current, size),
                pictureService.getQueryWrapper(pictureQueryRequest));
        return ResultUtils.success(picturePage);
    }

    /**
     * 分页获取图片列表（封装类）
     */
    @PostMapping("/list/page/vo")
    public BaseResponse<Page<PictureVO>> listPictureVOByPage(@RequestBody PictureQueryRequest pictureQueryRequest,
                                                             HttpServletRequest request) {
        long current = pictureQueryRequest.getCurrent();
        long size = pictureQueryRequest.getPageSize();
        // 限制爬虫
        throwIf(size > 20, ErrorCode.PARAMS_ERROR);
        //空间权限校验
        if (pictureQueryRequest.getSpaceId() == null) {
            //普通用户只能看到审核通过的图片
            pictureQueryRequest.setReviewStatus(PictureReviewStatusEnum.PASS.getValue());
            pictureQueryRequest.setNullSpaceId(true);
        } else {
            boolean hasPermission = StpKit.SPACE.hasPermission(SpaceUserPermissionConstant.PICTURE_VIEW);
            throwIf(!hasPermission, ErrorCode.NO_AUTH_ERROR);
            //已经改为注解鉴权
//            Space space = spaceService.getById(pictureQueryRequest.getSpaceId());
//            throwIf(space == null, ErrorCode.NOT_FOUND_ERROR, "空间不存在");
//            Long userId = space.getUserId();
//            throwIf(!userId.equals(userService.getLoginUser(request).getId()), ErrorCode.NO_AUTH_ERROR, "仅本人可以查看");
        }
        // 查询数据库
        Page<Picture> picturePage = pictureService.page(new Page<>(current, size),
                pictureService.getQueryWrapper(pictureQueryRequest));
        // 获取封装类
        return ResultUtils.success(pictureService.getPictureVOPage(picturePage, request));
    }

    /**
     * 分页获取图片列表（内部调用，供 AI 服务回调，跳过鉴权）
     */
    @PostMapping("/list/page/vo/internal")
    public BaseResponse<Page<PictureVO>> listPictureVOByPageInternal(@RequestBody PictureQueryRequest pictureQueryRequest,
                                                                     HttpServletRequest request) {
        aiInternalAuth.validateInternalRequest(request);
        long current = pictureQueryRequest.getCurrent();
        long size = pictureQueryRequest.getPageSize();
        throwIf(size > 20, ErrorCode.PARAMS_ERROR);
        validateInternalSpacePermission(pictureQueryRequest.getSpaceId(), request,
                SpaceUserPermissionConstant.PICTURE_VIEW);
        if (pictureQueryRequest.getSpaceId() == null) {
            pictureQueryRequest.setReviewStatus(PictureReviewStatusEnum.PASS.getValue());
            pictureQueryRequest.setNullSpaceId(true);
        }
        Page<Picture> picturePage = pictureService.page(new Page<>(current, size),
                pictureService.getQueryWrapper(pictureQueryRequest));
        return ResultUtils.success(pictureService.getPictureVOPage(picturePage, request));
    }

    /**
     * 分页获取图片列表（封装类） 用redis
     */
    @Deprecated
    @PostMapping("/list/page/vo.cache")
    public BaseResponse<Page<PictureVO>> listPictureVOByPageWithCache(@RequestBody PictureQueryRequest pictureQueryRequest,
                                                                      HttpServletRequest request) {
        long current = pictureQueryRequest.getCurrent();
        long size = pictureQueryRequest.getPageSize();
        // 限制爬虫
        throwIf(size > 20, ErrorCode.PARAMS_ERROR);

        //1.查询本地缓存
        String queryCondition = JSONUtil.toJsonStr(pictureQueryRequest);
        String hashKey = DigestUtils.md5DigestAsHex(queryCondition.getBytes());
        String localCacheKey = String.
                format("%s:%s", "listPictureVOByPageWithCache", hashKey);
        String localCacheValue = LOCAL_CACHE.getIfPresent(localCacheKey);
        if (StrUtil.isNotBlank(localCacheValue)) {
            Page<PictureVO> pageResult = JSONUtil.toBean(localCacheValue, Page.class);
            return ResultUtils.success(pageResult);
        }
        //2.查询redis
        //构建缓存的key

        String redisKey = String.
                format("%s:%s:%s", RedisConstant.KEY_PREFIX, "listPictureVOByPageWithCache", hashKey);
        //击中直接返回
        String cachedValue = stringRedisTemplate.opsForValue().get(redisKey);
        if (StrUtil.isNotBlank(cachedValue)) {
            //先往本地缓存中存数据
            LOCAL_CACHE.put(localCacheKey, cachedValue);

            Page<PictureVO> pageResult = JSONUtil.toBean(cachedValue, Page.class);
            return ResultUtils.success(pageResult);
        }
        //3.查询数据库
        //普通用户只能看到审核通过的图片
        pictureQueryRequest.setReviewStatus(PictureReviewStatusEnum.PASS.getValue());
        Page<Picture> picturePage = pictureService.page(new Page<>(current, size),
                pictureService.getQueryWrapper(pictureQueryRequest));
        // 获取封装类
        Page<PictureVO> pictureVOPage = pictureService.getPictureVOPage(picturePage, request);
        //先往本地缓存中存数据
        LOCAL_CACHE.put(localCacheKey, JSONUtil.toJsonStr(pictureVOPage));
        //存入redis
        stringRedisTemplate.opsForValue().set(redisKey, JSONUtil.toJsonStr(pictureVOPage), RandomUtil.randomInt(5, 11), TimeUnit.MINUTES);
        return ResultUtils.success(pictureVOPage);
    }

    /**
     * 编辑图片（给用户使用）
     */
    @PostMapping("/edit")
    @SaSpaceCheckPermission(value = SpaceUserPermissionConstant.PICTURE_EDIT)
    public BaseResponse<Boolean> editPicture(@RequestBody PictureEditRequest pictureEditRequest, HttpServletRequest request) {
        if (pictureEditRequest == null || pictureEditRequest.getId() <= 0) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR);
        }
        User loginUser = userService.getLoginUser(request);
        pictureService.editPicture(pictureEditRequest, loginUser);
        return ResultUtils.success(true);
    }

    /**
     * 编辑图片（内部调用，供 AI 服务回调，跳过用户鉴权）
     */
    @PostMapping("/edit/internal")
    public BaseResponse<Boolean> editPictureInternal(@RequestBody PictureEditRequest pictureEditRequest,
                                                     HttpServletRequest request) {
        aiInternalAuth.validateInternalRequest(request);
        if (pictureEditRequest == null || pictureEditRequest.getId() <= 0) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR);
        }
        long id = pictureEditRequest.getId();
        Picture oldPicture = pictureService.getById(id);
        throwIf(oldPicture == null, ErrorCode.NOT_FOUND_ERROR);
        validateInternalPictureScope(oldPicture, pictureEditRequest.getSpaceId());
        validateInternalPicturePermission(oldPicture, request, SpaceUserPermissionConstant.PICTURE_EDIT);
        Picture picture = new Picture();
        BeanUtils.copyProperties(pictureEditRequest, picture);
        picture.setTags(JSONUtil.toJsonStr(pictureEditRequest.getTags()));
        picture.setEditTime(new Date());
        boolean result = pictureService.updateById(picture);
        throwIf(!result, ErrorCode.OPERATION_ERROR);
        pictureService.syncPictureIndex(pictureService.getById(id));
        return ResultUtils.success(true);
    }

    private void validateInternalPictureScope(Picture picture, Long requestSpaceId) {
        Long pictureSpaceId = picture.getSpaceId();
        if (pictureSpaceId == null) {
            throwIf(requestSpaceId != null && requestSpaceId > 0, ErrorCode.NO_AUTH_ERROR, "图片不属于当前空间");
            return;
        }
        throwIf(requestSpaceId == null || !pictureSpaceId.equals(requestSpaceId),
                ErrorCode.NO_AUTH_ERROR, "图片不属于当前空间");
    }

    private void validateInternalSpacePermission(Long spaceId, HttpServletRequest request, String permission) {
        if (spaceId == null) {
            return;
        }
        User loginUser = getInternalLoginUser(request);
        Space space = spaceService.getById(spaceId);
        throwIf(space == null, ErrorCode.NOT_FOUND_ERROR, "空间不存在");
        List<String> permissions = spaceUserAuthManager.getPermissionList(space, loginUser);
        throwIf(!permissions.contains(permission), ErrorCode.NO_AUTH_ERROR, "无权访问该空间");
    }

    private void validateInternalPicturePermission(Picture picture, HttpServletRequest request, String permission) {
        User loginUser = getInternalLoginUser(request);
        Long spaceId = picture.getSpaceId();
        if (spaceId == null) {
            if (SpaceUserPermissionConstant.PICTURE_VIEW.equals(permission)) {
                return;
            }
            boolean isOwnerOrAdmin = Objects.equals(picture.getUserId(), loginUser.getId()) || userService.isAdmin(loginUser);
            throwIf(!isOwnerOrAdmin, ErrorCode.NO_AUTH_ERROR, "无权编辑该图片");
            return;
        }
        Space space = spaceService.getById(spaceId);
        throwIf(space == null, ErrorCode.NOT_FOUND_ERROR, "空间不存在");
        List<String> permissions = spaceUserAuthManager.getPermissionList(space, loginUser);
        throwIf(!permissions.contains(permission), ErrorCode.NO_AUTH_ERROR, "无权访问该空间");
    }

    private User getInternalLoginUser(HttpServletRequest request) {
        Long userId = aiInternalAuth.getRequiredInternalUserId(request);
        User loginUser = userService.getById(userId);
        throwIf(loginUser == null, ErrorCode.NO_AUTH_ERROR, "内部用户不存在");
        return loginUser;
    }

    /**
     * 审核图片
     *
     * @param pictureReviewRequest
     * @param request
     */
    @PostMapping("/review")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<Boolean> doReviewPicture(@RequestBody PictureReviewRequest pictureReviewRequest, HttpServletRequest request) {
        throwIf(pictureReviewRequest == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(request);
        pictureService.doPictureReview(pictureReviewRequest, loginUser);
        return ResultUtils.success(true);
    }


    @GetMapping("/tag_category")
    public BaseResponse<PictureTagCategory> listPictureTagCategory() {
        PictureTagCategory pictureTagCategory = new PictureTagCategory();
        pictureTagCategory.setTagList(PictureTagCategoryConstant.TAG_LIST);
        pictureTagCategory.setCategoryList(PictureTagCategoryConstant.CATEGORY_LIST);
        return ResultUtils.success(pictureTagCategory);
    }


    /**
     * 批量抓取图片并上传
     *
     * @param pictureUploadBatchRequest
     * @param request
     */
    @PostMapping("/upload/batch")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<Integer> uploadPictureByBatch(@RequestBody PictureUploadBatchRequest pictureUploadBatchRequest, HttpServletRequest request) {
        throwIf(pictureUploadBatchRequest == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(request);
        Integer loadedPictureCount = pictureService.uploadPictureByBatch(pictureUploadBatchRequest, loginUser);
        return ResultUtils.success(loadedPictureCount);
    }

    /**
     * 批量编辑图片
     *
     * @param pictureEditByBatchRequest
     * @param request
     * @return
     */
    @PostMapping("/edit/batch")
    @SaSpaceCheckPermission(value = SpaceUserPermissionConstant.PICTURE_EDIT)
    public BaseResponse<Boolean> editPictureByBatch(@RequestBody PictureEditByBatchRequest pictureEditByBatchRequest, HttpServletRequest request) {
        throwIf(pictureEditByBatchRequest == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(request);
        pictureService.editPictureByBatch(pictureEditByBatchRequest, loginUser);
        return ResultUtils.success(true);
    }

    @PostMapping("/search/color")
    @SaSpaceCheckPermission(value = SpaceUserPermissionConstant.PICTURE_VIEW)
    public BaseResponse<List<PictureVO>> searchPictureByColor(@RequestBody SearchPictureByColorRequest searchPictureByColorRequest, HttpServletRequest request) {
        throwIf(searchPictureByColorRequest == null, ErrorCode.PARAMS_ERROR);
        List<PictureVO> pictureVO = pictureService.searchPictureByColor(searchPictureByColorRequest.getSpaceId(),
                searchPictureByColorRequest.getPicColor(),
                userService.getLoginUser(request));
        return ResultUtils.success(pictureVO);
    }


    /**
     * 创建ai扩图任务
     *
     * @param createPictureOutPaintingTaskRequest
     * @param request
     * @return
     */
    @PostMapping("/out_painting/create_task")
    @SaSpaceCheckPermission(value = SpaceUserPermissionConstant.PICTURE_EDIT)
    public BaseResponse<CreateOutPaintingTaskResponse> createPictureOutPaintingTask(@RequestBody CreatePictureOutPaintingTaskRequest createPictureOutPaintingTaskRequest, HttpServletRequest request) {
        throwIf(createPictureOutPaintingTaskRequest == null
                || createPictureOutPaintingTaskRequest.getPictureId() == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(request);
        CreateOutPaintingTaskResponse response = pictureService.createPictureOutPaintingTask(createPictureOutPaintingTaskRequest, loginUser);
        return ResultUtils.success(response);
    }

    @GetMapping("/out_painting/get_task")
    public BaseResponse<GetOutPaintingTaskResponse> getPictureOutPaintingTask(String taskId) {
        throwIf(StrUtil.isBlank(taskId), ErrorCode.PARAMS_ERROR);
        GetOutPaintingTaskResponse response = aliYunAiApi.getOutPaintingTaskResponse(taskId);
        return ResultUtils.success(response);
    }

}
